"""Cross-stage invariants for a completed review session."""

from __future__ import annotations

from typing import Any

from .session_contracts import SessionSnapshot
from .session_verification import finding_requires_action_evidence


def validate_session_invariants(
    session: SessionSnapshot,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    active_sources = {
        source.source_id for source in session.sources if source.active
    }
    valid_evidence = {
        evidence.evidence_id: evidence
        for evidence in session.evidence
        if not evidence.stale and evidence.source_id in active_sources
    }
    current_checks = {
        check.check_id: check
        for check in session.checks
        if check.run_id == session.run_id and not check.stale
    }
    object_ids = {
        item.object_id
        for evidence in valid_evidence.values()
        for item in evidence.objects
    }

    for evidence in valid_evidence.values():
        for object_item in evidence.objects:
            if object_item.source_id != evidence.source_id:
                violations.append({
                    "code": "object_source_mismatch",
                    "message": (
                        f"对象 {object_item.object_id} 的来源与承载证据不一致。"
                    ),
                    "evidence_id": evidence.evidence_id,
                })

    for check in current_checks.values():
        unknown_evidence = (
            set(check.evidence_ids) | set(check.plan_evidence_ids)
        ) - set(valid_evidence)
        if unknown_evidence:
            violations.append({
                "code": "check_evidence_missing",
                "message": (
                    f"检查 {check.check_id} 引用了失效或未知证据："
                    f"{sorted(unknown_evidence)}"
                ),
                "check_id": check.check_id,
            })
        unknown_objects = set(check.object_ids) - object_ids
        if unknown_objects:
            violations.append({
                "code": "check_object_missing",
                "message": (
                    f"检查 {check.check_id} 引用了未知规范对象："
                    f"{sorted(unknown_objects)}"
                ),
                "check_id": check.check_id,
            })

    for action in session.actions:
        if action.source_id not in active_sources:
            violations.append({
                "code": "action_source_missing",
                "message": f"动作 {action.action_id} 引用了非活动来源。",
                "action_id": action.action_id,
            })
        unknown_evidence = set(action.evidence_ids) - set(valid_evidence)
        if unknown_evidence:
            violations.append({
                "code": "action_evidence_missing",
                "message": (
                    f"动作 {action.action_id} 引用了失效证据："
                    f"{sorted(unknown_evidence)}"
                ),
                "action_id": action.action_id,
            })

    action_ids = {action.action_id for action in session.actions}
    for transition in session.transitions:
        if transition.action_id not in action_ids:
            violations.append({
                "code": "transition_action_missing",
                "message": (
                    f"状态迁移 {transition.transition_id} 缺少动作记录。"
                ),
                "transition_id": transition.transition_id,
            })
        if not set(transition.evidence_ids).issubset(valid_evidence):
            violations.append({
                "code": "transition_evidence_missing",
                "message": (
                    f"状态迁移 {transition.transition_id} 引用了失效证据。"
                ),
                "transition_id": transition.transition_id,
            })

    for finding in session.findings:
        if finding.run_id != session.run_id or finding.stale:
            continue
        if not set(finding.check_ids).issubset(current_checks):
            violations.append({
                "code": "finding_check_missing",
                "message": f"发现 {finding.finding_id} 引用了失效检查。",
                "finding_id": finding.finding_id,
            })
        if not set(finding.evidence_ids).issubset(valid_evidence):
            violations.append({
                "code": "finding_evidence_missing",
                "message": f"发现 {finding.finding_id} 引用了失效证据。",
                "finding_id": finding.finding_id,
            })
        if finding.object_id and finding.object_id not in object_ids:
            violations.append({
                "code": "finding_object_missing",
                "message": f"发现 {finding.finding_id} 引用了未知规范对象。",
                "finding_id": finding.finding_id,
            })
        if not finding.claims:
            violations.append({
                "code": "finding_claim_missing",
                "message": f"发现 {finding.finding_id} 缺少结构化 claim。",
                "finding_id": finding.finding_id,
            })
        for claim in finding.claims:
            if claim.verification_status != "supported":
                violations.append({
                    "code": "finding_claim_unsupported",
                    "message": (
                        f"发现 {finding.finding_id} 的 claim {claim.claim_id} "
                        "未通过核验。"
                    ),
                    "finding_id": finding.finding_id,
                    "claim_id": claim.claim_id,
                })
        if finding_requires_action_evidence(finding):
            action_backed = any(
                evidence.action_id
                or any(
                    evidence.evidence_id in transition.evidence_ids
                    for transition in session.transitions
                )
                for evidence in (
                    valid_evidence[eid] for eid in finding.evidence_ids
                    if eid in valid_evidence
                )
            )
            if not action_backed:
                violations.append({
                    "code": "dynamic_finding_without_action",
                    "message": (
                        f"发现 {finding.finding_id} 包含动态结论，但没有动作证据。"
                    ),
                    "finding_id": finding.finding_id,
                })

    for gap in session.required_coverage:
        if gap.get("covered"):
            continue
        violations.append({
            "code": "required_coverage_missing",
            "message": f"必需覆盖单元 {gap['coverage_id']} 尚未覆盖。",
            "coverage_id": gap["coverage_id"],
            "gap_class": gap.get("gap_class"),
        })

    return violations
