"""Session routes are separate from the legacy screenshot response contract."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import FileResponse, PlainTextResponse

from .config import load_reviewer_config
from .errors import EngineError
from .session_contracts import EventInput, SessionCreate, SessionSnapshot
from .session_report import (
    audit_report, markdown_report, markdown_summary, structured_report,
    write_report_package, zip_report_package,
)
from .session_service import SessionService
from .session_store import SessionStore

ROOT = Path(__file__).resolve().parent.parent


def public_snapshot(snapshot: SessionSnapshot) -> SessionSnapshot:
    """Keep API polling bounded; raw uploads remain available through artifacts/report packages."""
    result = snapshot.model_copy(deep=True)
    for source in result.sources:
        source.input.image_base64 = ""
        source.input.document_base64 = ""
    return result


def install_session_routes(
    app, factory: Callable[[], SessionService] | None = None,
) -> None:
    router = APIRouter(prefix="/api/review-sessions", tags=["Collaborative reviews"])
    instance: SessionService | None = None

    def service() -> SessionService:
        nonlocal instance
        if instance is None:
            if factory:
                instance = factory()
            else:
                config = load_reviewer_config(required=False)
                path = Path(config.get("sessions", {}).get("storage_dir", "out/sessions"))
                instance = SessionService(SessionStore(path if path.is_absolute() else ROOT / path))
        return instance

    @router.get("/capabilities")
    async def capabilities():
        return service().capabilities()

    @router.post("", response_model=SessionSnapshot, status_code=201)
    async def create_session(request: SessionCreate):
        created = service().create(request)
        if request.auto_run:
            service().submit(created.session_id)
        return public_snapshot(created)

    @router.get("/{session_id}", response_model=SessionSnapshot)
    async def get_session(session_id: str):
        return public_snapshot(service().store.get(session_id))

    @router.get("/{session_id}/updates")
    async def updates(session_id: str, after_sequence: int = 0):
        snapshot = service().store.get(session_id)
        return {
            "sequence": snapshot.sequence, "changed": snapshot.sequence > after_sequence,
            "snapshot": (
                public_snapshot(snapshot).model_dump(mode="json")
                if snapshot.sequence > after_sequence else None
            ),
        }

    @router.post("/{session_id}/events", response_model=SessionSnapshot, status_code=202)
    async def submit_event(session_id: str, event: EventInput):
        snapshot, run = service().apply_event(session_id, event)
        if run:
            service().submit(session_id)
        return public_snapshot(snapshot)

    @router.post("/{session_id}/run", response_model=SessionSnapshot, status_code=202)
    async def run_session(session_id: str):
        snapshot = service().store.get(session_id)
        if snapshot.status in {"cancelled", "completed"}:
            raise EngineError(
                "session_run_invalid",
                "已完成或已取消的会话不能直接继续；请提交新事件开启复审。",
                status_code=409,
            )
        service().submit(session_id)
        return public_snapshot(snapshot)

    @router.get("/{session_id}/reports/{version}", response_model=SessionSnapshot)
    async def report(session_id: str, version: int):
        return public_snapshot(service().store.report(session_id, version))

    @router.get("/{session_id}/export", response_class=PlainTextResponse)
    async def export(
        session_id: str, version: int | None = None,
        format: Literal["human", "summary", "audit"] = "human",
    ):
        snapshot = service().store.report(session_id, version) if version is not None else service().store.get(session_id)
        if format == "summary":
            text = markdown_summary(snapshot, registry=service().registry)
        elif format == "audit":
            text = audit_report(
                snapshot, registry=service().registry,
                artifact_loader=service().store.artifact,
            )
        else:
            text = markdown_report(
                snapshot, registry=service().registry,
                artifact_loader=service().store.artifact,
                audit_href=(
                    f"/api/review-sessions/{session_id}/export"
                    f"?format=audit&version={snapshot.report_version}"
                ),
            )
        return PlainTextResponse(
            text, media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="review-{snapshot.report_version}.md"'},
        )

    @router.get("/{session_id}/structured-report")
    async def structured(session_id: str, version: int | None = None):
        snapshot = service().store.report(session_id, version) if version is not None else service().store.get(session_id)
        return structured_report(
            snapshot, registry=service().registry, artifact_loader=service().store.artifact,
        )

    @router.get("/{session_id}/package")
    async def package(session_id: str, version: int | None = None):
        snapshot = service().store.report(session_id, version) if version is not None else service().store.get(session_id)
        directory = service().store.root / session_id / f"package-v{snapshot.report_version}"
        write_report_package(snapshot, service().store, directory, registry=service().registry)
        zip_path = service().store.root / session_id / f"review-package-v{snapshot.report_version}.zip"
        zip_report_package(directory, zip_path)
        return FileResponse(
            zip_path, media_type="application/zip",
            filename=f"review-{session_id}-v{snapshot.report_version}.zip",
        )

    @router.get("/{session_id}/artifacts/{artifact_id}")
    async def artifact(session_id: str, artifact_id: str):
        path, mime = service().store.artifact(session_id, artifact_id)
        return FileResponse(path, media_type=mime)

    app.include_router(router)

    # FastAPI's existing app has no lifespan; append cleanup without changing v1 initialization.
    async def shutdown():
        if instance is not None:
            await instance.close()
    app.router.on_shutdown.append(shutdown)
