"""Session model profiles; local endpoints do not silently fall back to cloud."""

from __future__ import annotations

import os
from dataclasses import replace
from urllib.parse import urlparse

from .config import load_reviewer_config
from .errors import EngineError
from .model import ModelSettings, OpenAICompatibleModel
from .session_contracts import SessionCreate


def build_session_model(request: SessionCreate) -> OpenAICompatibleModel:
    config = load_reviewer_config(required=False)
    profile = config.get("providers", {}).get(request.provider, {})
    if request.provider == "local":
        if not profile.get("enabled", False):
            raise EngineError("local_session_model_disabled", "本地模型尚未启用；先启动视觉模型服务并配置 providers.local。", status_code=503)
        base = os.getenv("REVIEW_SESSION_LOCAL_URL", "") or str(profile.get("base_url", ""))
        selected = request.model_name or os.getenv("REVIEW_SESSION_LOCAL_MODEL", "") or str(profile.get("model", ""))
        parsed = urlparse(base)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or not selected:
            raise EngineError("local_session_model_invalid", "本地模型需要明确模型名和 loopback HTTP(S) 地址。", status_code=503)
        settings = ModelSettings(
            provider="local", base_url=base, model=selected,
            api_key=str(profile.get("api_key", "local")),
            timeout_seconds=180, max_retries=1,
            max_tokens=int(profile.get("max_tokens", 4096)),
        )
    else:
        selected = request.model_name
        if not selected and request.provider == "deepseek":
            selected = str(profile.get("reasoning_model", "")) or None
        settings = ModelSettings.from_env(request.provider, selected)
        settings = replace(settings, max_tokens=int(profile.get("session_max_tokens", 4096)))
    client = OpenAICompatibleModel(settings)
    # DeepSeek is treated as text-only unless a verified vision profile explicitly opts in.
    client.supports_images = bool(profile.get("vision", request.provider != "deepseek"))
    if request.provider == "qwen":
        client.session_extra_body = {
            "enable_thinking": bool(profile.get("session_enable_thinking", False)),
        }
    elif request.provider == "deepseek":
        client.session_extra_body = {
            "reasoning_effort": str(
                profile.get("session_reasoning_effort", "high")
            ),
        }
    else:
        client.session_extra_body = {}
    return client


def session_model_profiles() -> dict:
    config = load_reviewer_config(required=False)
    providers = config.get("providers", {})
    result = {}
    for name in ("qwen", "deepseek", "local"):
        p = providers.get(name, {})
        result[name] = {
            "enabled": bool(p.get("enabled", False)),
            "model": p.get("model") if name == "local" else p.get("reasoning_model"),
            "vision": bool(p.get("vision", name != "deepseek")),
            "verified": False,
        }
    return result
