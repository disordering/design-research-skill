"""Typed errors exposed by the engine and API."""

from __future__ import annotations

from typing import Any


class EngineError(Exception):
    """An error that can be converted into a stable API response."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 500,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}
