"""Reproducible evaluation of reviewed sessions against independent labels."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .session_contracts import SessionSnapshot


class FindingLabel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label_id: str
    object_id: str = ""
    claim_types: list[str] = Field(default_factory=list)
    title_contains: list[str] = Field(default_factory=list)
    title_similarity: float = Field(default=0.65, ge=0, le=1)


class EvaluationLabels(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    findings: list[FindingLabel] = Field(default_factory=list)


class BatchCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    labels: EvaluationLabels


class BatchEvaluationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    cases: list[BatchCase] = Field(min_length=1)


def _matches(label: FindingLabel, finding) -> bool:
    if label.object_id and label.object_id != finding.object_id:
        return False
    claim_types = {claim.claim_type for claim in finding.claims}
    if label.claim_types and not claim_types.intersection(label.claim_types):
        return False
    if label.title_contains:
        return all(
            text.lower() in finding.title.lower()
            for text in label.title_contains
        )
    if label.object_id:
        return True
    return SequenceMatcher(
        None, label.label_id.lower(), finding.title.lower(),
    ).ratio() >= label.title_similarity


def evaluate_session(
    session: SessionSnapshot,
    labels: EvaluationLabels,
) -> dict[str, Any]:
    findings = [
        finding for finding in session.findings
        if finding.run_id == session.run_id and not finding.stale
    ]
    used_findings = set()
    matches = []
    missed = []
    for label in labels.findings:
        match = next(
            (
                finding for finding in findings
                if finding.finding_id not in used_findings
                and _matches(label, finding)
            ),
            None,
        )
        if match is None:
            missed.append(label.model_dump(mode="json"))
            continue
        used_findings.add(match.finding_id)
        matches.append({
            "label_id": label.label_id,
            "finding_id": match.finding_id,
            "object_id": match.object_id,
            "claim_types": [
                claim.claim_type for claim in match.claims
            ],
        })
    extra = [
        {
            "finding_id": finding.finding_id,
            "title": finding.title,
            "object_id": finding.object_id,
            "claim_types": [claim.claim_type for claim in finding.claims],
        }
        for finding in findings if finding.finding_id not in used_findings
    ]
    true_positive = len(matches)
    precision = true_positive / len(findings) if findings else 0.0
    recall = true_positive / len(labels.findings) if labels.findings else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )
    supported_claims = [
        claim for finding in findings for claim in finding.claims
    ]
    coverage = session.required_coverage
    return {
        "schema_version": "session-evaluation-1.0",
        "dataset": labels.dataset,
        "session_id": session.session_id,
        "run_id": session.run_id,
        "report_version": session.report_version,
        "report_completeness": session.report_completeness,
        "finding_metrics": {
            "expected": len(labels.findings),
            "actual": len(findings),
            "matched": true_positive,
            "missed": len(missed),
            "extra": len(extra),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        },
        "claim_metrics": {
            "total": len(supported_claims),
            "supported": sum(
                claim.verification_status == "supported"
                for claim in supported_claims
            ),
            "derived": sum(claim.derived for claim in supported_claims),
            "support_rate": round(
                sum(
                    claim.verification_status == "supported"
                    for claim in supported_claims
                ) / len(supported_claims),
                4,
            ) if supported_claims else 0.0,
        },
        "coverage_metrics": {
            "required": len(coverage),
            "covered": sum(item.get("covered", False) for item in coverage),
            "missing": sum(not item.get("covered", False) for item in coverage),
            "missing_by_class": {
                gap_class: sum(
                    item.get("gap_class") == gap_class
                    for item in coverage if not item.get("covered", False)
                )
                for gap_class in sorted({
                    item.get("gap_class") for item in coverage
                    if not item.get("covered", False) and item.get("gap_class")
                })
            },
        },
        "verifier": session.verifier_model_status,
        "matches": matches,
        "missed": missed,
        "extra": extra,
    }


def evaluate_batch(
    snapshots: dict[str, SessionSnapshot],
    batch: BatchEvaluationInput,
) -> dict[str, Any]:
    case_results = []
    totals = {
        "expected": 0, "actual": 0, "matched": 0,
        "missed": 0, "extra": 0,
        "claim_total": 0, "claim_supported": 0, "claim_derived": 0,
        "coverage_required": 0, "coverage_covered": 0,
    }
    for case in batch.cases:
        snapshot = snapshots.get(case.session_id)
        if snapshot is None:
            raise ValueError(f"Unknown evaluation session: {case.session_id}")
        result = evaluate_session(snapshot, case.labels)
        case_results.append(result)
        finding = result["finding_metrics"]
        claim = result["claim_metrics"]
        coverage = result["coverage_metrics"]
        totals["expected"] += finding["expected"]
        totals["actual"] += finding["actual"]
        totals["matched"] += finding["matched"]
        totals["missed"] += finding["missed"]
        totals["extra"] += finding["extra"]
        totals["claim_total"] += claim["total"]
        totals["claim_supported"] += claim["supported"]
        totals["claim_derived"] += claim["derived"]
        totals["coverage_required"] += coverage["required"]
        totals["coverage_covered"] += coverage["covered"]
    precision = (
        totals["matched"] / totals["actual"] if totals["actual"] else 0.0
    )
    recall = (
        totals["matched"] / totals["expected"] if totals["expected"] else 0.0
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "schema_version": "session-batch-evaluation-1.0",
        "dataset": batch.dataset,
        "case_count": len(case_results),
        "aggregate": {
            "expected": totals["expected"],
            "actual": totals["actual"],
            "matched": totals["matched"],
            "missed": totals["missed"],
            "extra": totals["extra"],
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "claim_support_rate": round(
                totals["claim_supported"] / totals["claim_total"], 4,
            ) if totals["claim_total"] else 0.0,
            "derived_claim_rate": round(
                totals["claim_derived"] / totals["claim_total"], 4,
            ) if totals["claim_total"] else 0.0,
            "coverage_rate": round(
                totals["coverage_covered"] / totals["coverage_required"], 4,
            ) if totals["coverage_required"] else 0.0,
        },
        "cases": case_results,
    }
