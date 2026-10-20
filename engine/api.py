"""FastAPI entry points consumed by the interaction layer."""

from __future__ import annotations

import base64
import binascii
import os
from pathlib import Path
from typing import Callable, Literal

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .contracts import Decision, JsonReviewRequest, ReviewContext, ReviewReport
from .config import config_health, load_reviewer_config
from .criteria import CriteriaLibrary
from .errors import EngineError
from .local_model import local_dependency_status
from .model import PROVIDER_PRESETS
from .runtime import build_engine
from .service import ReviewEngine

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CRITERIA_PATH = ROOT / "判据库_v1.json"

EngineFactory = Callable[[str | None, str | None], ReviewEngine]


def create_app(
    *,
    criteria_path: str | Path = DEFAULT_CRITERIA_PATH,
    engine_factory: EngineFactory | None = None,
) -> FastAPI:
    criteria = CriteriaLibrary.load(criteria_path)
    factory = engine_factory or _default_engine_factory(criteria)

    app = FastAPI(
        title="Interaction Review Engine",
        version="1.0.0",
        description="Screenshot-to-heuristic-review API with evidence anchors.",
    )
    origins = [
        value.strip()
        for value in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
        ).split(",")
        if value.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.exception_handler(EngineError)
    async def engine_error_handler(_, exc: EngineError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "retryable": exc.retryable,
                    "details": exc.details,
                }
            },
        )

    @app.get("/healthz")
    async def healthz() -> dict:
        config = load_reviewer_config(required=False)
        local_health = config_health(config) if config else {}
        configured = [
            name
            for name, preset in PROVIDER_PRESETS.items()
            if any(os.getenv(env_name) for env_name in preset.key_env_names)
            or bool(
                config.get("providers", {})
                .get(name, {})
                .get("api_key", "")
                if isinstance(config.get("providers"), dict)
                else False
            )
        ]
        if os.getenv("REVIEW_API_KEY") and os.getenv("REVIEW_BASE_URL"):
            configured.append("generic")
        local_status = local_dependency_status()
        return {
            "status": "ok" if not local_health.get("errors") else "degraded",
            "criteria_version": criteria.version,
            "criteria_rules": len(criteria.rules),
            "configured_providers": configured,
            "config": local_health,
            "local_runtime_dependencies": local_status,
            "stub_allowed": os.getenv("REVIEW_ALLOW_STUB", "0").lower() in {"1", "true", "yes"},
        }

    @app.get("/api/criteria")
    async def criteria_metadata() -> dict:
        counts: dict[str, int] = {}
        for rule in criteria.rules:
            counts[rule.heuristic] = counts.get(rule.heuristic, 0) + 1
        return {
            "version": criteria.version,
            "purpose": criteria.purpose,
            "source": criteria.source.model_dump(),
            "rule_count": len(criteria.rules),
            "heuristic_counts": counts,
            "allowed_decisions": [decision.value for decision in Decision],
        }

    @app.post("/api/review-audit", response_model=ReviewReport)
    async def review_audit_upload(
        image: UploadFile = File(..., description="PNG, JPEG, or WEBP screenshot"),
        design_goal: str | None = Form(default=None),
        scenario: str | None = Form(default=None),
        platform: Literal[
            "web", "ios", "android", "desktop", "game", "unknown"
        ] = Form(default="unknown"),
        target_user: str | None = Form(default=None),
        provider: str | None = Form(default=None),
        model: str | None = Form(default=None),
        analysis_mode: str = Form(default="two_pass"),
    ) -> ReviewReport:
        try:
            context = ReviewContext(
                design_goal=design_goal,
                scenario=scenario,
                platform=platform,
                target_user=target_user,
            )
        except ValidationError as exc:
            # Reuse the context contract so whitespace normalization and length
            # limits match the JSON endpoint, then expose request-level errors.
            errors = [
                {**error, "loc": ("body", *error["loc"])}
                for error in exc.errors()
            ]
            raise RequestValidationError(errors) from exc
        raw = await image.read()
        engine = factory(provider, model)
        return await engine.review(
            raw,
            context=context,
            filename=image.filename or "screenshot.png",
            analysis_mode=analysis_mode,
        )

    @app.post("/api/review-audit/base64", response_model=ReviewReport)
    async def review_audit_json(payload: JsonReviewRequest) -> ReviewReport:
        try:
            raw = base64.b64decode(payload.image_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise EngineError(
                "invalid_base64_image",
                "image_base64 is not valid base64.",
                status_code=422,
            ) from exc
        context = ReviewContext(
            design_goal=payload.design_goal,
            scenario=payload.scenario,
            platform=payload.platform,
            target_user=payload.target_user,
        )
        engine = factory(payload.provider, payload.model)
        return await engine.review(
            raw,
            context=context,
            filename=payload.filename,
            analysis_mode=payload.analysis_mode,
        )

    return app


def _default_engine_factory(criteria: CriteriaLibrary) -> EngineFactory:
    def factory(provider: str | None, model: str | None) -> ReviewEngine:
        return build_engine(criteria, provider, model)

    return factory


app = create_app()
