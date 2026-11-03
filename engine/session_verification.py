"""Deterministic guards for findings before the semantic verifier sees them."""

from __future__ import annotations

import html
import json
import re
from typing import Any

from .session_contracts import Evidence, EvidenceObject, Finding, FindingClaim, SessionSnapshot


DYNAMIC_CLAIM_TERMS = (
    "点击后无响应", "点击后没有响应", "操作后无变化", "操作后未变化",
    "无法返回", "返回失败", "无法保存", "保存失败", "跳转失败",
    "实际无法", "实测无法", "未恢复", "无法恢复", "崩溃", "超时无反馈",
    "click did nothing", "no response after", "navigation failed",
    "save failed", "could not return", "did not recover",
)
READABILITY_TERMS = (
    "对比度", "可读性", "文字太小", "字号过小", "亮度不足",
    "contrast", "readability", "too small", "low contrast",
)
STRUCTURE_TERMS = (
    "截断", "溢出", "遮挡", "换行", "超出容器", "裁切",
    "truncat", "overflow", "clipp", "occlud", "wrap",
)
STATE_TERMS = (
    "选中态", "选中状态", "未高亮", "高亮不一致", "勾选状态",
    "selected state", "not highlighted", "checked state",
)


def _normalized(value: Any) -> str:
    text = html.unescape(str(value or "")).lower()
    return re.sub(r"\s+", "", text)


def _claim_text(finding: Finding) -> str:
    return " ".join([
        finding.title,
        finding.detection,
        finding.description,
    ]).lower()


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def finding_requires_action_evidence(finding: Finding) -> bool:
    dynamic_claim_types = {
        "state_change", "no_state_change", "action_result",
    }
    return (
        any(claim.claim_type in dynamic_claim_types for claim in finding.claims)
        or _contains_any(_claim_text(finding), DYNAMIC_CLAIM_TERMS)
    )


def _object_tokens(value: str) -> list[str]:
    whole = _normalized(value)
    parts = [
        _normalized(part)
        for part in re.split(r"[/\\|:;,，。()\s]+", value)
    ]
    return list(dict.fromkeys(
        token for token in [whole, *parts]
        if token and (len(token) >= 2)
    ))


def _evidence_candidates(evidence: Evidence) -> list[str]:
    candidates = [
        evidence.evidence_id,
        evidence.source_id,
        evidence.state_id or "",
        evidence.content[:12000],
    ]
    for value in evidence.locator.values():
        if isinstance(value, (str, int, float)):
            candidates.append(str(value))
        elif isinstance(value, list):
            for item in value[:300]:
                if isinstance(item, dict):
                    candidates.extend(
                        str(item.get(key) or "")
                        for key in ("selector", "label", "name", "node_id", "text", "url")
                    )
                else:
                    candidates.append(str(item))
    return candidates


def object_is_present(finding: Finding, evidence: Evidence) -> bool:
    tokens = _object_tokens(finding.object_ref)
    if not tokens:
        return False
    candidates = [_normalized(candidate) for candidate in _evidence_candidates(evidence)]
    return any(
        token in candidate or candidate in token
        for token in tokens
        for candidate in candidates
        if candidate
    )


def _evidence_objects(evidence: Evidence) -> list[EvidenceObject]:
    return list(evidence.objects)


def resolve_finding_object(
    finding: Finding,
    valid: dict[str, Evidence],
    preferred_object_ids: list[str] | None = None,
) -> EvidenceObject | None:
    support_evidence = [
        valid[evidence_id]
        for evidence_id in finding.evidence_ids
        if evidence_id in valid
    ]
    support_evidence.sort(
        key=lambda item: 0 if item.kind in {"design", "observation", "implementation"} else 1
    )
    objects = [
        item for evidence in support_evidence
        for item in _evidence_objects(evidence)
    ]
    by_id = {item.object_id: item for item in objects}
    if finding.object_id and finding.object_id in by_id:
        return by_id[finding.object_id]
    for object_id in preferred_object_ids or []:
        if object_id in by_id:
            return by_id[object_id]
    tokens = _object_tokens(finding.object_ref)
    if not tokens:
        return next(
            (
                item for evidence in support_evidence
                for item in evidence.objects
                if item.kind != "page"
            ),
            None,
        )
    matches = [
        item for evidence in support_evidence
        for item in _evidence_objects(evidence)
        if item.kind != "page"
        and any(
            token in _normalized(item.object_id)
            or token in _normalized(item.label)
            or token in _normalized(item.locator)
            or token in _normalized(evidence.evidence_id)
            for token in tokens
        )
    ]
    return matches[0] if matches else None


def claim_type_for_text(text: str) -> str:
    text = text.lower()
    if _contains_any(text, READABILITY_TERMS):
        return "readability"
    if _contains_any(text, STRUCTURE_TERMS):
        return "structure"
    if _contains_any(text, STATE_TERMS):
        return "state_visibility"
    if _contains_any(text, (
        "点击后无响应", "点击后没有响应", "操作后无变化", "操作后未变化",
        "click did nothing", "no response after",
    )):
        return "no_state_change"
    if _contains_any(text, DYNAMIC_CLAIM_TERMS):
        return "action_result"
    return "object_present"


def _derived_claim_type(finding: Finding) -> str:
    return claim_type_for_text(_claim_text(finding))


def ensure_finding_claims(
    finding: Finding, evidence_object: EvidenceObject,
) -> list[FindingClaim]:
    if finding.claims:
        return finding.claims
    finding.claims = [FindingClaim(
        claim_type=_derived_claim_type(finding),
        object_id=evidence_object.object_id,
        expected="发现所述设计条件",
        observed=_claim_text(finding)[:2000],
        evidence_ids=finding.evidence_ids,
        derived=True,
    )]
    return finding.claims


def verify_finding_claims(
    session: SessionSnapshot,
    finding: Finding,
    valid: dict[str, Evidence],
) -> tuple[bool, str]:
    objects = {
        item.object_id: item
        for evidence in valid.values()
        for item in evidence.objects
    }
    if not finding.claims:
        return False, "发现没有结构化 claim。"
    for claim in finding.claims:
        if not set(claim.evidence_ids).issubset(valid):
            claim.verification_status = "rejected"
            claim.verification_reason = "claim 引用了无效或过期证据。"
            return False, claim.verification_reason
        target = objects.get(claim.object_id)
        if target is None:
            claim.verification_status = "rejected"
            claim.verification_reason = "claim 的 object_id 不在本次有效证据对象中。"
            return False, claim.verification_reason
        support = [valid[eid] for eid in claim.evidence_ids]
        if not any(
            claim.object_id in {item.object_id for item in evidence.objects}
            for evidence in support
        ):
            claim.verification_status = "rejected"
            claim.verification_reason = "claim 引用的证据不包含目标对象。"
            return False, claim.verification_reason
        reason = ""
        if claim.claim_type in {
            "state_change", "no_state_change", "action_result",
        }:
            action_results = [
                _action_for_evidence(session, evidence)
                for evidence in support
            ]
            actions = [action for action in action_results if action is not None]
            if not actions or not any(action.status == "executed" for action in actions):
                reason = "动态 claim 没有成功执行的动作证据。"
            elif claim.claim_type == "state_change" and not any(
                action.outcome == "state_changed" for action in actions
            ):
                reason = "claim 声称状态变化，但动作结果不是 state_changed。"
            elif claim.claim_type == "no_state_change" and not any(
                action.outcome in {"no_observed_change", "observation_incomplete"}
                for action in actions
            ):
                reason = "claim 声称状态未变化，但动作记录显示发生了变化。"
        elif claim.claim_type == "readability":
            if not any(
                (
                    isinstance((evidence.analysis or {}).get("readability"), dict)
                    and (evidence.analysis or {}).get("readability")
                )
                or _has_contrast_data(evidence, claim.object_id)
                for evidence in support
            ):
                reason = "readability claim 缺少可读性指标。"
        elif claim.claim_type in {"structure", "state_visibility"}:
            if not any(_has_structural_data(evidence) for evidence in support):
                reason = "结构/状态 claim 缺少 OCR、元素或结构数据。"
        elif claim.claim_type == "requirement_match":
            kinds = {evidence.kind for evidence in support}
            if not {"requirement", "design"}.issubset(kinds):
                reason = "要求符合性 claim 必须同时包含要求与方案证据。"
        if reason:
            claim.verification_status = "rejected"
            claim.verification_reason = reason
            return False, reason
        claim.verification_status = "supported"
        claim.verification_reason = "证据对象、类型和观察结果通过程序核验。"
    return True, ""


def _has_structural_data(evidence: Evidence) -> bool:
    analysis = evidence.analysis or {}
    if int(analysis.get("element_count") or 0) > 0:
        return True
    if int(analysis.get("ocr_block_count") or 0) > 0:
        return True
    if evidence.locator.get("controls"):
        return True
    try:
        data = json.loads(evidence.content)
    except (TypeError, ValueError):
        return False
    return bool(
        isinstance(data, dict)
        and (
            data.get("visible_text")
            or data.get("inspection_targets")
            or data.get("arrow_annotations")
        )
    )


def _has_contrast_data(evidence: Evidence, object_id: str = "") -> bool:
    return any(
        (not object_id or item.object_id == object_id)
        and item.attributes.get("contrastRatio") is not None
        for item in evidence.objects
    )


def _action_for_evidence(
    session: SessionSnapshot, evidence: Evidence,
):
    actions = {action.action_id: action for action in session.actions}
    if evidence.action_id and evidence.action_id in actions:
        return actions[evidence.action_id]
    for transition in session.transitions:
        if evidence.evidence_id in transition.evidence_ids:
            return actions.get(transition.action_id)
    return None


def _action_matches_claim(action, text: str) -> tuple[bool, str]:
    if action is None or action.status != "executed":
        return False, "没有成功执行的动作记录。"
    target = f"{action.selector} {action.target_label} {action.reason}".lower()
    no_change = action.outcome in {"no_observed_change", "observation_incomplete"}
    if _contains_any(text, (
        "点击后无响应", "点击后没有响应", "操作后无变化", "操作后未变化",
        "click did nothing", "no response after",
    )) and not no_change:
        return False, "动作记录显示状态发生了变化，不能支持“无响应/无变化”的发现。"
    if _contains_any(text, ("无法返回", "返回失败", "could not return")):
        if action.kind not in {"back", "navigate"} and not _contains_any(
            target, ("返回", "back"),
        ):
            return False, "发现声称返回失败，但证据动作不是返回或导航。"
        if not no_change:
            return False, "动作记录显示返回已经产生状态变化，不能支持“无法返回”。"
    if _contains_any(text, ("无法保存", "保存失败", "save failed")):
        if not _contains_any(target, ("保存", "save", "提交", "submit")):
            return False, "发现声称保存失败，但证据动作目标不是保存或提交。"
        if not no_change:
            return False, "动作记录显示保存已产生状态变化，不能支持“保存失败”。"
    return True, ""


def verify_finding_support(
    session: SessionSnapshot,
    finding: Finding,
    valid: dict[str, Evidence],
) -> tuple[bool, str]:
    support = [valid[eid] for eid in finding.evidence_ids if eid in valid]
    assert support, "validated evidence ids are required before assertion checks"
    object_evidence = [
        evidence for evidence in support
        if evidence.kind in {"design", "observation", "implementation"}
        and object_is_present(finding, evidence)
    ]
    if not object_evidence:
        return (
            False,
            "对象标识未出现在任一方案、实现或观察证据的节点、控件、文本或状态中。",
        )

    text = _claim_text(finding)
    if finding_requires_action_evidence(finding):
        transition_evidence = {
            evidence_id
            for transition in session.transitions
            for evidence_id in transition.evidence_ids
        }
        observed = [
            evidence for evidence in object_evidence
            if evidence.action_id or evidence.evidence_id in transition_evidence
        ]
        if not observed:
            return (
                False,
                "发现声称实际点击、跳转、保存或恢复行为，但证据没有动作记录或状态迁移。",
            )
        action_results = [
            _action_matches_claim(_action_for_evidence(session, evidence), text)
            for evidence in observed
        ]
        if not any(matches for matches, _ in action_results):
            reason = next(
                (reason for _, reason in action_results if reason),
                "动作证据与发现声称的行为不一致。",
            )
            return False, reason

    if _contains_any(text, READABILITY_TERMS):
        if not any(
            (
                isinstance((evidence.analysis or {}).get("readability"), dict)
                and (evidence.analysis or {}).get("readability")
            )
            or _has_contrast_data(evidence, finding.object_id)
            for evidence in object_evidence
        ):
            return (
                False,
                "发现声称字号、对比度或可读性问题，但证据没有可复核的视觉可读性指标。",
            )

    if _contains_any(text, STRUCTURE_TERMS + STATE_TERMS):
        if not any(_has_structural_data(evidence) for evidence in object_evidence):
            return (
                False,
                "发现声称截断、溢出、遮挡或控件状态问题，但证据没有 OCR、元素或结构数据。",
            )
    return True, ""


def missing_task_state_coverage(
    session: SessionSnapshot,
) -> list[tuple[str, str]]:
    checks = [
        check for check in session.checks
        if check.run_id == session.run_id and check.scope_status == "included"
    ]
    evidence = {item.evidence_id: item for item in session.evidence if not item.stale}
    reviewed_evidence_ids = {
        review.evidence_id
        for review in session.screen_reviews
        if review.run_id == session.run_id
        and review.status in {"completed", "partial"}
    }
    missing = []
    for task in session.review_tasks:
        task_source_ids = set(task.source_ids) or {
            evidence[evidence_id].source_id
            for evidence_id in task.evidence_ids
            if evidence_id in evidence
        }
        required_states = list(dict.fromkeys(task.state_ids))
        if len(required_states) < 2:
            continue
        covered = set()
        for check in checks:
            if (
                check.task_id != task.task_id
                or check.execution_status != "executed"
            ):
                continue
            covered.update(
                evidence[evidence_id].state_id
                for evidence_id in check.evidence_ids
                if evidence_id in evidence and evidence[evidence_id].state_id
            )
        for evidence_id in reviewed_evidence_ids:
            item = evidence.get(evidence_id)
            if (
                item
                and item.source_id in task_source_ids
                and item.state_id
            ):
                covered.add(item.state_id)
        missing.extend(
            (task.task_id, state_id)
            for state_id in required_states if state_id not in covered
        )
    return missing
