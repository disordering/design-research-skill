"""Deterministic required-coverage matrix derived from tasks and observed states."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .session_contracts import SessionSnapshot


def coverage_id(task_id: str, state_id: str = "", page_id: str = "") -> str:
    key = f"{task_id}|{state_id or 'task'}|{page_id}"
    return "coverage-" + hashlib.sha256(key.encode()).hexdigest()[:16]


def _tokens(text: str) -> set[str]:
    value = str(text or "").lower()
    result = set(re.findall(r"[a-z0-9_]+", value))
    for chunk in re.findall(r"[\u4e00-\u9fff]+", value):
        result.update(chunk[index:index + 2] for index in range(len(chunk) - 1))
    return result


def _outcome_tokens(text: str) -> set[str]:
    value = str(text or "").lower()
    value = re.sub(
        r"显示|出现|提示|反馈|预期|应当|应该|用户看到|页面|界面",
        "",
        value,
    )
    return _tokens(value)


def _branch_match(
    session: SessionSnapshot,
    branch,
    transitions,
) -> dict[str, Any] | None:
    actions = {action.action_id: action for action in session.actions}
    evidence = {
        item.evidence_id: item
        for item in session.evidence
        if not item.stale
    }
    trigger_tokens = _tokens(branch.trigger)
    outcome_tokens = _outcome_tokens(branch.expected_outcome)
    for transition in transitions:
        action = actions.get(transition.action_id)
        if action is None or action.status != "executed":
            continue
        actual_parts = [
            action.kind if action else "",
            action.target_label if action else "",
            action.reason if action else "",
            action.outcome if action else "",
        ]
        trigger_actual = _tokens(" ".join(actual_parts))
        if trigger_tokens and not trigger_tokens.intersection(trigger_actual):
            continue

        destination = [
            evidence[evidence_id]
            for evidence_id in transition.evidence_ids
            if evidence_id in evidence
            and (
                evidence[evidence_id].state_id == transition.to_state
                or evidence[evidence_id].action_id == transition.action_id
            )
        ]
        if not destination:
            continue
        outcome_actual = _tokens(" ".join(item.content for item in destination))
        if not outcome_tokens:
            matched = True
            ratio = 1.0
        else:
            matched_tokens = outcome_tokens.intersection(outcome_actual)
            ratio = len(matched_tokens) / len(outcome_tokens)
            matched = ratio >= 0.6
        if matched:
            return {
                "matched_transition_id": transition.transition_id,
                "match_score": round(ratio, 4),
                "destination_evidence_ids": [
                    item.evidence_id for item in destination
                ],
            }
    return None


def build_required_coverage(session: SessionSnapshot) -> list[dict[str, Any]]:
    states = [
        state for state in session.page_states
        if state.source_id in {
            source.source_id for source in session.sources if source.active
        }
    ]
    reviewed_evidence = {
        review.evidence_id
        for review in session.screen_reviews
        if review.run_id == session.run_id
        and review.status in {"completed", "partial"}
    }
    evidence = {
        item.evidence_id: item
        for item in session.evidence
        if not item.stale
    }
    current_checks = [
        check for check in session.checks
        if check.run_id == session.run_id
        and not check.stale
        and check.scope_status == "included"
        and check.execution_status == "executed"
    ]
    covered_states = set()
    covered_tasks = set()
    for check in current_checks:
        if check.task_id:
            covered_tasks.add(check.task_id)
        for evidence_id in check.evidence_ids:
            state_id = evidence.get(evidence_id, None)
            if state_id and state_id.state_id:
                covered_states.add((check.task_id, state_id.state_id))
    for evidence_id in reviewed_evidence:
        item = evidence.get(evidence_id)
        if item and item.state_id:
            for task in session.review_tasks:
                task_source_ids = set(task.source_ids) or {
                    evidence[eid].source_id
                    for eid in task.evidence_ids
                    if eid in evidence
                }
                if item.source_id in task_source_ids:
                    covered_states.add((task.task_id, item.state_id))

    sources = {source.source_id: source for source in session.sources}
    matrix = []
    transitions = [
        transition for transition in session.transitions
        if transition.from_state in {
            state.state_id for state in states
        }
        and transition.to_state in {
            state.state_id for state in states
        }
    ]
    for task in session.review_tasks:
        for branch in task.branches:
            branch_match = _branch_match(session, branch, transitions)
            matrix.append({
                "coverage_id": "coverage-" + hashlib.sha256(
                    f"{task.task_id}|{branch.branch_id}".encode()
                ).hexdigest()[:16],
                "task_id": task.task_id,
                "task_text": task.text,
                "branch_id": branch.branch_id,
                "trigger": branch.trigger,
                "expected_outcome": branch.expected_outcome,
                "source_id": (
                    evidence[branch.evidence_ids[0]].source_id
                    if branch.evidence_ids and branch.evidence_ids[0] in evidence
                    else (task.source_ids[0] if task.source_ids else "")
                ),
                "covered": branch_match is not None,
                "coverage_kind": "branch",
                **(
                    {
                        "matched_transition_id": branch_match[
                            "matched_transition_id"
                        ],
                        "match_score": branch_match["match_score"],
                        "destination_evidence_ids": branch_match[
                            "destination_evidence_ids"
                        ],
                    }
                    if branch_match else {}
                ),
            })
        candidates = [
            state for state in states
            if state.source_id in set(task.source_ids)
            and (
                not task.page_ids
                or state.page_id in set(task.page_ids)
            )
        ]
        declared = set(task.state_ids)
        if declared:
            candidates = [
                state for state in candidates
                if state.state_id in declared
            ]
        if not candidates and not task.state_ids:
            matrix.append({
                "coverage_id": coverage_id(task.task_id),
                "task_id": task.task_id,
                "task_text": task.text,
                "page_id": "",
                "state_id": "",
                "source_id": task.source_ids[0] if task.source_ids else "",
                "covered": task.task_id in covered_tasks,
                "coverage_kind": "task",
            })
            continue
        known_states = {state.state_id for state in candidates}
        for missing_state_id in sorted(declared - known_states):
            matrix.append({
                "coverage_id": coverage_id(task.task_id, missing_state_id),
                "task_id": task.task_id,
                "task_text": task.text,
                "page_id": "",
                "state_id": missing_state_id,
                "source_id": task.source_ids[0] if task.source_ids else "",
                "covered": False,
                "coverage_kind": "state",
            })
        seen_states = set()
        for state in candidates:
            if state.state_id in seen_states:
                continue
            seen_states.add(state.state_id)
            matrix.append({
                "coverage_id": coverage_id(
                    task.task_id, state.state_id, state.page_id,
                ),
                "task_id": task.task_id,
                "task_text": task.text,
                "page_id": state.page_id,
                "state_id": state.state_id,
                "source_id": state.source_id,
                "covered": (task.task_id, state.state_id) in covered_states,
                "coverage_kind": "state",
            })
    for item in matrix:
        if item.get("covered"):
            continue
        source = sources.get(item.get("source_id"))
        if source and not source.active:
            item["gap_class"] = "source_inactive"
        elif source and source.acquisition_status in {"blocked", "failed", "pending", "partial"}:
            item["gap_class"] = "access_or_source"
        elif item.get("coverage_kind") == "branch":
            item["gap_class"] = "unobserved_branch"
        elif item.get("coverage_kind") == "state":
            state_exists = any(
                state.state_id == item.get("state_id")
                for state in states
            )
            item["gap_class"] = (
                "state_not_reviewed"
                if state_exists
                else "state_not_observed"
            )
        else:
            item["gap_class"] = "task_not_planned"
    return matrix


def missing_required_coverage(session: SessionSnapshot) -> list[dict[str, Any]]:
    return [
        item for item in build_required_coverage(session)
        if not item["covered"]
    ]
