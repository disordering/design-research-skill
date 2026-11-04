"""Observed state graph and action-backed path coverage."""

from __future__ import annotations

from typing import Any

from .session_contracts import SessionSnapshot
from .session_verification import missing_task_state_coverage


def build_state_graph(session: SessionSnapshot) -> dict[str, Any]:
    active_sources = {
        source.source_id
        for source in session.sources
        if source.active
    }
    evidence = {
        item.evidence_id: item
        for item in session.evidence
        if not item.stale and item.source_id in active_sources
    }
    current_checks = [
        check for check in session.checks
        if check.run_id == session.run_id
        and not check.stale
        and check.scope_status == "included"
        and check.execution_status == "executed"
    ]
    checks_by_evidence: dict[str, list[str]] = {}
    for check in current_checks:
        for evidence_id in check.evidence_ids:
            checks_by_evidence.setdefault(evidence_id, []).append(check.check_id)
    reviewed_evidence_ids = {
        review.evidence_id
        for review in session.screen_reviews
        if review.run_id == session.run_id
        and review.status in {"completed", "partial"}
    }

    nodes: dict[str, dict[str, Any]] = {}
    for state in session.page_states:
        if state.source_id not in active_sources:
            continue
        node = nodes.setdefault(state.state_id, {
            "state_id": state.state_id,
            "page_id": state.page_id,
            "source_id": state.source_id,
            "context_version": state.context_version,
            "mode": state.mode,
            "locator": state.locator,
            "evidence_ids": [],
            "check_ids": [],
            "covered": False,
        })
        node["evidence_ids"] = list(dict.fromkeys([
            *node["evidence_ids"], *state.evidence_ids,
        ]))
        node["check_ids"] = list(dict.fromkeys([
            *node["check_ids"],
            *(cid for eid in state.evidence_ids for cid in checks_by_evidence.get(eid, [])),
        ]))
        node["reviewed"] = any(
            evidence_id in reviewed_evidence_ids
            for evidence_id in node["evidence_ids"]
        )
        node["covered"] = bool(node["check_ids"]) or node["reviewed"]

    actions = {action.action_id: action for action in session.actions}
    edges = []
    for transition in session.transitions:
        if transition.from_state not in nodes or transition.to_state not in nodes:
            continue
        action = actions.get(transition.action_id)
        edges.append({
            "transition_id": transition.transition_id,
            "from_state": transition.from_state,
            "to_state": transition.to_state,
            "action_id": transition.action_id,
            "action_kind": action.kind if action else "unknown",
            "target_label": action.target_label if action else "",
            "outcome": action.outcome if action else None,
            "evidence_ids": transition.evidence_ids,
            "verification_status": transition.verification_status,
        })

    incoming: dict[str, int] = {}
    outgoing: dict[str, int] = {}
    for edge in edges:
        outgoing[edge["from_state"]] = outgoing.get(edge["from_state"], 0) + 1
        incoming[edge["to_state"]] = incoming.get(edge["to_state"], 0) + 1

    uncovered = missing_task_state_coverage(session)
    return {
        "schema_version": "session-flow-1.0",
        "context_version": session.context_version,
        "nodes": [
            {
                **node,
                "incoming": incoming.get(state_id, 0),
                "outgoing": outgoing.get(state_id, 0),
            }
            for state_id, node in nodes.items()
        ],
        "edges": edges,
        "uncovered_task_states": [
            {"task_id": task_id, "state_id": state_id}
            for task_id, state_id in uncovered
        ],
        "summary": {
            "state_count": len(nodes),
            "transition_count": len(edges),
            "covered_state_count": sum(node["covered"] for node in nodes.values()),
            "uncovered_task_state_count": len(uncovered),
        },
    }
