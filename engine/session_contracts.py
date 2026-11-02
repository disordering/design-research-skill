"""Versioned contracts for collaborative, multi-source reviews."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from urllib.parse import urlparse
import re

from pydantic import BaseModel, ConfigDict, Field, model_validator


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def identifier(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


SourceKind = Literal["website", "figma_board", "figma_prototype", "document", "image"]
EvidenceKind = Literal["requirement", "design", "implementation", "observation", "statement"]
SourceRole = Literal["unspecified", "design_brief", "product_spec", "design", "implementation",
                     "expert_opinion", "user_statement", "review_instruction"]
Execution = Literal["planned", "running", "executed", "blocked", "failed", "not_executed"]
Decision = Literal[
    "candidate_issue", "no_visible_issue", "insufficient_evidence", "not_applicable",
    "met", "observed_violation", "open", "no_conflict", "needs_clarification", "resolved",
]


class SourceInput(Contract):
    kind: SourceKind
    reference: str = Field(default="", max_length=4000)
    title: str = Field(default="", max_length=200)
    content: str = Field(default="", max_length=150000)
    image_base64: str = Field(default="", max_length=21000000)
    version: str = Field(default="unknown", max_length=200)
    evidence_kind: EvidenceKind | None = None
    role: SourceRole = "unspecified"
    declared_by: str = Field(default="unknown", max_length=200)
    document_base64: str = Field(default="", max_length=12000000)
    filename: str = Field(default="", max_length=200)
    figma_snapshot_id: str = Field(default="", pattern=r"^$|^[a-z0-9][a-z0-9-]{0,79}$")

    @model_validator(mode="after")
    def valid_source(self) -> "SourceInput":
        if self.figma_snapshot_id and self.kind != "figma_board":
            raise ValueError("figma_snapshot_id is only valid for figma_board sources.")
        if urlparse(self.reference).username or urlparse(self.reference).password:
            raise ValueError("Credentials must not appear in source references.")
        if self.kind in {"website", "figma_board", "figma_prototype"}:
            parsed = urlparse(self.reference)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("A web source requires an HTTP(S) URL.")
            if parsed.username or parsed.password:
                raise ValueError("Credentials must not appear in source URLs.")
            if self.kind.startswith("figma_") and parsed.hostname not in {"figma.com", "www.figma.com"}:
                raise ValueError("Figma sources must use figma.com.")
        elif self.kind == "document" and not self.content and not self.document_base64:
            parsed = urlparse(self.reference)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("A document requires inline content, an uploaded file, or an HTTP(S) URL without credentials.")
        elif self.kind == "image" and not self.image_base64:
            raise ValueError("An image requires base64 content.")
        return self


class Limits(Contract):
    max_actions: int = Field(default=12, ge=0, le=100)
    max_checks: int = Field(default=64, ge=1, le=500)
    max_model_calls: int = Field(default=60, ge=1, le=100)
    max_seconds: int = Field(default=900, ge=10, le=7200)
    max_images_per_call: int = Field(default=12, ge=0, le=16)
    max_material_chunks: int = Field(default=24, ge=1, le=100)


class SessionCreate(Contract):
    purpose: str = Field(min_length=1, max_length=12000)
    design_purpose: str = Field(default="", max_length=12000)
    target_user: str = Field(default="", max_length=2000)
    sources: list[SourceInput] = Field(min_length=1, max_length=30)
    limits: Limits = Field(default_factory=Limits)
    allow_interaction: bool = False
    auto_run: bool = False
    provider: Literal["qwen", "deepseek", "generic", "local"] = "qwen"
    model_name: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def combined_input_limit(self) -> "SessionCreate":
        if sum(len(s.content) + len(s.image_base64) + len(s.document_base64) for s in self.sources) > 30_000_000:
            raise ValueError("Combined source content exceeds 30 MB.")
        return self


class SourceRecord(Contract):
    source_id: str = Field(default_factory=lambda: identifier("src"))
    input: SourceInput
    acquisition_status: Literal["pending", "success", "partial", "blocked", "failed"] = "pending"
    error: str = ""
    captured_at: str | None = None
    observed_version: str | None = None
    active: bool = True


class Evidence(Contract):
    evidence_id: str = Field(default_factory=lambda: identifier("ev"))
    source_id: str
    kind: EvidenceKind
    source_version: str
    context_version: int
    captured_at: str = Field(default_factory=now)
    locator: dict[str, Any]
    content: str = Field(max_length=40000)
    artifact_id: str | None = None
    raw_artifact_id: str | None = None
    original_artifact_id: str | None = None
    analysis_artifact_id: str | None = None
    overlay_artifact_ids: dict[str, str] = Field(default_factory=dict)
    analysis: dict[str, Any] = Field(default_factory=dict)
    action_id: str | None = None
    state_id: str | None = None
    stale: bool = False


class EvidenceQuote(Contract):
    evidence_id: str
    quote: str = Field(min_length=1, max_length=2000)


class Constraint(Contract):
    id: str = Field(pattern=r"^(G|REQ)[A-Za-z0-9_.-]{1,100}$")
    text: str = Field(min_length=1, max_length=3000)
    evidence_ids: list[str] = Field(min_length=1)
    is_assumption: bool = False
    parent_id: str | None = None
    source_quotes: list[EvidenceQuote] = Field(default_factory=list)


class MaterialOpinion(Contract):
    id: str = Field(pattern=r"^OP[A-Za-z0-9_.-]{1,100}$")
    text: str = Field(min_length=1, max_length=3000)
    source_quotes: list[EvidenceQuote] = Field(min_length=1)


class MaterialRelationship(Contract):
    from_evidence_id: str
    to_evidence_id: str
    relation: Literal["same_object", "described_transition", "design_implementation"]
    reason: str = Field(min_length=1, max_length=2000)
    basis: Literal["described", "hypothesis"] = "hypothesis"


class MaterialConflict(Contract):
    conflict_id: str = ""
    topic: str = Field(min_length=1, max_length=500)
    claim_ids: list[str] = Field(min_length=2)
    source_quotes: list[EvidenceQuote] = Field(min_length=2)
    reason: str = Field(min_length=1, max_length=3000)
    status: Literal["open", "needs_clarification", "resolved"] = "open"
    blocking: bool = False


class ConflictDisposition(Contract):
    conflict_id: str
    decision: str = Field(min_length=1, max_length=4000)
    reason: str = Field(min_length=1, max_length=3000)
    actor: str
    source_id: str
    context_version: int
    created_at: str = Field(default_factory=now)
    accepted_claim_ids: list[str] = Field(default_factory=list)
    rejected_claim_ids: list[str] = Field(default_factory=list)
    rejected_quote_signatures: list[str] = Field(default_factory=list)


class MaterialUnderstanding(Contract):
    task_summary: str
    target_user_summary: str = ""
    goals: list[Constraint] = Field(default_factory=list, max_length=40)
    requirements: list[Constraint] = Field(default_factory=list, max_length=100)
    opinions: list[MaterialOpinion] = Field(default_factory=list, max_length=40)
    conflicts: list[MaterialConflict] = Field(default_factory=list, max_length=40)
    relationships: list[MaterialRelationship] = Field(default_factory=list, max_length=50)
    unknowns: list[str] = Field(default_factory=list, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=40)


class PlannedCheck(Contract):
    ref: str
    applicability: Literal["applicable", "not_applicable", "needs_context"]
    reason: str = Field(min_length=1, max_length=2000)
    source_ids: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_needed: list[str] = Field(default_factory=list, max_length=10)
    object_refs: list[str] = Field(default_factory=list, max_length=15)
    constraint_refs: list[str] = Field(
        default_factory=list, max_length=20,
        description="G/REQ constraints and OP discussion links; OP never becomes a scored requirement.",
    )
    required_evidence_kinds: list[EvidenceKind] = Field(default_factory=list)


class CheckPlanBatch(Contract):
    items: list[PlannedCheck]


class PageState(Contract):
    page_id: str
    state_id: str
    source_id: str
    context_version: int
    locator: dict[str, Any]
    evidence_ids: list[str]
    mode: Literal["design", "observation"]


class Transition(Contract):
    transition_id: str = Field(default_factory=lambda: identifier("transition"))
    source_id: str
    from_state: str
    to_state: str
    action_id: str
    evidence_ids: list[str]
    verification_status: Literal["observed"] = "observed"


class Question(Contract):
    question_id: str = Field(default_factory=lambda: identifier("question"))
    text: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=2000)
    check_ids: list[str] = Field(default_factory=list)
    blocking: bool = False
    answered: bool = False
    answer: str = ""
    kind: Literal["context", "access", "authorization", "tool_recovery"] = "context"
    source_id: str | None = None
    action_id: str | None = None
    answer_actor: Literal["unknown", "human", "program"] = "unknown"


class Action(Contract):
    action_id: str = Field(default_factory=lambda: identifier("action"))
    source_id: str
    kind: Literal["click", "fill", "back", "navigate", "observe", "scroll", "inspect_node", "inspect_document"]
    node_id: str = Field(default="", max_length=100)
    chunk_index: int = Field(default=0, ge=0, le=100)
    selector: str = Field(default="", max_length=1000)
    value: str = Field(default="", max_length=4000)
    url: str = Field(default="", max_length=4000)
    x: float | None = Field(default=None, ge=0, le=1)
    y: float | None = Field(default=None, ge=0, le=1)
    scroll_x: int = Field(default=0, ge=-2000, le=2000)
    scroll_y: int = Field(default=0, ge=-2000, le=2000)
    expected_state_id: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)
    target_label: str = Field(default="", max_length=200)
    observed_target: str = Field(default="", max_length=500)
    target_marker_artifact_id: str | None = None
    requires_explicit_authorization: bool = True
    status: Literal["pending", "authorized", "running", "executed", "blocked", "failed", "interrupted"] = "pending"
    context_version: int = 1
    run_id: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    error: str = ""
    outcome: Literal["state_changed", "no_observed_change", "read", "observation_incomplete"] | None = None

    def validate_target(self) -> "Action":
        if self.kind == "click" and not self.selector and (self.x is None or self.y is None):
            raise ValueError("A click requires a selector or both normalized x/y coordinates.")
        if self.kind == "fill" and not self.selector:
            raise ValueError("A fill requires an observed control selector.")
        if self.kind == "scroll" and not (self.scroll_x or self.scroll_y):
            raise ValueError("A scroll requires a non-zero bounded scroll_x/scroll_y.")
        if self.kind == "inspect_node" and not re.fullmatch(r"\d+:\d+", self.node_id):
            raise ValueError("inspect_node requires a valid node_id.")
        if self.kind == "navigate":
            parsed = urlparse(self.url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("navigate requires an HTTP(S) URL without credentials.")
        return self


class CheckItem(Contract):
    check_id: str
    ref: str
    kind: Literal["rule", "method", "goal", "conflict"]
    run_id: str
    context_version: int
    criteria_version: str
    execution_status: Execution = "planned"
    decision: Decision | None = None
    reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    scope_status: Literal["included", "excluded"] = "included"
    stale: bool = False
    applicability: Literal["not_assessed", "applicable", "not_applicable", "needs_context"] = "not_assessed"
    plan_reason: str = ""
    evidence_needed: list[str] = Field(default_factory=list)
    object_refs: list[str] = Field(default_factory=list)
    constraint_refs: list[str] = Field(default_factory=list)
    plan_evidence_ids: list[str] = Field(default_factory=list)
    required_evidence_kinds: list[EvidenceKind] = Field(default_factory=list)

    @model_validator(mode="after")
    def decision_matches_kind(self) -> "CheckItem":
        allowed = {
            "rule": {"candidate_issue", "no_visible_issue", "insufficient_evidence", "not_applicable"},
            "method": {"candidate_issue", "no_visible_issue", "insufficient_evidence", "not_applicable"},
            "goal": {"met", "observed_violation", "insufficient_evidence"},
            "conflict": {"open", "no_conflict", "needs_clarification", "resolved"},
        }
        if self.decision is not None and self.decision not in allowed[self.kind]:
            raise ValueError("Decision does not match the check kind.")
        if self.execution_status != "executed" and self.decision is not None:
            raise ValueError("A check without execution cannot contain a judgment.")
        return self


class Finding(Contract):
    finding_id: str = Field(default_factory=lambda: identifier("finding"))
    kind: Literal["issue", "nonconformity", "conflict", "suggestion"]
    title: str = Field(min_length=1, max_length=200)
    check_ids: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    principle: str = Field(min_length=1, max_length=5000)
    detection: str = Field(min_length=1, max_length=5000)
    description: str = Field(min_length=1, max_length=5000)
    suggestion: str = Field(min_length=1, max_length=5000)
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    severity_reason: str = Field(min_length=1, max_length=3000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    context_version: int = 1
    run_id: str = ""
    review_status: Literal["unreviewed", "confirmed", "rejected", "needs_verification"] = "unreviewed"
    human_severity: Literal["critical", "high", "medium", "low"] | None = None
    review_reason: str = ""
    reviewer: str = "unknown"
    reviewed_at: str | None = None
    disposition: Literal["fix", "accept_risk", "defer"] | None = None
    stale: bool = False
    object_ref: str = Field(default="", max_length=1000)
    mechanism: str = Field(default="", max_length=1000)
    change_action: str = Field(default="", max_length=1000)
    location: dict[str, Any] = Field(default_factory=dict)


class Recheck(Contract):
    recheck_id: str = Field(default_factory=lambda: identifier("recheck"))
    previous_finding_id: str
    current_finding_ids: list[str] = Field(default_factory=list)
    resolution: Literal[
        "resolved", "partially_resolved", "persists", "cannot_determine",
        "not_applicable", "manually_excluded",
    ] = "cannot_determine"
    reason: str = "新版证据尚未取得，不能依据漏报推断已解决。"
    evidence_ids: list[str] = Field(default_factory=list)
    human_confirmation: Literal["unreviewed", "confirmed"] = "unreviewed"
    reviewer: str = "unknown"
    reviewed_at: str | None = None


class QuestionResolution(Contract):
    question_id: str
    reason: str = Field(min_length=1, max_length=3000)
    evidence_ids: list[str] = Field(min_length=1)


class EventInput(Contract):
    event_id: str = Field(min_length=1, max_length=160)
    expected_context_version: int = Field(ge=1)
    type: Literal[
        "reply", "change_goal", "change_scope", "add_sources", "review_finding",
        "authorize_action", "resume", "cancel", "finish", "recheck", "confirm_recheck",
        "resolve_conflict",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
    actor: str = Field(default="unknown", max_length=200)


class SessionSnapshot(Contract):
    review_mode: Literal["materials", "design", "runtime", "mixed"] = "materials"
    schema_version: Literal["session-1.0"] = "session-1.0"
    session_id: str = Field(default_factory=lambda: identifier("session"))
    run_id: str = Field(default_factory=lambda: identifier("run"))
    status: Literal[
        "created", "reading", "planning", "checking", "awaiting_input",
        "rechecking", "completed", "cancelled",
    ] = "created"
    revision: int = 0
    sequence: int = 0
    context_version: int = 1
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    request: SessionCreate
    task_summary: str = ""
    scope: str = ""
    goals: list[Constraint] = Field(default_factory=list)
    requirements: list[Constraint] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    sources: list[SourceRecord] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    page_states: list[PageState] = Field(default_factory=list)
    transitions: list[Transition] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    checks: list[CheckItem] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    screen_reviews: list[ScreenTechnicalReview] = Field(default_factory=list)
    rechecks: list[Recheck] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    run_limitations: list[str] = Field(default_factory=list)
    model_calls: list[dict[str, Any]] = Field(default_factory=list)
    report_version: int = 0
    report_completeness: Literal["complete", "partial"] = "partial"
    capability_status: dict[str, Any] = Field(default_factory=dict)
    material_understanding: MaterialUnderstanding | None = None
    understanding_context_version: int = 0
    understanding_evidence_ids: list[str] = Field(default_factory=list)
    check_plan_fingerprint: str = ""
    conflict_dispositions: list[ConflictDisposition] = Field(default_factory=list)
    active_phase: Literal["T01", "T02", "T03", "T04", "T05", "T06", "T07", "T08", "T09", "T10"] = "T01"


class AgentStep(Contract):
    task_summary: str
    scope: str = ""
    goals: list[Constraint] = Field(default_factory=list, max_length=40)
    requirements: list[Constraint] = Field(default_factory=list, max_length=100)
    assumptions: list[str] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list, max_length=3)
    action: Action | None = None
    ready_for_review: bool = True
    priority_refs: list[str] = Field(default_factory=list)
    question_resolutions: list[QuestionResolution] = Field(default_factory=list, max_length=3)


class CheckJudgment(Contract):
    check_id: str
    decision: Decision
    reason: str = Field(min_length=1, max_length=6000)
    evidence_ids: list[str] = Field(default_factory=list)


class JudgmentBatch(Contract):
    judgments: list[CheckJudgment]
    findings: list[Finding] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list, max_length=3)


class Verification(Contract):
    supported_finding_ids: list[str]
    rejected: dict[str, str] = Field(default_factory=dict)


class ScreenTechnicalIssue(Contract):
    issue_id: str = Field(default_factory=lambda: identifier("screen-issue"))
    rule_ids: list[str] = Field(min_length=1, max_length=12)
    heuristic_ids: list[str] = Field(default_factory=list, max_length=10)
    title: str = Field(min_length=1, max_length=300)
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    confidence: float = Field(default=0.5, ge=0, le=1)
    principle: str = Field(default="", max_length=3000)
    user_impact: str = Field(default="", max_length=3000)
    detection: str = Field(min_length=1, max_length=3000)
    description: str = Field(min_length=1, max_length=3000)
    suggestion: str = Field(min_length=1, max_length=3000)
    evidence_bbox: dict[str, Any] = Field(default_factory=dict)
    visible_text: str = Field(default="", max_length=1000)


class ScreenTechnicalReview(Contract):
    review_id: str = Field(default_factory=lambda: identifier("screen-review"))
    run_id: str = ""
    evidence_id: str
    source_id: str
    node_id: str = ""
    page_type: str = "unknown"
    status: Literal["completed", "partial", "failed", "skipped"] = "partial"
    summary: str = ""
    dimensions: dict[str, int] = Field(default_factory=dict)
    rule_results: list[dict[str, Any]] = Field(default_factory=list, max_length=40)
    issues: list[ScreenTechnicalIssue] = Field(default_factory=list, max_length=40)
    technical_metrics: dict[str, Any] = Field(default_factory=dict)
    ocr_artifact_id: str | None = None
    elements_artifact_id: str | None = None
    metrics_artifact_id: str | None = None
    overlay_artifact_ids: dict[str, str] = Field(default_factory=dict)
    model_call_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ActionGrounding(Contract):
    evidence_id: str
    matches_intent: bool
    observed_target: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=2000)


class RecheckBatch(Contract):
    items: list[Recheck]
