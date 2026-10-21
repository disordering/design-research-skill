"""按具体问题去重的离线回归，包含 S07 原始审计与公开评审入口。

fixtures/s07_raw_audit.json 原样复制自 20261021-192850-s07/raw-audit.json。
固定模型只回放该审计，不发起网络请求，也不重新判断测试图片。
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
import io
import json
from pathlib import Path

from PIL import Image
import pytest

from engine.contracts import Decision, RawAuditResult, ReviewContext, ReviewReport, Severity
from engine.criteria import CriteriaLibrary, heuristic_label
from engine.model import ModelCallResult
from engine.service import ReviewEngine, _build_summary
from engine.stub import StubModel


SOURCE = Path(__file__).resolve().parents[1]
S07_FIXTURE = SOURCE / "fixtures" / "s07_raw_audit.json"


def library():
    return CriteriaLibrary.load(SOURCE / "判据库_v1.json")


def engine(model=None):
    return ReviewEngine(library(), model or StubModel(), provider="offline-fixture",
                        model_name="s07-fixed-output", is_stub=True)


def finding(rule_ids=None, *, title="提醒状态缺少标记", confidence=0.8):
    return {
        "rule_ids": ["R17"] if rule_ids is None else rule_ids,
        "title": title,
        "severity": "medium",
        "confidence": confidence,
        "detection": "课程提醒 ON OFF 没有选中区别",
        "description": "用户无法读出当前提醒状态",
        "suggestion": "给 ON 加选中标记",
        "evidence": {
            "x": 0.1, "y": 0.1, "width": 0.2, "height": 0.1,
            "description": "课程提醒 ON OFF 区域",
            "visible_text": "ON OFF",
        },
    }


def raw_audit(findings, *, candidate_rules=None, decisions=None):
    if candidate_rules is None:
        candidate_rules = {rule for item in findings for rule in item["rule_ids"]}
    decisions = decisions or {}
    statuses = [
        {"rule_id": rule_id,
         "decision": decisions.get(rule_id, "candidate_issue" if rule_id in candidate_rules
                                   else "no_visible_issue"),
         "confidence": 0.9, "reason": "固定回归样本中的逐项状态"}
        for rule_id in library().rule_ids
    ]
    return RawAuditResult.model_validate({"rule_statuses": statuses, "findings": findings})


def s07_raw():
    return RawAuditResult.model_validate_json(S07_FIXTURE.read_text(encoding="utf-8"))


def assert_s07_findings(findings, raw):
    assert len(findings) == 5
    assert [item.id for item in findings] == [f"F{index:03d}" for index in range(1, 6)]
    expected = {item.title: item for item in raw.findings}
    assert {item.title for item in findings} == set(expected)
    for item in findings:
        original = expected[item.title]
        assert item.rule_ids == original.rule_ids
        assert item.evidence == original.evidence
        assert item.detection == original.detection
        assert item.description == original.description
        assert item.suggestion == original.suggestion
    r17 = [item for item in findings if "R17" in item.rule_ids]
    assert {item.title for item in r17} == {
        "当前界面主题没有可见选中标记", "作业到期的开启状态无法辨认",
    }
    by_title = {item.title: item for item in r17}
    theme = by_title["当前界面主题没有可见选中标记"].evidence
    reminder = by_title["作业到期的开启状态无法辨认"].evidence
    assert theme.visible_text == "浅色；深色"
    assert reminder.visible_text == "ON；OFF"
    assert theme.y + theme.height < reminder.y


def test_s07_preserves_five_findings_and_four_candidate_rules_without_warnings():
    raw = s07_raw()
    findings, rules, warnings = engine()._normalize(raw)

    assert_s07_findings(findings, raw)
    assert len(rules) == 24
    assert {item.rule_id for item in rules if item.decision is Decision.CANDIDATE_ISSUE} == {
        "R12", "R16", "R17", "R18",
    }
    original_statuses = {item.rule_id: item.decision for item in raw.rule_statuses}
    assert {item.rule_id: item.decision for item in rules} == original_statuses
    assert warnings == []
    summary = _build_summary(rules, findings)
    assert summary.rules_total == 24
    assert summary.candidate_issues == 4
    assert summary.medium_count == 5
    assert summary.critical_count == summary.high_count == summary.low_count == 0


@pytest.mark.parametrize("coordinate", ["x", "y"])
def test_same_rule_and_problem_text_at_different_locations_are_kept(coordinate):
    first = finding(title="第一处提醒")
    second = finding(title="第二处提醒")
    second["evidence"][coordinate] = 0.6

    findings, rules, warnings = engine()._normalize(raw_audit([first, second]))

    assert len(findings) == 2
    by_title = {item.title: item for item in findings}
    assert by_title["第一处提醒"].evidence.model_dump() == first["evidence"]
    assert by_title["第二处提醒"].evidence.model_dump() == second["evidence"]
    assert all(item.rule_ids == ["R17"] for item in findings)
    assert next(item for item in rules if item.rule_id == "R17").decision is Decision.CANDIDATE_ISSUE
    assert warnings == []


@pytest.mark.parametrize("field,replacement", [
    ("detection", "课程提醒 ON OFF 文字被相邻图形遮挡"),
    ("suggestion", "为课程提醒增加独立的当前值文字说明"),
], ids=["different-mechanism", "independent-action"])
def test_same_location_with_different_mechanism_or_action_is_kept(field, replacement):
    first = finding(title="第一项问题")
    second = finding(title="第二项问题")
    second[field] = replacement

    findings, _, warnings = engine()._normalize(raw_audit([first, second]))

    assert len(findings) == 2
    by_title = {item.title: item for item in findings}
    assert getattr(by_title["第一项问题"], field) == first[field]
    assert getattr(by_title["第二项问题"], field) == replacement
    assert all(item.rule_ids == ["R17"] for item in findings)
    assert by_title["第一项问题"].evidence == by_title["第二项问题"].evidence
    assert warnings == []


@pytest.mark.parametrize("field,replacement", [
    ("description", "相同截图区域中的作业到期控件"),
    ("visible_text", "浅色 深色"),
], ids=["different-control", "different-visible-text"])
def test_same_box_does_not_merge_different_evidence_objects(field, replacement):
    first = finding(title="第一处证据")
    second = finding(title="第二处证据")
    second["evidence"][field] = replacement

    findings, _, warnings = engine()._normalize(raw_audit([first, second]))

    assert len(findings) == 2
    assert {getattr(item.evidence, field) for item in findings} == {
        first["evidence"][field], replacement,
    }
    assert warnings == []


@pytest.mark.parametrize("reverse", [False, True], ids=["low-first", "high-first"])
def test_same_problem_merges_rule_union_and_keeps_highest_confidence_payload(reverse):
    lower = finding(["R01", "R02"], title="低置信度记录", confidence=0.2)
    lower["severity"] = "critical"
    lower["description"] = "低置信度记录的影响描述"
    higher = finding(["R01", "R03"], title="高置信度记录", confidence=0.9)
    higher["severity"] = "low"
    higher["description"] = "高置信度记录的影响描述"
    inputs = [lower, higher]
    if reverse:
        inputs.reverse()

    findings, rules, _ = engine()._normalize(raw_audit(inputs))

    assert len(findings) == 1
    actual = findings[0]
    assert set(actual.rule_ids) == {"R01", "R02", "R03"}
    assert len(actual.rule_ids) == 3
    assert actual.title == higher["title"]
    assert actual.confidence == 0.9
    assert actual.severity is Severity.LOW
    assert actual.description == higher["description"]
    assert actual.detection == higher["detection"]
    assert actual.suggestion == higher["suggestion"]
    assert actual.evidence.model_dump() == higher["evidence"]
    criteria = library()
    assert actual.principle == "；".join(
        f"{rule_id} {criteria.by_id[rule_id].title}" for rule_id in actual.rule_ids
    )
    assert actual.heuristics == list(dict.fromkeys(
        heuristic_label(criteria.by_id[rule_id].heuristic) for rule_id in actual.rule_ids
    ))
    assert all(item.decision is Decision.CANDIDATE_ISSUE
               for item in rules if item.rule_id in actual.rule_ids)


def test_same_problem_merges_even_without_a_shared_rule():
    inputs = [finding(["R01"], title="导航判据记录"),
              finding(["R02"], title="步骤判据记录")]

    findings, rules, _ = engine()._normalize(raw_audit(inputs))

    assert len(findings) == 1
    assert set(findings[0].rule_ids) == {"R01", "R02"}
    assert findings[0].title == "导航判据记录"
    assert all(item.decision is Decision.CANDIDATE_ISSUE
               for item in rules if item.rule_id in {"R01", "R02"})


@pytest.mark.parametrize("titles", [("后排序标题", "先排序标题"), ("先排序标题", "后排序标题")])
def test_equal_confidence_merge_keeps_first_payload_and_unions_rules(titles):
    first = finding(["R01"], title=titles[0])
    first["description"] = "输入首条的影响描述"
    first["severity"] = "low"
    second = finding(["R02"], title=titles[1])
    second["description"] = "输入第二条的影响描述"
    second["severity"] = "critical"

    findings, _, _ = engine()._normalize(raw_audit([first, second]))

    assert len(findings) == 1
    assert findings[0].title == titles[0]
    assert findings[0].description == first["description"]
    assert findings[0].severity is Severity.LOW
    assert set(findings[0].rule_ids) == {"R01", "R02"}


def test_whitespace_only_variants_are_one_problem_without_rewriting_representative():
    first = finding(title="首条原始文案", confidence=0.9)
    second = deepcopy(first)
    second["title"] = "仅空白不同的文案"
    second["confidence"] = 0.2
    for field in ("detection", "suggestion"):
        second[field] = second[field].replace(" ", " \n\t ")
    for field in ("description", "visible_text"):
        second["evidence"][field] = second["evidence"][field].replace(" ", " \n\t ")

    findings, _, _ = engine()._normalize(raw_audit([first, second]))

    assert len(findings) == 1
    assert findings[0].title == first["title"]
    assert findings[0].detection == first["detection"]
    assert findings[0].suggestion == first["suggestion"]
    assert findings[0].evidence.model_dump() == first["evidence"]


def test_invalid_rule_links_are_filtered_before_same_problem_rule_union():
    first = finding(["R01", "R02", "R99"], confidence=0.9)
    second = finding(["R03"], title="同一问题的另一个有效判据", confidence=0.2)
    raw = raw_audit([first, second], candidate_rules={"R01", "R03"},
                    decisions={"R02": "no_visible_issue"})

    findings, rules, warnings = engine()._normalize(raw)

    assert len(findings) == 1
    assert set(findings[0].rule_ids) == {"R01", "R03"}
    assert "R02" not in findings[0].principle
    assert "R99" not in findings[0].principle
    decisions = {item.rule_id: item.decision for item in rules}
    assert decisions["R01"] is decisions["R03"] is Decision.CANDIDATE_ISSUE
    assert decisions["R02"] is Decision.NO_VISIBLE_ISSUE
    assert "R99" not in decisions
    assert any("R02" in warning and "非 candidate_issue" in warning for warning in warnings)
    assert any("R99" in warning and "未知判据" in warning for warning in warnings)


def test_candidate_without_a_complete_finding_is_still_downgraded():
    raw = raw_audit([finding(["R01"])], candidate_rules={"R01", "R04"})

    findings, rules, warnings = engine()._normalize(raw)

    assert len(findings) == 1
    by_rule = {item.rule_id: item for item in rules}
    assert by_rule["R01"].decision is Decision.CANDIDATE_ISSUE
    assert by_rule["R04"].decision is Decision.INSUFFICIENT_EVIDENCE
    assert by_rule["R04"].confidence == 0.0
    assert "完整证据" in by_rule["R04"].reason
    assert any("R04" in warning and "降级" in warning for warning in warnings)


class FixedS07Model:
    """公开入口的固定模型回放器；只允许一次单阶段调用。"""

    def __init__(self):
        self.calls = 0

    async def complete(self, messages, *, json_mode=True, extra_body=None):
        self.calls += 1
        assert self.calls == 1
        assert json_mode is True
        return ModelCallResult(
            text=S07_FIXTURE.read_text(encoding="utf-8"), provider="offline-fixture",
            model="s07-fixed-output", usage={}, request_id=None, latency_ms=0,
            json_mode_used=True,
        )


def test_public_single_pass_review_returns_complete_s07_contract():
    model = FixedS07Model()
    image = io.BytesIO()
    # 空白图只用于走通图片输入契约；问题内容来自已保存的 S07 原始审计。
    Image.new("RGB", (640, 360), "white").save(image, format="PNG")
    context = ReviewContext(design_goal="查看当前主题和提醒状态，并按需要修改通知设置。",
                            target_user="首次调整个人设置的学生", platform="web")

    report = asyncio.run(engine(model).review(image.getvalue(), context=context,
                                            filename="offline-replay.png",
                                            analysis_mode="single_pass"))
    restored = ReviewReport.model_validate(json.loads(report.model_dump_json()))

    assert model.calls == 1
    assert restored.context == context
    assert restored.model.analysis_mode == "single_pass"
    assert restored.model.is_stub is True
    assert restored.status == "partial"
    assert len(restored.warnings) == 1
    assert "离线契约 Stub" in restored.warnings[0]
    assert restored.image.width == 640
    assert restored.image.height == 360
    assert restored.screen_analysis == s07_raw().screen_analysis
    assert_s07_findings(restored.findings, s07_raw())
    assert len(restored.rule_results) == 24
    assert restored.summary.rules_total == 24
    assert restored.summary.candidate_issues == 4
    assert restored.summary.medium_count == 5
    assert restored.summary.critical_count == restored.summary.high_count == restored.summary.low_count == 0
    assert (restored.summary.candidate_issues + restored.summary.no_visible_issue
            + restored.summary.insufficient_evidence + restored.summary.not_applicable) == 24
