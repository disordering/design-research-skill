"""One candidate owns each rule; preserve independent evidence on other rules."""

from pathlib import Path

import pytest

from engine.contracts import Decision, RawAuditResult
from engine.criteria import CriteriaLibrary
from engine.service import ReviewEngine
from engine.stub import StubModel


def finding(rule_ids, confidence, title):
    return {
        "rule_ids": rule_ids, "title": title, "severity": "medium", "confidence": confidence,
        "detection": "Visible evidence for " + title,
        "description": "User consequence for " + title,
        "suggestion": "Repair suggestion for " + title,
        "evidence": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2, "description": title},
    }


def normalize(findings):
    library = CriteriaLibrary.load(Path(__file__).resolve().parents[1] / "判据库_v1.json")
    engine = ReviewEngine(library, StubModel(), provider="stub", model_name="test-only", is_stub=True)
    rule_ids = list(dict.fromkeys(rule for item in findings for rule in item["rule_ids"]))
    raw = RawAuditResult.model_validate({
        "rule_statuses": [
            {"rule_id": rule, "decision": "candidate_issue", "confidence": 0.9}
            for rule in rule_ids
        ],
        "findings": findings,
    })
    return engine._normalize(raw)


@pytest.mark.parametrize("reverse", [False, True], ids=["low-first", "high-first"])
def test_duplicate_rule_keeps_highest_confidence_in_either_order(reverse):
    inputs = [finding(["R01"], 0.2, "low"), finding(["R01"], 0.9, "high")]
    if reverse:
        inputs.reverse()
    findings, rules, _ = normalize(inputs)

    assert len(findings) == 1
    assert findings[0].rule_ids == ["R01"]
    assert findings[0].title == "high"
    assert findings[0].confidence == 0.9
    assert findings[0].evidence.description == "high"
    assert next(rule for rule in rules if rule.rule_id == "R01").decision is Decision.CANDIDATE_ISSUE


@pytest.mark.parametrize("reverse", [False, True], ids=["low-first", "high-first"])
def test_overlapping_findings_preserve_unique_rules_and_their_evidence(reverse):
    inputs = [finding(["R01", "R02"], 0.3, "low"), finding(["R01", "R03"], 0.9, "high")]
    if reverse:
        inputs.reverse()
    findings, rules, _ = normalize(inputs)

    by_title = {item.title: item for item in findings}
    assert len(findings) == 2
    assert by_title["high"].rule_ids == ["R01", "R03"]
    assert by_title["low"].rule_ids == ["R02"]
    assert by_title["high"].evidence.description == "high"
    assert by_title["low"].evidence.description == "low"
    assert "R02" not in by_title["high"].principle
    assert "R01" not in by_title["low"].principle
    assert "R03" not in by_title["low"].principle
    assigned = [rule for item in findings for rule in item.rule_ids]
    assert sorted(assigned) == ["R01", "R02", "R03"]
    assert len(assigned) == len(set(assigned))
    assert all(rule.decision is Decision.CANDIDATE_ISSUE for rule in rules if rule.rule_id in assigned)


@pytest.mark.parametrize("titles", [("z-first", "a-second"), ("a-first", "z-second")])
def test_equal_confidence_prefers_first_candidate_stably(titles):
    findings, _, _ = normalize([finding(["R01"], 0.8, title) for title in titles])

    assert len(findings) == 1
    assert findings[0].title == titles[0]
    assert findings[0].evidence.description == titles[0]
