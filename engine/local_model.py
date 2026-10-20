"""Lazy local Transformers backend for Holo1.5 and UI-TARS."""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import io
import time
from dataclasses import dataclass
from typing import Any

from PIL import Image

from .config import load_reviewer_config
from .errors import EngineError
from .model import ModelCallResult

LOCAL_PROVIDERS = {
    "local_holo": ("models", "local_holo15"),
    "local_ui_tars": ("models", "local_ui_tars"),
}


@dataclass(frozen=True)
class LocalModelSettings:
    provider: str
    model_id: str
    device: str = "auto"
    dtype: str = "auto"
    load_in_4bit: bool = True
    max_new_tokens: int = 4096
    min_pixels: int = 200_704
    max_pixels: int = 2_000_000
    trust_remote_code: bool = True

    @classmethod
    def from_provider(cls, provider: str) -> "LocalModelSettings":
        path = LOCAL_PROVIDERS.get(provider)
        if path is None:
            raise EngineError(
                "unsupported_local_provider",
                f"Unsupported local provider: {provider}.",
                status_code=422,
            )
        config = load_reviewer_config(required=True)
        current: Any = config
        for key in path:
            current = current.get(key, {}) if isinstance(current, dict) else {}
        if not isinstance(current, dict):
            current = {}
        if not current.get("enabled", False):
            raise EngineError(
                "local_provider_disabled",
                f"{provider} is disabled in config/reviewer.toml.",
                status_code=403,
                details={"config_key": ".".join(path)},
            )
        model_id = str(current.get("model_id", "")).strip()
        if not model_id:
            raise EngineError(
                "local_model_missing",
                f"{provider} has no model_id in config/reviewer.toml.",
                status_code=500,
            )
        return cls(
            provider=provider,
            model_id=model_id,
            device=str(current.get("device", "auto")),
            dtype=str(current.get("dtype", "auto")),
            load_in_4bit=bool(current.get("load_in_4bit", True)),
            max_new_tokens=int(current.get("max_new_tokens", 4096)),
            min_pixels=int(current.get("min_pixels", 200_704)),
            max_pixels=int(current.get("max_pixels", 2_000_000)),
            trust_remote_code=bool(current.get("trust_remote_code", True)),
        )


def local_dependency_status() -> dict[str, bool]:
    return {
        "torch": importlib.util.find_spec("torch") is not None,
        "transformers": importlib.util.find_spec("transformers") is not None,
        "qwen_vl_utils": importlib.util.find_spec("qwen_vl_utils") is not None,
    }


class LocalTransformersModel:
    """Experimental local backend. Heavy imports happen only on first call."""

    def __init__(self, settings: LocalModelSettings) -> None:
        self.settings = settings
        self._lock = asyncio.Lock()
        self._model = None
        self._processor = None
        self._torch = None
        self._device = None

    async def complete(
        self,
        messages: list[dict],
        *,
        json_mode: bool = True,
        extra_body: dict[str, Any] | None = None,
    ) -> ModelCallResult:
        async with self._lock:
            return await asyncio.to_thread(self._complete_sync, messages)

    def _complete_sync(self, messages: list[dict]) -> ModelCallResult:
        started = time.perf_counter()
        self._ensure_loaded()
        torch = self._torch
        processor = self._processor
        model = self._model

        hf_messages, images = self._convert_messages(messages)
        try:
            if hasattr(processor, "apply_chat_template"):
                prompt = processor.apply_chat_template(
                    hf_messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            else:
                prompt = processor.tokenizer.apply_chat_template(
                    hf_messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
        except Exception as exc:
            raise EngineError(
                "local_prompt_failed",
                "The local model processor could not build a chat prompt.",
                status_code=500,
                details={"error": str(exc)},
            ) from exc

        inputs = processor(
            text=[prompt],
            images=images or None,
            return_tensors="pt",
            min_pixels=self.settings.min_pixels,
            max_pixels=self.settings.max_pixels,
        )
        inputs = {
            key: value.to(self._device) if hasattr(value, "to") else value
            for key, value in dict(inputs).items()
        }
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=self.settings.max_new_tokens,
                do_sample=False,
            )
        input_tokens = int(inputs["input_ids"].shape[-1])
        output_tokens = int(generated.shape[-1] - input_tokens)
        text = processor.batch_decode(
            generated[:, input_tokens:],
            skip_special_tokens=True,
        )[0].strip()
        if not text:
            raise EngineError(
                "local_empty_response",
                "The local model returned an empty response.",
                status_code=502,
                retryable=True,
            )
        return ModelCallResult(
            text=text,
            provider=self.settings.provider,
            model=self.settings.model_id,
            usage={
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            request_id=None,
            latency_ms=max(1, int((time.perf_counter() - started) * 1000)),
            json_mode_used=False,
        )

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        status = local_dependency_status()
        missing = [name for name, present in status.items() if not present]
        if missing:
            raise EngineError(
                "local_dependencies_missing",
                "Local model dependencies are missing; install requirements-perception.txt "
                "in a 64-bit Python 3.11+ environment.",
                status_code=503,
                details={"missing": missing},
            )

        import torch
        from transformers import AutoProcessor

        try:
            from transformers import AutoModelForImageTextToText as AutoVisionModel
        except ImportError:
            try:
                from transformers import AutoModelForVision2Seq as AutoVisionModel
            except ImportError:
                from transformers import (
                    Qwen2_5_VLForConditionalGeneration as AutoVisionModel,
                )

        if self.settings.device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            device = self.settings.device
        if device.startswith("cuda") and not torch.cuda.is_available():
            raise EngineError(
                "local_cuda_unavailable",
                "CUDA was requested but is not available in this Python environment.",
                status_code=503,
            )
        if device == "cuda" and self.settings.load_in_4bit and self.settings.model_id.endswith("7B"):
            if torch.cuda.get_device_properties(0).total_memory < 8 * 1024**3:
                raise EngineError(
                    "local_vram_insufficient",
                    "A 7B 4-bit model should use a GPU with at least 8 GB VRAM; "
                    "the planned RTX 5070 Ti has 16 GB.",
                    status_code=503,
                )

        dtype = _resolve_dtype(torch, self.settings.dtype, device)
        model_kwargs: dict[str, Any] = {
            "trust_remote_code": self.settings.trust_remote_code,
            "torch_dtype": dtype,
        }
        if self.settings.load_in_4bit:
            if importlib.util.find_spec("bitsandbytes") is None:
                raise EngineError(
                    "bitsandbytes_missing",
                    "load_in_4bit is enabled but bitsandbytes is not installed.",
                    status_code=503,
                )
            from transformers import BitsAndBytesConfig

            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=dtype,
            )
            model_kwargs["device_map"] = "auto"
        elif device == "cuda":
            model_kwargs["device_map"] = device

        try:
            self._processor = AutoProcessor.from_pretrained(
                self.settings.model_id,
                trust_remote_code=self.settings.trust_remote_code,
            )
            self._model = AutoVisionModel.from_pretrained(
                self.settings.model_id,
                **model_kwargs,
            ).eval()
        except Exception as exc:
            raise EngineError(
                "local_model_load_failed",
                f"Could not load local model {self.settings.model_id}.",
                status_code=503,
                details={"error": str(exc)},
            ) from exc

        self._torch = torch
        if hasattr(self._model, "device"):
            self._device = self._model.device
        else:
            self._device = next(self._model.parameters()).device

    def _convert_messages(self, messages: list[dict]) -> tuple[list[dict], list[Image.Image]]:
        converted: list[dict] = []
        images: list[Image.Image] = []
        for message in messages:
            content = message.get("content")
            if isinstance(content, str):
                converted.append({"role": message.get("role", "user"), "content": content})
                continue
            if not isinstance(content, list):
                continue
            parts: list[dict] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    parts.append({"type": "text", "text": str(item.get("text", ""))})
                elif item.get("type") == "image_url":
                    image_url = item.get("image_url", {})
                    url = image_url.get("url", "") if isinstance(image_url, dict) else ""
                    image = _decode_data_url(url)
                    images.append(image)
                    parts.append({"type": "image", "image": image})
            converted.append({"role": message.get("role", "user"), "content": parts})
        return converted, images


def _decode_data_url(url: str) -> Image.Image:
    if not url.startswith("data:image/") or ";base64," not in url:
        raise EngineError(
            "local_image_url_unsupported",
            "The local backend currently accepts Base64 image data URLs only.",
            status_code=422,
        )
    encoded = url.split(";base64,", 1)[1]
    try:
        raw = base64.b64decode(encoded, validate=True)
        image = Image.open(io.BytesIO(raw))
        image.load()
        return image.convert("RGB")
    except Exception as exc:
        raise EngineError(
            "local_image_decode_failed",
            "Could not decode image data for the local model.",
            status_code=422,
        ) from exc


def _resolve_dtype(torch, dtype_name: str, device: str):
    normalized = dtype_name.lower()
    if normalized in {"float16", "fp16", "half"}:
        return torch.float16
    if normalized in {"bfloat16", "bf16"}:
        return torch.bfloat16
    if normalized in {"float32", "fp32"}:
        return torch.float32
    if device.startswith("cuda"):
        return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    return torch.float32
