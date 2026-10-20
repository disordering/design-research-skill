"""Pydantic contracts shared by the engine, API, and UI consumers."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Decision(str, Enum):
    CANDIDATE_ISSUE = "candidate_issue"
    NO_VISIBLE_ISSUE = "no_visible_issue"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewContext(BaseModel):
    """Context supplied by the reviewer. Missing fields must not be inferred."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    design_goal: str | None = Field(default=None, max_length=2000)
    scenario: str | None = Field(default=None, max_length=2000)
    platform: Literal["web", "ios", "android", "desktop", "game", "unknown"] = "unknown"
    target_user: str | None = Field(default=None, max_length=1000)


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    url: str
    relationship: str


class EvidenceAnchor(BaseModel):
    """A normalized crop box over the submitted screenshot."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    description: str = Field(min_length=1, max_length=500)
    visible_text: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_bounds(self) -> "EvidenceAnchor":
        if self.x + self.width > 1.0001 or self.y + self.height > 1.0001:
            raise ValueError("Evidence box must stay inside the normalized image bounds.")
        return self


class Finding(BaseModel):
    """One four-part finding, potentially backed by multiple criteria."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str
    decision: Literal["candidate_issue"] = "candidate_issue"
    rule_ids: list[str] = Field(min_length=1)
    heuristics: list[str] = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    principle: str = Field(min_length=1)
    detection: str = Field(min_length=1)
    description: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)
    evidence: EvidenceAnchor
    sources: list[SourceReference] = Field(min_length=1)
    review_status: Literal["unreviewed"] = "unreviewed"


class RuleResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rule_id: str
    title: str
    heuristic: str
    decision: Decision
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=1000)


class ScreenAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    page_type: str = "unknown"
    visible_text: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    observed_states: list[str] = Field(default_factory=list)
    task_clues: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class ImageInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha256: str
    mime_type: str
    width: int
    height: int
    original_width: int
    original_height: int
    resized: bool


class ModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    analysis_mode: Literal["two_pass", "single_pass", "ensemble"]
    is_stub: bool


class ReviewSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules_total: int
    candidate_issues: int
    no_visible_issue: int
    insufficient_evidence: int
    not_applicable: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int


class ReviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    review_id: str
    status: Literal["completed", "partial"]
    model: ModelInfo
    context: ReviewContext
    image: ImageInfo
    screen_analysis: ScreenAnalysis
    criteria_version: str
    criteria_source: SourceReference
    summary: ReviewSummary
    findings: list[Finding]
    rule_results: list[RuleResult]
    warnings: list[str] = Field(default_factory=list)
    timings_ms: dict[str, int] = Field(default_factory=dict)
    diagnostics: dict = Field(default_factory=dict)
    perception: dict = Field(default_factory=dict)
    criteria_relevance: list[dict] = Field(default_factory=list)
    goal_constraints: list[dict] = Field(default_factory=list)
    goal_checks: list[dict] = Field(default_factory=list)
    artifacts: dict = Field(default_factory=dict)


class JsonReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    image_base64: str = Field(min_length=32)
    mime_type: str = "image/png"
    filename: str = "screenshot.png"
    design_goal: str | None = Field(default=None, max_length=2000)
    scenario: str | None = Field(default=None, max_length=2000)
    platform: Literal["web", "ios", "android", "desktop", "game", "unknown"] = "unknown"
    target_user: str | None = Field(default=None, max_length=1000)
    provider: Literal[
        "qwen",
        "deepseek",
        "generic",
        "stub",
        "local_holo",
        "local_ui_tars",
    ] | None = None
    model: str | None = Field(default=None, max_length=200)
    analysis_mode: Literal["two_pass", "single_pass"] = "two_pass"


class RuleStatus(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    rule_id: str
    decision: Decision
    confidence: float = Field(default=0.5, ge=0, le=1)
    reason: str = Field(default="", max_length=1000)


class RawFinding(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    rule_ids: list[str] = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    severity: Severity
    confidence: float = Field(default=0.5, ge=0, le=1)
    principle: str = Field(default="", max_length=2000)
    detection: str = Field(min_length=1, max_length=2000)
    description: str = Field(min_length=1, max_length=2000)
    suggestion: str = Field(min_length=1, max_length=2000)
    evidence: EvidenceAnchor

    @field_validator("rule_ids")
    @classmethod
    def normalize_rule_ids(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip().upper() for value in values if value.strip()))


class RawAuditResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    screen_analysis: ScreenAnalysis | None = None
    rule_statuses: list[RuleStatus]
    findings: list[RawFinding] = Field(default_factory=list)
