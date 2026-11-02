"""Transactional session snapshots, event deduplication and immutable reports."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .errors import EngineError
from .session_contracts import EventInput, SessionSnapshot, now, identifier


class SessionStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "sessions.sqlite3"
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    session_id TEXT NOT NULL, event_id TEXT NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(session_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS reports (
                    session_id TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(session_id, version)
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL, path TEXT NOT NULL,
                    mime_type TEXT NOT NULL, sha256 TEXT NOT NULL
                );
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.db_path, timeout=15)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            with db:
                yield db
        finally:
            db.close()

    def create(self, session: SessionSnapshot) -> None:
        with self.connection() as db:
            db.execute("INSERT INTO sessions VALUES(?,?,?)", (
                session.session_id, session.revision, session.model_dump_json(),
            ))

    def get(self, session_id: str) -> SessionSnapshot:
        with self.connection() as db:
            row = db.execute("SELECT body FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise EngineError("session_not_found", "会话不存在。", status_code=404)
        return SessionSnapshot.model_validate_json(row[0])

    def save(
        self, session: SessionSnapshot, *, event: EventInput | None = None,
        report: bool = False,
    ) -> bool:
        previous_revision = session.revision
        session.updated_at = now()
        session.sequence += 1
        session.revision += 1
        try:
            with self.connection() as db:
                if event is not None:
                    old = db.execute(
                        "SELECT body FROM events WHERE session_id=? AND event_id=?",
                        (session.session_id, event.event_id),
                    ).fetchone()
                    if old:
                        if old[0] != self._event_body(event):
                            raise EngineError("event_id_conflict", "事件 ID 已用于不同内容。", status_code=409)
                        session.revision = previous_revision
                        session.sequence -= 1
                        return False
                    db.execute("INSERT INTO events VALUES(?,?,?)", (
                        session.session_id, event.event_id, self._event_body(event),
                    ))
                result = db.execute(
                    "UPDATE sessions SET revision=?,body=? WHERE id=? AND revision=?",
                    (session.revision, session.model_dump_json(), session.session_id, previous_revision),
                )
                if result.rowcount != 1:
                    raise EngineError("session_revision_conflict", "会话已更新，请重新读取。", status_code=409)
                if report:
                    db.execute("INSERT INTO reports VALUES(?,?,?)", (
                        session.session_id, session.report_version, session.model_dump_json(),
                    ))
        except Exception:
            session.revision = previous_revision
            session.sequence -= 1
            raise
        return True

    def existing_event(self, session_id: str, event: EventInput) -> bool:
        with self.connection() as db:
            row = db.execute("SELECT body FROM events WHERE session_id=? AND event_id=?", (
                session_id, event.event_id,
            )).fetchone()
        if row and row[0] != self._event_body(event):
            raise EngineError("event_id_conflict", "事件 ID 已用于不同内容。", status_code=409)
        return row is not None

    @staticmethod
    def _event_body(event: EventInput) -> str:
        return json.dumps(event.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)

    def report(self, session_id: str, version: int) -> SessionSnapshot:
        with self.connection() as db:
            row = db.execute("SELECT body FROM reports WHERE session_id=? AND version=?", (
                session_id, version,
            )).fetchone()
        if row is None:
            raise EngineError("report_not_found", "报告版本不存在。", status_code=404)
        return SessionSnapshot.model_validate_json(row[0])

    def write_artifact(self, session_id: str, data: bytes, mime_type: str) -> str:
        self.get(session_id)
        artifact_id = identifier("artifact")
        suffix = {"image/png": ".png", "application/json": ".json", "text/plain": ".txt"}.get(mime_type, ".bin")
        directory = self.root / session_id
        directory.mkdir(exist_ok=True)
        destination = directory / (artifact_id + suffix)
        destination.write_bytes(data)
        with self.connection() as db:
            db.execute("INSERT INTO artifacts VALUES(?,?,?,?,?)", (
                artifact_id, session_id, str(destination), mime_type, hashlib.sha256(data).hexdigest(),
            ))
        return artifact_id

    def artifact(self, session_id: str, artifact_id: str) -> tuple[Path, str]:
        with self.connection() as db:
            row = db.execute("SELECT path,mime_type FROM artifacts WHERE id=? AND session_id=?", (
                artifact_id, session_id,
            )).fetchone()
        if row is None:
            raise EngineError("artifact_not_found", "证据文件不存在。", status_code=404)
        resolved = Path(row[0]).resolve()
        if not resolved.is_relative_to(self.root) or not resolved.is_file():
            raise EngineError("artifact_unavailable", "证据文件不可用。", status_code=404)
        return resolved, row[1]

    def capabilities(self) -> dict[str, Any]:
        return {"storage": "sqlite", "report_versions": "immutable", "event_idempotency": True}
