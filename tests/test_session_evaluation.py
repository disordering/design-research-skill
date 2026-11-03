"""评分按有依据的参考原子和去重预测分别计数。"""
import pytest

from engine.session_contracts import Finding, FindingClaim, SessionCreate, SessionSnapshot
from engine.session_evaluation import BatchEvaluationInput, EvaluationLabels, evaluate_batch, evaluate_session


def atom(expected, observed, *, status="supported", evidence="回执图"):
    return FindingClaim(claim_type="requirement_match", object_id="回执", expected=expected,
                        observed=observed, evidence_ids=[evidence], verification_status=status)


def issue(fid, text, *claims, kind="issue", evidence="回执图"):
    return Finding(finding_id=fid, kind=kind, title=text, detection=text, check_ids=["R18"],
                   evidence_ids=[evidence], description="用户核对本次选择", principle="显示所选内容",
                   suggestion="读取已选记录", severity_reason="提交内容错配", object_id="回执",
                   run_id="run-test", claims=list(claims))


def snapshot(findings):
    request = SessionCreate(purpose="核对回执", sources=[{"kind": "document", "content": "任务说明"}])
    return SessionSnapshot(request=request, run_id="run-test", findings=findings)


def labels(*pairs):
    return EvaluationLabels(dataset="独立评分测试", findings=[
        {"label_id": name, "title_contains": [term], "object_id": "回执"} for name, term in pairs
    ])


def test_two_supported_atoms_in_one_prediction_and_mixed_batch_denominators():
    session = snapshot([issue("F1", "时段错误：14:00 显示 09:00；地点错误：二层显示一层",
                              atom("14:00", "09:00"), atom("二层", "一层"))])
    reference = labels(("时段", "时段错误"), ("地点", "地点错误"))
    first = evaluate_session(session, reference)
    assert first["finding_metrics"]["matched"] == 2
    assert first["finding_metrics"]["matched_predictions"] == first["finding_metrics"]["actual"] == 1
    assert first["finding_metrics"]["precision"] == first["finding_metrics"]["recall"] == 1.0
    assert len({m["claim_id"] for m in first["matches"]}) == 2
    empty = snapshot([])
    result = evaluate_batch(
        {s.session_id: s for s in (session, empty)},
        BatchEvaluationInput(dataset="合并", cases=[{"session_id": s.session_id, "labels": reference}
                                                 for s in (session, empty)]),
    )["aggregate"]
    assert result["precision"] == 1.0 and result["recall"] == 0.5 and result["f1"] == 0.6667


@pytest.mark.parametrize("reverse", [False, True])
def test_overlapping_labels_are_matched_globally_in_either_order(reverse):
    # 一条只提到报错，另一条同时满足两个关键词。两个参考必须占用不同主张。
    one = issue("F1", "回执报错，页面空白", atom("显示回执", "回执报错，页面空白"))
    two = issue("F2", "显示过期地点，回执报错", atom("显示新地点", "显示过期地点，回执报错"))
    observations = [one, two]
    terms = [("现象甲", "报错"), ("现象乙", "过期地点")]
    if reverse:
        observations.reverse()
        terms.reverse()
    result = evaluate_session(snapshot(observations), labels(*terms))
    assert {(row["label_id"], row["finding_id"]) for row in result["matches"]} == {("现象甲", "F1"), ("现象乙", "F2")}
    assert result["finding_metrics"]["matched_predictions"] == result["finding_metrics"]["matched"] == 2


@pytest.mark.parametrize("reverse", [False, True])
def test_rephrased_same_reference_is_reported_as_duplicate_not_a_second_hit(reverse):
    one = issue("F1", "时段错误：预约下午却显示上午", atom("下午", "上午"))
    two = issue("F2", "时段错误：回执把下午印成上午", atom("下午", "上午"))
    identical = two.model_copy(update={"finding_id": "F3"})
    session = snapshot([one, two, identical][::-1] if reverse else [one, two, identical])
    result = evaluate_session(session, labels(("时段", "时段错误")))
    counts = result["finding_metrics"]
    assert counts["matched"] == counts["actual"] == counts["matched_predictions"] == 1
    assert counts["duplicates"] == 2 and counts["duplicate_rate"] == 0.6667 and counts["extra"] == 0
    assert len(result["duplicates"]) == 2


def test_only_evidenced_explicit_atom_counts_when_title_mentions_two_issues():
    original = issue("F1", "时段错误：14:00 显示 09:00；地点错误：二层显示一层", atom("14:00", "09:00"))
    reference = labels(("时段", "时段错误"), ("地点", "地点错误"))
    for claims in ([atom("14:00", "09:00")],
                   [atom("14:00", "09:00"), atom("二层", "一层", status="rejected")],
                   [atom("14:00", "09:00"), atom("二层", "一层", evidence="其他图")]):
        result = evaluate_session(snapshot([original.model_copy(update={"claims": claims})]), reference)
        assert [r["label_id"] for r in result["matches"]] == ["时段"]
    other = issue("F2", "时段错误", atom("字体 16", "字体 12"))
    assert evaluate_session(snapshot([other]), reference)["finding_metrics"]["matched"] == 0


def test_copying_one_ambiguous_claim_cannot_fill_two_references():
    finding = issue("F1", "时段错误：下午变上午，无法核对", atom("下午", "上午"))
    copy = issue("F2", "无法核对，时段错误：下午变上午", atom("下午", "上午"))
    reference = labels(("参考甲", "时段错误"), ("参考乙", "无法核对"))
    result = evaluate_session(snapshot([finding, copy]), reference)
    assert result["finding_metrics"]["matched"] == result["finding_metrics"]["missed"] == 1
    assert result["finding_metrics"]["duplicates"] == 1


@pytest.mark.parametrize("id_pair", [("P1", "P2"), ("P2", "P1")])
def test_equivalent_claims_union_possible_labels_but_score_once(id_pair):
    short = issue(id_pair[0], "时段错误：下午显示为上午", atom("下午", "上午"))
    long = issue(id_pair[1], "时段错误：下午显示为上午，无法核对", atom("下午", "上午"))
    reference = labels(("时段参考", "时段错误"), ("额外参考", "无法核对"))
    for predictions in ([short, long], [long, short]):
        result = evaluate_session(snapshot(predictions), reference)
        counts = result["finding_metrics"]
        assert counts["matched"] == counts["missed"] == counts["duplicates"] == counts["actual"] == 1
        trace, = result["matches"]
        sources = {item["finding_id"]: item["eligible_labels"] for item in trace["equivalent_claims"]}
        assert set(sources[short.finding_id]) == {"时段参考"}
        assert set(sources[long.finding_id]) == {"时段参考", "额外参考"}
        assert trace["label_id"] in sources[trace["finding_id"]]


def test_extra_wording_can_resolve_another_reference_in_global_assignment():
    first = issue("F1", "时段错误：下午显示上午", atom("下午", "上午"))
    second = issue("F2", "时段错误、无法核对：下午显示上午", atom("下午", "上午"))
    third = issue("F3", "时段错误：清晨显示正午", atom("清晨", "正午"))
    result = evaluate_session(snapshot([first, second, third]), labels(("甲", "时段错误"), ("乙", "无法核对")))
    assert {(m["label_id"], m["finding_id"]) for m in result["matches"]} == {("乙", "F2"), ("甲", "F3")}
    assert result["finding_metrics"]["actual"] == result["finding_metrics"]["matched"] == 2
    assert result["finding_metrics"]["duplicates"] == 1


def test_suggestion_conflict_and_zero_denominators():
    entries = [issue("S", "展示成组", kind="suggestion"), issue("C", "文档矛盾", kind="conflict")]
    result = evaluate_session(snapshot(entries), labels())
    assert {e["kind"] for e in result["separate"]} == {"suggestion", "conflict"}
    assert result["finding_metrics"]["actual"] == 0 and result["finding_metrics"]["duplicate_rate"] is None
    assert all(result["finding_metrics"][k] is None for k in ("precision", "recall", "f1"))
    assert result["claim_metrics"]["support_rate"] is None


@pytest.mark.parametrize("id_pair", [("P1", "P2"), ("P2", "P1")])
def test_related_prediction_with_an_additional_unmatched_claim_keeps_separate_evidence(id_pair):
    a = issue(id_pair[0], "时段错误：下午显示上午", atom("下午", "上午"))
    b = issue(id_pair[1], "时段错误：下午显示上午；文字黑色写成白色", atom("下午", "上午"), atom("黑色", "白色"))
    for predictions in ([a, b], [b, a]):
        result = evaluate_session(snapshot(predictions), labels(("时段", "时段错误")))
        assert result["finding_metrics"]["duplicates"] == 0 and result["finding_metrics"]["overlap_pending"] == 1
        assert result["finding_metrics"]["precision"] == 0.5
        assert result["overlap_pending"][0]["finding_id"] == b.finding_id


def test_explicit_claim_terms_and_legacy_single_finding():
    raw = issue("F1", "核对回执", atom("14:00", "09:00"), atom("二层", "一层"))
    ref = EvaluationLabels(dataset="条件", findings=[{
        "label_id": "时段", "object_id": "回执", "claim_types": ["requirement_match"],
        "title_contains": ["核对回执"], "claim_contains": ["14:00", "09:00"],
    }])
    assert evaluate_session(snapshot([raw]), ref)["finding_metrics"]["matched"] == 1
    legacy = issue("F2", "时段错误，地点错误")
    result = evaluate_session(snapshot([legacy]), labels(("时段", "时段错误"), ("地点", "地点错误")))
    assert result["finding_metrics"]["matched"] == 1
