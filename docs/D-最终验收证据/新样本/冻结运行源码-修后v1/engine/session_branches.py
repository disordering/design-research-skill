"""Conservative branch inference from explicitly authoritative material."""

from __future__ import annotations

import hashlib
import re

from .session_contracts import Evidence, ReviewBranch, ReviewTask, SessionSnapshot


MARKERS = (
    "如果", "若", "当", "一旦", "取消", "返回", "失败", "错误",
    "权限", "空状态", "异常", "超时",
)


def _sentences(text: str) -> list[str]:
    return [
        " ".join(item.split())
        for item in re.split(r"(?<=[。！？；;])\s*|\n+", text)
        if 8 <= len(" ".join(item.split())) <= 500
    ]


def _split_branch(sentence: str) -> tuple[str, str] | None:
    conditional = re.match(
        r"^(?:如果|若|当|一旦)(.+?)(?:则|就|应|需要|要)(.+)$",
        sentence,
    )
    if conditional:
        return (
            f"如果{conditional.group(1).strip()}",
            conditional.group(2).strip().rstrip("。；;"),
        )
    for marker in ("之后", "后", "时", "情况下"):
        index = sentence.find(marker)
        if index > 0 and index + len(marker) < len(sentence):
            trigger = sentence[:index + len(marker)].strip()
            outcome = sentence[index + len(marker):].strip("，,：: ")
            if outcome:
                return trigger, outcome.rstrip("。；;")
    if any(marker in sentence for marker in MARKERS):
        return sentence.rstrip("。；;"), "完成该条件分支并按材料反馈"
    return None


def inferred_branches(
    session: SessionSnapshot,
    tasks: list[ReviewTask],
    materials: dict[str, Evidence],
) -> list[ReviewTask]:
    sources = {source.source_id: source for source in session.sources}
    authoritative = {
        evidence.source_id
        for evidence in materials.values()
        if sources.get(evidence.source_id)
        and sources[evidence.source_id].input.role in {
            "design_brief", "product_spec", "user_statement",
        }
    }
    for task in tasks:
        existing = {
            (branch.trigger.strip().lower(), branch.expected_outcome.strip().lower())
            for branch in task.branches
        }
        for evidence in materials.values():
            if evidence.source_id not in authoritative:
                continue
            if task.source_ids and evidence.source_id not in set(task.source_ids):
                continue
            for sentence in _sentences(evidence.content):
                split = _split_branch(sentence)
                if split is None:
                    continue
                trigger, outcome = split
                key = (trigger.lower(), outcome.lower())
                if key in existing:
                    continue
                existing.add(key)
                digest = hashlib.sha256(
                    f"{task.task_id}|{trigger}|{outcome}".encode()
                ).hexdigest()[:12]
                task.branches.append(ReviewBranch(
                    branch_id=f"BR-INF-{digest}",
                    trigger=trigger,
                    expected_outcome=outcome,
                    evidence_ids=[evidence.evidence_id],
                    basis="inferred",
                ))
    return tasks
