"""Local TOML configuration loading without exposing secrets."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import tomli

from .errors import EngineError

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config" / "reviewer.toml"
DEFAULT_EXAMPLE_CONFIG_PATH = ROOT / "config" / "reviewer.example.toml"


def config_path_from_env() -> Path:
    configured = os.getenv("REVIEW_CONFIG", "").strip()
    return Path(configured) if configured else DEFAULT_CONFIG_PATH


def load_reviewer_config(path: str | Path | None = None, *, required: bool = False) -> dict[str, Any]:
    resolved = Path(path) if path else config_path_from_env()
    if not resolved.exists():
        if required:
            raise EngineError(
                "config_not_found",
                f"Reviewer config was not found at {resolved}.",
                status_code=500,
                details={
                    "hint": "Copy config/reviewer.example.toml to config/reviewer.toml."
                },
            )
        return {}
    try:
        return tomli.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, tomli.TOMLDecodeError) as exc:
        raise EngineError(
            "config_invalid",
            f"Could not parse reviewer config at {resolved}.",
            status_code=500,
            details={"error": str(exc)},
        ) from exc


def validate_reviewer_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    app = _table(config, "app")
    criteria_path = app.get("criteria_path", "判据库_v1.json")
    if not Path(criteria_path).exists():
        errors.append(f"app.criteria_path does not exist: {criteria_path}")

    qwen = _table(config, "providers", "qwen")
    if qwen.get("enabled", False):
        key = str(qwen.get("api_key", "")).strip() or os.getenv("DASHSCOPE_API_KEY", "").strip()
        if not key:
            errors.append("providers.qwen.api_key is empty")
        for field in (
            "reasoning_model",
            "ui_perception_model",
            "ocr_model",
            "text_embedding_model",
            "text_rerank_model",
            "vlm_embedding_model",
            "vlm_rerank_model",
        ):
            if not str(qwen.get(field, "")).strip():
                errors.append(f"providers.qwen.{field} is empty")

    deepseek = _table(config, "providers", "deepseek")
    if deepseek.get("enabled", False):
        key = str(deepseek.get("api_key", "")).strip() or os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not key:
            errors.append("providers.deepseek.api_key is empty")
        if not str(deepseek.get("reasoning_model", "")).strip():
            errors.append("providers.deepseek.reasoning_model is empty")

    for provider, section_name in (
        ("local_holo", "local_holo15"),
        ("local_ui_tars", "local_ui_tars"),
    ):
        local = _table(config, "models", section_name)
        if local.get("enabled", False) and not str(local.get("model_id", "")).strip():
            errors.append(f"models.{section_name}.model_id is empty")

    return errors


def config_health(config: dict[str, Any]) -> dict[str, Any]:
    qwen = _table(config, "providers", "qwen")
    deepseek = _table(config, "providers", "deepseek")
    errors = validate_reviewer_config(config)
    return {
        "config_schema_valid": True,
        "ready": not errors,
        "criteria_path": _table(config, "app").get("criteria_path", "判据库_v1.json"),
        "errors": errors,
        "providers": {
            "qwen": {
                "enabled": bool(qwen.get("enabled", False)),
                "api_key_configured": bool(
                    str(qwen.get("api_key", "")).strip()
                    or os.getenv("DASHSCOPE_API_KEY", "").strip()
                ),
                "models": {
                    key: qwen.get(key)
                    for key in (
                        "reasoning_model",
                        "ui_perception_model",
                        "ocr_model",
                        "text_embedding_model",
                        "text_rerank_model",
                        "vlm_embedding_model",
                        "vlm_rerank_model",
                    )
                },
            },
            "deepseek": {
                "enabled": bool(deepseek.get("enabled", False)),
                "api_key_configured": bool(
                    str(deepseek.get("api_key", "")).strip()
                    or os.getenv("DEEPSEEK_API_KEY", "").strip()
                ),
                "models": {
                    "reasoning_model": deepseek.get("reasoning_model"),
                    "vision_model": deepseek.get("vision_model"),
                },
            },
            "local": {
                "local_holo": _table(config, "models", "local_holo15"),
                "local_ui_tars": _table(config, "models", "local_ui_tars"),
            },
        },
    }


def _table(config: dict[str, Any], *keys: str) -> dict[str, Any]:
    current: Any = config
    for key in keys:
        if not isinstance(current, dict):
            return {}
        current = current.get(key, {})
    return current if isinstance(current, dict) else {}
