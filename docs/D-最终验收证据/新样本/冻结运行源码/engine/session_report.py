"""Auditable session reports and portable evidence packages."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import zipfile
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any, Callable

from .session_contracts import SessionSnapshot
from .session_flow import build_state_graph
from .session_screen_review import _outside_screen_responsibility
from .session_verification import missing_task_state_coverage

ArtifactLoader = Callable[[str, str], tuple[Path, str]]

STAGES = {
    "T01": "接收与能力检查",
    "T02": "材料读取与证据登记",
    "T03": "任务与材料理解",
    "T04": "检查规划与适用性筛选",
    "T05": "执行、取证与逐屏技术审查",
    "T06": "逐项判断",
    "T07": "证据核验与发现归并",
    "T08": "讨论、变更与重查",
    "T09": "报告与保存",
    "T10": "修改后复审",
}

OPERATION_STAGE = {
    "understand": "T03",
    "plan_checks": "T04",
    "plan": "T05",
    "ground_action": "T05",
    "judge": "T06",
    "verify": "T07",
    "recheck": "T10",
}


def _text(value: Any) -> str:
    return escape(str(value), quote=False).replace("\r", "").replace("\n", "  \n")


def _excerpt(value: Any, limit: int = 900) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _format_counts(value: dict[str, Any]) -> str:
    return "；".join(f"{key}={count}" for key, count in sorted(value.items())) or "无"


def _screen_crop(item: dict[str, Any]) -> bool:
    locator = item.get("locator", {})
    return bool(
        item.get("analysis", {}).get("screen_crop")
        or (
            locator.get("requested_node_id")
            and locator.get("node_id")
            and locator.get("requested_node_id") != locator.get("node_id")
        )
    )


def _crop_kind(item: dict[str, Any]) -> str:
    recorded = item.get("analysis", {}).get("crop_kind")
    if recorded:
        return str(recorded)
    if not _screen_crop(item):
        return "source_capture"
    locator = item.get("locator", {})
    width = int(locator.get("screenshot_width") or 0)
    height = int(locator.get("screenshot_height") or 0)
    return "full_screen" if width >= 800 and height >= 450 else "supporting_crop"


def _model_image_eligible(item: dict[str, Any]) -> bool:
    recorded = item.get("analysis", {}).get("model_image_eligible")
    if recorded is not None:
        return bool(recorded)
    locator = item.get("locator", {})
    width = int(locator.get("screenshot_width") or 0)
    height = int(locator.get("screenshot_height") or 0)
    return bool(width >= 200 and height >= 200)


def _locator_brief(locator: dict[str, Any]) -> str:
    if not isinstance(locator, dict):
        return _excerpt(locator, 500)
    if locator.get("requested_node_id"):
        return (
            f"Figma 节点 {locator.get('node_id') or locator.get('requested_node_id')}；"
            f"可见文本 {len(locator.get('visible_text_ids', []))}；"
            f"隐藏文本 {len(locator.get('hidden_text_ids', []))}；"
            f"连线 {len(locator.get('arrow_annotations', []))}；"
            f"截图 {locator.get('screenshot_width') or '?'}×{locator.get('screenshot_height') or '?'}；"
            f"文件身份{'已验证' if locator.get('file_identity_verified') else '未由桌面 MCP 验证'}"
        )
    if "chunk_index" in locator:
        return (
            f"文档分块 {locator.get('chunk_index')}/{locator.get('chunk_count')}；"
            f"行 {locator.get('start_line')}-{locator.get('end_line')}；"
            f"字符 {locator.get('start_character')}-{locator.get('end_character')}"
        )
    if locator.get("url"):
        return f"URL {locator['url']}；状态 {locator.get('state_id') or locator.get('state') or '未知'}"
    return _excerpt(json.dumps(locator, ensure_ascii=False), 600)


def _spec_brief(spec: dict[str, Any] | None) -> str:
    if not spec:
        return ""
    if str(spec.get("id", "")).startswith("R"):
        return (
            f"{spec.get('title', '')}；适用：{_excerpt(spec.get('applies_if'), 260)}；"
            f"检查：{_excerpt(spec.get('check'), 360)}；"
            f"触发：{_excerpt(spec.get('mark_issue_if'), 360)}；"
            f"弃权：{_excerpt(spec.get('abstain_if'), 320)}"
        )
    return (
        f"{spec.get('title', '')}；对象：{_excerpt(spec.get('object'), 260)}；"
        f"适用：{_excerpt(spec.get('applies'), 300)}；"
        f"触发：{_excerpt(spec.get('mark'), 360)}；"
        f"弃权：{_excerpt(spec.get('abstain'), 320)}"
    )


def _process_io_brief(stage: str, value: dict[str, Any], *, output: bool) -> str:
    if stage == "T01":
        if output:
            caps = value.get("capabilities", {})
            return (
                f"契约 {caps.get('schema_version', '')}；方法 {caps.get('methods_version', '')}；"
                f"R={caps.get('rules', 0)}；E={caps.get('methods', 0)}"
            )
        return f"评审目的 1 条；来源 {value.get('source_count', 0)} 项"
    if stage == "T02":
        if output:
            statuses = Counter(SOURCE_STATUS_LABELS.get(v, v) for v in value.get("source_status", {}).values())
            return (
                f"证据 {value.get('evidence_count', 0)} 条；来源状态 "
                f"{_format_counts(dict(statuses))}"
            )
        return f"来源 {len(value.get('sources', []))} 项"
    if stage == "T03":
        if output:
            return (
                f"目标 {len(value.get('goals', []))}；要求 {len(value.get('requirements', []))}；"
                f"意见 {len(value.get('opinions', []))}；冲突 {len(value.get('conflicts', []))}；"
                f"未知 {len(value.get('unknowns', []))}"
            )
        return f"用于理解的材料证据 {len(value.get('evidence_ids', []))} 条"
    if stage == "T04":
        if output:
            applicability = {
                APPLICABILITY_LABELS.get(key, key): count
                for key, count in value.get("applicability", {}).items()
            }
            return (
                f"检查 {value.get('check_count', 0)} 项；"
                f"{_format_counts(applicability)}"
            )
        return (
            f"目标 {len(value.get('goal_refs', []))}；要求 {len(value.get('requirement_refs', []))}；"
            f"可用证据 {len(value.get('evidence_ids', []))}"
        )
    if stage == "T05":
        if output:
            outcomes = Counter(x.get("outcome") for x in value.get("action_outcomes", []))
            return (
                f"动作 {value.get('action_count', 0)}；状态变化 {value.get('transition_count', 0)}；"
                f"结果 {_format_counts(dict(outcomes))}"
            )
        return (
            f"交互授权 {'是' if value.get('authorized_interaction') else '否'}；"
            f"计划检查 {len(value.get('planned_check_refs', []))}"
        )
    if stage == "T06":
        return (
            _format_counts({
                DECISION_LABELS.get(key, key): count
                for key, count in value.get("decisions", {}).items()
            })
            if output else
            f"检查 {len(value.get('check_ids', []))}；计划证据 {len(value.get('evidence_ids', []))}"
        )
    if stage == "T07":
        return (
            f"通过核验 {len(value.get('verified_finding_ids', []))}；退回 {len(value.get('rejected', []))}"
            if output else f"候选发现 {value.get('candidate_finding_count', 0)}"
        )
    if stage == "T08":
        return (
            f"问题 {len(value.get('questions', []))}；业务决定 {len(value.get('conflict_dispositions', []))}"
            if output else f"上下文版本 {value.get('context_version')}"
        )
    if stage == "T09":
        return (
            f"报告 v{value.get('report_version')}；完整性 "
            f"{'完整' if value.get('report_completeness') == 'complete' else '部分'}；"
            f"状态 {'已完成' if value.get('status') == 'completed' else value.get('status')}"
            if output else f"运行 {value.get('run_id')}；检查 {value.get('check_count')}"
        )
    if stage == "T10":
        return (
            f"复审记录 {len(value.get('rechecks', []))}"
            if output else f"旧问题 {len(value.get('previous_finding_ids', []))}"
        )
    return _excerpt(json.dumps(value, ensure_ascii=False), 1000)


def _call_output_brief(call: dict[str, Any]) -> str:
    output = call.get("output")
    if not isinstance(output, dict):
        return call.get("validation_error") or "无结构化输出"
    operation = call.get("operation")
    if operation == "understand":
        return (
            f"目标 {len(output.get('goals', []))}；要求 {len(output.get('requirements', []))}；"
            f"意见 {len(output.get('opinions', []))}；冲突 {len(output.get('conflicts', []))}"
        )
    if operation == "plan_checks":
        return (
            f"计划 {len(output.get('items', []))} 项："
            f"{', '.join(item.get('ref', '') for item in output.get('items', []))}"
        )
    if operation == "plan":
        action = output.get("action") or {}
        return (
            f"ready_for_review={output.get('ready_for_review')}；"
            f"动作 {action.get('kind', '无')}"
        )
    if operation == "judge":
        decisions = {item.get("decision") for item in output.get("judgments", [])}
        return (
            f"判断 {len(output.get('judgments', []))}；发现 {len(output.get('findings', []))}；"
            f"状态 {', '.join(sorted(x for x in decisions if x))}"
        )
    if operation == "verify":
        return (
            f"支持 {len(output.get('supported_finding_ids', []))}；"
            f"拒绝 {len(output.get('rejected', {}))}"
        )
    if operation == "recheck":
        return f"复审 {len(output.get('items', []))} 项"
    return _excerpt(json.dumps(output, ensure_ascii=False), 700)


def _current_checks(session: SessionSnapshot):
    return [c for c in session.checks if c.run_id == session.run_id and not c.stale]


def _current_findings(session: SessionSnapshot):
    return [f for f in session.findings if f.run_id == session.run_id and not f.stale]


def _current_actions(session: SessionSnapshot):
    return [a for a in session.actions if a.run_id == session.run_id]


def _artifact_link(
    session: SessionSnapshot,
    artifact_id: str | None,
    *,
    base_dir: Path | None,
    artifact_loader: ArtifactLoader | None,
    artifact_links: dict[str, str] | None,
) -> str:
    if not artifact_id:
        return ""
    if artifact_links and artifact_id in artifact_links:
        return artifact_links[artifact_id]
    if base_dir and artifact_loader:
        try:
            path, _ = artifact_loader(session.session_id, artifact_id)
            return Path(os.path.relpath(path, base_dir)).as_posix()
        except Exception:
            pass
    return f"/api/review-sessions/{session.session_id}/artifacts/{artifact_id}"


def _artifact_preview(
    session: SessionSnapshot,
    artifact_id: str | None,
    *,
    artifact_loader: ArtifactLoader | None,
    fallback: str = "",
    max_size: tuple[int, int] = (640, 400),
) -> str:
    # Markdown viewers render real image files reliably; data URIs are often
    # displayed as raw text. The packaged report must point at the copied PNG.
    return fallback


def _image_preview_html(link: str, alt: str, *, width: int) -> str:
    return (
        f'<img src="{escape(link, quote=True)}" alt="{escape(alt, quote=True)}" '
        f'style="display:block;max-width:100%;width:{width}px;height:auto;'
        'margin:12px 0;border:1px solid #ddd;border-radius:4px;" loading="lazy">'
    )


def _parse_artifact(artifact_loader: ArtifactLoader | None, session_id: str, artifact_id: str | None):
    if not artifact_loader or not artifact_id:
        return None
    try:
        path, _ = artifact_loader(session_id, artifact_id)
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _hydrate_calls(session: SessionSnapshot, artifact_loader: ArtifactLoader | None = None) -> list[dict[str, Any]]:
    by_id = {check.check_id: check for check in session.checks}
    result = []
    for index, source in enumerate(session.model_calls, start=1):
        output = source.get("output")
        if output is None:
            output = _parse_artifact(artifact_loader, session.session_id, source.get("raw_artifact_id"))
        input_payload = source.get("input")
        if not input_payload:
            derived_check_ids = []
            derived_finding_ids = []
            derived_refs = []
            if isinstance(output, dict):
                derived_check_ids = [
                    item.get("check_id") for item in output.get("judgments", [])
                    if item.get("check_id")
                ]
                derived_finding_ids = output.get("supported_finding_ids", [])
                derived_refs = [
                    item.get("ref") for item in output.get("items", [])
                    if item.get("ref")
                ]
            input_payload = {
                "note": "旧版模型调用未保存原始输入；以下索引由输出和当前会话状态后补重建",
                "context_version": session.context_version,
                "evidence_ids": session.understanding_evidence_ids,
                "check_ids": derived_check_ids,
                "check_refs": derived_refs,
                "finding_ids": derived_finding_ids,
            }
        check_ids: list[str] = []
        if isinstance(output, dict):
            check_ids.extend(
                item["check_id"] for item in output.get("judgments", [])
                if isinstance(item, dict) and item.get("check_id")
            )
        check_ids.extend(source.get("check_ids", []))
        check_ids = list(dict.fromkeys(check_ids))
        check_refs = list(dict.fromkeys(
            [*(source.get("check_refs") or []), *(by_id[cid].ref for cid in check_ids if cid in by_id)]
        ))
        call = {
            "call_index": index,
            "call_id": source.get("call_id") or f"MC-{index:03d}",
            "run_id": source.get("run_id"),
            "stage": source.get("stage") or OPERATION_STAGE.get(source.get("operation"), "T05"),
            "operation": source.get("operation"),
            "provider": source.get("provider"),
            "model": source.get("model"),
            "attempt": source.get("attempt"),
            "status": source.get("status", "completed"),
            "is_stub": source.get("is_stub", False),
            "latency_ms": source.get("latency_ms"),
            "usage": source.get("usage", {}),
            "raw_artifact_id": source.get("raw_artifact_id"),
            "request_id": source.get("request_id"),
            "input": input_payload,
            "input_source": "recorded" if source.get("input") else "reconstructed_from_output_and_current_state",
            "output": output,
            "check_ids": check_ids,
            "check_refs": check_refs,
            "validation_error": source.get("validation_error", ""),
            "run_scope": "current" if source.get("run_id") == session.run_id else "history",
        }
        result.append(call)
    return result


def _source_payload(session: SessionSnapshot) -> list[dict[str, Any]]:
    friendly = {
        "initial_purpose": "评审委托",
        "design_purpose": "设计目的",
        "target_user": "目标用户",
        "change_goal": "变更后的评审目标",
        "change_scope": "变更后的评审范围",
    }
    result = []
    for source in session.sources:
        evidence = [
            e for e in session.evidence
            if e.source_id == source.source_id and not e.stale
        ]
        result.append({
            "source_id": source.source_id,
            "kind": source.input.kind,
            "title": source.input.title,
            "display_title": friendly.get(
                source.input.reference.removeprefix("user://"),
                source.input.title or source.input.reference,
            ),
            "reference": source.input.reference,
            "role": source.input.role,
            "declared_by": source.input.declared_by,
            "declared_version": source.input.version,
            "observed_version": source.observed_version,
            "acquisition_status": source.acquisition_status,
            "error": source.error,
            "active": source.active,
            "evidence_ids": [e.evidence_id for e in evidence],
            "root_evidence_id": evidence[0].evidence_id if evidence else None,
            "root_artifact_id": evidence[0].artifact_id if evidence else None,
        })
    return result


def _evidence_payload(session: SessionSnapshot) -> list[dict[str, Any]]:
    checks = _current_checks(session)
    findings = _current_findings(session)
    actions = _current_actions(session)
    result = []
    for evidence in session.evidence:
        analysis = dict(evidence.analysis or {})
        if evidence.analysis_artifact_id:
            analysis.setdefault(
                "analysis_source",
                "capture" if analysis.get("geometry_available") else "backfill_global_only",
            )
        result.append({
            **evidence.model_dump(mode="json"),
            "analysis": analysis,
            "used_by_checks": [c.ref for c in checks if evidence.evidence_id in {
                *c.evidence_ids, *c.plan_evidence_ids,
            }],
            "used_by_findings": [f.finding_id for f in findings if evidence.evidence_id in f.evidence_ids],
            "used_by_actions": [a.action_id for a in actions if evidence.evidence_id in a.evidence_ids],
            "summary": _excerpt(evidence.content, 1200),
        })
    return result


def _check_payload(session: SessionSnapshot, registry=None) -> list[dict[str, Any]]:
    evidence_by_id = {e.evidence_id: e for e in session.evidence}
    findings = _current_findings(session)
    constraints = {c.id: c for c in [*session.goals, *session.requirements]}
    result = []
    for check in _current_checks(session):
        spec = None
        if registry is not None:
            try:
                spec = registry.spec(check.ref)
            except Exception:
                spec = None
        evidence_ids = list(dict.fromkeys([
            *check.plan_evidence_ids, *check.evidence_ids,
            *(eid for finding in findings if check.check_id in finding.check_ids for eid in finding.evidence_ids),
        ]))
        result.append({
            **check.model_dump(mode="json"),
            "title": (
                constraints[check.ref].text if check.ref in constraints
                else (spec or {}).get("title", check.ref)
            ),
            "spec": spec,
            "finding_ids": [f.finding_id for f in findings if check.check_id in f.check_ids],
            "evidence_chain": [
                {
                    "evidence_id": eid,
                    "source_id": evidence_by_id[eid].source_id,
                    "kind": evidence_by_id[eid].kind,
                    "version": evidence_by_id[eid].source_version,
                    "locator": evidence_by_id[eid].locator,
                    "excerpt": _excerpt(evidence_by_id[eid].content, 1500),
                    "artifact_id": evidence_by_id[eid].artifact_id,
                    "raw_artifact_id": evidence_by_id[eid].raw_artifact_id,
                    "original_artifact_id": evidence_by_id[eid].original_artifact_id,
                }
                for eid in evidence_ids if eid in evidence_by_id
            ],
        })
    return result


def _finding_payload(session: SessionSnapshot, calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence_by_id = {e.evidence_id: e for e in session.evidence}
    checks = {c.check_id: c for c in _current_checks(session)}
    result = []
    for finding in _current_findings(session):
        verify_calls = [
            c["call_id"] for c in calls
            if c["operation"] == "verify" and isinstance(c.get("output"), dict)
            and finding.finding_id in c["output"].get("supported_finding_ids", [])
        ]
        result.append({
            **finding.model_dump(mode="json"),
            "check_refs": [checks[cid].ref for cid in finding.check_ids if cid in checks],
            "verify_call_ids": verify_calls,
            "evidence_chain": [
                {
                    "evidence_id": eid,
                    "source_id": evidence_by_id[eid].source_id,
                    "kind": evidence_by_id[eid].kind,
                    "version": evidence_by_id[eid].source_version,
                    "locator": evidence_by_id[eid].locator,
                    "excerpt": _excerpt(evidence_by_id[eid].content, 1800),
                    "artifact_id": evidence_by_id[eid].artifact_id,
                }
                for eid in finding.evidence_ids if eid in evidence_by_id
            ],
        })
    return result


def _material_understanding_payload(session: SessionSnapshot) -> dict[str, Any] | None:
    if not session.material_understanding:
        return None
    data = session.material_understanding.model_dump(mode="json")
    evidence = {e.evidence_id: e for e in session.evidence if not e.stale}
    source_roles = {s.source_id: s.input.role for s in session.sources if s.active}
    opinions = []
    excluded = []
    for opinion in data.get("opinions", []):
        roles = {
            source_roles.get(evidence[item["evidence_id"]].source_id)
            for item in opinion.get("source_quotes", [])
            if item.get("evidence_id") in evidence
        }
        if roles.intersection({"expert_opinion", "user_statement"}):
            opinions.append(opinion)
        else:
            excluded.append(opinion)
    data["opinions"] = opinions
    data["excluded_workflow_items"] = excluded
    return data


def _process_steps(session: SessionSnapshot, calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks = _current_checks(session)
    findings = _current_findings(session)
    actions = _current_actions(session)
    evidence = [e for e in session.evidence if not e.stale]
    current_calls = [c for c in calls if c["run_id"] == session.run_id]
    by_operation: dict[str, list[dict[str, Any]]] = {}
    for call in current_calls:
        by_operation.setdefault(call["operation"], []).append(call)

    def ids(stage: str) -> list[str]:
        return [c["call_id"] for c in current_calls if c["stage"] == stage]

    plans = {
        "applicable": sum(c.applicability == "applicable" for c in checks),
        "needs_context": sum(c.applicability == "needs_context" for c in checks),
        "not_applicable": sum(c.applicability == "not_applicable" for c in checks),
        "not_assessed": sum(c.applicability == "not_assessed" for c in checks),
    }
    decisions = Counter(c.decision for c in checks if c.decision)
    stages = [
        {
            "stage": "T01", "title": STAGES["T01"], "status": "completed",
            "input": {"purpose": session.request.purpose, "source_count": len(session.sources)},
            "output": {"session_id": session.session_id, "capabilities": session.capability_status},
            "model_call_ids": [], "evidence_ids": [],
        },
        {
            "stage": "T02", "title": STAGES["T02"],
            "status": "partial" if any(s.acquisition_status in {"failed", "blocked", "partial"} for s in session.sources) else "completed",
            "input": {"sources": [
                {"source_id": s.source_id, "kind": s.input.kind, "reference": s.input.reference,
                 "role": s.input.role, "version": s.input.version}
                for s in session.sources
            ]},
            "output": {
                "evidence_count": len(evidence),
                "evidence_ids": [e.evidence_id for e in evidence],
                "source_status": {s.source_id: s.acquisition_status for s in session.sources},
                "warnings": session.run_limitations,
            },
            "model_call_ids": [], "evidence_ids": [e.evidence_id for e in evidence],
        },
        {
            "stage": "T03", "title": STAGES["T03"],
            "status": "completed" if session.material_understanding else "failed",
            "input": {"evidence_ids": session.understanding_evidence_ids,
                      "context_version": session.understanding_context_version},
            "output": _material_understanding_payload(session) or {},
            "model_call_ids": ids("T03"),
            "evidence_ids": session.understanding_evidence_ids,
        },
        {
            "stage": "T04", "title": STAGES["T04"],
            "status": "completed" if checks and all(c.applicability != "not_assessed" for c in checks) else "partial",
            "input": {"goal_refs": [g.id for g in session.goals],
                      "requirement_refs": [r.id for r in session.requirements],
                      "evidence_ids": [e.evidence_id for e in evidence]},
            "output": {"check_count": len(checks), "applicability": plans,
                       "check_refs": [c.ref for c in checks]},
            "model_call_ids": ids("T04"), "evidence_ids": [e.evidence_id for e in evidence],
        },
        {
            "stage": "T05", "title": STAGES["T05"],
            "status": "not_needed" if not actions and not ids("T05") else (
                "partial" if any(a.status != "executed" for a in actions) else "completed"
            ),
            "input": {"authorized_interaction": session.request.allow_interaction,
                      "planned_check_refs": [c.ref for c in checks]},
            "output": {"action_count": len(actions), "actions": [a.model_dump(mode="json") for a in actions],
                       "action_outcomes": [
                           {
                               "action_id": action.action_id,
                               "outcome": {
                                   "state_changed": "观察到状态变化",
                                   "no_observed_change": "未观察到状态变化",
                                   "read": "读取/观察",
                                   "observation_incomplete": "结果画面受限，未验证变化",
                               }.get(action.outcome, "尚无可靠结果"),
                           }
                           for action in actions
                       ],
                       "transition_count": len(session.transitions)},
            "model_call_ids": ids("T05"),
            "evidence_ids": list(dict.fromkeys(eid for a in actions for eid in a.evidence_ids)),
        },
        {
            "stage": "T06", "title": STAGES["T06"],
            "status": "completed" if checks and all(c.execution_status == "executed" for c in checks) else "partial",
            "input": {"check_ids": [c.check_id for c in checks],
                      "evidence_ids": list(dict.fromkeys(eid for c in checks for eid in c.plan_evidence_ids))},
            "output": {"decisions": dict(decisions),
                       "judgments": [{"check_id": c.check_id, "ref": c.ref, "decision": c.decision,
                                      "reason": c.reason, "evidence_ids": c.evidence_ids}
                                     for c in checks]},
            "model_call_ids": ids("T06"),
            "evidence_ids": list(dict.fromkeys(eid for c in checks for eid in c.evidence_ids)),
        },
        {
            "stage": "T07", "title": STAGES["T07"],
            "status": "not_needed" if not findings else "completed",
            "input": {"candidate_finding_count": len(findings)},
            "output": {"verified_finding_ids": [f.finding_id for f in findings],
                       "rejected": [w for w in session.warnings if "未支持" in w or "退回补证" in w]},
            "model_call_ids": ids("T07"),
            "evidence_ids": list(dict.fromkeys(eid for f in findings for eid in f.evidence_ids)),
        },
        {
            "stage": "T08", "title": STAGES["T08"],
            "status": "waiting" if any(q.blocking and not q.answered for q in session.questions) else (
                "completed" if session.questions or session.conflict_dispositions else "not_needed"
            ),
            "input": {"context_version": session.context_version, "events": [
                m for m in session.messages
                if (m.get("type") == "purpose" or m.get("run_id") == session.run_id)
                and m.get("type") in {
                    "purpose", "run_started", "run_finished", "finding_binding_rejected",
                }
            ]},
            "output": {"questions": [q.model_dump(mode="json") for q in session.questions],
                       "conflict_dispositions": [d.model_dump(mode="json") for d in session.conflict_dispositions]},
            "model_call_ids": [], "evidence_ids": [],
        },
        {
            "stage": "T09", "title": STAGES["T09"], "status": "completed",
            "input": {"run_id": session.run_id, "check_count": len(checks)},
            "output": {"report_version": session.report_version,
                       "report_completeness": session.report_completeness,
                       "status": session.status},
            "model_call_ids": [], "evidence_ids": [],
        },
        {
            "stage": "T10", "title": STAGES["T10"],
            "status": "not_needed" if not session.rechecks else "completed",
            "input": {"previous_finding_ids": [r.previous_finding_id for r in session.rechecks]},
            "output": {"rechecks": [r.model_dump(mode="json") for r in session.rechecks]},
            "model_call_ids": ids("T10"),
            "evidence_ids": list(dict.fromkeys(eid for r in session.rechecks for eid in r.evidence_ids)),
        },
    ]
    for step in stages:
        step["model_time_ms"] = sum(
            call.get("latency_ms") or 0 for call in current_calls
            if call["stage"] == step["stage"]
        )
    return stages


def _screen_issue_cluster(issue: dict[str, Any]) -> str:
    text = " ".join([
        str(issue.get("title") or ""),
        str(issue.get("detection") or ""),
        str(issue.get("description") or ""),
    ]).lower()
    heuristics = set(issue.get("heuristic_ids") or [])
    facets = (
        ("state-visibility", ("选中", "状态", "当前", "selected", "state")),
        ("feedback-clarity", ("反馈", "响应", "提示", "结果", "feedback", "response")),
        ("navigation-location", ("导航", "返回", "页签", "当前位置", "navigation", "back")),
        ("input-validation", ("输入", "校验", "范围", "格式", "validation", "input")),
        ("error-recovery", ("错误", "失败", "异常", "恢复", "error", "recover")),
        ("visual-hierarchy", ("层级", "主操作", "突出", "权重", "hierarchy", "primary")),
        ("control-semantics", ("全选", "单选", "复选", "开关", "控件", "control", "checkbox", "radio")),
    )
    matched = [
        name for name, terms in facets
        if any(term in text for term in terms)
    ]
    if any(term in text for term in ("对比度", "不可读", "低对比", "小字")):
        matched.append("legibility")
    if not matched and heuristics:
        matched.extend(sorted(heuristics)[:2])
    if not matched:
        rules = issue.get("rule_ids") or []
        matched.extend(str(rule) for rule in rules[:2])
    return "+".join(dict.fromkeys(matched)) or "screen:" + re.sub(
        r"\s+", "", str(issue.get("title") or issue.get("issue_id")),
    )


def _systemic_screen_issues(
    reviews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    clusters: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for review in reviews:
        for issue in review.get("issues", []):
            clusters.setdefault(_screen_issue_cluster(issue), []).append((review, issue))

    result: list[dict[str, Any]] = []
    for cluster_id, entries in clusters.items():
        review, primary = max(
            entries,
            key=lambda item: (
                severity_order.get(item[1].get("severity"), 0),
                float(item[1].get("confidence") or 0),
            ),
        )
        affected = []
        seen_nodes = set()
        for item_review, issue in entries:
            node_id = str(item_review.get("node_id") or "")
            if not node_id or node_id in seen_nodes:
                continue
            seen_nodes.add(node_id)
            affected.append({
                "node_id": node_id,
                "page_type": item_review.get("page_type", ""),
                "observed_title": issue.get("title", ""),
            })
        result.append({
            **primary,
            "issue_id": f"systemic-{cluster_id}",
            "systemic_cluster": cluster_id,
            "title": (
                f"重复出现：{primary.get('title')}"
                if len(entries) > 1 else primary.get("title")
            ),
            "description": primary.get("description"),
            "suggestion": primary.get("suggestion"),
            "detection": (
                f"在 {len(entries)} 个界面观察中重复出现；代表证据：{primary.get('detection', '')}"
                if len(entries) > 1 else primary.get("detection", "")
            ),
            "heuristic_ids": list(dict.fromkeys(
                heuristic_id
                for _, issue in entries
                for heuristic_id in (issue.get("heuristic_ids") or [])
            )),
            "rule_ids": list(dict.fromkeys(
                rule_id
                for _, issue in entries
                for rule_id in (issue.get("rule_ids") or [])
            )),
            "node_id": review.get("node_id", ""),
            "page_type": review.get("page_type", ""),
            "affected_locations": affected,
            "occurrence_count": len(entries),
        })
    result.sort(
        key=lambda item: (
            -severity_order.get(item.get("severity"), 0),
            -int(item.get("occurrence_count") or 0),
            str(item.get("title") or ""),
        )
    )
    return [
        item for item in result
        if item.get("severity") in {"critical", "high", "medium"}
    ][:8]


def structured_report(
    session: SessionSnapshot, *, registry=None, artifact_loader: ArtifactLoader | None = None,
) -> dict[str, Any]:
    calls = _hydrate_calls(session, artifact_loader)
    checks = _check_payload(session, registry)
    findings = _finding_payload(session, calls)
    evidence = _evidence_payload(session)
    sources = _source_payload(session)
    current_checks = _current_checks(session)
    current_findings = _current_findings(session)
    current_screen_reviews = [
        review for review in session.screen_reviews if review.run_id == session.run_id
    ]
    screen_review_payloads = []
    for review in current_screen_reviews:
        payload = review.model_dump(mode="json")
        kept_issues = []
        excluded_titles = []
        for issue in payload.get("issues", []):
            if _outside_screen_responsibility(issue):
                excluded_titles.append(issue.get("title", "未命名候选"))
            else:
                kept_issues.append(issue)
        payload["issues"] = kept_issues
        if excluded_titles:
            payload["warnings"] = list(dict.fromkeys([
                *payload.get("warnings", []),
                (
                    "报告发布前按交互职责移出业务内容候选："
                    + "；".join(excluded_titles)
                    + "。原文仍保留在会话审计记录中。"
                ),
            ]))
        metrics = payload.get("technical_metrics", {})
        if (
            payload.get("status") == "completed"
            and int(metrics.get("ui_element_count", 0)) == 0
        ):
            payload["status"] = "partial"
            payload["warnings"] = list(dict.fromkeys([
                *payload.get("warnings", []),
                "UI 元素识别为 0；本屏只完成了 OCR、像素统计和图像规则审查。",
            ]))
        screen_review_payloads.append(payload)
    systemic_screen_issues = _systemic_screen_issues(screen_review_payloads)
    execution = Counter(c.execution_status for c in current_checks)
    decisions = Counter(c.decision for c in current_checks if c.decision)
    severity = Counter(f.severity for f in current_findings)
    models = sorted({
        f"{c.get('provider')}/{c.get('model')}" for c in session.model_calls if c.get("model")
    })
    test_fixture = bool(session.model_calls) and all(c.get("is_stub") for c in session.model_calls)
    current_calls = [c for c in calls if c["run_id"] == session.run_id]
    state_graph = session.flow_graph or build_state_graph(session)
    method_fingerprints = (
        registry.fingerprints() if registry is not None
        else session.capability_status.get("method_fingerprints", {})
    )
    return {
        "schema_version": "session-report-1.0",
        "review_id": session.session_id,
        "run_id": session.run_id,
        "status": session.status,
        "report_version": session.report_version,
        "report_completeness": session.report_completeness,
        "technical_path": {
            "version": "A 0.2-method-draft / T01-T10",
            "stages": [{"stage": key, "title": value} for key, value in STAGES.items()],
        },
        "versions": {
            "criteria": next((c.criteria_version for c in current_checks), ""),
            "criteria_source": (
                registry.criteria.source.model_dump(mode="json")
                if registry is not None else session.capability_status.get("criteria_source", {})
            ),
            "method_root": (
                str(registry.root) if registry is not None
                else session.capability_status.get("method_root", "")
            ),
            "technical_path_version": session.capability_status.get(
                "technical_path_version", "A-0.2/T01-T10",
            ),
            "method_validation": (
                registry.delivery_validation if registry is not None
                else session.capability_status.get("method_validation", {})
            ),
            "method_fingerprints": method_fingerprints,
            "session_schema": session.schema_version,
            "context": session.context_version,
            "report": session.report_version,
            "models": models,
            "verifier": session.verifier_model_status,
            "is_stub": test_fixture,
        },
        "context": {
            "purpose": session.request.purpose,
            "design_purpose": session.request.design_purpose,
            "target_user": session.request.target_user,
            "scope": session.scope,
            "task_summary": session.task_summary,
            "review_mode": session.review_mode,
            "allow_interaction": session.request.allow_interaction,
        },
        "summary": {
            "checks_total": len(current_checks),
            "execution": dict(execution),
            "decisions": dict(decisions),
            "finding_count": len(current_findings),
            "claim_count": sum(len(f.claims) for f in current_findings),
            "supported_claim_count": sum(
                claim.verification_status == "supported"
                for finding in current_findings for claim in finding.claims
            ),
            "derived_claim_count": sum(
                claim.derived
                for finding in current_findings for claim in finding.claims
            ),
            "severity": dict(severity),
            "unresolved_questions": sum(not q.answered for q in session.questions),
            "blocking_questions": sum(q.blocking and not q.answered for q in session.questions),
            "uncovered_task_state_count": len(
                missing_task_state_coverage(session)
            ),
            "required_coverage_count": len(session.required_coverage),
            "uncovered_coverage_count": sum(
                not item.get("covered") for item in session.required_coverage
            ),
            "contract_violation_count": len(session.contract_violations),
            "covered_state_count": state_graph.get("summary", {}).get(
                "covered_state_count", 0,
            ),
            "transition_count": state_graph.get("summary", {}).get(
                "transition_count", 0,
            ),
            "evidence_count": len([e for e in session.evidence if not e.stale]),
            "action_count": len(_current_actions(session)),
            "model_call_count": len([c for c in calls if c["run_id"] == session.run_id]),
            "model_latency_ms": sum(call.get("latency_ms") or 0 for call in current_calls),
            "visual_analysis_count": sum(bool(e.get("analysis_artifact_id")) for e in evidence),
            "ui_element_count": sum(int(e.get("analysis", {}).get("element_count", 0)) for e in evidence),
            "ocr_block_count": sum(int(e.get("analysis", {}).get("ocr_block_count", 0)) for e in evidence),
            "connector_count": sum(
                int(e.get("analysis", {}).get("arrow_count", 0)) for e in evidence
            ),
            "screen_crop_count": sum(
                _screen_crop(e) for e in evidence
            ),
            "full_screen_crop_count": sum(
                _crop_kind(e) == "full_screen"
                for e in evidence
            ),
            "supporting_crop_count": sum(
                _crop_kind(e) == "supporting_crop"
                for e in evidence
            ),
            "model_eligible_image_count": sum(
                bool(e.get("artifact_id"))
                and _model_image_eligible(e)
                for e in evidence
            ),
            "model_image_input_count": len({
                evidence_id
                for call in current_calls
                for evidence_id in call.get("input", {}).get("image_evidence_ids", [])
            }),
            "direct_text_node_count": sum(
                int(e.get("analysis", {}).get("visible_text_node_count", 0))
                for e in evidence
            ),
            "accessibility_node_count": sum(
                int(e.get("analysis", {}).get("accessibility_node_count", 0))
                for e in evidence
            ),
            "screen_review_count": sum(
                review["status"] == "completed" for review in screen_review_payloads
            ),
            "screen_review_partial_count": sum(
                review["status"] == "partial" for review in screen_review_payloads
            ),
            "screen_issue_count": sum(
                len(review["issues"]) for review in screen_review_payloads
            ),
            "systemic_screen_issue_count": len(systemic_screen_issues),
        },
        "sources": sources,
        "constraints": {
            "review_tasks": [task.model_dump(mode="json") for task in session.review_tasks],
            "goals": [g.model_dump(mode="json") for g in session.goals],
            "requirements": [r.model_dump(mode="json") for r in session.requirements],
            "assumptions": session.assumptions,
        },
        "required_coverage": session.required_coverage,
        "contract_violations": session.contract_violations,
        "material_understanding": _material_understanding_payload(session),
        "process": _process_steps(session, calls),
        "checks": checks,
        "rule_results": [c for c in checks if c["kind"] == "rule"],
        "goal_checks": [c for c in checks if c["kind"] in {"goal", "conflict"}],
        "findings": findings,
        "screen_reviews": screen_review_payloads,
        "systemic_screen_issues": systemic_screen_issues,
        "questions": [q.model_dump(mode="json") for q in session.questions],
        "conflicts": (
            [c.model_dump(mode="json") for c in session.material_understanding.conflicts]
            if session.material_understanding else []
        ),
        "conflict_dispositions": [d.model_dump(mode="json") for d in session.conflict_dispositions],
        "evidence": evidence,
        "model_calls": calls,
        "actions": [a.model_dump(mode="json") for a in _current_actions(session)],
        "transitions": [t.model_dump(mode="json") for t in session.transitions],
        "state_graph": state_graph,
        "rechecks": [r.model_dump(mode="json") for r in session.rechecks],
        "history": {
            "messages": session.messages,
            "warnings": list(dict.fromkeys(session.warnings)),
            "run_limitations": session.run_limitations,
        },
    }


def _md_evidence(
    session: SessionSnapshot, evidence_id: str, evidence_by_id: dict,
    *, base_dir: Path | None, artifact_loader: ArtifactLoader | None,
    artifact_links: dict[str, str] | None,
    compact: bool = False,
) -> str:
    evidence = evidence_by_id.get(evidence_id)
    if evidence is None:
        return f"- `{evidence_id}`：证据不存在或已失效"
    lines = [
        f"- `{evidence.evidence_id}` / {evidence.kind} / 来源 `{evidence.source_id}`"
        f" / 版本 {_text(evidence.source_version)}",
        f"  - 定位：{_text(_locator_brief(evidence.locator))}",
        f"  - 内容：{_text(_excerpt(evidence.content, 280 if compact else 1800))}",
    ]
    if evidence.artifact_id:
        link = _artifact_link(
            session, evidence.artifact_id, base_dir=base_dir,
            artifact_loader=artifact_loader, artifact_links=artifact_links,
        )
        lines.append(f"  - 画面：[`{evidence.artifact_id}`]({link})")
    if evidence.raw_artifact_id:
        link = _artifact_link(
            session, evidence.raw_artifact_id, base_dir=base_dir,
            artifact_loader=artifact_loader, artifact_links=artifact_links,
        )
        lines.append(f"  - 原始记录：[`{evidence.raw_artifact_id}`]({link})")
    if evidence.original_artifact_id:
        link = _artifact_link(
            session, evidence.original_artifact_id, base_dir=base_dir,
            artifact_loader=artifact_loader, artifact_links=artifact_links,
        )
        lines.append(f"  - 原始文件：[`{evidence.original_artifact_id}`]({link})")
    if evidence.analysis_artifact_id:
        link = _artifact_link(
            session, evidence.analysis_artifact_id, base_dir=base_dir,
            artifact_loader=artifact_loader, artifact_links=artifact_links,
        )
        lines.append(f"  - 视觉分析：[`{evidence.analysis_artifact_id}`]({link})")
    for name, artifact_id in evidence.overlay_artifact_ids.items():
        link = _artifact_link(
            session, artifact_id, base_dir=base_dir,
            artifact_loader=artifact_loader, artifact_links=artifact_links,
        )
        lines.append(f"  - 叠加图 {name}：[`{artifact_id}`]({link})")
    return "\n".join(lines)


def markdown_summary(session: SessionSnapshot, *, registry=None) -> str:
    report = structured_report(session, registry=registry)
    summary = report["summary"]
    findings = report["findings"]
    systemic_issues = report.get("systemic_screen_issues", [])
    groups: dict[str, dict[str, Any]] = {}
    check_refs = {item["check_id"]: item["ref"] for item in report["checks"]}
    for question in report["questions"]:
        if question["answered"]:
            continue
        group, action = _gap_group(question["text"])
        item = groups.setdefault(group, {"action": action, "refs": set(), "count": 0})
        item["count"] += 1
        item["refs"].update(check_refs.get(cid, cid) for cid in question["check_ids"])
    lines = [
        "# 交互方案评审摘要", "",
        f"- 评审方式：{MODE_LABELS.get(session.review_mode, session.review_mode)}",
        f"- 技术路径：A `0.2-method-draft`，T01–T10",
        f"- 判据版本：`{report['versions']['criteria']}`（24条 R + 8项 E）",
        f"- 计划 / 执行：{summary['checks_total']} / {summary['execution'].get('executed', 0)}",
        f"- 跨项候选发现：{summary['finding_count']}；"
        f"系统性问题：{len(systemic_issues)}；未决主题：{len(groups)}",
        "",
        "## 结论",
        "",
    ]
    if findings:
        lines.append(
            f"静态设计层面确认 {len(findings)} 条候选不符合项；"
            f"{summary['decisions'].get('insufficient_evidence', 0)} 项仍需补充动态或数值证据。"
        )
    elif systemic_issues:
        lines.append(
            f"静态设计层面形成 {len(systemic_issues)} 条系统性问题；"
            f"跨项候选发现 {len(findings)} 条，"
            f"{summary['decisions'].get('insufficient_evidence', 0)} 项仍需补充动态或运行证据。"
        )
    else:
        lines.append("当前没有通过证据核验的候选不符合项；这不等于产品无问题。")
    for issue in systemic_issues[:4]:
        lines.append(
            f"- {SEVERITY_LABELS.get(issue['severity'], issue['severity'])}："
            f"{_text(issue['title'])}"
        )
    for index, finding in enumerate(findings, start=1):
        lines.extend([
            "",
            f"### {_finding_display_id(index)} · {_text(finding['title'])}",
            "",
            f"- 严重度：{SEVERITY_LABELS.get(finding['severity'], finding['severity'])}；"
            f"状态：{REVIEW_LABELS.get(finding['review_status'], finding['review_status'])}",
            f"- 关联要求：{', '.join(finding['check_refs'])}",
            f"- 检测：{_text(_first_sentence(finding['detection']))}",
            f"- 建议：{_text(_first_sentence(finding['suggestion']))}",
        ])
    lines += [
        "",
        "## 主要缺口",
        "",
        "| 缺口 | 影响要求 | 建议补充 |",
        "| --- | --- | --- |",
    ]
    if groups:
        for name, item in groups.items():
            lines.append(
                f"| {_text(name)} | {_text(', '.join(sorted(item['refs'])) or '未关联')}"
                f" | {_text(item['action'])} |"
            )
    else:
        lines.append("| 无 | — | — |")
    lines += [
        "",
        "**边界**：本摘要只说明静态方案与明确要求的关系；持久化、跳转、提交结果、"
        "错误恢复等动态行为仍需原型或测试环境验证。",
        "",
        "完整人审报告见 `report-showcase.md`，逐步审计与全部证据见 `report-details.md`。",
        "",
    ]
    return "\n".join(lines)


def audit_report(
    session: SessionSnapshot,
    *,
    registry=None,
    artifact_loader: ArtifactLoader | None = None,
    base_dir: Path | None = None,
    artifact_links: dict[str, str] | None = None,
) -> str:
    report = structured_report(session, registry=registry, artifact_loader=artifact_loader)
    summary = report["summary"]
    evidence_by_id = {e.evidence_id: e for e in session.evidence if not e.stale}
    calls = report["model_calls"]
    current_calls = [c for c in calls if c["run_id"] == session.run_id]
    lines = [
        "# 协同交互方案评审报告", "",
        f"> 会话：`{session.session_id}`  ",
        f"> 运行：`{session.run_id}`  ",
        f"> 报告版本：`{session.report_version}`  ",
        f"> 状态 / 完整性：`{session.status}` / `{session.report_completeness}`  ",
        f"> 技术路径：`A 0.2-method-draft / T01–T10`  ",
        f"> 判据版本：`{report['versions']['criteria']}`  ",
        f"> 证据模式：`{session.review_mode}`",
        "",
        "## 一、结论摘要",
        "",
        f"本次围绕“{_text(session.request.purpose)}”执行 {summary['checks_total']} 项检查。"
        f"执行状态：{_text(_format_counts(summary['execution']))}；"
        f"判断状态：{_text(_format_counts(summary['decisions']))}。"
        "`complete` 仅表示计划项均有可追溯处置，不代表产品全部通过。",
        "",
    ]
    if not report["findings"]:
        lines.append("当前没有通过证据核验的候选发现；请结合未决项理解范围。")
    for finding in report["findings"]:
        lines.append(
            f"- `{finding['finding_id']}` **{finding['title']}**"
            f"（{finding['severity']}，{finding['review_status']}）"
        )
    lines += [
        "",
        "## 二、版本、路径与复现",
        "",
        "| 字段 | 当前值 |",
        "| --- | --- |",
        f"| 会话 / 运行 | `{session.session_id}` / `{session.run_id}` |",
        f"| 上下文 / 报告版本 | {session.context_version} / {session.report_version} |",
        f"| 会话契约 | `{session.schema_version}` |",
        f"| 判据 / 方法 | `{report['versions']['criteria']}` / A T01–T10 |",
        f"| 方法目录 | {_text(report['versions']['method_root'])} |",
        f"| 判据来源 | {_text(report['versions']['criteria_source'])} |",
        f"| 模型 | {_text('；'.join(report['versions']['models']) or '尚未调用')} |",
        f"| 是否测试夹具 | {'是' if report['versions']['is_stub'] else '否'} |",
        f"| 方法文件指纹 | `{_text(report['versions']['method_fingerprints'])}` |",
        "",
        "复现依据是本次保存的原始材料、证据、模型原始响应、检查计划与判断记录；"
        "不得用新运行结果覆盖本版本。",
        "",
        "判定口径：R/E01–E06 使用 `candidate_issue`、`no_visible_issue`、"
        "`insufficient_evidence`、`not_applicable`；G/REQ/E07 使用 `met`、"
        "`observed_violation`、`insufficient_evidence`；E08 使用 `open`、"
        "`no_conflict`、`needs_clarification`、`resolved`。`complete` 只表示计划项均有处置，"
        "不表示问题数为零或运行效果已验证。",
        "",
        "## 三、输入材料",
        "",
        "| 来源 | 类型/角色 | 版本 | 读取状态 | 证据数 | 入口 |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    source_images = []
    for source in report["sources"]:
        lines.append(
            f"| `{source['source_id']}` {_text(source['title'] or source['reference'])}"
            f" | {source['kind']} / {source['role']} | {_text(source['observed_version'] or source['declared_version'])}"
            f" | {source['acquisition_status']} | {len(source['evidence_ids'])} | {_text(source['reference'])} |"
        )
        if source["root_artifact_id"]:
            link = _artifact_link(
                session, source["root_artifact_id"], base_dir=base_dir,
                artifact_loader=artifact_loader, artifact_links=artifact_links,
            )
            source_images.append((source["title"] or source["source_id"], link))
    for title, link in source_images:
        lines += ["", _image_preview_html(link, title, width=640)]

    lines += [
        "",
        "## 四、T01–T10 逐步输入输出",
        "",
        "| 阶段 | 状态 | 输入摘要 | 输出摘要 | 模型调用 | 模型耗时 |",
        "| --- | --- | --- | --- | --- | ---: |",
    ]
    for step in report["process"]:
        input_summary = _excerpt(step["input"], 360)
        output_summary = _excerpt(step["output"], 420)
        lines.append(
            f"| {step['stage']} {step['title']} | {step['status']} | {_text(input_summary)}"
            f" | {_text(output_summary)} | {', '.join(step['model_call_ids']) or '无'}"
            f" | {step['model_time_ms']}ms |"
        )
    lines += ["", "```mermaid", "flowchart LR"]
    for step in report["process"]:
        lines.append(
            f'    {step["stage"]}["{step["stage"]} {step["title"]}<br/>{step["status"]}"]'
        )
    for left, right in zip(report["process"], report["process"][1:]):
        lines.append(f'    {left["stage"]} --> {right["stage"]}')
    lines += ["```", ""]
    for step in report["process"]:
        lines += [
            "",
            f"### {step['stage']} · {step['title']}",
            "",
            f"- 状态：`{step['status']}`",
            f"- 输入：{_text(_process_io_brief(step['stage'], step['input'], output=False))}",
            f"- 输出：{_text(_process_io_brief(step['stage'], step['output'], output=True))}",
            f"- 模型调用：{', '.join(step['model_call_ids']) or '无'}",
            f"- 模型耗时：{step['model_time_ms']}ms",
            f"- 关联证据：{', '.join(step['evidence_ids']) or '无'}",
        ]

    lines += ["", "## 五、目标要求对应与材料理解", ""]
    understanding = report.get("material_understanding")
    if understanding:
        lines.append(f"- 任务理解：{_text(understanding.get('task_summary', ''))}")
        lines.append(f"- 目标用户：{_text(understanding.get('target_user_summary') or '未明确')}")
        for goal in report["constraints"]["goals"]:
            lines.append(
                f"- `{goal['id']}` G：{_text(goal['text'])}；来源 "
                f"{', '.join(goal['evidence_ids'])}"
            )
            for quote in goal.get("source_quotes", []):
                lines.append(f"  - 原文 `{quote['evidence_id']}`：{_text(quote['quote'])}")
        for requirement in report["constraints"]["requirements"]:
            lines.append(
                f"- `{requirement['id']}` REQ：{_text(requirement['text'])}；来源 "
                f"{', '.join(requirement['evidence_ids'])}"
            )
            for quote in requirement.get("source_quotes", []):
                lines.append(f"  - 原文 `{quote['evidence_id']}`：{_text(quote['quote'])}")
        for opinion in understanding.get("opinions", []):
            lines.append(f"- 意见 `{opinion['id']}`：{_text(opinion['text'])}")
        for conflict in understanding.get("conflicts", []):
            lines.append(
                f"- 冲突 `{conflict['conflict_id']}`：{_text(conflict['topic'])}"
                f"（{conflict['status']}）"
            )
        for unknown in understanding.get("unknowns", []):
            lines.append(f"- 未知：{_text(unknown)}")
    else:
        lines.append("材料理解未完成；不得用评审委托替代产品目标或要求。")

    graph = report.get("state_graph", {})
    if graph.get("nodes"):
        lines += [
            "",
            "### 已观察状态与动作迁移",
            "",
            "| 状态 | 来源 | 定位 | 入/出 | 已接入检查 |",
            "| --- | --- | --- | ---: | --- |",
        ]
        for node in graph["nodes"]:
            lines.append(
                f"| `{node['state_id']}` | {node['source_id']} | "
                f"{_text(_locator_brief(node.get('locator', {})))} | "
                f"{node.get('incoming', 0)}/{node.get('outgoing', 0)} | "
                f"{'是' if node.get('covered') else '否'} |"
            )
        if graph.get("edges"):
            lines += [
                "",
                "| 迁移 | 动作 | 目标 | 结果 |",
                "| --- | --- | --- | --- |",
            ]
            for edge in graph["edges"]:
                lines.append(
                    f"| `{edge['from_state']}` → `{edge['to_state']}` | "
                    f"{_text(edge.get('action_kind'))} | {_text(edge.get('target_label') or '—')} | "
                    f"{_text(edge.get('outcome') or edge.get('verification_status'))} |"
                )
    if report.get("required_coverage"):
        lines += [
            "",
            "### 必需覆盖矩阵",
            "",
            "| 覆盖单元 | 任务 | 状态 | 来源 | 已覆盖 | 缺证类型 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for item in report["required_coverage"]:
            lines.append(
                f"| `{item['coverage_id']}` | {item['task_id']} | "
                f"{_text(item.get('state_id') or '任务级')} | "
                f"{_text(item.get('source_id') or '—')} | "
                f"{'是' if item.get('covered') else '否'} | "
                f"{_text(item.get('gap_class') or '—')} |"
            )

    lines += [
        "",
        "## 六、证据链总表",
        "",
        "| 证据 | 来源 / 类型 | 版本 | 定位 | 内容摘要 | 被哪些检查/发现使用 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for evidence in report["evidence"]:
        if evidence["used_by_checks"] or evidence["used_by_findings"] or evidence["used_by_actions"]:
            lines.append(
                f"| `{evidence['evidence_id']}` | {evidence['source_id']} / {evidence['kind']}"
                f" | {_text(evidence['source_version'])} | {_text(_locator_brief(evidence['locator']))}"
                f" | {_text(_excerpt(evidence['summary'], 300))}"
                f" | {_text(', '.join(evidence['used_by_checks']) or ', '.join(evidence['used_by_findings']) or ', '.join(evidence['used_by_actions']) or '仅登记')} |"
            )

    lines += [
        "",
        "## 七、逐项检查与判断",
        "",
        "| 编号 | 类型 | 适用性 | 执行 | 判断 | 证据 | 发现 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for check in report["checks"]:
        lines.append(
            f"| `{check['ref']}` {_text(check['title'])} | {check['kind']} | {check['applicability']}"
            f" | {check['execution_status']} | {check['decision'] or '—'}"
            f" | {_text(', '.join(check['evidence_ids']) or '无')}"
            f" | {_text(', '.join(check['finding_ids']) or '无')} |"
        )
    for check in report["checks"]:
        lines += [
            "",
            f"### {check['ref']} · {_text(check['title'])}",
            "",
            f"- 检查 ID / 类型：`{check['check_id']}` / {check['kind']}",
            f"- 计划：{check['applicability']}；{_text(check['plan_reason'])}",
            f"- 对象：{_text(check['object_refs'])}",
            f"- 必需证据类型：{_text(check['required_evidence_kinds'])}",
            f"- 缺项：{_text(check['evidence_needed'])}",
            f"- 执行 / 判断：{check['execution_status']} / {check['decision'] or '未判断'}",
            f"- 判断理由：{_text(check['reason'])}",
        ]
        if check.get("spec"):
            spec = check["spec"]
            lines.append(f"- 判据/方法定义：{_text(_spec_brief(spec))}")
        if check["evidence_chain"]:
            lines.append("- 证据链：")
            for evidence in check["evidence_chain"]:
                lines.append(_md_evidence(
                    session, evidence["evidence_id"], evidence_by_id,
                    base_dir=base_dir, artifact_loader=artifact_loader, artifact_links=artifact_links,
                    compact=True,
                ))
        else:
            lines.append("- 证据链：无有效证据，结论不得视为通过。")

    lines += ["", "## 八、发现与修改建议", ""]
    if not report["findings"]:
        lines.append("当前没有通过证据核验的候选发现。")
    for finding in report["findings"]:
        lines += [
            f"### `{finding['finding_id']}` {_text(finding['title'])}",
            "",
            f"- 类型 / 严重度 / 置信度：{finding['kind']} / {finding['severity']} / {finding['confidence']}",
            f"- 审核状态：{finding['review_status']}；人工等级：{finding['human_severity'] or '未调整'}",
            f"- 关联检查：{', '.join(finding['check_refs'])}",
            f"- 规范对象：{_text(finding.get('object_id') or '未关联')} / "
            f"{_text(finding.get('object_ref') or '无')}",
            f"- 原则：{_text(finding['principle'])}",
            f"- 检测：{_text(finding['detection'])}",
            f"- 描述：{_text(finding['description'])}",
            f"- 建议：{_text(finding['suggestion'])}",
            f"- 严重度理由：{_text(finding['severity_reason'])}",
            f"- 核验调用：{', '.join(finding['verify_call_ids']) or '未记录'}",
            f"- 结构化断言：{len(finding.get('claims', []))} 项",
            "- 证据链：",
        ]
        for claim in finding.get("claims", []):
            lines.append(
                f"  - `{claim['claim_id']}` {claim['claim_type']} / "
                f"{claim['verification_status']}"
                f"{' / 程序派生' if claim.get('derived') else ''}："
                f"{_text(claim.get('observed') or '')}"
                f"；{_text(claim.get('verification_reason') or '')}"
            )
        for evidence in finding["evidence_chain"]:
            lines.append(_md_evidence(
                session, evidence["evidence_id"], evidence_by_id,
                base_dir=base_dir, artifact_loader=artifact_loader, artifact_links=artifact_links,
            ))

    lines += [
        "",
        "## 九、问题、冲突与业务决定",
        "",
    ]
    if report["questions"]:
        for question in report["questions"]:
            state = "已回答" if question["answered"] else "未回答"
            lines.append(
                f"- `{question['question_id']}` [{state}] {_text(question['text'])}"
                f"；影响检查：{', '.join(question['check_ids']) or '未关联'}"
                f"；答复：{_text(question['answer'] or '无')}"
            )
    else:
        lines.append("无登记问题。")
    for conflict in report["conflicts"]:
        lines.append(
            f"- 冲突 `{conflict['conflict_id']}`：{_text(conflict['topic'])}"
            f"；声明 {conflict['claim_ids']}；状态 {conflict['status']}"
        )
    for decision in report["conflict_dispositions"]:
        lines.append(
            f"- 业务决定 `{decision['conflict_id']}`：{_text(decision['decision'])}"
            f"；决定者 {_text(decision['actor'])}；理由 {_text(decision['reason'])}"
        )

    lines += [
        "",
        "## 十、模型调用、输入与原始输出",
        "",
        "| 调用 | 阶段/操作 | 模型 | 输入索引 | 输出摘要 | 原始响应 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for call in current_calls:
        raw_link = _artifact_link(
            session, call["raw_artifact_id"], base_dir=base_dir,
            artifact_loader=artifact_loader, artifact_links=artifact_links,
        )
        lines.append(
            f"| `{call['call_id']}` | {call['stage']} / {call['operation']} | "
            f"{_text(call['provider'])}/{_text(call['model'])} | "
            f"{_text(('后补索引（原始输入未保存）：' if call['input_source'] != 'recorded' else '原始索引：') + _excerpt(call['input'], 500))} | "
            f"{_text(_call_output_brief(call))} | "
            f"[`{call['raw_artifact_id']}`]({raw_link}) |"
        )
    for call in current_calls:
        lines += [
            "",
            f"### {call['call_id']} · {call['stage']} {call['operation']}",
            "",
            f"- 状态：{call['status']}；尝试：{call['attempt']}；耗时：{call['latency_ms']}ms",
            f"- 运行范围 / 输入来源：{call['run_scope']} / {call['input_source']}",
            f"- 用量：{_text(call['usage'])}",
            f"- 输入索引：{_text(json.dumps(call['input'], ensure_ascii=False)[:5000])}",
            f"- 输出来源：{_text(_call_output_brief(call))}",
        ]
        if call["raw_artifact_id"]:
            raw_link = _artifact_link(
                session, call["raw_artifact_id"], base_dir=base_dir,
                artifact_loader=artifact_loader, artifact_links=artifact_links,
            )
            lines.append(f"- 完整原始响应：[`{call['raw_artifact_id']}`]({raw_link})")

    lines += [
        "",
        "## 十一、复审、历史与限制",
        "",
        f"- 完整性：`{session.report_completeness}`",
        f"- 当前运行限制：{_text('；'.join(session.run_limitations) or '无')}",
        f"- 会话历史警告：{_text('；'.join(dict.fromkeys(session.warnings)) or '无')}",
    ]
    if report["rechecks"]:
        for item in report["rechecks"]:
            lines.append(
                f"- 旧问题 `{item['previous_finding_id']}`：{item['resolution']}"
                f" / {item['human_confirmation']}；{_text(item['reason'])}"
            )
    else:
        lines.append("- 本轮没有登记复审项。")

    lines += [
        "",
        "## 十二、可复核文件",
        "",
        "报告包应同时包含 `report.json`、`process.json`、`checks.json`、`evidence.json`、"
        "`findings.json`、`stages/T01.json`—`stages/T10.json`、`report-showcase.md`、"
        "`report-summary.md`、`method/` 方法原文与哈希以及原始响应附件。"
        "单独打开 Markdown 时，模型原始响应和证据画面仍可通过会话 artifact 接口按 ID 读取。",
        "",
    ]
    if session.model_calls:
        lines.append(
            f"> 本报告引用模型调用 {len(current_calls)} 次；测试夹具"
            f"{'是' if report['versions']['is_stub'] else '否'}。"
        )
    return "\n".join(lines)


EXECUTION_LABELS = {
    "planned": "已计划",
    "running": "执行中",
    "executed": "已执行",
    "blocked": "受阻",
    "failed": "失败",
    "not_executed": "未执行",
}

DECISION_LABELS = {
    "met": "符合（设计层面）",
    "observed_violation": "观察到不符合",
    "insufficient_evidence": "证据不足",
    "candidate_issue": "候选问题",
    "no_visible_issue": "未发现可见问题",
    "not_applicable": "不适用",
    "open": "未决",
    "no_conflict": "未发现冲突",
    "needs_clarification": "待澄清",
    "resolved": "已解决",
}

SEVERITY_LABELS = {
    "critical": "严重",
    "high": "高",
    "medium": "中",
    "low": "低",
}

REVIEW_LABELS = {
    "unreviewed": "待人工审核",
    "confirmed": "人工已确认",
    "rejected": "人工已驳回",
    "needs_verification": "待补证",
}

ROLE_LABELS = {
    "design_brief": "设计目的",
    "product_spec": "策划/产品要求",
    "design": "交互方案",
    "implementation": "工程说明",
    "expert_opinion": "专家意见",
    "user_statement": "用户说明",
    "review_instruction": "评审委托",
    "unspecified": "未标注",
}

MODE_LABELS = {
    "materials": "材料审查",
    "design": "静态设计检查",
    "runtime": "运行检查",
    "mixed": "设计 + 运行混合检查",
}

STAGE_STATUS_LABELS = {
    "completed": "已完成",
    "partial": "部分完成",
    "failed": "失败",
    "not_needed": "无需执行",
    "waiting": "等待输入",
}

APPLICABILITY_LABELS = {
    "applicable": "适用",
    "not_applicable": "不适用",
    "needs_context": "待补上下文",
    "not_assessed": "未评估",
}

KIND_LABELS = {
    "rule": "通用判据",
    "method": "流程方法",
    "goal": "目标/要求",
    "conflict": "材料冲突",
}

EVIDENCE_KIND_LABELS = {
    "requirement": "要求原文",
    "design": "设计方案/画面",
    "implementation": "工程实现",
    "observation": "实际观察",
    "statement": "说明/意见",
}

SOURCE_STATUS_LABELS = {
    "success": "读取成功",
    "partial": "部分读取",
    "blocked": "访问受阻",
    "failed": "读取失败",
    "pending": "待读取",
}


def _first_sentence(value: str) -> str:
    text = " ".join(str(value or "").split())
    match = re.search(r"(?<=[。！？!?；;])\s*", text)
    return text[:match.start()] if match else text


def _human_evidence_excerpt(evidence: Any, limit: int = 700) -> str:
    content = str(
        evidence.get("content", "") if isinstance(evidence, dict)
        else getattr(evidence, "content", "")
    ).strip()
    try:
        data = json.loads(content)
    except ValueError:
        return _excerpt(content, limit)
    if not isinstance(data, dict):
        return _excerpt(content, limit)
    visible = [
        str(item.get("text", "")).strip()
        for item in data.get("visible_text", [])
        if isinstance(item, dict) and str(item.get("text", "")).strip()
    ]
    if visible:
        useful = [
            text for text in visible
            if text not in {"01", "02", "03"} and not re.fullmatch(r"[\d.]+", text)
        ]
        weighted = [
            text for text in useful
            if any(key in text for key in (
                "设计目的", "目标", "要求", "规则", "入口", "状态",
                "错误", "失败", "取消", "返回", "保存", "反馈",
                "权限", "限制", "成功", "完成",
            ))
        ]
        chosen = list(dict.fromkeys([*weighted[:10], *useful[:5]]))
        return _excerpt("；".join(chosen), limit)
    if data.get("node") and data.get("reading_note"):
        node = data.get("node", {})
        return (
            f"界面截图：{node.get('name', '未命名节点')} "
            f"({node.get('width', '?')}×{node.get('height', '?')})"
        )
    return _excerpt(content, limit)


def _humanize_ids(text: str, aliases: dict[str, str]) -> str:
    result = str(text or "")
    for identifier, alias in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace(identifier, alias)
    return result


def _gap_group(text: str) -> tuple[str, str]:
    normalized = text.lower()
    categories = (
        ("help-and-rules", ("帮助", "规则", "说明", "tips", "help")),
        ("input-validation", ("输入", "格式", "校验", "范围", "input", "validation")),
        ("persistence", ("记忆", "持久", "保存", "退出", "persist", "remember")),
        ("sort-and-filter", ("排序", "筛选", "过滤", "sort", "filter")),
        ("confirmation", ("确认", "二次确认", "不可逆", "confirm", "irreversible")),
        ("empty-state", ("空状态", "没有结果", "无结果", "empty")),
        ("error-recovery", ("错误", "异常", "失败", "超时", "error", "failure", "recover")),
        ("navigation", ("返回", "跳转", "入口", "路径", "back", "navigation")),
        ("feedback", ("提示", "反馈", "toast", "feedback", "result")),
        ("access-control", ("权限", "登录", "访问", "permission", "access")),
    )
    for name, terms in categories:
        if any(term in normalized for term in terms):
            return name, _first_sentence(text)
    return "other", _first_sentence(text)


def _finding_display_id(index: int) -> str:
    return f"F{index:03d}"


def _evidence_table_row(
    session: SessionSnapshot,
    evidence: Any,
    *,
    base_dir: Path | None,
    artifact_loader: ArtifactLoader | None,
    artifact_links: dict[str, str] | None,
    source_titles: dict[str, str],
    display_id: str | None = None,
) -> str:
    get = evidence.get if isinstance(evidence, dict) else lambda key, default=None: getattr(evidence, key, default)
    evidence_id = get("evidence_id")
    source_id = get("source_id")
    kind = get("kind")
    locator = get("locator", {})
    artifact_id = get("artifact_id")
    link = _artifact_link(
        session, artifact_id, base_dir=base_dir,
        artifact_loader=artifact_loader, artifact_links=artifact_links,
    )
    attachment = (
        f"[查看原图]({link})"
        if artifact_id and link else
        "—"
    )
    return (
        f"| `{display_id or evidence_id}` | {_text(source_titles.get(source_id, source_id))}"
        f" | {EVIDENCE_KIND_LABELS.get(kind, kind)} | {_text(_locator_brief(locator))}"
        f" | {_text(_human_evidence_excerpt(evidence))} |"
        f" {attachment} |"
    )


def human_report(
    session: SessionSnapshot,
    *,
    registry=None,
    artifact_loader: ArtifactLoader | None = None,
    base_dir: Path | None = None,
    artifact_links: dict[str, str] | None = None,
    audit_href: str = "report-details.md",
    stage_prefix: str = "",
) -> str:
    report = structured_report(session, registry=registry, artifact_loader=artifact_loader)
    checks = report["checks"]
    findings = report["findings"]
    source_titles = {
        item["source_id"]: (
            "本轮评审委托" if item["role"] == "review_instruction"
            else item.get("display_title") or item["title"] or item["reference"]
        )
        for item in report["sources"]
    }
    evidence_by_id = {item["evidence_id"]: item for item in report["evidence"]}
    evidence_aliases = {
        evidence_id: f"EV{index:02d}"
        for index, evidence_id in enumerate(evidence_by_id, start=1)
    }
    humanize = lambda value: _humanize_ids(str(value or ""), evidence_aliases)
    check_by_id = {item["check_id"]: item for item in checks}
    ref_by_check = {item["check_id"]: item["ref"] for item in checks}
    counts = report["summary"]
    serialized_href = (
        f"{stage_prefix}report.json" if base_dir or stage_prefix
        else f"/api/review-sessions/{session.session_id}/structured-report"
    )
    process_href = (
        f"{stage_prefix}process.json" if base_dir or stage_prefix
        else f"/api/review-sessions/{session.session_id}/structured-report"
    )
    critical_high = sum(
        item["severity"] in {"critical", "high"} for item in findings
    )
    title = "交互方案评审报告"
    design_sources = [
        item for item in report["sources"] if item["role"] == "design" and item["active"]
    ]
    if design_sources:
        title = f"{design_sources[0].get('display_title') or design_sources[0]['title'] or '交互方案'}评审报告"

    lines = [
        f"# {_text(title)}",
        "",
        f"> 评审对象：{_text('、'.join(item.get('display_title') or item['title'] or item['reference'] for item in report['sources'] if item['kind'] != 'document' or item['role'] != 'review_instruction'))}  ",
        f"> 评审方式：{MODE_LABELS.get(session.review_mode, session.review_mode)}  ",
        f"> 方法版本：A `{report['versions']['criteria']}` / T01–T10  ",
        f"> 判据来源：{_text(report['versions'].get('criteria_source', {}).get('name', '未记录'))}  ",
        f"> 方法校验：{report['versions'].get('method_validation', {}).get('checked_files', 0)} 个文件，"
        f"差异 {report['versions'].get('method_validation', {}).get('mismatches', 0)}  ",
        "> 感知链：Figma 文本节点 + 逐屏截图 + 连线几何 + 确定性视觉指标 + 视觉模型语义判断  ",
        f"> 模型：{_text('、'.join(report['versions']['models']) or '尚未调用')}  ",
        f"> 报告版本：v{session.report_version}  ",
        f"> 运行状态：计划项已执行 {counts['execution'].get('executed', 0)}/{counts['checks_total']}；"
        f"待人工审核发现 {len(findings)}  ",
        "",
        "## 一、结论摘要",
        "",
    ]
    if findings:
        finding_sentence = "；".join(
            f"{_finding_display_id(i)} {item['title']}（{SEVERITY_LABELS.get(item['severity'], item['severity'])}）"
            for i, item in enumerate(findings, start=1)
        )
        lines.append(
            f"本轮为静态设计评审，形成 **{len(findings)} 条待人工审核的候选不符合项**：{finding_sentence}。"
        )
    else:
        lines.append("本轮没有通过证据核验的候选不符合项；这不等于方案已全部通过。")
    dynamic_pending = sum(
        item["decision"] == "insufficient_evidence" for item in checks
    )
    lines += [
        f"另有 **{dynamic_pending} 项证据不足**，主要涉及运行结果、数值规则或未提供的界面状态。"
        "因此本报告可以支持“静态方案是否符合明确要求”的判断，不能证明实际系统已经按方案运行。",
        "",
        "| 本轮结果 | 数量 |",
        "| --- | ---: |",
        f"| 计划检查 | {counts['checks_total']} |",
        f"| 已执行 | {counts['execution'].get('executed', 0)} |",
        f"| 设计层面符合 | {counts['decisions'].get('met', 0)} |",
        f"| 候选问题 | {counts['decisions'].get('candidate_issue', 0)} |",
        f"| 观察到不符合（含 E07 汇总） | {counts['decisions'].get('observed_violation', 0)} |",
        f"| 证据不足 | {counts['decisions'].get('insufficient_evidence', 0)} |",
        f"| 未发现可见问题 | {counts['decisions'].get('no_visible_issue', 0)} |",
        f"| 不适用 / 待澄清 | {counts['decisions'].get('not_applicable', 0)} / {counts['decisions'].get('needs_clarification', 0)} |",
        f"| 未答问题 | {counts['unresolved_questions']} |",
        f"| 严重/高等级发现 | {critical_high} |",
        f"| 已附加视觉分析 | {counts.get('visual_analysis_count', 0)} |",
        f"| Figma 文本节点 / 完整局部界面 / 补充裁片 | "
        f"{counts.get('direct_text_node_count', 0)} / {counts.get('full_screen_crop_count', 0)}"
        f" / {counts.get('supporting_crop_count', 0)} |",
        f"| 画面证据 / 模型实际接收 | "
        f"{counts.get('visual_analysis_count', 0)} / {counts.get('model_image_input_count', 0)} |",
        f"| 已完成逐屏技术审查 / 部分完成 | "
        f"{counts.get('screen_review_count', 0)} / {counts.get('screen_review_partial_count', 0)} |",
        f"| 屏内技术候选问题 | {counts.get('screen_issue_count', 0)} |",
        f"| 结构元素 / 连线节点 | "
        f"{counts.get('ui_element_count', 0)} / {counts.get('connector_count', 0)} |",
        "",
        "**能下的结论**",
        "",
        "- 策划案中的明确规则是否在交互案中被表达，以及是否存在可定位的静态不一致。",
        "- 哪些要求缺少界面、数值或运行证据，不能据此判通过。",
        "",
        "**不能下的结论**",
        "",
        "- 不能确认持久化、跳转、提交结果、错误恢复等动态行为已经在真实环境生效。",
        "- 不能把“完整性：完整”解释成“全部通过”；它只表示本轮计划项都有可追溯处置。",
        "",
        "## 二、评审范围与材料",
        "",
        "| 材料 | 角色 | 版本 | 读取结果 | 证据数 |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for source in report["sources"]:
        lines.append(
            f"| {_text(source_titles.get(source['source_id'], source['title'] or source['reference']))} | "
            f"{ROLE_LABELS.get(source['role'], source['role'])} | "
            f"{_text(source['observed_version'] or source['declared_version'])} | "
            f"{SOURCE_STATUS_LABELS.get(source['acquisition_status'], source['acquisition_status'])}"
            f" | {len(source['evidence_ids'])} |"
        )
    lines.append("")
    for source in report["sources"]:
        artifact_id = source.get("root_artifact_id")
        if not artifact_id:
            continue
        link = _artifact_link(
            session, artifact_id, base_dir=base_dir,
            artifact_loader=artifact_loader, artifact_links=artifact_links,
        )
        preview = _artifact_preview(
            session, artifact_id, artifact_loader=artifact_loader,
            fallback=link, max_size=(640, 420),
        )
        root_evidence = evidence_by_id.get(source.get("root_evidence_id"), {})
        locator = root_evidence.get("locator", {})
        image_width = int(locator.get("screenshot_width") or 0)
        image_height = int(locator.get("screenshot_height") or 0)
        preview_width = 360 if image_height > image_width * 1.4 else 640
        lines += [
            _image_preview_html(
                preview,
                source_titles.get(source["source_id"], source["source_id"]),
                width=preview_width,
            ),
            "",
        ]

    lines += [
        "## 三、执行过程",
        "",
        "| 阶段 | 做了什么 | 主要输入 | 主要输出 | 结果 | 审计文件 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for step in report["process"]:
        stage_input = _process_io_brief(step["stage"], step["input"], output=False)
        stage_output = _process_io_brief(step["stage"], step["output"], output=True)
        stage_name = step["stage"]
        stage_file = (
            f"[stages/{stage_name}.json]({stage_prefix}stages/{stage_name}.json)"
            if base_dir or stage_prefix else "见结构化报告"
        )
        lines.append(
            f"| {stage_name} | {_text(step['title'])} | {_text(stage_input)}"
            f" | {_text(stage_output)} | {STAGE_STATUS_LABELS.get(step['status'], step['status'])}"
            f" / {step['model_time_ms']}ms | {stage_file} |"
        )
    lines += [
        "",
        "每个阶段的完整输入、输出、模型调用和原始响应见附录 `report-details.md` 与 `stages/`。",
        "",
        "## 四、目标要求对应",
        "",
        "| 编号 | 明确目标/要求 | 设计评审结果 | 结论摘要 | 证据 |",
        "| --- | --- | --- | --- | --- |",
    ]
    constraints = {**{
        item["id"]: item for item in report["constraints"]["goals"]
    }, **{
        item["id"]: item for item in report["constraints"]["requirements"]
    }}
    for item in checks:
        if item["ref"] not in constraints:
            continue
        lines.append(
            f"| `{item['ref']}` | {_text(constraints[item['ref']]['text'])}"
            f" | {DECISION_LABELS.get(item['decision'], item['decision'] or '未判断')}"
            f" | {_text(_excerpt(humanize(item['reason']), 260))}"
            f" | {_text(', '.join(evidence_aliases.get(eid, eid) for eid in item['evidence_ids']) or '无')} |"
        )

    screen_reviews = report.get("screen_reviews", [])
    systemic_issues = report.get("systemic_screen_issues", [])
    lines += [
        "", "## 五、逐屏技术审查", "",
        "每个完整局部界面单独执行 OCR、UI 元素识别、视觉统计和该屏规则审查；"
        "跨屏流程仍由后面的全局检查处理。",
        "",
    ]
    if systemic_issues:
        lines += [
            "### 系统性问题",
            "",
            "| 合并问题 | 启发式 | 严重度 | 出现范围 | 用户影响 | 建议 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for issue in systemic_issues:
            affected = "、".join(
                f"{item.get('page_type') or item.get('node_id')}"
                for item in issue.get("affected_locations", [])
            )
            lines.append(
                f"| {_text(issue.get('title'))} "
                f"| {_text(', '.join(issue.get('heuristic_ids', [])))} "
                f"| {SEVERITY_LABELS.get(issue.get('severity'), issue.get('severity'))} "
                f"| {_text(affected or issue.get('page_type') or issue.get('node_id'))} "
                f"| {_text(issue.get('user_impact') or issue.get('description'))} "
                f"| {_text(issue.get('suggestion'))} |"
            )
        lines += [""]
    if not screen_reviews:
        lines.append("本轮没有完成逐屏技术审查，不能把长流程总图当作已经逐屏检查。")
    else:
        lines += ["### 逐屏明细", ""]
    for review in screen_reviews:
        evidence = evidence_by_id.get(review["evidence_id"])
        if evidence is None:
            continue
        alias = evidence_aliases.get(review["evidence_id"], review["evidence_id"])
        link = _artifact_link(
            session, evidence.get("artifact_id"), base_dir=base_dir,
            artifact_loader=artifact_loader, artifact_links=artifact_links,
        )
        preview = _artifact_preview(
            session, evidence.get("artifact_id"), artifact_loader=artifact_loader,
            fallback=link, max_size=(760, 520),
        )
        technical = review.get("technical_metrics", {})
        readability = technical.get("readability", {})
        density = technical.get("density", {})
        dimensions = review.get("dimensions", {})
        lines += [
            f"### `{alias}` {_text(review.get('page_type') or '界面技术审查')}",
            "",
            f"- 状态：{_text(review.get('status'))}；Figma 节点："
            f"`{_text(review.get('node_id') or '—')}`；尺寸："
            f"{dimensions.get('width', '?')}×{dimensions.get('height', '?')}",
            f"- 结论：{_text(review.get('summary') or '—')}",
            f"- 元素 / 可交互 / OCR：{technical.get('ui_element_count', 0)} / "
            f"{technical.get('interactive_element_count', 0)} / {technical.get('ocr_block_count', 0)}",
            f"- 低对比文本候选 / 小字候选：{readability.get('low_contrast_count', 0)} / "
            f"{readability.get('small_text_candidate_count', 0)}",
            f"- 交互覆盖代理 / 文本覆盖代理：{density.get('interaction_coverage', '—')} / "
            f"{density.get('text_coverage', '—')}",
            "",
            _image_preview_html(
                preview, f"{alias} 界面预览",
                width=720 if dimensions.get("width", 0) >= dimensions.get("height", 0) else 440,
            ),
            "",
        ]
        if review.get("issues"):
            lines += [
                "<details>",
                f"<summary>展开本屏 {len(review['issues'])} 条原始观察</summary>",
                "",
                "| 屏内问题 | 启发式 | 规则 | 严重度 | 现象 | 用户影响 | 建议 |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
            for issue in review["issues"]:
                lines.append(
                    f"| {_text(issue.get('title'))} "
                    f"| {_text(', '.join(issue.get('heuristic_ids', [])))} "
                    f"| {_text(', '.join(issue.get('rule_ids', [])))} "
                    f"| {SEVERITY_LABELS.get(issue.get('severity'), issue.get('severity'))} "
                    f"| {_text(issue.get('detection'))} "
                    f"| {_text(issue.get('user_impact') or issue.get('description'))} "
                    f"| {_text(issue.get('suggestion'))} |"
                )
            lines += ["", "</details>", ""]
        else:
            lines += ["本屏未通过规则审查形成候选问题。", ""]
        rule_results = review.get("rule_results", [])
        if rule_results:
            lines += [
                "<details>",
                f"<summary>展开本屏 {len(rule_results)} 项规则结果</summary>",
                "",
                "| 规则 | 判断 | 理由 | 置信度 |",
                "| --- | --- | --- | ---: |",
            ]
            for result in rule_results:
                lines.append(
                    f"| `{result.get('rule_id')}` | "
                    f"{DECISION_LABELS.get(result.get('decision'), result.get('decision'))} "
                    f"| {_text(_excerpt(result.get('reason'), 360))} "
                    f"| {result.get('confidence', '—')} |"
                )
            lines += ["", "</details>", ""]
        if review.get("warnings"):
            lines += [
                "> 本屏限制：" + _text("；".join(review["warnings"])),
                "",
            ]
        lines.append(f"[查看原图]({link})")
        lines.append("")

    lines += ["", "## 六、关键发现", ""]
    if not findings:
        lines.append("当前没有通过证据核验的候选发现。")
    for index, finding in enumerate(findings, start=1):
        display_id = _finding_display_id(index)
        lines += [
            f"### {display_id} · {_text(finding['title'])}",
            "",
            f"- **严重度**：{SEVERITY_LABELS.get(finding['severity'], finding['severity'])}；"
            f"**状态**：{REVIEW_LABELS.get(finding['review_status'], finding['review_status'])}",
            f"- **关联要求**：{', '.join(finding['check_refs'])}",
            f"- **判断依据**：{_text(humanize(finding['principle']))}",
            f"- **看到的现象**：{_text(humanize(finding['detection']))}",
            f"- **为什么是问题**：{_text(humanize(finding['description']))}",
            f"- **建议动作**：{_text(humanize(finding['suggestion']))}",
            f"- **严重度理由**：{_text(humanize(finding['severity_reason']))}",
            "",
            "**证据链**",
            "",
            "| 证据 | 来源 | 类型 | 定位 | 能看出什么 | 附件 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for item in finding["evidence_chain"]:
            evidence = evidence_by_id.get(item["evidence_id"])
            if evidence is None:
                continue
            lines.append(_evidence_table_row(
                session, evidence,
                base_dir=base_dir, artifact_loader=artifact_loader,
                artifact_links=artifact_links, source_titles=source_titles,
                display_id=evidence_aliases.get(item["evidence_id"]),
            ))
        image_items = [
            evidence_by_id[item["evidence_id"]]
            for item in finding["evidence_chain"]
            if item["evidence_id"] in evidence_by_id
            and evidence_by_id[item["evidence_id"]].get("artifact_id")
        ]
        if image_items:
            def observation_priority(item: dict[str, Any]) -> tuple[int, int, int]:
                return (
                    1 if _crop_kind(item) == "full_screen" else 0,
                    1 if item.get("kind") in {"design", "observation"} else 0,
                    1 if _screen_crop(item) else 0,
                )

            image = max(image_items, key=observation_priority)
            link = _artifact_link(
                session, image["artifact_id"], base_dir=base_dir,
                artifact_loader=artifact_loader, artifact_links=artifact_links,
            )
            preview = _artifact_preview(
                session, image["artifact_id"], artifact_loader=artifact_loader,
                fallback=link, max_size=(760, 520),
            )
            alias = evidence_aliases.get(image["evidence_id"], image["evidence_id"])
            node = image.get("locator", {}).get("node_id")
            locator = image.get("locator", {})
            preview_width = (
                720 if int(locator.get("screenshot_width") or 0)
                >= int(locator.get("screenshot_height") or 0) else 440
            )
            lines += [
                "",
                _image_preview_html(
                    preview, f"{finding['title']}证据 {alias} {node or ''}",
                    width=preview_width,
                ),
                "",
                f"> 上图为与现象最接近的 "
                f"{'完整局部界面' if _crop_kind(image) == 'full_screen' else '视觉证据'} "
                f"`{alias}`（Figma 节点 `{node or '—'}`）；其他材料证据仍列在上方证据链。",
                "",
            ]

    groups: dict[str, dict[str, Any]] = {}
    for question in report["questions"]:
        if question["answered"]:
            continue
        group, action = _gap_group(question["text"])
        item = groups.setdefault(group, {"action": action, "refs": set(), "questions": []})
        item["questions"].append(question)
        item["refs"].update(ref_by_check.get(cid, cid) for cid in question["check_ids"])
    understanding = report.get("material_understanding") or {}
    lines += [
        "## 七、未决与需要补充的材料",
        "",
    ]
    if understanding.get("unknowns"):
        lines += ["### 材料理解未决", ""]
        lines.extend(f"- {_text(item)}" for item in understanding["unknowns"])
        lines.append("")
    if understanding.get("assumptions"):
        lines += ["### 当前假设", ""]
        lines.extend(f"- {_text(item)}" for item in understanding["assumptions"])
        lines.append("")
    if not groups:
        lines.append("当前没有未答问题。")
    else:
        lines += [
            "| 缺口 | 影响要求 | 需要补充什么 | 当前未决数量 |",
            "| --- | --- | --- | ---: |",
        ]
        for name, item in groups.items():
            lines.append(
                f"| {_text(name)} | {_text(', '.join(sorted(item['refs'])) or '未关联')}"
                f" | {_text(item['action'])} | {len(item['questions'])} |"
            )

    lines += [
        "",
        "## 八、证据链总表",
        "",
        "以下证据是本轮全部有效来源。详细检查项到证据的逐条对应见 `report-details.md`。",
        "",
        "| 证据 | 来源 | 类型 | 定位 | 可读内容 | 附件 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["evidence"]:
        if not item["used_by_checks"] and not item["used_by_findings"] and not item["used_by_actions"]:
            continue
        lines.append(_evidence_table_row(
            session, item, base_dir=base_dir, artifact_loader=artifact_loader,
            artifact_links=artifact_links, source_titles=source_titles,
            display_id=evidence_aliases.get(item["evidence_id"]),
        ))
    visual_items = [
        item for item in report["evidence"]
        if item.get("analysis_artifact_id")
    ]
    screen_crops = [
        item for item in visual_items
        if item.get("analysis", {}).get("screen_crop")
    ]
    arrow_rows = [
        (item, arrow)
        for item in visual_items
        for arrow in item.get("analysis", {}).get("arrow_annotations", [])
    ]
    lines += [
        "",
        "### 证据粒度",
        "",
        "| 感知对象 | 数量 | 用途与边界 |",
        "| --- | ---: | --- |",
        f"| Figma 文本节点 | {counts.get('direct_text_node_count', 0)} | "
        "直接读取节点中的可见文字，不经过 OCR 猜测；隐藏节点不计入当前画面。 |",
        f"| 完整局部界面 | {counts.get('full_screen_crop_count', 0)} | "
        "每个界面节点单独取得画面并作为独立证据，避免只凭流程总图判断小字和控件。 |",
        f"| 补充裁片 | {counts.get('supporting_crop_count', 0)} | "
        "导航条、提示条或子图示等局部材料；有分析记录，但不能单独代表完整页面状态。 |",
        f"| 模型实际接收画面 | {counts.get('model_image_input_count', 0)} | "
        f"本轮候选中可分析画面 {counts.get('visual_analysis_count', 0)} 张；"
        "低于模型图像下限的裁片只保留统计和人工查看入口。 |",
        f"| 连接线/箭头 | {counts.get('connector_count', 0)} | "
        "读取 Figma 连线节点的位置、轴向和邻近画板；连线语义需结合画面与说明确认。 |",
        f"| 视觉分析截图 | {counts.get('visual_analysis_count', 0)} | "
        "每张截图执行像素统计、元素映射、文本块度量并生成叠加图。 |",
    ]
    if screen_crops:
        lines += [
            "",
            "### 逐屏证据",
            "",
            "以下画面均来自 Figma 子节点，不是把长流程总图重复裁切后声称已逐屏阅读。",
            "",
        ]
        for item in screen_crops:
            locator = item.get("locator", {})
            evidence_id = evidence_aliases.get(item["evidence_id"], item["evidence_id"])
            link = _artifact_link(
                session, item.get("artifact_id"), base_dir=base_dir,
                artifact_loader=artifact_loader, artifact_links=artifact_links,
            )
            name = (
                locator.get("node_id")
                or locator.get("requested_node_id")
                or item["evidence_id"]
            )
            dimensions = (
                f"{locator.get('screenshot_width') or '?'}×"
                f"{locator.get('screenshot_height') or '?'}"
            )
            preview_width = (
                720 if int(locator.get("screenshot_width") or 0)
                >= int(locator.get("screenshot_height") or 0) else 440
            )
            lines += [
                f"**`{evidence_id}` · Figma 节点 `{name}` · {dimensions} · "
                f"{'完整界面' if _crop_kind(item) == 'full_screen' else '补充裁片'}**",
                "",
                _image_preview_html(
                    _artifact_preview(
                        session, item.get("artifact_id"),
                        artifact_loader=artifact_loader, fallback=link, max_size=(760, 520),
                    ),
                    f"{evidence_id} 局部界面",
                    width=preview_width,
                ),
                "",
            ]
    if arrow_rows:
        lines += [
            "### 连线标注",
            "",
            "| 证据 | 连线节点 | 画布轴向 | 邻近画板 | 当前可支持的含义 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for item, arrow in arrow_rows:
            evidence_id = evidence_aliases.get(item["evidence_id"], item["evidence_id"])
            targets = ", ".join(
                f"`{target.get('node_id')}` {target.get('name')}"
                for target in arrow.get("nearby_targets", [])
            ) or "未落在已识别画板内"
            lines.append(
                f"| `{evidence_id}` | `{_text(arrow.get('node_id', '—'))}` "
                f"{_text(arrow.get('name', ''))} | {_text(arrow.get('orientation', 'unknown'))} "
                f"| {_text(targets)} | 仅确认图上有连线及邻接关系；"
                "跳转、反馈或指向含义须结合对应画面和文字证据。 |"
            )
    lines += [
        "",
        "### 视觉测量与统计",
        "",
        "全局语义判断使用 Figma 文本节点、逐屏截图、连线和以下可复算指标；"
        "完整局部界面另有逐屏 OCR/UI 解析结果，见第五节的屏内技术审查。",
        "",
    ]
    if visual_items:
        lines += [
            "| 证据 | 计算来源 | 元素 | OCR 块 | 显著性前项 | 低对比文本 | 小字候选 | 负空间代理 | 高饱和面积 | 叠加图 |",
            "| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |",
        ]
        for item in visual_items:
            analysis = item.get("analysis", {})
            readability = analysis.get("readability", {})
            density = analysis.get("density", {})
            global_metrics = analysis.get("global", {})
            focus_top = analysis.get("focus_top", [])
            scale_limited = bool(analysis.get("measurement_scale_limited"))
            top_label = "—"
            if focus_top:
                top = focus_top[0]
                top_label = f"{top.get('element_id')} {top.get('label')} ({top.get('focus_share')})"
            overlay_links = []
            for name, artifact_id in item.get("overlay_artifact_ids", {}).items():
                overlay_links.append(
                    f"[{name}]({_artifact_link(session, artifact_id, base_dir=base_dir, artifact_loader=artifact_loader, artifact_links=artifact_links)})"
                )
            source_label = (
                "采集时计算" if analysis.get("analysis_source") == "capture"
                else "原始元数据重算"
                if analysis.get("analysis_source") == "reconstructed_from_original_metadata"
                else "旧证据补算"
            )
            lines.append(
                f"| `{evidence_aliases.get(item['evidence_id'], item['evidence_id'])}`"
                f" | {source_label}"
                f" | {analysis.get('element_count', 0)} | {analysis.get('ocr_block_count', 0)}"
                f" | {_text(top_label)} | {readability.get('low_contrast_count', 0)}"
                f"{'*' if scale_limited else ''}"
                f" | {readability.get('small_text_candidate_count', 0)}"
                f"{'*' if scale_limited else ''}"
                f" | {global_metrics.get('negative_space_proxy', '—')}"
                f" | {global_metrics.get('high_saturation_fraction', '—')}"
                f" | {' / '.join(overlay_links) or '—'} |"
            )
        if any(item.get("analysis", {}).get("measurement_scale_limited") for item in visual_items):
            lines += [
                "",
                "> `*` 表示长流程总图在截图端被整体缩小。小字数、局部低对比和元素框可用于索引，"
                "但需回到局部高分辨率画面或响应式原型才能判定可读性问题。",
            ]
        if any(not item.get("analysis", {}).get("geometry_available", False) for item in visual_items):
            lines += [
                "",
                "> 标记为“旧证据补算”的行没有可直接归一化的元素绝对坐标，只计算全局视觉指标；",
                "> “原始元数据重算”使用当时保存的 Figma MCP 原始层级恢复坐标。两者不能混为采集时结果。",
            ]
    else:
        lines.append("当前证据尚未附加确定性视觉测量。")
    lines += [
        "",
        "**证据别名对照**",
        "",
        "| 别名 | 完整证据 ID |",
        "| --- | --- |",
    ]
    for evidence_id, alias in evidence_aliases.items():
        lines.append(f"| `{alias}` | `{evidence_id}` |")

    lines += [
        "",
        "## 九、跨职能配合与业务决定",
        "",
    ]
    if not report["conflicts"] and not report["conflict_dispositions"]:
        lines.append("本轮没有可定位的正式材料冲突，也没有登记业务裁决。")
    for conflict in report["conflicts"]:
        lines.append(
            f"- {_text(conflict['topic'])}：{conflict['status']}；"
            f"涉及 {', '.join(conflict['claim_ids'])}"
        )
    for decision in report["conflict_dispositions"]:
        lines.append(
            f"- 决定者 {_text(decision['actor'])}：{_text(decision['decision'])}；"
            f"理由 {_text(decision['reason'])}"
        )

    lines += [
        "",
        "## 十、边界与验证限制",
        "",
        f"- 当前证据模式：{MODE_LABELS.get(session.review_mode, session.review_mode)}。",
        f"- 交互授权：{'允许' if session.request.allow_interaction else '未允许'}；"
        "未执行的动作不能算通过。",
        "- Figma 桌面 MCP 无法独立核验当前打开文件身份时，报告会保留该限制。",
        "- 历史运行警告与当前运行结果分开；旧失败不会改写成当前判断。",
        f"- 当前运行限制：{_text('；'.join(session.run_limitations) or '无')}。",
    ]
    all_warnings = list(dict.fromkeys(report["history"].get("warnings", [])))
    run_starts = [
        message for message in report["history"].get("messages", [])
        if message.get("type") == "run_started"
    ]
    warning_start = (
        int(run_starts[-1].get("warning_count", 0))
        if run_starts and "warning_count" in run_starts[-1]
        else 0
    )
    current_warnings = all_warnings[warning_start:]
    warning_label = (
        "当前运行警告"
        if run_starts and "warning_count" in run_starts[-1]
        else "本会话累计警告（含早期失败尝试）"
    )
    if current_warnings:
        lines += [
            f"- {warning_label}：",
            *[
                f"  - {_text(_excerpt(warning, 500))}"
                for warning in current_warnings[:12]
            ],
        ]
    lines += [
        "",
        "## 十一、逐项检查摘要",
        "",
        "<details>",
        f"<summary>展开 {len(checks)} 项计划与判断</summary>",
        "",
        "| 编号 | 类型 | 适用性 | 执行 | 判断 | 理由摘要 | 证据 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in checks:
        lines.append(
            f"| `{item['ref']}` | {KIND_LABELS.get(item['kind'], item['kind'])}"
            f" | {APPLICABILITY_LABELS.get(item['applicability'], item['applicability'])}"
            f" | {EXECUTION_LABELS.get(item['execution_status'], item['execution_status'])}"
            f" | {DECISION_LABELS.get(item['decision'], item['decision'] or '未判断')}"
            f" | {_text(_excerpt(humanize(item['reason']), 180))}"
            f" | {_text(', '.join(evidence_aliases.get(eid, eid) for eid in item['evidence_ids']) or '无')} |"
        )
    model_calls = [item for item in report["model_calls"] if item["run_scope"] == "current"]
    model_summary: dict[tuple[str, str], dict[str, Any]] = {}
    for call in model_calls:
        key = (call["stage"], call["operation"])
        item = model_summary.setdefault(key, {"count": 0, "latency": 0})
        item["count"] += 1
        item["latency"] += call.get("latency_ms") or 0
    lines += [
        "",
        "</details>",
        "",
        "## 十一、审计与原始文件",
        "",
        "| 内容 | 文件 |",
        "| --- | --- |",
        f"| 完整逐步审计报告 | [report-details.md]({audit_href}) |",
        f"| 机器可读完整报告 | [report.json]({serialized_href}) |",
        f"| 阶段输入输出 | [process.json]({process_href}) / "
        f"[stages/index.json]({stage_prefix}stages/index.json) |",
        f"| 检查与证据链 | [checks.json]({serialized_href}) / "
        f"[evidence.json]({serialized_href}) |",
        f"| 发现与核验 | [findings.json]({serialized_href}) |",
        f"| 模型原始响应 | `{stage_prefix}raw/` |",
        f"| 画面与原始文件 | `{stage_prefix}artifacts/` |",
        f"| 本轮方法原文 | `{stage_prefix}method/` |",
        f"| 文件校验 | "
        f"{f'[SHA256SUMS.txt]({stage_prefix}SHA256SUMS.txt)' if base_dir or stage_prefix else '见下载包'} |",
        "",
        "### 模型调用概览",
        "",
        "| 阶段 / 操作 | 调用次数 | 总耗时 |",
        "| --- | ---: | ---: |",
    ]
    for (stage, operation), item in sorted(model_summary.items()):
        lines.append(f"| {stage} / {operation} | {item['count']} | {item['latency']}ms |")
    lines += [
        "",
        f"> 当前运行模型调用 {len(model_calls)} 次；完整输入索引和原始响应的保存状态见 `report-details.md`。",
        "",
    ]
    return "\n".join(lines)


def markdown_report(
    session: SessionSnapshot,
    *,
    registry=None,
    artifact_loader: ArtifactLoader | None = None,
    base_dir: Path | None = None,
    artifact_links: dict[str, str] | None = None,
    audit_href: str = "report-details.md",
    stage_prefix: str = "",
) -> str:
    return human_report(
        session, registry=registry, artifact_loader=artifact_loader,
        base_dir=base_dir, artifact_links=artifact_links,
        audit_href=audit_href, stage_prefix=stage_prefix,
    )


def _copy_artifact(
    store, session: SessionSnapshot, artifact_id: str | None,
    destination: Path, prefix: str = "artifact",
) -> str | None:
    if not artifact_id:
        return None
    try:
        source, _ = store.artifact(session.session_id, artifact_id)
    except Exception:
        return None
    suffix = source.suffix or ".bin"
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f"{prefix}-{artifact_id}{suffix}"
    shutil.copy2(source, target)
    return target


def write_report_package(
    session: SessionSnapshot,
    store,
    directory: Path | str,
    *,
    registry=None,
) -> dict[str, Any]:
    directory = Path(directory)
    artifacts_dir = directory / "artifacts"
    raw_dir = directory / "raw"
    method_dir = directory / "method"
    directory.mkdir(parents=True, exist_ok=True)
    calls = _hydrate_calls(session, store.artifact)
    artifact_links: dict[str, str] = {}
    copied: dict[str, str] = {}
    for call in calls:
        path = _copy_artifact(store, session, call.get("raw_artifact_id"), raw_dir, call["call_id"])
        if path:
            relative = path.relative_to(directory).as_posix()
            artifact_links[call["raw_artifact_id"]] = relative
            copied[call["raw_artifact_id"]] = relative
    for evidence in session.evidence:
        if evidence.stale:
            continue
        for artifact_id in dict.fromkeys([
            evidence.artifact_id,
            evidence.raw_artifact_id,
            evidence.original_artifact_id,
            evidence.analysis_artifact_id,
            *evidence.overlay_artifact_ids.values(),
        ]):
            path = _copy_artifact(store, session, artifact_id, artifacts_dir, evidence.evidence_id)
            if path:
                relative = path.relative_to(directory).as_posix()
                artifact_links[artifact_id] = relative
                copied[artifact_id] = relative
    for review in session.screen_reviews:
        if review.run_id != session.run_id:
            continue
        for artifact_id in dict.fromkeys([
            review.ocr_artifact_id,
            review.elements_artifact_id,
            review.metrics_artifact_id,
            *review.overlay_artifact_ids.values(),
        ]):
            path = _copy_artifact(
                store, session, artifact_id, artifacts_dir, review.review_id,
            )
            if path:
                relative = path.relative_to(directory).as_posix()
                artifact_links[artifact_id] = relative
                copied[artifact_id] = relative
    method_files: list[str] = []
    if registry is not None:
        method_dir.mkdir(parents=True, exist_ok=True)
        for name in registry.fingerprints():
            source = registry.root / name
            target = method_dir / Path(name).name
            shutil.copy2(source, target)
            method_files.append(target.relative_to(directory).as_posix())

    structured = structured_report(session, registry=registry, artifact_loader=store.artifact)
    structured["artifacts"] = copied
    structured["method_files"] = method_files
    files: dict[str, Any] = {
        "report.json": structured,
        "process.json": structured["process"],
        "checks.json": structured["checks"],
        "evidence.json": structured["evidence"],
        "findings.json": structured["findings"],
        "screen-reviews.json": structured["screen_reviews"],
        "flow-graph.json": structured["state_graph"],
        "coverage.json": structured["required_coverage"],
        "contract-violations.json": structured["contract_violations"],
    }
    from .figma_report import build_figma_plugin_script, build_figma_report_plan

    figma_plan = build_figma_report_plan(session, registry=registry)
    files["figma-report-plan.json"] = figma_plan
    for name, payload in files.items():
        (directory / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    (directory / "figma-report-plugin.js").write_text(
        build_figma_plugin_script(figma_plan), encoding="utf-8",
    )
    stages_dir = directory / "stages"
    stages_dir.mkdir(parents=True, exist_ok=True)
    for step in structured["process"]:
        (stages_dir / f"{step['stage']}.json").write_text(
            json.dumps(step, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    (stages_dir / "index.json").write_text(
        json.dumps([
            {
                "stage": step["stage"], "title": step["title"], "status": step["status"],
                "file": f"stages/{step['stage']}.json",
                "model_call_ids": step["model_call_ids"],
                "evidence_ids": step["evidence_ids"],
            }
            for step in structured["process"]
        ], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (directory / "report-showcase.md").write_text(
        markdown_report(
            session, registry=registry, artifact_loader=store.artifact,
            base_dir=directory, artifact_links=artifact_links,
        ),
        encoding="utf-8",
    )
    (directory / "report-details.md").write_text(
        audit_report(
            session, registry=registry, artifact_loader=store.artifact,
            base_dir=directory, artifact_links=artifact_links,
        ),
        encoding="utf-8",
    )
    (directory / "report-summary.md").write_text(
        markdown_summary(session, registry=registry), encoding="utf-8",
    )
    manifest = {
        "review_id": session.session_id,
        "run_id": session.run_id,
        "report_version": session.report_version,
        "status": session.status,
        "report_completeness": session.report_completeness,
        "versions": structured["versions"],
        "summary": structured["summary"],
        "generated_from": "stored SessionSnapshot",
        "artifact_count": len(copied),
        "stage_files": [f"stages/{key}.json" for key in STAGES],
        "method_files": method_files,
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    hash_lines = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hash_lines.append(f"{digest}  {path.relative_to(directory).as_posix()}")
    (directory / "SHA256SUMS.txt").write_text("\n".join(hash_lines) + "\n", encoding="utf-8")
    return {
        "directory": str(directory),
        "report": str(directory / "report-showcase.md"),
        "details": str(directory / "report-details.md"),
        "summary": str(directory / "report-summary.md"),
        "structured": str(directory / "report.json"),
        "artifact_count": len(copied),
        "stage_files": [str(directory / "stages" / f"{key}.json") for key in STAGES],
        "method_files": method_files,
    }


def zip_report_package(directory: Path | str, zip_path: Path | str) -> Path:
    directory, zip_path = Path(directory), Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(directory).as_posix())
    return zip_path
