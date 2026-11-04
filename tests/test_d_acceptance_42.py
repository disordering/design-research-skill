"""D 的正式验收补测：真实产品方法配受控响应；不代表模型正确率。"""
import asyncio
import json
import pytest

from engine.errors import EngineError
from engine.model import ModelCallResult
from engine.session_adapters import Capture
from engine.session_contracts import (
    Action, CheckItem, Constraint, EventInput, Evidence, Finding, Question, Recheck, SourceRecord,
    SessionCreate, SessionSnapshot, SourceInput,
)
from engine.session_evaluation import EvaluationLabels, evaluate_session
from engine.session_report import structured_report
from engine.session_service import SessionService
from engine.session_store import SessionStore
from test_session_service import FixtureAdapters, FixtureModel, create_service, request


def test_qa16_tool_failure_is_recorded_without_product_finding(tmp_path):
    class BrokenClick(FixtureAdapters):
        async def act(self, *args, **kwargs):
            raise EngineError("browser_action_failed", "受控工具点击失败", status_code=502)

    async def run():
        service, _ = create_service(tmp_path, adapters=BrokenClick())
        session = service.create(request(website=True, allow_interaction=True, actor_type="ai"))
        await service._read_sources(session)
        action = Action(source_id=session.sources[0].source_id, kind="click", selector="#save",
                        expected_state_id="fixture-state", reason="受控点击失败验收")
        await service._perform_action(session, action)
        assert action.status == "failed"
        assert "受控工具点击失败" in action.error
        assert not session.findings and not session.transitions
    asyncio.run(run())


def test_qa21_unsupported_rejection_reruns_without_erasing_prior_evidence(tmp_path):
    service, _ = create_service(tmp_path, model=FixtureModel(issue=True))
    first = asyncio.run(service.run(service.create(request(actor_type="ai")).session_id))
    original = first.findings[0]
    changed, run_needed = service.apply_event(first.session_id, EventInput(
        event_id="QA21-反对但未补证", expected_context_version=1, type="review_finding",
        actor="D-AI验收", actor_type="ai", payload={"finding_id": original.finding_id,
        "review_status": "rejected", "reason": "我不喜欢这个结论，请撤回；没有新增事实。"}))
    assert run_needed
    second = asyncio.run(service.run(changed.session_id))
    assert any(not f.stale and f.run_id == second.run_id for f in second.findings)
    old = next(f for f in second.findings if f.finding_id == original.finding_id)
    assert old.stale and old.review_status == "rejected" and old.evidence_ids == original.evidence_ids
    assert service.store.report(first.session_id, 1).findings[0].review_status == "unreviewed"
    assert any(m.get("event_id") == "QA21-反对但未补证" for m in second.messages)


def test_qa22_new_fact_reruns_and_preserves_old_value_and_reason(tmp_path):
    model = FixtureModel(issue=True)
    service, _ = create_service(tmp_path, model=model)
    first = asyncio.run(service.run(service.create(request(actor_type="ai")).session_id))
    finding = first.findings[0]
    model.issue = False
    changed, needed = service.apply_event(first.session_id, EventInput(
        event_id="QA22-补充事实", expected_context_version=1, type="recheck", actor="D-AI验收", actor_type="ai",
        payload={"updates": [{"source_id": first.sources[0].source_id, "input": {
            "kind": "document", "content": "补充真实对象关系：三张卡片只展示，没有选择能力。",
            "evidence_kind": "design", "version": "补证-2"}}]}))
    assert needed
    second = asyncio.run(service.run(changed.session_id))
    assert not [f for f in second.findings if f.run_id == second.run_id and not f.stale]
    assert next(f for f in second.findings if f.finding_id == finding.finding_id).stale
    assert service.store.report(first.session_id, 1).findings[0].detection == finding.detection
    assert any("三张卡片只展示" in e.content and not e.stale for e in second.evidence)
    assert any(m.get("event_id") == "QA22-补充事实" for m in second.messages)


def test_qa24_resume_persists_review_questions_and_interrupts_running_action(tmp_path):
    service, _ = create_service(tmp_path, model=FixtureModel(issue=True))
    first = asyncio.run(service.run(service.create(request(actor_type="ai")).session_id))
    reviewed, _ = service.apply_event(first.session_id, EventInput(
        event_id="QA24-审核", expected_context_version=1, type="review_finding", actor="D-AI验收", actor_type="ai",
        payload={"finding_id": first.findings[0].finding_id, "review_status": "confirmed", "reason": "受控审核记录"}))
    question = Question(text="等待目标说明", reason="恢复时保留追问", blocking=True)
    reviewed.questions.append(question)
    action = Action(source_id=reviewed.sources[0].source_id, kind="click", selector="#save",
                    expected_state_id="old-state", reason="中断前动作", status="running")
    reviewed.actions.append(action)
    service.store.save(reviewed)
    restored, _ = create_service(tmp_path)
    resumed, needed = restored.apply_event(first.session_id, EventInput(
        event_id="QA24-恢复", expected_context_version=1, type="resume", actor="D-AI验收", actor_type="ai"))
    assert needed and resumed.findings[0].review_status == "confirmed"
    assert next(q for q in resumed.questions if q.question_id == question.question_id).answered is False
    assert next(a for a in resumed.actions if a.action_id == action.action_id).status == "interrupted"
    assert not restored.adapters.actions


def test_qa26_retired_function_with_formal_scope_evidence_is_not_fixed(tmp_path):
    """要求取消功能：正式材料证实已取消时应归档为不适用，而非继续要求旧控件出现。"""
    service, _ = create_service(tmp_path, model=FixtureModel(issue=True))
    first = asyncio.run(service.run(service.create(request(actor_type="ai")).session_id))
    previous = first.findings[0]
    changed, _ = service.apply_event(first.session_id, EventInput(
        event_id="QA26-取消原功能", expected_context_version=1, type="recheck", actor="D-AI验收", actor_type="ai",
        payload={"updates": [{"source_id": first.sources[0].source_id, "input": {
            "kind": "document", "content": "正式需求 v2：取消全部选择功能，原选择卡不再属于本版本范围。",
            "role": "product_spec", "version": "v2"}}]}))
    asyncio.run(service._read_sources(changed))
    fresh = [e for e in changed.evidence if e.context_version == changed.context_version and not e.stale]
    assert fresh

    class RetiredModel:
        async def complete(self, messages, **kwargs):
            return ModelCallResult(text=json.dumps({"items": [{
                "previous_finding_id": previous.finding_id, "resolution": "not_applicable",
                "reason": "正式需求 v2 取消原功能，旧问题退出新版范围；并未宣称问题修复。",
                "evidence_ids": [fresh[0].evidence_id]}]}, ensure_ascii=False),
                provider="test-fixture", model="QA26-范围取消固定响应", usage={}, request_id=None,
                latency_ms=0, json_mode_used=True)
    asyncio.run(service._recheck(changed, RetiredModel()))
    assert changed.rechecks[0].resolution == "not_applicable"
    assert next(f for f in changed.findings if f.finding_id == previous.finding_id).stale


def test_qa27_unselected_reference_remains_in_false_negative_denominator(tmp_path):
    service, _ = create_service(tmp_path)
    session = service.create(request(limits={"max_checks": 1}, actor_type="ai"))
    finished = asyncio.run(service.run(session.session_id))
    result = evaluate_session(finished, EvaluationLabels(dataset="QA27-冻结参考", findings=[
        {"label_id": "低相关性但真实存在的问题", "title_contains": ["冻结参考问题"]}]))
    assert result["finding_metrics"]["expected"] == result["finding_metrics"]["missed"] == 1
    assert result["finding_metrics"]["recall"] == 0
    assert any(c.execution_status == "not_executed" for c in finished.checks)


def test_qa28_same_texture_finding_merges_checks_without_losing_goal_states(tmp_path):
    service, _ = create_service(tmp_path)
    session = service.create(request(actor_type="ai"))
    for index in range(3):
        check = CheckItem(check_id=f"G0{index + 1}", ref=f"G0{index + 1}", kind="goal", run_id=session.run_id,
                          context_version=1, criteria_version=service.registry.version,
                          execution_status="executed", decision="observed_violation", reason="同一背景纹理干扰")
        session.checks.append(check)
        service._merge_finding(session, Finding(kind="issue", title="背景纹理过密影响识别",
            check_ids=[check.check_id], evidence_ids=["texture-evidence"], principle="目标",
            detection="同一区域背景纹理过密", description="降低前景可读性", suggestion="降低背景纹理密度",
            severity_reason="局部阅读受影响", object_ref="同一背景", mechanism="纹理干扰",
            change_action="降低背景纹理密度", run_id=session.run_id))
    assert len(session.findings) == 1 and len(session.findings[0].check_ids) == 3
    assert [c.decision for c in session.checks if c.ref.startswith("G0")] == ["observed_violation"] * 3


def test_qa32_finish_preserves_partial_report_and_per_item_reason(tmp_path):
    service, _ = create_service(tmp_path)
    first = service.create(request(actor_type="ai"))
    finished, _ = service.apply_event(first.session_id, EventInput(
        event_id="QA32-结束", expected_context_version=1, type="finish", actor="D-AI验收", actor_type="ai"))
    assert finished.report_completeness == "partial"
    assert all(c.execution_status == "not_executed" and c.decision is None and c.reason for c in finished.checks)
    assert service.store.report(finished.session_id, 1).report_completeness == "partial"


@pytest.mark.parametrize("proof", ["product_spec", "design_brief", "unrelated", "new_run_only", "stale", "old_context", "statement", "missing", "inactive"])
@pytest.mark.parametrize("route", ["model", "confirm_event"])
def test_qa26_scope_proof_guards_model_and_confirmation(tmp_path, proof, route):
    service, _ = create_service(tmp_path, model=FixtureModel(issue=True))
    first = asyncio.run(service.run(service.create(request(actor_type="ai")).session_id))
    previous = first.findings[0]
    changed, _ = service.apply_event(first.session_id, EventInput(
        event_id="新版范围", expected_context_version=1, type="recheck", actor="D-AI验收", actor_type="ai",
        payload={"updates": [{"source_id": first.sources[0].source_id, "input": {
            "kind": "document", "content": "正式新版要求取消全部选择功能，原选择卡不再适用。",
            "role": "design_brief" if proof == "design_brief" else "product_spec", "version": "v2"}}]}))
    asyncio.run(service._read_sources(changed))
    fresh = next(e for e in changed.evidence if e.context_version == changed.context_version and not e.stale)
    if proof in {"unrelated", "new_run_only"}:
        unrelated = SourceRecord(input=SourceInput(kind="document", role="product_spec", content="无关模块要求", version="v2"))
        changed.sources.append(unrelated)
        fresh.source_id = unrelated.source_id
        if proof == "new_run_only":
            # 同编号在新轮绑定其他来源，不能替旧轮问题建立正式需求关联。
            original_check = next(c for c in changed.checks if c.check_id in previous.check_ids and c.run_id == previous.run_id)
            changed.checks.append(original_check.model_copy(update={"run_id": changed.run_id,
                "context_version": changed.context_version, "stale": False, "source_ids": [unrelated.source_id]}))
    elif proof == "stale":
        fresh.stale = True
    elif proof == "old_context":
        fresh.context_version = 1
    elif proof == "statement":
        fresh.kind = "statement"
        changed.sources[0].input.role = "user_statement"
    elif proof == "inactive":
        changed.sources[0].active = False
    evidence_ids = [] if proof == "missing" else [fresh.evidence_id]
    good = proof in {"product_spec", "design_brief"}
    if route == "model":
        class Decision:
            async def complete(self, messages, **kwargs):
                return ModelCallResult(text=json.dumps({"items": [{
                    "previous_finding_id": previous.finding_id, "resolution": "not_applicable",
                    "reason": "受控取消条款核对", "evidence_ids": evidence_ids}]}), provider="test-fixture",
                    model="QA26边界固定响应", usage={}, request_id=None, latency_ms=0, json_mode_used=True)
        asyncio.run(service._recheck(changed, Decision()))
        assert changed.rechecks[0].resolution == ("not_applicable" if good else "cannot_determine")
    else:
        service.store.save(changed)
        event = EventInput(type="confirm_recheck", event_id="AI确认范围", expected_context_version=changed.context_version,
            actor="D-AI验收", actor_type="ai", payload={"recheck_id": changed.rechecks[0].recheck_id,
            "resolution": "not_applicable", "reason": "受控取消条款核对", "evidence_ids": evidence_ids})
        if good:
            confirmed, _ = service.apply_event(changed.session_id, event)
            assert confirmed.rechecks[0].resolution == "not_applicable"
            assert confirmed.messages[-1]["actor_type"] == "ai"
        else:
            with pytest.raises(EngineError) as error:
                service.apply_event(changed.session_id, event)
            assert error.value.code == "recheck_scope_evidence_required"
    assert previous.finding_id in {f.finding_id for f in changed.findings}


@pytest.mark.parametrize("last,expected", [("insufficient_evidence", "insufficient_evidence"), ("observed_violation", "observed_violation")])
def test_qa05_qa06_three_child_goals_preserve_unknown_and_violation(tmp_path, last, expected):
    service, _ = create_service(tmp_path)
    session = asyncio.run(service.run(service.create(request(actor_type="ai")).session_id))
    evidence_ids = [session.evidence[0].evidence_id]
    session.goals = [Constraint(id="G02", text="三个子目标", evidence_ids=evidence_ids),
                     *(Constraint(id=f"G02.{i}", text=f"子目标{i}", parent_id="G02", evidence_ids=evidence_ids) for i in range(1, 4))]
    service._prepare_checks(session)
    for c in session.checks:
        if c.ref.startswith("G02"):
            c.execution_status, c.decision, c.reason = "executed", "met", "受控三子项"
            c.evidence_ids = evidence_ids
    next(c for c in session.checks if c.ref == "G02.3").decision = last
    service._aggregate_goals(session)
    assert next(c for c in session.checks if c.ref == "G02").decision == expected
    assert next(c for c in session.checks if c.ref == "E07").decision == expected
