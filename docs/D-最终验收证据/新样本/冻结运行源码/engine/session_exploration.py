"""Deterministic bounded action proposals for observed controls and coverage gaps."""

from __future__ import annotations

import re
from typing import Any

from .session_contracts import Action, SessionSnapshot


ALIASES = {
    "保存": {"save", "submit"},
    "提交": {"submit", "save"},
    "取消": {"cancel", "close"},
    "返回": {"back", "return"},
    "下一步": {"next", "continue"},
    "继续": {"continue", "next"},
    "删除": {"delete", "remove"},
    "确认": {"confirm", "ok"},
    "关闭": {"close", "cancel"},
}


def _tokens(text: Any) -> set[str]:
    value = str(text or "").lower()
    result = set(re.findall(r"[a-z0-9_]{2,}", value))
    for chunk in re.findall(r"[\u4e00-\u9fff]+", value):
        result.update(chunk[index:index + 2] for index in range(len(chunk) - 1))
    for chinese, english in ALIASES.items():
        if chinese in value:
            result.update(english)
    return result


def _control_text(control: dict[str, Any]) -> str:
    return " ".join(str(control.get(key) or "") for key in (
        "label", "name", "ariaLabel", "title", "role", "tag", "selector",
    ))


def auto_gap_action(
    session: SessionSnapshot,
    gaps: list[dict[str, Any]],
) -> Action | None:
    sources = {
        source.source_id: source
        for source in session.sources
        if source.active
    }
    latest_by_source = {}
    for evidence in session.evidence:
        if evidence.stale or evidence.source_id not in sources:
            continue
        latest_by_source[evidence.source_id] = evidence
    gap_tokens = _tokens(" ".join(
        " ".join([
            str(gap.get("coverage_title") or ""),
            str(gap.get("reason") or ""),
            " ".join(gap.get("evidence_needed") or []),
        ])
        for gap in gaps
    ))
    if not gap_tokens:
        return None

    candidates = []
    for source_id, evidence in latest_by_source.items():
        source = sources[source_id]
        if source.input.kind != "website" or not evidence.state_id:
            continue
        controls = evidence.locator.get("controls", [])
        if not isinstance(controls, list):
            continue
        for index, control in enumerate(controls[:120]):
            if not isinstance(control, dict):
                continue
            selector = str(control.get("selector") or "")
            label = str(
                control.get("ariaLabel")
                or control.get("label")
                or control.get("name")
                or ""
            )
            if (
                not selector
                or control.get("disabled")
                or control.get("hidden")
                or not label
            ):
                continue
            tokens = _tokens(_control_text(control))
            overlap = gap_tokens.intersection(tokens)
            if not overlap:
                continue
            if any(
                action.source_id == source_id
                and action.selector == selector
                and action.expected_state_id == evidence.state_id
                and action.outcome == "no_observed_change"
                for action in session.actions
            ):
                continue
            candidates.append((
                len(overlap),
                len(gap_tokens.intersection(_tokens(label))),
                -index,
                source_id,
                evidence,
                control,
                selector,
                label,
            ))
    if not candidates:
        return None
    _, _, _, source_id, evidence, control, selector, label = max(
        candidates, key=lambda item: item[:3],
    )
    return Action(
        source_id=source_id,
        kind="click",
        selector=selector,
        expected_state_id=evidence.state_id or "",
        reason=f"程序按覆盖缺口选择已观察控件：{label}",
        target_label=label,
        requires_explicit_authorization=False,
    )
