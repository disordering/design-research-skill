"""Core review pipeline and deterministic normalization."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from .contracts import (
    Decision,
    Finding,
    ImageInfo,
    ModelInfo,
    RawAuditResult,
    ReviewContext,
    ReviewReport,
    ReviewSummary,
    RuleResult,
    RuleStatus,
    Severity,
    ScreenAnalysis,
    SourceReference,
)
from .criteria import CriteriaLibrary, Criterion, heuristic_label
from .errors import EngineError
from .imaging import PreparedImage, prepare_image
from .model import ModelCallResult
from .parsing import parse_json_object
from .prompting import (
    AUDIT_SCHEMA,
    OBSERVE_SCHEMA,
    build_audit_messages,
    build_observe_messages,
    build_repair_messages,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class ReviewModel(Protocol):
    async def complete(
        self,
        messages: list[dict],
        *,
        json_mode: bool = True,
        extra_body: dict[str, Any] | None = None,
    ) -> ModelCallResult:
        ...


class ReviewEngine:
    """Screenshot -> visual understanding -> 24 criteria -> normalized findings."""

    def __init__(
        self,
        criteria: CriteriaLibrary,
        model: ReviewModel,
        *,
        provider: str,
        model_name: str,
        is_stub: bool = False,
    ) -> None:
        self.criteria = criteria
        self.model = model
        self.provider = provider
        self.model_name = model_name
        self.is_stub = is_stub

    async def review(
        self,
        image_bytes: bytes,
        *,
        context: ReviewContext | None = None,
        filename: str = "screenshot.png",
        analysis_mode: str = "two_pass",
    ) -> ReviewReport:
        if analysis_mode not in {"two_pass", "single_pass"}:
            raise EngineError(
                "invalid_analysis_mode",
                "analysis_mode must be 'two_pass' or 'single_pass'.",
                status_code=422,
            )

        started = time.perf_counter()
        context = context or ReviewContext()
        image_started = time.perf_counter()
        image = prepare_image(image_bytes, filename=filename)
        image_ms = _elapsed_ms(image_started)
        warnings: list[str] = []
        screen_analysis: ScreenAnalysis | None = None
        observe_ms = 0

        if analysis_mode == "two_pass":
            observe_started = time.perf_counter()
            try:
                screen_analysis, _ = await self._request_validated(
                    build_observe_messages(image.data_url, context),
                    ScreenAnalysis,
                    repair_contract=OBSERVE_SCHEMA,
                    label="visual observation",
                )
            except EngineError as exc:
                warnings.append(
                    f"视觉理解阶段失败，继续尝试单阶段审慎评审：{exc.message}"
                )
            observe_ms = _elapsed_ms(observe_started)

        audit_started = time.perf_counter()
        raw_audit, audit_warnings = await self._request_validated(
            build_audit_messages(image.data_url, context, screen_analysis, self.criteria),
            RawAuditResult,
            repair_contract=AUDIT_SCHEMA,
            label="criteria audit",
        )
        warnings.extend(audit_warnings)
        audit_ms = _elapsed_ms(audit_started)

        if screen_analysis is None:
            screen_analysis = raw_audit.screen_analysis or ScreenAnalysis(
                uncertainties=["视觉理解阶段未返回结构化结果。"]
            )

        findings, rule_results, normalization_warnings = self._normalize(raw_audit)
        warnings.extend(normalization_warnings)
        if self.is_stub:
            warnings.insert(
                0,
                "当前结果由离线契约 Stub 生成，不代表真实截图判断；接入视觉模型后必须重跑。",
            )

        summary = _build_summary(rule_results, findings)
        total_ms = _elapsed_ms(started)
        return ReviewReport(
            review_id=str(uuid.uuid4()),
            status="partial" if warnings else "completed",
            model=ModelInfo(
                provider=self.provider,
                model=self.model_name,
                analysis_mode=analysis_mode,  # type: ignore[arg-type]
                is_stub=self.is_stub,
            ),
            context=context,
            image=_image_info(image),
            screen_analysis=screen_analysis,
            criteria_version=self.criteria.version,
            criteria_source=self.criteria.source,
            summary=summary,
            findings=findings,
            rule_results=rule_results,
            warnings=_deduplicate(warnings),
            timings_ms={
                "image_prepare": image_ms,
                "visual_observation": observe_ms,
                "criteria_audit": audit_ms,
                "total": total_ms,
            },
        )

    async def _request_validated(
        self,
        messages: list[dict],
        schema: type[SchemaT],
        *,
        repair_contract: str,
        label: str,
        extra_body: dict[str, Any] | None = None,
    ) -> tuple[SchemaT, list[str]]:
        warnings: list[str] = []
        result = await self.model.complete(
            messages,
            json_mode=True,
            extra_body=extra_body,
        )
        raw_text = result.text
        try:
            return schema.model_validate(parse_json_object(raw_text)), warnings
        except (ValueError, ValidationError) as first_error:
            validation_error = _format_validation_error(first_error)
            warnings.append(f"{label} 首次输出未通过结构校验，已发起一次 JSON 修复。")

        repair_messages = build_repair_messages(
            raw_text,
            validation_error,
            repair_contract,
        )
        repaired = await self.model.complete(
            repair_messages,
            json_mode=True,
            extra_body=extra_body,
        )
        try:
            return schema.model_validate(parse_json_object(repaired.text)), warnings
        except (ValueError, ValidationError) as second_error:
            raise EngineError(
                "model_contract_failed",
                f"{label} did not satisfy the output contract after one repair attempt.",
                status_code=502,
                retryable=True,
                details={"validation_error": _format_validation_error(second_error)},
            ) from second_error

    def _normalize(
        self,
        raw: RawAuditResult,
    ) -> tuple[list[Finding], list[RuleResult], list[str]]:
        warnings: list[str] = []
        statuses: dict[str, RuleStatus] = {}

        for status in raw.rule_statuses:
            rule_id = status.rule_id.strip().upper()
            if rule_id not in self.criteria.by_id:
                warnings.append(f"模型返回了未知判据 {rule_id}，已忽略。")
                continue
            if rule_id in statuses:
                warnings.append(f"模型重复返回判据 {rule_id}，采用最后一条。")
            statuses[rule_id] = status.model_copy(update={"rule_id": rule_id})

        for rule_id in self.criteria.rule_ids:
            if rule_id not in statuses:
                warnings.append(f"模型漏报判据 {rule_id}，已保守记为证据不足。")
                statuses[rule_id] = _fallback_status(rule_id)

        claimed_rules: set[str] = set()
        normalized_findings: list[Finding] = []
        # Stable sorting keeps the first candidate on a confidence tie. Each rule
        # belongs to its highest-confidence finding; other rules retain their
        # own evidence instead of being merged into an unrelated candidate.
        for raw_finding in sorted(raw.findings, key=lambda item: -item.confidence):
            valid_rules: list[str] = []
            for rule_id in raw_finding.rule_ids:
                normalized_id = rule_id.strip().upper()
                criterion = self.criteria.by_id.get(normalized_id)
                if criterion is None:
                    warnings.append(f"问题引用了未知判据 {normalized_id}，已移除。")
                    continue
                if statuses[normalized_id].decision is not Decision.CANDIDATE_ISSUE:
                    warnings.append(
                        f"问题引用了非 candidate_issue 判据 {normalized_id}，已移除。"
                    )
                    continue
                if normalized_id in claimed_rules:
                    warnings.append(
                        f"判据 {normalized_id} 被多个问题重复引用，优先保留置信度较高的候选；"
                        "置信度相同时保留先出现的一条。"
                    )
                    continue
                valid_rules.append(normalized_id)

            if not valid_rules:
                continue

            criteria = [self.criteria.by_id[rule_id] for rule_id in valid_rules]
            severity = raw_finding.severity
            confidence = raw_finding.confidence
            provisional = Finding(
                id="pending",
                rule_ids=valid_rules,
                heuristics=_unique(
                    heuristic_label(criterion.heuristic) for criterion in criteria
                ),
                title=raw_finding.title,
                severity=severity,
                confidence=confidence,
                principle="；".join(
                    f"{criterion.id} {criterion.title}" for criterion in criteria
                ),
                detection=raw_finding.detection,
                description=raw_finding.description,
                suggestion=raw_finding.suggestion,
                evidence=raw_finding.evidence,
                sources=[self.criteria.source],
            )

            normalized_findings.append(provisional)
            claimed_rules.update(valid_rules)

        for rule_id, status in list(statuses.items()):
            if (
                status.decision is Decision.CANDIDATE_ISSUE
                and rule_id not in claimed_rules
            ):
                warnings.append(
                    f"判据 {rule_id} 被判为问题但缺少四段式问题，已降级为证据不足。"
                )
                statuses[rule_id] = _fallback_status(
                    rule_id,
                    reason="模型标记为问题但未提供完整证据与四段式建议。",
                )

        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
        }
        normalized_findings.sort(
            key=lambda item: (severity_order[item.severity], -item.confidence, item.title)
        )
        final_findings = [
            finding.model_copy(update={"id": f"F{index:03d}"})
            for index, finding in enumerate(normalized_findings, start=1)
        ]

        rule_results: list[RuleResult] = []
        for criterion in self.criteria.rules:
            status = statuses[criterion.id]
            reason = status.reason.strip() or _default_reason(criterion, status.decision)
            rule_results.append(
                RuleResult(
                    rule_id=criterion.id,
                    title=criterion.title,
                    heuristic=heuristic_label(criterion.heuristic),
                    decision=status.decision,
                    confidence=status.confidence,
                    reason=reason,
                )
            )
        return final_findings, rule_results, warnings


def _fallback_status(rule_id: str, *, reason: str | None = None) -> RuleStatus:
    return RuleStatus(
        rule_id=rule_id,
        decision=Decision.INSUFFICIENT_EVIDENCE,
        confidence=0.0,
        reason=reason or "模型未返回该判据的可靠结论。",
    )


def _default_reason(criterion: Criterion, decision: Decision) -> str:
    if decision is Decision.NOT_APPLICABLE:
        return criterion.abstain_if
    if decision is Decision.NO_VISIBLE_ISSUE:
        return f"截图中未发现违反“{criterion.title}”的可见证据。"
    if decision is Decision.INSUFFICIENT_EVIDENCE:
        return criterion.abstain_if
    return criterion.mark_issue_if


def _build_summary(
    rule_results: list[RuleResult],
    findings: list[Finding],
) -> ReviewSummary:
    decision_counts = {decision: 0 for decision in Decision}
    for result in rule_results:
        decision_counts[result.decision] += 1
    severity_counts = {severity: 0 for severity in Severity}
    for finding in findings:
        severity_counts[finding.severity] += 1
    return ReviewSummary(
        rules_total=len(rule_results),
        candidate_issues=decision_counts[Decision.CANDIDATE_ISSUE],
        no_visible_issue=decision_counts[Decision.NO_VISIBLE_ISSUE],
        insufficient_evidence=decision_counts[Decision.INSUFFICIENT_EVIDENCE],
        not_applicable=decision_counts[Decision.NOT_APPLICABLE],
        critical_count=severity_counts[Severity.CRITICAL],
        high_count=severity_counts[Severity.HIGH],
        medium_count=severity_counts[Severity.MEDIUM],
        low_count=severity_counts[Severity.LOW],
    )


def _image_info(image: PreparedImage) -> ImageInfo:
    return ImageInfo(
        sha256=image.sha256,
        mime_type=image.mime_type,
        width=image.width,
        height=image.height,
        original_width=image.original_width,
        original_height=image.original_height,
        resized=image.resized,
    )


def _format_validation_error(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return json.dumps(
            error.errors(include_url=False, include_context=False), ensure_ascii=False
        )
    return str(error)


def _elapsed_ms(started: float) -> int:
    return max(1, int((time.perf_counter() - started) * 1000))


def _unique(values) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
