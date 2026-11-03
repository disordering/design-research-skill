"""以当前版本的评审结果对照原子参考，分别统计参考命中和预测条目。"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Hashable, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .session_contracts import Finding, FindingClaim, SessionSnapshot


class FindingLabel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label_id: str = Field(min_length=1)
    object_id: str = ""
    claim_types: list[str] = Field(default_factory=list)
    title_contains: list[str] = Field(default_factory=list)
    claim_contains: list[str] = Field(default_factory=list)
    title_similarity: float = Field(default=0.65, ge=0, le=1)

    @field_validator("title_contains", "claim_contains")
    @classmethod
    def nonempty_terms(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("匹配关键词不能为空。")
        return values


class EvaluationLabels(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    findings: list[FindingLabel] = Field(default_factory=list)

    @field_validator("findings")
    @classmethod
    def unique_labels(cls, values: list[FindingLabel]) -> list[FindingLabel]:
        if len({label.label_id for label in values}) != len(values):
            raise ValueError("同一任务的每个原子参考须有独立编号。")
        return values


class BatchCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    labels: EvaluationLabels


class BatchEvaluationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    cases: list[BatchCase] = Field(min_length=1)


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _claim_key(claim: FindingClaim) -> tuple:
    return (
        claim.object_id, claim.claim_type, _normalized(claim.observed),
        _normalized(claim.expected),
    )


def _prediction_key(finding: Finding) -> tuple:
    # 合并重复输出时保留不同对象、位置、证据和成因之间的区别。
    claims = frozenset(
        (_claim_key(claim), claim.verification_status, frozenset(claim.evidence_ids))
        for claim in finding.claims
    )
    return (
        finding.object_id, finding.object_ref, json.dumps(finding.location, sort_keys=True),
        _normalized(finding.title), _normalized(finding.detection),
        _normalized(finding.mechanism), _normalized(finding.change_action),
        frozenset(finding.evidence_ids), claims,
    )


def _contains(text: str, terms: list[str]) -> bool:
    return all(_normalized(term) in text for term in terms)


def _title_matches(label: FindingLabel, text: str) -> bool:
    if label.title_contains:
        return _contains(text, label.title_contains)
    identifier = _normalized(label.label_id)
    if label.object_id:
        # 对象只限定位置。遗漏现象关键词时，只有与完整标题同名的参考能直接匹配。
        return identifier != _normalized(label.object_id) and identifier == text
    return SequenceMatcher(None, identifier, text).ratio() >= label.title_similarity


def _claims_for_scoring(finding: Finding) -> list[FindingClaim | None]:
    if not finding.claims:
        # 旧版报告用整条有证据的问题充当一个匹配位置。
        return [None] if finding.evidence_ids else []
    distinct = {}
    for claim in finding.claims:
        if (claim.verification_status == "supported" and claim.observed.strip()
                and set(claim.evidence_ids).intersection(finding.evidence_ids)):
            distinct.setdefault(_claim_key(claim), claim)
    return list(distinct.values())


def _matches(label: FindingLabel, finding: Finding, claim: FindingClaim | None) -> bool:
    object_id = claim.object_id if claim else finding.object_id
    if label.object_id and label.object_id != object_id:
        return False
    if label.claim_types and (claim is None or claim.claim_type not in label.claim_types):
        return False
    if label.claim_contains:
        if claim is None or not _contains(_normalized(claim.expected + " " + claim.observed), label.claim_contains):
            return False
        # 参考直接给出主张内容时，标题字段只负责定位所属的报告条目。
        return _contains(_normalized(finding.title), label.title_contains)
    if claim is None:
        return _title_matches(label, _normalized(finding.title))
    # 明确点名“对象存在”的旧标签用标题定位问题，由结构化主张核验该对象。
    if label.claim_types == ["object_present"] and claim.claim_type == "object_present":
        return _title_matches(label, _normalized(finding.title))
    # 原子条件须落在该条主张的叙述内。分句中的数值可将时段和地点分别绑定。
    observed = _normalized(claim.observed)
    expected = _normalized(claim.expected)
    if _title_matches(label, observed):
        return True
    for statement in re.split(r"[。；;\n]+", finding.title + "\n" + finding.detection):
        text = _normalized(statement)
        if observed in text and expected in text and _title_matches(label, text):
            return True
    return False


Left = TypeVar("Left", bound=Hashable)
Right = TypeVar("Right", bound=Hashable)


def _allocate(choices: dict[Left, list[Right]]) -> dict[Right, Left]:
    """跨预测寻找最大匹配。沿交替路径重新分配，避免输入顺序造成漏检。"""
    owners = {}
    assignments = {}
    for first in sorted(choices, key=lambda key: len(choices[key])):
        queue = deque([first])
        parents = {}
        while queue:
            left = queue.popleft()
            for slot in choices[left]:
                if slot in parents:
                    continue
                parents[slot] = left
                if slot in owners:
                    queue.append(owners[slot])
                    continue
                while slot is not None:
                    left = parents[slot]
                    previous = assignments.get(left)
                    owners[slot] = left
                    assignments[left] = slot
                    slot = previous
                queue.clear()
                break
    return owners


def _same_scope(first: Finding, second: Finding) -> bool:
    return (
        first.object_id == second.object_id and first.object_ref == second.object_ref
        and first.location == second.location and bool(set(first.evidence_ids) & set(second.evidence_ids))
    )


@dataclass
class _EvidenceUse:
    finding: Finding
    claim: FindingClaim | None
    labels: list[str]
    key: tuple


def _evidence_key(finding: Finding, claim: FindingClaim | None) -> tuple:
    if claim is None:
        return ("legacy", finding.finding_id)
    # 标签是判分条件。证据位置只取决于原始来源、对象、观察值与预期值。
    return (
        "claim", finding.object_id, finding.object_ref, json.dumps(finding.location, sort_keys=True),
        _claim_key(claim), tuple(sorted(set(claim.evidence_ids) & set(finding.evidence_ids))),
    )


def _match_findings(findings: list[Finding], labels: list[FindingLabel]) -> tuple[list, list, list]:
    ordered_labels = sorted(labels, key=lambda label: (
        label.object_id, tuple(label.title_contains), tuple(label.claim_contains), tuple(label.claim_types), label.label_id
    ))
    options = {label.label_id: [] for label in ordered_labels}
    uses = {}
    ranks = {}
    sizes = {}
    for finding in findings:
        rows = [_EvidenceUse(finding, claim, [label.label_id for label in ordered_labels if _matches(label, finding, claim)],
                             _evidence_key(finding, claim)) for claim in _claims_for_scoring(finding)]
        fid = finding.finding_id
        uses[fid] = rows
        sizes[fid] = len({_claim_key(claim) for claim in finding.claims}) or 1
        known = sum(bool(row.labels) for row in rows)
        # 优先选所有主张都有参考的原件，部分重合的意见保留供复核。业务字段先于流水编号比较。
        ranks[fid] = (sizes[fid] - known, -known, _normalized(finding.title), _normalized(finding.detection),
                      tuple(sorted(repr(row.key) for row in rows)), fid)

    witnesses = defaultdict(list)
    for fid in sorted(uses, key=ranks.get):
        for row in uses[fid]:
            witnesses[row.key].append(row)
    for key, rows in witnesses.items():
        for label_id in {label_id for row in rows for label_id in row.labels}:
            options[label_id].append(key)
    owners = _allocate(options)
    # 同一证据允许多种表述。匹配后必须回链到真正支持该标签的原始措辞。
    credited = {}
    matches = []
    for key, label_id in owners.items():
        rows = witnesses[key]
        row = next(row for row in rows if label_id in row.labels)
        finding, claim = row.finding, row.claim
        credited[label_id] = finding
        entry = {
            "label_id": label_id, "finding_id": finding.finding_id,
            "object_id": claim.object_id if claim else finding.object_id,
            "claim_types": [claim.claim_type] if claim else [],
            "claim_id": claim.claim_id if claim else None,
            "evidence_ids": sorted(set(claim.evidence_ids) & set(finding.evidence_ids)) if claim else finding.evidence_ids,
        }
        if len(rows) > 1:
            entry["equivalent_claims"] = [{"finding_id": use.finding.finding_id,
                                           "claim_id": use.claim.claim_id, "eligible_labels": use.labels}
                                          for use in rows]
        matches.append(entry)

    hits = {finding.finding_id for finding in credited.values()}
    duplicates = []
    overlap = []
    for finding in findings:
        fid = finding.finding_id
        if fid in hits:
            continue
        same_scope = {}
        related = set()
        for row in uses[fid]:
            label_ids = set(row.labels).intersection(credited)
            if row.key in owners:
                label_ids.add(owners[row.key])
            related.update(label_ids)
            same_scope[row.key] = sorted(label for label in label_ids if _same_scope(finding, credited[label]))
        if not related:
            continue
        repeated = _allocate(same_scope)
        if len(repeated) == sizes[fid]:
            targets = sorted({credited[label].finding_id for label in repeated})
            duplicates.append({"finding_id": fid, "duplicate_of": targets[0], "covered_by": targets})
        else:
            overlap.append({"finding_id": fid, "overlapping_label_ids": sorted(related)})
    return matches, duplicates, overlap

def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _rates(counts: dict) -> dict:
    actual, expected = counts["actual"], counts["expected"]
    predictions, references = counts["matched_predictions"], counts["matched"]
    # 用原始计数计算调和平均，避免舍入误差。两边都有样本但无命中时得零。
    return {
        "precision": _ratio(predictions, actual),
        "recall": _ratio(references, expected),
        "duplicate_rate": _ratio(counts["duplicates"], actual + counts["duplicates"]),
        "f1": (_ratio(2 * predictions * references, predictions * expected + references * actual) or 0.0)
              if actual and expected else None,
    }


def evaluate_session(session: SessionSnapshot, labels: EvaluationLabels) -> dict[str, Any]:
    findings = []
    separate = []
    duplicates = []
    representatives = {}
    for finding in session.findings:
        if finding.run_id != session.run_id or finding.stale:
            continue
        if finding.kind not in ("issue", "nonconformity"):
            separate.append({"finding_id": finding.finding_id, "kind": finding.kind, "title": finding.title})
            continue
        signature = _prediction_key(finding)
        if signature in representatives:
            duplicates.append({"finding_id": finding.finding_id, "duplicate_of": representatives[signature]})
            continue
        representatives[signature] = finding.finding_id
        findings.append(finding)
    matches, repeated, overlap = _match_findings(findings, labels.findings)
    duplicates.extend(repeated)
    excluded_ids = {item["finding_id"] for item in repeated}
    findings = [finding for finding in findings if finding.finding_id not in excluded_ids]
    hit_labels = {item["label_id"] for item in matches}
    hit_predictions = {item["finding_id"] for item in matches}
    missed = [label.model_dump(mode="json") for label in labels.findings if label.label_id not in hit_labels]
    extra = [{
        "finding_id": finding.finding_id, "title": finding.title, "object_id": finding.object_id,
        "claim_types": [claim.claim_type for claim in finding.claims],
    } for finding in findings if finding.finding_id not in hit_predictions]
    counts = {
        "expected": len(labels.findings), "actual": len(findings), "matched": len(hit_labels),
        "matched_predictions": len(hit_predictions), "missed": len(missed), "extra": len(extra),
        "duplicates": len(duplicates), "suggestions": sum(x["kind"] == "suggestion" for x in separate),
        "conflicts": sum(x["kind"] == "conflict" for x in separate), "overlap_pending": len(overlap),
    }
    claims = [claim for finding in findings for claim in finding.claims]
    supported = sum(claim.verification_status == "supported" for claim in claims)
    coverage = session.required_coverage
    missing = [item for item in coverage if not item.get("covered", False)]
    return {
        "schema_version": "session-evaluation-1.1",
        "dataset": labels.dataset, "session_id": session.session_id, "run_id": session.run_id,
        "report_version": session.report_version, "report_completeness": session.report_completeness,
        "finding_metrics": {**counts, **_rates(counts)},
        "claim_metrics": {
            "total": len(claims), "supported": supported, "derived": sum(c.derived for c in claims),
            "support_rate": _ratio(supported, len(claims)),
        },
        "coverage_metrics": {
            "required": len(coverage), "covered": len(coverage) - len(missing), "missing": len(missing),
            "missing_by_class": dict(Counter(item["gap_class"] for item in missing if item.get("gap_class"))),
        },
        "verifier": session.verifier_model_status,
        "matches": matches, "missed": missed, "extra": extra, "duplicates": duplicates, "separate": separate,
        "overlap_pending": overlap,
    }


def evaluate_batch(snapshots: dict[str, SessionSnapshot], batch: BatchEvaluationInput) -> dict[str, Any]:
    results = []
    counts = Counter()
    claims = Counter()
    coverage = Counter()
    for case in batch.cases:
        if case.session_id not in snapshots:
            raise ValueError(f"Unknown evaluation session: {case.session_id}")
        result = evaluate_session(snapshots[case.session_id], case.labels)
        results.append(result)
        counts.update({k: v for k, v in result["finding_metrics"].items()
                       if k not in ("precision", "recall", "f1", "duplicate_rate")})
        claims.update({k: result["claim_metrics"][k] for k in ("total", "supported", "derived")})
        coverage.update({k: result["coverage_metrics"][k] for k in ("required", "covered")})
    return {
        "schema_version": "session-batch-evaluation-1.1", "dataset": batch.dataset, "case_count": len(results),
        "aggregate": {
            **counts, **_rates(counts),
            "claim_support_rate": _ratio(claims["supported"], claims["total"]),
            "derived_claim_rate": _ratio(claims["derived"], claims["total"]),
            "coverage_rate": _ratio(coverage["covered"], coverage["required"]),
        },
        "cases": results,
    }
