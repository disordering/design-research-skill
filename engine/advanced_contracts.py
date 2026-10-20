"""Contracts for the evidence-first advanced review pipeline."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import EvidenceAnchor, RawAuditResult, Severity


class NormalizedBox(BaseModel):
    model_config = ConfigDict(extra="ignore")

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def bounds(self) -> "NormalizedBox":
        if self.x + self.width > 1.001 or self.y + self.height > 1.001:
            raise ValueError("Normalized box exceeds image bounds.")
        return self

    def as_list(self) -> list[float]:
        return [self.x, self.y, self.width, self.height]


class OCRBlock(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    text: str = Field(min_length=1)
    bbox: NormalizedBox
    confidence: float = Field(default=0.5, ge=0, le=1)
    estimated_height_px: float | None = Field(default=None, ge=0)


class OCRResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    blocks: list[OCRBlock] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class UIElement(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: str = "E"
    label: str = ""
    role: str = "other"
    bbox: NormalizedBox
    interactable: bool = False
    visual_importance: float = Field(default=0.5, ge=0, le=1)
    state: str = "default"
    confidence: float = Field(default=0.5, ge=0, le=1)

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return str(value or "E").strip().upper()


class UIResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page_type: str = "unknown"
    summary: str = ""
    elements: list[UIElement] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class GoalConstraint(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: str
    text: str
    category: Literal[
        "layout",
        "hierarchy",
        "density",
        "style",
        "anti_pattern",
        "readability",
        "interaction",
        "other",
    ] = "other"
    metric_hint: str = ""
    target_roles: list[str] = Field(default_factory=list)
    priority: int = Field(default=2, ge=1, le=3)


class GoalDecomposition(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    page_summary: str = ""
    constraints: list[GoalConstraint] = Field(default_factory=list)


class RuleRelevance(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    rule_id: str
    visual: float = Field(ge=0, le=1)
    text: float = Field(ge=0, le=1)
    attribute: float = Field(ge=0, le=1)
    prior: float = Field(ge=0, le=1)
    final: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)


class RelevanceResult(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    scene_summary: str = ""
    rankings: list[RuleRelevance] = Field(default_factory=list)


class PrototypeMatch(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    role: str
    result_bbox: NormalizedBox
    reference_bbox: NormalizedBox | None = None
    iou: float | None = Field(default=None, ge=0, le=1)
    center_offset: float | None = Field(default=None, ge=0)
    size_ratio_change: float | None = Field(default=None)


class AdvancedReviewArtifacts(BaseModel):
    model_config = ConfigDict(extra="ignore")

    report_json: str | None = None
    elements_json: str | None = None
    ocr_json: str | None = None
    metrics_json: str | None = None
    criteria_relevance_csv: str | None = None
    overlay_elements: str | None = None
    overlay_focus: str | None = None
    overlay_prototype_match: str | None = None


class GoalCheck(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    constraint_id: str
    status: Literal["observed_violation", "met", "insufficient_evidence"]
    title: str = ""
    severity: Severity = Severity.MEDIUM
    confidence: float = Field(default=0.5, ge=0, le=1)
    detection: str = ""
    description: str = ""
    suggestion: str = ""
    evidence: EvidenceAnchor | None = None


class AdvancedAuditResult(RawAuditResult):
    goal_checks: list[GoalCheck] = Field(default_factory=list)


class StageNote(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    stage: str
    purpose: str
    conclusion: str


class MetricNote(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    metric: str
    value: Any
    why_measured: str
    interpretation: str


class FindingNote(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    finding_id: str
    judgment_source: str
    explanation: str
    user_impact: str = ""
    action_rationale: str = ""


class RelevanceNote(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    rule_id: str
    why_relevant: str


class NarrativeResult(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    title: str
    executive_summary: str
    stages: list[StageNote] = Field(default_factory=list)
    metrics: list[MetricNote] = Field(default_factory=list)
    findings: list[FindingNote] = Field(default_factory=list)
    relevance: list[RelevanceNote] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
