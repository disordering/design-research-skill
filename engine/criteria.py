"""Criteria-library loading and validation."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .contracts import Decision, SourceReference
from .errors import EngineError


class Criterion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str
    heuristic: str
    title: str
    applies_if: str
    check: str
    mark_issue_if: str
    abstain_if: str
    suggestion: str


class CriteriaLibrary(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version: str
    purpose: str
    source: SourceReference
    allowed_decisions: list[Decision]
    rules: list[Criterion] = Field(min_length=1)

    def __init__(self, **data: object) -> None:
        super().__init__(**data)
        ids = [rule.id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("Criteria rule IDs must be unique.")

    @classmethod
    def load(cls, path: str | Path) -> "CriteriaLibrary":
        criteria_path = Path(path)
        try:
            raw = json.loads(criteria_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise EngineError(
                "criteria_not_found",
                f"Criteria library was not found at {criteria_path}.",
                status_code=500,
            ) from exc
        except json.JSONDecodeError as exc:
            raise EngineError(
                "criteria_invalid_json",
                f"Criteria library is not valid JSON: {exc}.",
                status_code=500,
            ) from exc
        try:
            return cls.model_validate(raw)
        except ValueError as exc:
            raise EngineError(
                "criteria_invalid_schema",
                f"Criteria library does not match the expected schema: {exc}.",
                status_code=500,
            ) from exc

    @property
    def by_id(self) -> dict[str, Criterion]:
        return {rule.id: rule for rule in self.rules}

    @property
    def rule_ids(self) -> list[str]:
        return [rule.id for rule in self.rules]


HEURISTIC_TITLES = {
    "H01": "系统状态的可见性",
    "H02": "系统与现实世界的匹配",
    "H03": "用户控制与自由",
    "H04": "一致性与标准",
    "H05": "错误预防",
    "H06": "识别而非回忆",
    "H07": "灵活性与效率",
    "H08": "美学与极简设计",
    "H09": "帮助用户识别、诊断和恢复错误",
    "H10": "帮助与文档",
}


def heuristic_label(heuristic_id: str) -> str:
    title = HEURISTIC_TITLES.get(heuristic_id, "未知启发式原则")
    return f"{heuristic_id} {title}"
