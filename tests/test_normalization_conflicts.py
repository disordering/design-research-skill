"""同一具体问题去重；不同问题保留完整的判据关联与独立证据。"""

from pathlib import Path

import pytest

from engine.contracts import Decision, RawAuditResult
from engine.criteria import CriteriaLibrary
from engine.service import ReviewEngine
from engine.stub import StubModel


def finding(rule_ids, confidence, title, *, problem=None):
    problem = title if problem is None else problem
    return {
        "rule_ids": rule_ids, "title": title, "severity": "medium", "confidence": confidence,
        "detection": "具体可见表现：" + problem,
        "description": "候选记录的用户影响：" + title,
        "suggestion": "独立修改动作：" + problem,
        "evidence": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2,
                     "description": problem},
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
def test_same_problem_keeps_highest_confidence_in_either_order(reverse):
    inputs = [finding(["R01"], 0.2, "low", problem="相同导航状态问题"),
              finding(["R01"], 0.9, "high", problem="相同导航状态问题")]
    if reverse:
        inputs.reverse()
    findings, rules, _ = normalize(inputs)

    assert len(findings) == 1
    assert findings[0].rule_ids == ["R01"]
    assert findings[0].title == "high"
    assert findings[0].confidence == 0.9
    assert findings[0].evidence.description == "相同导航状态问题"
    assert findings[0].description == "候选记录的用户影响：high"
    assert findings[0].detection == "具体可见表现：相同导航状态问题"
    assert findings[0].suggestion == "独立修改动作：相同导航状态问题"
    assert next(rule for rule in rules if rule.rule_id == "R01").decision is Decision.CANDIDATE_ISSUE


@pytest.mark.parametrize("reverse", [False, True], ids=["low-first", "high-first"])
def test_distinct_problems_preserve_shared_rules_and_their_evidence(reverse):
    inputs = [finding(["R01", "R02"], 0.3, "low"), finding(["R01", "R03"], 0.9, "high")]
    if reverse:
        inputs.reverse()
    findings, rules, _ = normalize(inputs)

    by_title = {item.title: item for item in findings}
    assert len(findings) == 2
    assert by_title["high"].rule_ids == ["R01", "R03"]
    assert by_title["low"].rule_ids == ["R01", "R02"]
    assert by_title["high"].evidence.description == "high"
    assert by_title["low"].evidence.description == "low"
    assert "R02" not in by_title["high"].principle
    assert "R01" in by_title["low"].principle
    assert "R02" in by_title["low"].principle
    assert "R03" not in by_title["low"].principle
    assigned = [rule for item in findings for rule in item.rule_ids]
    assert sorted(assigned) == ["R01", "R01", "R02", "R03"]
    assert all(len(item.rule_ids) == len(set(item.rule_ids)) for item in findings)
    for title in ("low", "high"):
        assert by_title[title].detection == "具体可见表现：" + title
        assert by_title[title].description == "候选记录的用户影响：" + title
        assert by_title[title].suggestion == "独立修改动作：" + title
    assert all(rule.decision is Decision.CANDIDATE_ISSUE for rule in rules if rule.rule_id in assigned)


@pytest.mark.parametrize("titles", [("z-first", "a-second"), ("a-first", "z-second")])
def test_equal_confidence_same_problem_prefers_first_candidate_stably(titles):
    findings, _, _ = normalize([
        finding(["R01"], 0.8, title, problem="相同导航状态问题") for title in titles
    ])

    assert len(findings) == 1
    assert findings[0].title == titles[0]
    assert findings[0].evidence.description == "相同导航状态问题"
    assert findings[0].description == "候选记录的用户影响：" + titles[0]
