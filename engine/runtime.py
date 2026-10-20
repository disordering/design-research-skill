"""Build ReviewEngine instances from config without duplicating routing logic."""

from __future__ import annotations

import os

from .criteria import CriteriaLibrary
from .errors import EngineError
from .local_model import LocalModelSettings, LocalTransformersModel
from .model import OpenAICompatibleModel, ModelSettings
from .service import ReviewEngine
from .stub import StubModel

LOCAL_BACKENDS = {"local_holo", "local_ui_tars"}


def build_engine(
    criteria: CriteriaLibrary,
    provider: str | None = None,
    model: str | None = None,
) -> ReviewEngine:
    selected = (provider or os.getenv("REVIEW_PROVIDER", "qwen")).strip().lower()
    if selected == "stub":
        stub_allowed = os.getenv("REVIEW_ALLOW_STUB", "0").lower() in {"1", "true", "yes"}
        if not stub_allowed:
            raise EngineError(
                "stub_disabled",
                "The stub provider is disabled. Set REVIEW_ALLOW_STUB=1 for contract previews.",
                status_code=403,
            )
        return ReviewEngine(
            criteria,
            StubModel(),
            provider="stub",
            model_name="contract-stub-v1",
            is_stub=True,
        )
    if selected in LOCAL_BACKENDS:
        settings = LocalModelSettings.from_provider(selected)
        if model:
            settings = LocalModelSettings(
                provider=settings.provider,
                model_id=model,
                device=settings.device,
                dtype=settings.dtype,
                load_in_4bit=settings.load_in_4bit,
                max_new_tokens=settings.max_new_tokens,
                min_pixels=settings.min_pixels,
                max_pixels=settings.max_pixels,
                trust_remote_code=settings.trust_remote_code,
            )
        local = LocalTransformersModel(settings)
        return ReviewEngine(
            criteria,
            local,
            provider=selected,
            model_name=local.settings.model_id,
        )
    settings = ModelSettings.from_env(selected, model)
    return ReviewEngine(
        criteria,
        OpenAICompatibleModel(settings),
        provider=settings.provider,
        model_name=settings.model,
    )
