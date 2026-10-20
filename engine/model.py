"""OpenAI-compatible multimodal model client with provider presets."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx

from .config import load_reviewer_config
from .errors import EngineError

SleepFn = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class ProviderPreset:
    name: str
    base_url: str
    key_env_names: tuple[str, ...]
    default_model: str


PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "qwen": ProviderPreset(
        name="qwen",
        base_url="https://maas.qianwenaiapi.com/compatible-mode/v1",
        key_env_names=("DASHSCOPE_API_KEY", "QWENAI_API_KEY"),
        default_model="qwen3.8-flash",
    ),
    "deepseek": ProviderPreset(
        name="deepseek",
        base_url="https://api.deepseek.com",
        key_env_names=("DEEPSEEK_API_KEY",),
        default_model="deepseek-flash",
    ),
}


@dataclass(frozen=True)
class ModelSettings:
    provider: str
    model: str
    base_url: str
    api_key: str = field(repr=False)
    timeout_seconds: float = 120.0
    max_retries: int = 3
    json_mode: bool = True
    max_tokens: int = 8000

    @classmethod
    def from_env(
        cls,
        provider: str | None = None,
        model: str | None = None,
    ) -> "ModelSettings":
        selected = (provider or os.getenv("REVIEW_PROVIDER", "qwen")).strip().lower()
        if selected not in {*PROVIDER_PRESETS, "generic"}:
            raise EngineError(
                "unsupported_provider",
                f"Unsupported model provider: {selected}.",
                status_code=422,
            )

        if selected == "generic":
            base_url = os.getenv("REVIEW_BASE_URL", "").strip()
            api_key = os.getenv("REVIEW_API_KEY", "").strip()
            selected_model = (model or os.getenv("REVIEW_MODEL", "")).strip()
            if not base_url or not selected_model:
                raise EngineError(
                    "generic_provider_not_configured",
                    "REVIEW_BASE_URL and REVIEW_MODEL are required for the generic provider.",
                    status_code=503,
                )
            key_env_names = ("REVIEW_API_KEY",)
        else:
            preset = PROVIDER_PRESETS[selected]
            local_config = load_reviewer_config(required=False)
            qwen_config = (
                local_config.get("providers", {}).get("qwen", {})
                if isinstance(local_config.get("providers"), dict)
                else {}
            )
            deepseek_config = (
                local_config.get("providers", {}).get("deepseek", {})
                if isinstance(local_config.get("providers"), dict)
                else {}
            )
            provider_config = qwen_config if selected == "qwen" else deepseek_config
            configured_base_url = str(
                provider_config.get(
                    "chat_base_url" if selected == "qwen" else "base_url",
                    "",
                )
            ).strip()
            base_url = os.getenv("REVIEW_BASE_URL", configured_base_url or preset.base_url).strip()
            api_key = next(
                (os.getenv(name, "").strip() for name in preset.key_env_names if os.getenv(name)),
                "",
            )
            if not api_key:
                api_key = str(provider_config.get("api_key", "")).strip()
            configured_model_key = "reasoning_model" if selected == "qwen" else "vision_model"
            selected_model = (
                model
                or os.getenv("REVIEW_MODEL", "")
                or str(provider_config.get(configured_model_key, "")).strip()
                or preset.default_model
            ).strip()
            key_env_names = preset.key_env_names

        if not api_key:
            env_names = " or ".join(key_env_names)
            raise EngineError(
                "api_key_missing",
                f"{selected} requires an API key in {env_names}.",
                status_code=503,
                retryable=False,
            )

        return cls(
            provider=selected,
            model=selected_model,
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=float(os.getenv("REVIEW_TIMEOUT_SECONDS", "120")),
            max_retries=int(os.getenv("REVIEW_MAX_RETRIES", "3")),
            json_mode=os.getenv("REVIEW_JSON_MODE", "1").lower() not in {"0", "false", "no"},
            max_tokens=int(os.getenv("REVIEW_MAX_TOKENS", "8000")),
        )

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


@dataclass(frozen=True)
class ModelCallResult:
    text: str
    provider: str
    model: str
    usage: dict[str, Any]
    request_id: str | None
    latency_ms: int
    json_mode_used: bool


class OpenAICompatibleModel:
    def __init__(
        self,
        settings: ModelSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self.settings = settings
        self._transport = transport
        self._sleep = sleep

    async def complete(
        self,
        messages: list[dict],
        *,
        json_mode: bool = True,
        extra_body: dict[str, Any] | None = None,
    ) -> ModelCallResult:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": self.settings.max_tokens,
            "stream": False,
        }
        requested_json_mode = json_mode and self.settings.json_mode
        if requested_json_mode:
            payload["response_format"] = {"type": "json_object"}
        if extra_body:
            payload.update(extra_body)

        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(self.settings.timeout_seconds, connect=15.0)
        started = time.perf_counter()
        last_error: str | None = None
        fallback_json_mode = False

        async with httpx.AsyncClient(
            timeout=timeout,
            transport=self._transport,
            follow_redirects=True,
        ) as client:
            for attempt in range(1, self.settings.max_retries + 1):
                try:
                    response = await client.post(
                        self.settings.chat_completions_url,
                        headers=headers,
                        json=payload,
                    )
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    if attempt < self.settings.max_retries:
                        await self._sleep(2 ** attempt)
                        continue
                    raise EngineError(
                        "model_network_error",
                        "The model provider could not be reached.",
                        status_code=502,
                        retryable=True,
                        details={"attempts": attempt},
                    ) from exc

                if (
                    response.status_code in {400, 422}
                    and "response_format" in payload
                    and not fallback_json_mode
                ):
                    error_text = response.text.lower()
                    if "response_format" in error_text or "json" in error_text:
                        payload.pop("response_format", None)
                        fallback_json_mode = True
                        continue

                if response.status_code == 401:
                    raise EngineError(
                        "model_auth_failed",
                        "The model provider rejected the API key.",
                        status_code=502,
                        retryable=False,
                    )
                if response.status_code in {408, 409, 429} or response.status_code >= 500:
                    last_error = f"HTTP {response.status_code}: {response.text[:500]}"
                    if attempt < self.settings.max_retries:
                        retry_after = response.headers.get("retry-after")
                        delay = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                        await self._sleep(delay)
                        continue
                    raise EngineError(
                        "model_upstream_error",
                        f"Model provider returned HTTP {response.status_code}.",
                        status_code=502,
                        retryable=True,
                        details={"attempts": attempt, "upstream": response.text[:500]},
                    )
                if response.status_code >= 400:
                    raise EngineError(
                        "model_request_rejected",
                        f"Model provider rejected the request with HTTP {response.status_code}.",
                        status_code=502,
                        retryable=False,
                        details={"upstream": response.text[:1000]},
                    )

                try:
                    body = response.json()
                    choice = body["choices"][0]
                    content = choice["message"]["content"]
                except (ValueError, KeyError, IndexError, TypeError) as exc:
                    raise EngineError(
                        "model_response_invalid",
                        "Model provider returned an unexpected response envelope.",
                        status_code=502,
                        retryable=True,
                        details={"upstream": response.text[:1000]},
                    ) from exc

                text = _normalize_content(content)
                if not text.strip():
                    raise EngineError(
                        "model_empty_response",
                        "Model returned an empty text response.",
                        status_code=502,
                        retryable=True,
                    )
                latency_ms = int((time.perf_counter() - started) * 1000)
                return ModelCallResult(
                    text=text,
                    provider=self.settings.provider,
                    model=self.settings.model,
                    usage=body.get("usage") if isinstance(body.get("usage"), dict) else {},
                    request_id=body.get("id"),
                    latency_ms=latency_ms,
                    json_mode_used=bool(payload.get("response_format")),
                )

        raise EngineError(
            "model_request_failed",
            "Model request failed after all retry attempts.",
            status_code=502,
            retryable=True,
            details={"last_error": last_error},
        )


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return ""
