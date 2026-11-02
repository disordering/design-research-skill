"""Contract/workflow fixtures, not model-accuracy or real-user evidence."""

import asyncio
import json

import pytest

from engine.errors import EngineError
from engine.model import ModelCallResult
from engine.session_adapters import Capture
from engine.session_contracts import (
    Action, EventInput, Finding, Question, SessionCreate, SourceInput, Constraint,
)
from engine.session_report import markdown_report
from engine.session_service import SessionService
from engine.session_store import SessionStore


class FixtureAdapters:
    def __init__(self, blocked=False, require_authorization=False):
        self.blocked = blocked
        self.require_authorization = require_authorization
        self.actions = []
        self.reads = 0

    def capabilities(self):
        return {"fixture": {"is_test_fixture": True}}

    async def read(self, session_id, source):
        self.reads += 1
        if self.blocked and source.input.kind == "website":
            raise EngineError("access_denied", "需要权限", status_code=403)
        return Capture(
            content=source.input.content or "测试夹具：保存设置按钮",
            locator={"url": source.input.reference, "is_test_fixture": True},
            state_id="fixture-state",
        )

    async def needs_authorization(self, *args):
        return self.require_authorization

    async def act(self, session_id, source, action, *, authorized):
        self.actions.append((action.action_id, authorized))
        return Capture(content="夹具动作结果", locator={"is_test_fixture": True}, state_id="fixture-state-after")

    async def close(self):
        pass


class FixtureModel:
    is_stub = True

    def __init__(self, issue=False, invalid_evidence=False, question=False, action=False, omit=False, recheck_without_evidence=False):
        self.issue = issue
        self.invalid_evidence = invalid_evidence
        self.question = question
        self.action = action
        self.omit = omit
        self.recheck_without_evidence = recheck_without_evidence
        self.operations = []

    async def complete(self, messages, **kwargs):
        data = json.loads(messages[1]["content"][0]["text"])
        self.operations.append(data["operation"])
        context = data["context"]
        eid = context["evidence"][0]["evidence_id"]
        if data["operation"] == "understand":
            result = {"task_summary": context["purpose"]}
        elif data["operation"] == "plan_checks":
            result = {"items": [{
                "ref": c["ref"], "applicability": "applicable",
                "reason": "契约夹具计划，不证明模型效果",
                "source_ids": [s["source_id"] for s in context["sources"]],
                "evidence_ids": [eid], "evidence_needed": [], "object_refs": ["fixture"],
            } for c in data["checks"]]}
        elif data["operation"] == "plan":
            result = {"task_summary": context["purpose"], "ready_for_review": True}
            if self.question:
                result.update({"ready_for_review": False, "questions": [{
                    "text": "请说明目标用户", "reason": "影响术语适用性", "blocking": True,
                }]})
                self.question = False
            if self.action and not context["actions"]:
                source = next(s for s in context["sources"] if s["kind"] == "website")
                evidence = next(e for e in context["evidence"] if e["source_id"] == source["source_id"])
                result["action"] = {
                    "source_id": source["source_id"], "kind": "click", "selector": "#save",
                    "expected_state_id": evidence["state_id"], "reason": "测试保存",
                    "requires_explicit_authorization": True,
                }
        elif data["operation"] == "judge":
            judgments = []
            findings = []
            for check in data["checks"]:
                decision = "met" if check["kind"] == "goal" else "no_conflict" if check["kind"] == "conflict" else "no_visible_issue"
                if self.issue and check["ref"] == "R17":
                    decision = "candidate_issue"
                    findings.append({
                        "kind": "issue", "title": "夹具选择状态问题", "check_ids": [check["check_id"]],
                        "evidence_ids": ["nonexistent"] if self.invalid_evidence else [eid],
                        "principle": "测试依据", "detection": "测试现象", "description": "测试影响",
                        "suggestion": "测试修改", "severity_reason": "测试任务局部受阻",
                        "object_ref": "fixture-control", "mechanism": "selection", "change_action": "show-state",
                    })
                judgments.append({
                    "check_id": check["check_id"], "decision": decision, "reason": "契约测试判断，非模型效果",
                    "evidence_ids": [eid],
                })
            result = {"judgments": judgments[1:] if self.omit else judgments, "findings": findings}
        elif data["operation"] == "verify":
            result = {"supported_finding_ids": [f["finding_id"] for f in data["findings"]]}
        else:
            result = {"items": [{
                "previous_finding_id": f["finding_id"], "resolution": "resolved",
                "reason": "夹具复审结果", "evidence_ids": [] if self.recheck_without_evidence else [eid],
            } for f in data["previous_findings"]]}
        return ModelCallResult(
            text=json.dumps(result, ensure_ascii=False), provider="test-fixture",
            model="contract-fixture", usage={}, request_id=None, latency_ms=1, json_mode_used=True,
        )


def create_service(tmp_path, model=None, adapters=None, factory=None):
    model = model or FixtureModel()
    service = SessionService(
        SessionStore(tmp_path), adapters=adapters or FixtureAdapters(),
        model_factory=factory or (lambda request: model),
    )
    return service, model


def request(website=False, **kwargs):
    return SessionCreate(
        purpose="检查保存设置", sources=[SourceInput(
            kind="website" if website else "document",
            reference="https://example.test/" if website else "",
            content="" if website else "测试规则：保存成功后显示结果。",
        )], **kwargs,
    )


def test_raw_input_runs_through_all_methods_and_report_versions(tmp_path):
    service, model = create_service(tmp_path)
    session = service.create(request())
    finished = asyncio.run(service.run(session.session_id))
    assert finished.status == "completed"
    assert finished.report_completeness == "complete"
    assert len(finished.checks) == 32
    assert all(c.execution_status == "executed" for c in finished.checks)
    assert finished.report_version == 1
    assert model.operations == [
        "understand", "plan_checks", "plan_checks", "plan", "judge", "judge",
    ]
    assert all(call.get("call_id") and call.get("stage") for call in finished.model_calls)
    assert all("evidence_ids" in call.get("input", {}) for call in finished.model_calls)
    assert all(call.get("output") for call in finished.model_calls)
    assert service.store.report(session.session_id, 1).report_version == 1
    assert "contract-fixture" in markdown_report(finished)


def test_access_failure_is_partial_and_not_a_product_finding(tmp_path):
    service, _ = create_service(tmp_path, adapters=FixtureAdapters(blocked=True))
    finished = asyncio.run(service.run(service.create(request(website=True)).session_id))
    assert finished.sources[0].acquisition_status == "blocked"
    assert finished.report_completeness == "partial"
    assert not finished.findings


def test_missing_model_configuration_never_creates_stub_judgments(tmp_path):
    def missing(_):
        raise EngineError("api_key_missing", "missing", status_code=503)
    service, _ = create_service(tmp_path, factory=missing)
    finished = asyncio.run(service.run(service.create(request()).session_id))
    assert finished.status == "awaiting_input"
    assert not finished.model_calls
    assert all(c.decision is None for c in finished.checks)
    assert finished.report_completeness == "partial"


def test_provider_rejection_detail_is_preserved_without_fake_judgments(tmp_path):
    def rejected(_):
        raise EngineError(
            "model_request_rejected", "Model provider rejected the request with HTTP 403.",
            status_code=502, details={"upstream": '{"code":"AccessDenied.Unpurchased"}'},
        )
    service, _ = create_service(tmp_path, factory=rejected)
    finished = asyncio.run(service.run(service.create(request()).session_id))
    assert finished.report_completeness == "partial"
    assert not finished.findings
    assert any("AccessDenied.Unpurchased" in warning for warning in finished.warnings)


def test_question_reply_changes_context_and_restarts_actual_checks(tmp_path):
    service, model = create_service(tmp_path, model=FixtureModel(question=True))
    first = asyncio.run(service.run(service.create(request()).session_id))
    assert first.status == "awaiting_input"
    question = next(q for q in first.questions if not q.answered)
    event = EventInput(event_id="answer", expected_context_version=1, type="reply",
                       payload={"question_id": question.question_id, "text": "第一次使用的学生"})
    updated, run = service.apply_event(first.session_id, event)
    assert run and updated.context_version == 2 and updated.run_id != first.run_id
    second = asyncio.run(service.run(first.session_id))
    assert second.status == "completed"
    assert second.report_version == 2
    assert service.store.report(first.session_id, 1).context_version == 1


def test_goal_change_invalidates_old_results_and_duplicate_event_does_not_repeat(tmp_path):
    service, _ = create_service(tmp_path)
    first = asyncio.run(service.run(service.create(request()).session_id))
    event = EventInput(event_id="goal", expected_context_version=1, type="change_goal", payload={"purpose": "检查退出恢复"})
    new, run = service.apply_event(first.session_id, event)
    assert run and new.request.purpose == "检查退出恢复"
    assert all(c.stale for c in new.checks if c.run_id == first.run_id)
    repeated, rerun = service.apply_event(first.session_id, event)
    assert not rerun and repeated.context_version == 2
    assert repeated.revision == new.revision
    with pytest.raises(EngineError) as error:
        service.apply_event(first.session_id, event.model_copy(update={"event_id": "different"}))
    assert error.value.code == "context_version_conflict"


def test_stop_preserves_results_and_unexecuted_checks(tmp_path):
    service, _ = create_service(tmp_path)
    session = service.create(request())
    stopped, run = service.apply_event(session.session_id, EventInput(
        event_id="stop", expected_context_version=1, type="cancel",
    ))
    assert not run and stopped.status == "cancelled"
    assert stopped.report_completeness == "partial"
    assert all(c.decision is None and c.execution_status == "not_executed" for c in stopped.checks)


def test_action_is_not_executed_until_authorized_and_event_is_idempotent(tmp_path):
    adapters = FixtureAdapters(require_authorization=True)
    service, _ = create_service(tmp_path, model=FixtureModel(action=True), adapters=adapters)
    first = asyncio.run(service.run(service.create(request(website=True)).session_id))
    assert not adapters.actions
    assert first.status == "awaiting_input"
    action = first.actions[0]
    event = EventInput(event_id="permit", expected_context_version=1, type="authorize_action",
                       payload={"action_id": action.action_id, "approved": True})
    service.apply_event(first.session_id, event)
    second = asyncio.run(service.run(first.session_id))
    assert adapters.actions == [(action.action_id, True)]
    assert second.actions[0].status == "executed"
    assert not service.apply_event(first.session_id, event)[1]


def test_changed_context_cancels_previous_authorization(tmp_path):
    service, _ = create_service(tmp_path, model=FixtureModel(action=True), adapters=FixtureAdapters(require_authorization=True))
    first = asyncio.run(service.run(service.create(request(website=True)).session_id))
    service.apply_event(first.session_id, EventInput(
        event_id="goal", expected_context_version=1, type="change_goal", payload={"purpose": "仅查看文字"},
    ))
    with pytest.raises(EngineError) as error:
        service.apply_event(first.session_id, EventInput(
            event_id="permit", expected_context_version=2, type="authorize_action",
            payload={"action_id": first.actions[0].action_id, "approved": True},
        ))
    assert error.value.code == "authorization_stale"


def test_invalid_finding_evidence_cannot_become_a_confirmed_issue(tmp_path):
    service, _ = create_service(tmp_path, model=FixtureModel(issue=True, invalid_evidence=True))
    finished = asyncio.run(service.run(service.create(request()).session_id))
    assert not finished.findings
    assert next(c for c in finished.checks if c.ref == "R17").decision == "insufficient_evidence"


def test_missing_model_judgments_are_failed_not_passed(tmp_path):
    service, _ = create_service(tmp_path, model=FixtureModel(omit=True))
    finished = asyncio.run(service.run(service.create(request()).session_id))
    failed = [c for c in finished.checks if c.execution_status == "failed"]
    assert len(failed) == 2 and all(c.decision is None for c in failed)
    assert finished.report_completeness == "partial"


def test_review_records_do_not_overwrite_model_severity(tmp_path):
    service, _ = create_service(tmp_path, model=FixtureModel(issue=True))
    first = asyncio.run(service.run(service.create(request()).session_id))
    finding = first.findings[0]
    reviewed, run = service.apply_event(first.session_id, EventInput(
        event_id="review", expected_context_version=1, type="review_finding", actor="reviewer-a",
        payload={"finding_id": finding.finding_id, "review_status": "confirmed", "reason": "核对了证据", "severity": "high"},
    ))
    assert not run
    assert reviewed.findings[0].severity == "medium"
    assert reviewed.findings[0].human_severity == "high"
    assert reviewed.findings[0].reviewer == "reviewer-a"


def test_new_version_does_not_auto_resolve_old_finding(tmp_path):
    model = FixtureModel(issue=True, recheck_without_evidence=True)
    service, _ = create_service(tmp_path, model=model)
    first = asyncio.run(service.run(service.create(request()).session_id))
    model.issue = False
    changed, _ = service.apply_event(first.session_id, EventInput(
        event_id="v2", expected_context_version=1, type="recheck",
        payload={"updates": [{"source_id": first.sources[0].source_id,
                              "input": {"kind": "document", "content": "新版方案", "version": "v2"}}]},
    ))
    second = asyncio.run(service.run(first.session_id))
    assert second.rechecks[0].resolution == "cannot_determine"
    assert second.rechecks[0].human_confirmation == "unreviewed"
    assert all(e.stale for e in second.evidence if e.source_id == first.sources[0].source_id and e.context_version == 1)


def test_resource_limit_is_reported_not_silently_skipped(tmp_path):
    service, _ = create_service(tmp_path)
    finished = asyncio.run(service.run(service.create(request(limits={"max_checks": 8})).session_id))
    assert sum(c.execution_status == "executed" for c in finished.checks) == 8
    assert sum(c.execution_status == "not_executed" for c in finished.checks) == 24
    assert finished.report_completeness == "partial"


def test_planner_priorities_reorder_existing_checks_instead_of_silently_ignoring_them(tmp_path):
    from engine.session_contracts import AgentStep
    service, _ = create_service(tmp_path)
    session = service.create(request(limits={"max_checks": 2}))
    service._accept_plan(session, AgentStep(task_summary="Check the flow", priority_refs=["E01", "E07"]))
    assert [c.ref for c in session.checks[:2]] == ["E01", "E07"]
    assert len(session.checks) == 32


def test_noop_action_keeps_before_after_evidence_without_a_verified_path(tmp_path):
    class Noop(FixtureAdapters):
        async def act(self, session_id, source, action, *, authorized):
            return Capture(content="Same fixture", locator={}, state_id="fixture-state")

    async def run():
        service, _ = create_service(tmp_path, adapters=Noop())
        session = service.create(request(website=True, allow_interaction=True))
        await service._read_sources(session)
        action = Action(
            source_id=session.sources[0].source_id, kind="click", selector="#next",
            expected_state_id="fixture-state", reason="Try Next", requires_explicit_authorization=False,
        )
        assert await service._perform_action(session, action)
        assert action.status == "executed"
        assert action.outcome == "no_observed_change"
        assert len(action.evidence_ids) == 2
        assert not session.transitions
        exported = markdown_report(session)
        assert "未观察到状态变化" in exported
        assert action.evidence_ids[0] in exported and action.evidence_ids[1] in exported
    asyncio.run(run())


def test_partial_action_does_not_become_a_verified_transition(tmp_path):
    class Partial(FixtureAdapters):
        async def act(self, session_id, source, action, *, authorized):
            return Capture(content="Incomplete", locator={}, state_id="different-state", partial=True)

    async def run():
        service, _ = create_service(tmp_path, adapters=Partial())
        session = service.create(request(website=True, allow_interaction=True))
        await service._read_sources(session)
        action = Action(
            source_id=session.sources[0].source_id, kind="click", selector="#next",
            expected_state_id="fixture-state", reason="Try Next", requires_explicit_authorization=False,
        )
        await service._perform_action(session, action)
        assert action.outcome == "observation_incomplete"
        assert not session.transitions
    asyncio.run(run())


def test_check_budget_is_not_reset_when_continuing_the_same_run(tmp_path):
    async def run():
        service, model = create_service(tmp_path)
        session = service.create(request(limits={"max_checks": 2}))
        await service._read_sources(session)
        await service._judge(session, model)
        calls = len(model.operations)
        for check in session.checks:
            if check.execution_status == "not_executed":
                check.execution_status = "planned"
        await service._judge(session, model)
        assert len(model.operations) == calls
        assert sum(c.execution_status == "executed" for c in session.checks) == 2
    asyncio.run(run())


def test_review_instruction_alone_cannot_become_a_formal_product_requirement(tmp_path):
    from engine.session_contracts import AgentStep

    async def run():
        service, _ = create_service(tmp_path)
        session = service.create(request(design_purpose="帮助用户管理健身器材并保留购买意愿"))
        await service._read_sources(session)
        instruction = next(e for e in session.evidence if any(
            s.source_id == e.source_id and s.input.reference == "user://initial_purpose"
            for s in session.sources
        ))
        design = next(e for e in session.evidence if any(
            s.source_id == e.source_id and s.input.reference == "user://design_purpose"
            for s in session.sources
        ))
        step = AgentStep(task_summary="Task", goals=[Constraint(
            id="G01", text="Product goal", evidence_ids=[instruction.evidence_id],
        )])
        with pytest.raises(EngineError) as error:
            service._accept_plan(session, step)
        assert error.value.code == "plan_review_scope_constraint"
        step.goals[0].evidence_ids = [design.evidence_id]
        service._accept_plan(session, step)
        assert session.goals[0].evidence_ids == [design.evidence_id]
    asyncio.run(run())


def test_planned_not_applicable_check_does_not_turn_missing_execution_into_failure(tmp_path):
    class InsufficientJudge(FixtureModel):
        async def complete(self, messages, **kwargs):
            data = json.loads(messages[1]["content"][0]["text"])
            assert data["operation"] == "judge"
            check = data["checks"][0]
            eid = data["context"]["evidence"][0]["evidence_id"]
            return ModelCallResult(
                text=json.dumps({
                    "judgments": [{
                        "check_id": check["check_id"],
                        "decision": "insufficient_evidence",
                        "reason": "No runtime evidence was observed",
                        "evidence_ids": [eid],
                    }],
                    "findings": [],
                }),
                provider="test-fixture", model="fixture", usage={}, request_id=None,
                latency_ms=1, json_mode_used=True,
            )

    async def run():
        service, model = create_service(tmp_path, model=InsufficientJudge())
        session = service.create(request(limits={"max_checks": 1}))
        await service._read_sources(session)
        service._prepare_checks(session, ["R21"])
        check = next(c for c in session.checks if c.ref == "R21")
        check.applicability = "not_applicable"
        check.plan_reason = "No error-state object exists in this material."
        check.evidence_ids = [session.evidence[0].evidence_id]
        await service._judge(session, model)
        assert check.execution_status == "executed"
        assert check.decision == "not_applicable"
        assert not session.findings
    asyncio.run(run())


@pytest.mark.parametrize("repair_succeeds", [False, True])
def test_hallucinated_state_is_repaired_once_with_real_context_or_rejected(tmp_path, repair_succeeds):
    class InvalidPlan(FixtureModel):
        def __init__(self):
            super().__init__()
            self.plan_attempts = 0

        async def complete(self, messages, **kwargs):
            data = json.loads(messages[1]["content"][0]["text"])
            if data["operation"] != "plan" or data["context"]["actions"]:
                return await super().complete(messages, **kwargs)
            self.plan_attempts += 1
            source = next(s for s in data["context"]["sources"] if s["kind"] == "website")
            result = {
                "task_summary": "Observe the fixture", "ready_for_review": False,
                "action": {
                    "kind": "observe", "source_id": source["source_id"],
                    "expected_state_id": source["latest_state_id"] if repair_succeeds and self.plan_attempts == 2 else "invented-state",
                    "reason": "Read safely", "requires_explicit_authorization": False,
                },
            }
            return ModelCallResult(
                text=json.dumps(result), provider="test-fixture", model="invalid-plan-fixture",
                usage={}, request_id=None, latency_ms=1, json_mode_used=True,
            )

    async def run():
        model = InvalidPlan()
        service, _ = create_service(tmp_path, model=model)
        session = service.create(request(website=True, limits={"max_checks": 1}))
        finished = await service.run(session.session_id)
        assert model.plan_attempts == 2
        assert next(c for c in finished.model_calls if c["operation"] == "plan" and c["attempt"] == 2)
        if repair_succeeds:
            assert finished.actions[0].status == "executed"
            assert finished.actions[0].outcome == "read"
            assert not finished.transitions
            assert sum(c.execution_status == "executed" for c in finished.checks) == 1
        else:
            assert not finished.actions
            assert sum(c.execution_status == "executed" for c in finished.checks) == 1
            assert finished.run_limitations
            assert finished.report_completeness == "partial"
    asyncio.run(run())


def test_broken_planning_stops_interaction_but_keeps_evidence_based_review(tmp_path):
    class BrokenPlan(FixtureModel):
        async def complete(self, messages, **kwargs):
            data = json.loads(messages[1]["content"][0]["text"])
            if data["operation"] != "plan":
                return await super().complete(messages, **kwargs)
            return ModelCallResult(text="{}", provider="test-fixture", model="broken-plan-fixture",
                                   usage={}, request_id=None, latency_ms=1, json_mode_used=True)

    service, _ = create_service(tmp_path, model=BrokenPlan())
    finished = asyncio.run(service.run(service.create(request()).session_id))
    assert not finished.actions
    assert sum(c.execution_status == "executed" for c in finished.checks) == 32
    assert finished.report_completeness == "partial" and finished.run_limitations
    updated, _ = service.apply_event(finished.session_id, EventInput(
        event_id="continue", expected_context_version=1, type="resume",
    ))
    assert updated.run_id != finished.run_id
    assert not updated.run_limitations
    assert service.store.report(finished.session_id, 1).run_limitations


def test_full_raw_material_is_kept_while_model_indexes_are_bounded(tmp_path):
    service, _ = create_service(tmp_path)
    session = service.create(request())
    raw = "Original material\n" * 30000 + "END-OF-ORIGINAL"
    node_ids = [f"1:{index}" for index in range(5000)]
    service._capture(session, session.sources[0], Capture(
        content="Bounded excerpt", locator={"node_ids": node_ids}, state_id="large-material",
        raw_content=raw,
    ))
    evidence = session.evidence[0]
    path, _ = service.store.artifact(session.session_id, evidence.raw_artifact_id)
    assert path.read_text(encoding="utf-8") == raw
    context = service._model_context(session)
    assert len(context["evidence"][0]["locator"]["node_ids"]) == 128
    assert context["evidence"][0]["locator"]["node_ids_total"] == 5000
    assert len(evidence.locator["node_ids"]) == 5000


def test_coordinate_plan_requires_a_current_image_actually_received_by_the_model(tmp_path):
    import io
    from PIL import Image
    from engine.session_contracts import AgentStep

    service, _ = create_service(tmp_path)
    session = service.create(request(website=True))
    image = io.BytesIO()
    Image.new("RGB", (300, 500), "red").save(image, "PNG")
    service._capture(session, session.sources[0], Capture(
        content="Fixture screenshot", locator={}, state_id="current-image", image=image.getvalue(),
    ))
    step = AgentStep(task_summary="Fixture task", action=Action(
        source_id=session.sources[0].source_id, kind="click", x=0.5, y=0.5,
        expected_state_id="current-image", reason="Fixture click", requires_explicit_authorization=False,
    ))
    with pytest.raises(EngineError) as error:
        service._validate_plan(session, step, image_input_ids=[])
    assert error.value.code == "plan_image_unavailable"
    service._validate_plan(session, step, image_input_ids=[session.evidence[0].evidence_id])


def test_noop_click_is_not_replayed_at_the_same_state_and_target(tmp_path):
    from engine.session_contracts import AgentStep
    service, _ = create_service(tmp_path)
    session = service.create(request(website=True))
    service._capture(session, session.sources[0], Capture(
        content="Fixture", locator={}, state_id="same-state",
    ))
    previous = Action(
        source_id=session.sources[0].source_id, kind="click", selector="#fixture",
        expected_state_id="same-state", reason="Try once", status="executed",
        outcome="no_observed_change", run_id=session.run_id,
    )
    session.actions.append(previous)
    step = AgentStep(task_summary="Fixture", action=previous.model_copy(update={"status": "pending"}))
    with pytest.raises(EngineError) as error:
        service._validate_plan(session, step)
    assert error.value.code == "plan_noop_repeat"
    step.action.selector = "#different"
    service._validate_plan(session, step)


def test_noop_prototype_click_does_not_establish_a_dynamic_product_defect(tmp_path):
    class NoopJudgment(FixtureModel):
        async def complete(self, messages, **kwargs):
            data = json.loads(messages[1]["content"][0]["text"])
            assert data["operation"] == "judge"
            check_id = data["checks"][0]["check_id"]
            eid = data["context"]["evidence"][0]["evidence_id"]
            result = {
                "judgments": [{"check_id": check_id, "decision": "candidate_issue",
                               "reason": "Only a no-op was observed", "evidence_ids": [eid]}],
                "findings": [{
                    "kind": "issue", "title": "Unverified navigation failure",
                    "check_ids": [check_id], "evidence_ids": [eid],
                    "principle": "Fixture", "detection": "No effect", "description": "Task allegedly blocked",
                    "suggestion": "Fix link", "severity_reason": "Fixture consequence",
                }],
            }
            return ModelCallResult(text=json.dumps(result), provider="test-fixture",
                                   model="noop-fixture", usage={}, request_id=None, latency_ms=1, json_mode_used=True)

    async def run():
        service, model = create_service(tmp_path, model=NoopJudgment())
        session = service.create(SessionCreate(
            purpose="Fixture flow test", limits={"max_checks": 1},
            sources=[SourceInput(kind="figma_prototype", reference="https://www.figma.com/proto/abc/Test")],
        ))
        source = session.sources[0]
        service._capture(session, source, Capture(content="Fixture canvas", locator={}, state_id="same-state"))
        session.actions.append(Action(
            source_id=source.source_id, kind="click", x=0.5, y=0.95,
            expected_state_id="same-state", reason="Fixture attempt", status="executed",
            outcome="no_observed_change", run_id=session.run_id,
        ))
        service._prepare_checks(session, ["E03"])
        await service._judge(session, model)
        assert not session.findings
        assert next(c for c in session.checks if c.ref == "E03").decision == "insufficient_evidence"
        assert any("未核实命中真实热点" in warning for warning in session.warnings)
    asyncio.run(run())


def test_access_recovery_resolves_only_its_own_question_not_business_approval(tmp_path):
    service, _ = create_service(tmp_path)
    session = service.create(request(website=True))
    source = session.sources[0]
    service._question(session, "Restore access", "Access failed", blocking=True,
                      kind="access", source_id=source.source_id)
    service._question(session, "Confirm requirement", "Business ambiguity", blocking=True)
    service._capture(session, source, Capture(content="Partial", locator={}, state_id="partial", partial=True))
    assert not session.questions[0].answered
    service._capture(session, source, Capture(content="Readable", locator={}, state_id="ready"))
    assert session.questions[0].answered
    assert session.questions[0].answer_actor == "program"
    assert not session.questions[1].answered


def test_tool_recovery_questions_are_nonblocking_and_natural_replies_can_resolve_context(tmp_path):
    from engine.session_contracts import AgentStep, QuestionResolution
    service, _ = create_service(tmp_path)
    session = service.create(request())
    service._capture(session, session.sources[0], Capture(content="Known fact", locator={}, state_id="fact"))
    service._accept_plan(session, AgentStep(task_summary="Fixture", questions=[
        Question(text="Where to click?", reason="Tool recovery", kind="tool_recovery", blocking=True),
    ]))
    assert not session.questions[0].blocking
    service._question(session, "Who uses it?", "Terminology", blocking=True)
    question = session.questions[-1]
    service._accept_plan(session, AgentStep(task_summary="Fixture", question_resolutions=[
        QuestionResolution(question_id=question.question_id, reason="New material describes the user",
                           evidence_ids=[session.evidence[0].evidence_id]),
    ]))
    assert question.answered and question.answer_actor == "program"
    assert "根据材料推定" in question.answer


def test_model_question_resolution_cannot_grant_authorization(tmp_path):
    from engine.session_contracts import AgentStep, QuestionResolution
    service, _ = create_service(tmp_path)
    session = service.create(request())
    service._capture(session, session.sources[0], Capture(content="Fact", locator={}, state_id="fact"))
    service._question(session, "Authorize action", "Sensitive action", blocking=True,
                      kind="authorization", action_id="fixture-action")
    with pytest.raises(EngineError) as error:
        service._accept_plan(session, AgentStep(task_summary="Fixture", question_resolutions=[
            QuestionResolution(question_id=session.questions[0].question_id, reason="Model tries to approve",
                               evidence_ids=[session.evidence[0].evidence_id]),
        ]))
    assert error.value.code == "plan_question_resolution_invalid"
    assert not session.questions[0].answered


@pytest.mark.parametrize("matches_intent", [False, True])
def test_coordinate_grounding_uses_marked_image_and_never_clicks_during_verification(tmp_path, matches_intent):
    import io
    from PIL import Image

    class Grounder(FixtureModel):
        supports_images = True

        async def complete(self, messages, **kwargs):
            data = json.loads(messages[1]["content"][0]["text"])
            assert data["operation"] == "ground_action"
            assert sum(item["type"] == "image_url" for item in messages[1]["content"]) == 2
            result = {
                "evidence_id": data["evidence_id"], "matches_intent": matches_intent,
                "observed_target": "Cancel" if matches_intent else "Save",
                "reason": "Fixture grounding, not model efficacy",
            }
            return ModelCallResult(text=json.dumps(result), provider="test-fixture",
                                   model="grounding-fixture", usage={}, request_id=None, latency_ms=1, json_mode_used=True)

    async def run():
        adapters = FixtureAdapters()
        service, model = create_service(tmp_path, adapters=adapters, model=Grounder())
        session = service.create(request(website=True))
        raw = io.BytesIO()
        Image.new("RGB", (300, 500), "white").save(raw, "PNG")
        service._capture(session, session.sources[0], Capture(
            content="Fixture screenshot", locator={}, state_id="current", image=raw.getvalue(),
        ))
        action = Action(source_id=session.sources[0].source_id, kind="click", x=0.5, y=0.9,
                        expected_state_id="current", target_label="Cancel", reason="Try Cancel")
        assert await service._ground_action(session, model, action) is matches_intent
        assert not adapters.actions
        path, _ = service.store.artifact(session.session_id, action.target_marker_artifact_id)
        assert Image.open(path).getpixel((149, 449)) == (255, 0, 0)
        assert action.observed_target == ("Cancel" if matches_intent else "Save")
        if not matches_intent:
            assert session.actions[0].status == "blocked"
            assert session.actions[0].error.startswith("action_target_mismatch:")
    asyncio.run(run())
@pytest.mark.parametrize("child_decision,expected", [
    ("insufficient_evidence", "insufficient_evidence"),
    ("observed_violation", "observed_violation"),
    ("met", "met"),
])
def test_compound_goal_cannot_hide_unknown_or_violation(tmp_path, child_decision, expected):
    service, _ = create_service(tmp_path)
    session = asyncio.run(service.run(service.create(request()).session_id))
    eid = session.evidence[0].evidence_id
    session.goals = [
        Constraint(id="G02", text="复合目标", evidence_ids=[eid]),
        Constraint(id="G02.1", text="焦点", evidence_ids=[eid], parent_id="G02"),
        Constraint(id="G02.2", text="可读", evidence_ids=[eid], parent_id="G02"),
    ]
    service._prepare_checks(session)
    for check in session.checks:
        if check.ref.startswith("G"):
            check.execution_status = "executed"
            check.decision = "met"
            check.evidence_ids = [eid]
    next(c for c in session.checks if c.ref == "G02.2").decision = child_decision
    service.store.save(session)
    service._aggregate_goals(session)
    assert next(c for c in session.checks if c.ref == "G02").decision == expected
    assert next(c for c in session.checks if c.ref == "E07").decision == expected


def test_tall_figma_design_reads_visible_leaf_screens_but_business_text_does_not(tmp_path):
    class FigmaBoardAdapters:
        def __init__(self):
            self.nodes = []

        def capabilities(self):
            return {"figma_board": {"is_test_fixture": True}}

        async def read(self, sid, source):
            return Capture(
                content='{"visible_text":[{"text":"Flow overview"}]}',
                locator={
                    "requested_node_id": "1:1", "node_id": "1:1",
                    "inspection_targets": [
                        {"node_id": "1:2", "name": "Screen one", "hidden": False, "container": False, "screen_like": True},
                        {"node_id": "1:3", "name": "Screen two", "hidden": False, "container": False, "screen_like": True},
                        {"node_id": "1:4", "name": "Screen three", "hidden": False, "container": False, "screen_like": True},
                        {"node_id": "1:5", "name": "Hidden", "hidden": True, "container": False, "screen_like": True},
                        {"node_id": "1:6", "name": "Decoration", "hidden": False, "container": False, "screen_like": False},
                    ],
                },
                state_id="figma-root",
            )

        async def act(self, sid, source, action, **kwargs):
            self.nodes.append(action.node_id)
            return Capture(
                content=f"screen {action.node_id}",
                locator={"requested_node_id": "1:1", "node_id": action.node_id},
                state_id=f"state-{action.node_id}",
            )

        async def close(self):
            pass

    design_adapter = FigmaBoardAdapters()
    design_service, _ = create_service(tmp_path / "design", adapters=design_adapter)
    design = design_service.create(SessionCreate(
        purpose="Check a Figma flow", limits={"max_images_per_call": 4},
        sources=[SourceInput(
            kind="figma_board", role="design",
            reference="https://www.figma.com/design/abc/Test?node-id=1-1",
        )],
    ))
    asyncio.run(design_service._read_sources(design))
    assert design_adapter.nodes == ["1:2", "1:3"]
    assert len([e for e in design.evidence if e.source_id == design.sources[0].source_id]) == 3
    root_ids = design_service._understanding_evidence(
        design, design_service._valid_evidence(design),
    )
    root_evidence = next(
        e.evidence_id for e in design.evidence
        if e.source_id == design.sources[0].source_id and e.locator.get("node_id") == "1:1"
    )
    assert [
        item.evidence_id for item in root_ids.values()
        if item.source_id == design.sources[0].source_id
    ] == [root_evidence]
    asyncio.run(design_service._read_sources(design))
    assert design_adapter.nodes == ["1:2", "1:3"]
    assert len([e for e in design.evidence if e.source_id == design.sources[0].source_id]) == 3

    business_adapter = FigmaBoardAdapters()
    business_service, _ = create_service(tmp_path / "business", adapters=business_adapter)
    business = business_service.create(SessionCreate(
        purpose="Read business rules", limits={"max_images_per_call": 4},
        sources=[SourceInput(
            kind="figma_board", role="product_spec",
            reference="https://www.figma.com/design/abc/Test?node-id=1-1",
        )],
    ))
    asyncio.run(business_service._read_sources(business))
    assert business_adapter.nodes == []
    assert len([e for e in business.evidence if e.source_id == business.sources[0].source_id]) == 1


def test_visual_capture_persists_metrics_and_overlay_artifacts(tmp_path):
    import io
    from PIL import Image

    service, _ = create_service(tmp_path)
    session = service.create(SessionCreate(
        purpose="Analyze a visual fixture",
        sources=[SourceInput(
            kind="figma_board", role="design",
            reference="https://www.figma.com/design/abc/Test?node-id=1-1",
        )],
    ))
    raw = io.BytesIO()
    Image.new("RGB", (600, 400), "white").save(raw, "PNG")
    evidence_ids = service._capture(session, session.sources[0], Capture(
        content='{"node":{"width":"600","height":"400"},"visible_text":[]}',
        locator={"node_id": "1:1", "requested_node_id": "1:1"},
        state_id="visual-state",
        image=raw.getvalue(),
        controls=[{
            "node_id": "1:2", "name": "Confirm", "kind": "button",
            "hidden": False, "x": 400, "y": 300, "width": 120, "height": 50,
        }],
    ))
    evidence = next(e for e in session.evidence if e.evidence_id == evidence_ids[0])
    assert evidence.analysis_artifact_id
    assert evidence.analysis["element_count"] == 1
    assert set(evidence.overlay_artifact_ids) == {
        "overlay-elements.png", "overlay-focus.png", "overlay-flow.png",
    }
    metrics_path, _ = service.store.artifact(session.session_id, evidence.analysis_artifact_id)
    assert metrics_path.exists()


def test_complete_screen_runs_single_image_technical_review_once(tmp_path):
    import io
    from PIL import Image
    from engine.session_contracts import ScreenTechnicalIssue, ScreenTechnicalReview
    from engine.session_screen_review import ScreenModelCall, ScreenReviewOutput

    class Reviewer:
        def __init__(self):
            self.calls = 0

        async def review(self, *, evidence, image_bytes, context, max_calls):
            self.calls += 1
            assert image_bytes
            assert max_calls > 0
            return ScreenReviewOutput(
                review=ScreenTechnicalReview(
                    evidence_id=evidence.evidence_id,
                    source_id=evidence.source_id,
                    node_id=evidence.locator["node_id"],
                    page_type="game_shop",
                    status="completed",
                    summary="Fixture per-screen review",
                    technical_metrics={"ui_element_count": 2, "ocr_block_count": 3},
                    issues=[ScreenTechnicalIssue(
                        rule_ids=["R14"],
                            heuristic_ids=["H05"],
                            title="九位数量值会截断",
                        severity="medium",
                        confidence=0.8,
                            principle="H05 错误预防",
                            user_impact="输入较长数量时用户无法核对完整数值",
                            detection="数量框按七位占位，但相邻汇总值达到九位",
                            description="数值变长后可能截断，提交前无法核对完整数量",
                            suggestion="按最长九位值扩展数量框并验证截断反馈",
                    )],
                ),
                artifacts={
                    "screen-ocr.json": (b"{}", "application/json"),
                    "screen-elements.json": (b"{}", "application/json"),
                    "screen-metrics.json": (b"{}", "application/json"),
                    "overlay-elements.png": (image_bytes, "image/png"),
                },
                calls=[ScreenModelCall(
                    operation="screen_audit", provider="fixture", model="fixture",
                    usage={}, latency_ms=1, request_id=None, raw_text='{"ok":true}',
                    status="validated", schema_name="AdvancedAuditResult",
                )],
            )

    class RealLikeModel:
        is_stub = False

    reviewer = Reviewer()
    service, _ = create_service(tmp_path)
    service.screen_reviewer = reviewer
    session = service.create(SessionCreate(
        purpose="Screen review fixture",
        limits={"max_model_calls": 10},
        sources=[SourceInput(
            kind="figma_board", role="design",
            reference="https://www.figma.com/design/abc/Test?node-id=1-1",
        )],
    ))
    raw = io.BytesIO()
    Image.new("RGB", (1062, 600), "white").save(raw, "PNG")
    service._capture(session, session.sources[0], Capture(
        content='{"node":{"width":"1062","height":"600"},"visible_text":[]}',
        locator={
            "node_id": "1:2", "requested_node_id": "1:1",
            "screenshot_width": 1062, "screenshot_height": 600,
        },
        state_id="screen-state",
        image=raw.getvalue(),
    ))
    asyncio.run(service._review_individual_screens(session, RealLikeModel()))
    assert reviewer.calls == 1
    assert len(session.screen_reviews) == 1
    review = session.screen_reviews[0]
    assert review.ocr_artifact_id and review.elements_artifact_id and review.metrics_artifact_id
    assert "overlay-elements.png" in review.overlay_artifact_ids
    assert review.model_call_ids
    assert session.model_calls[-1]["operation"] == "screen_audit"
    rendered = markdown_report(
        session, registry=service.registry, artifact_loader=service.store.artifact,
    )
    assert "## 五、逐屏技术审查" in rendered
    assert "Fixture per-screen review" in rendered
    assert "界面预览" in rendered
    assert '<img src="/api/review-sessions/' in rendered
    from engine.figma_report import build_figma_plugin_script, build_figma_report_plan

    plan = build_figma_report_plan(session, registry=service.registry)
    assert plan["source_root_node_id"] == "1:1"
    assert plan["file_key"] == "abc"
    assert plan["findings"][0]["title"] == "九位数量值会截断"
    assert plan["annotations"][0]["target_node_id"] == "1:2"
    script = build_figma_plugin_script(plan)
    assert "AI审查标注副本" in script and "figma.createAutoLayout" in script
    assert 'const annotationPrefix = `AI审查批注 · ${plan.source_title} · `;' in script
    assert "if (child.name.startsWith(annotationPrefix)) child.remove();" in script
    assert "${annotationPrefix}目标框" in script
    assert '"panel_bg":"#FFFFFF"' in script
    assert "annotationPanel" not in script
    asyncio.run(service._review_individual_screens(session, RealLikeModel()))
    assert reviewer.calls == 1


def test_screen_review_separates_business_values_from_interaction_evidence(tmp_path):
    from types import SimpleNamespace
    from engine.session_screen_review import (
        _interaction_heuristic_probes,
        _outside_screen_responsibility,
        _principle_with_heuristics,
    )
    from engine.advanced_contracts import (
        NormalizedBox, OCRBlock, OCRResult, UIElement, UIResult,
    )
    from engine.cv_metrics import compute_pipeline_metrics

    service, _ = create_service(tmp_path)
    business_only = SimpleNamespace(
        title="价格上限提示缺失",
        detection="策划价格尚未确认，输入有效范围未知",
        description="需要产品补充最大可输入数量和兑换比例",
        suggestion="补充价格规则和积分上限",
    )
    overflow = SimpleNamespace(
        title="九位结果值会截断",
        detection="占位符只有七位，但相邻结果值显示九位数字，文本接近容器边缘",
        description="数值变长后用户无法完整核对待分解结果",
        suggestion="按最长九位值扩展容器，并验证换行或截断反馈",
    )
    selection = SimpleNamespace(
        title="高亮物品与详情标题不一致",
        detection="左侧高亮 15 级，右侧详情显示 12 级",
        description="玩家无法确认当前选中对象",
        suggestion="让列表选中态和详情对象保持一致",
    )
    unit_copy = SimpleNamespace(
        title="分解可得数值无单位",
        detection="详情区显示 123456789，但没有说明是积分还是材料",
        description="玩家无法理解数值含义和换算关系",
        suggestion="补充单位、数值规则和消耗说明",
    )
    missing_output_copy = SimpleNamespace(
        title="分解结果与规则在点击前不可预知",
        detection="操作旁没有说明会得到什么、消耗什么",
        description="玩家无法判断分解产出与可分解条件",
        suggestion="补充积分数量、销毁范围和等级边界",
    )

    assert _outside_screen_responsibility(business_only)
    assert _outside_screen_responsibility(unit_copy)
    assert _outside_screen_responsibility(missing_output_copy)
    assert not _outside_screen_responsibility(overflow)
    assert not _outside_screen_responsibility(selection)

    finding = SimpleNamespace(
        rule_ids=["R17"], principle="选中状态与详情内容冲突",
    )
    heuristic_ids, principle = _principle_with_heuristics(
        finding, service.registry.criteria,
    )
    assert heuristic_ids == ["H06"]
    assert "H06 识别而非回忆" in principle

    from PIL import Image
    image = Image.new("RGB", (1000, 400), "white")
    ui = UIResult(elements=[
        UIElement(
            id="E1", label="数量输入", role="input", interactable=True,
            bbox=NormalizedBox(x=0.1, y=0.2, width=0.1, height=0.04),
        ),
        UIElement(
            id="E2", label="15级吴山石", role="list_item", state="selected",
            bbox=NormalizedBox(x=0.1, y=0.5, width=0.2, height=0.1),
        ),
    ])
    ocr = OCRResult(blocks=[
        OCRBlock(
            text="0000000",
            bbox=NormalizedBox(x=0.1, y=0.2, width=0.05, height=0.04),
            estimated_height_px=16,
        ),
        OCRBlock(
            text="123456789",
            bbox=NormalizedBox(x=0.1, y=0.3, width=0.07, height=0.04),
            estimated_height_px=16,
        ),
    ])
    metrics = compute_pipeline_metrics(image, ui.elements, ocr.blocks)
    probes = _interaction_heuristic_probes(image, ui, ocr, metrics)
    assert probes["numeric_adaptation"]["max_visible_digits"] == 9
    assert probes["numeric_adaptation"]["max_placeholder_digits"] == 7
    assert probes["numeric_adaptation"]["length_mismatch"] is True
    assert probes["state"]["selected_or_explicit_state_elements"][0]["label"] == "15级吴山石"


def test_systemic_screen_issues_merge_repeated_patterns_and_cap_primary_findings():
    from engine.session_report import _systemic_screen_issues

    def issue(title, rule_ids, heuristics):
        return {
            "issue_id": title,
            "title": title,
            "severity": "medium",
            "confidence": 0.7,
            "detection": title,
            "description": title,
            "suggestion": "修正",
            "rule_ids": rule_ids,
            "heuristic_ids": heuristics,
        }

    reviews = []
    for index in range(4):
        reviews.append({
            "node_id": f"1:{index + 2}",
            "page_type": f"界面 {index + 1}",
            "issues": [
                issue(
                    "全选与绑定复用同一空心圆",
                    ["R12"],
                    ["H04"],
                ),
                issue(
                    "列表缺少可辨认的当前选中态",
                    ["R17"],
                    ["H06"],
                ),
            ],
        })
    for index in range(12):
        reviews.append({
            "node_id": f"2:{index + 2}",
            "page_type": f"低优先级界面 {index + 1}",
            "issues": [issue(
                f"低优先级图标含义不清 {index}",
                ["R16"],
                ["H06"],
            )],
        })
    merged = _systemic_screen_issues(reviews)
    assert len(merged) <= 8
    control = next(
        item for item in merged
        if item["systemic_cluster"] == "selection-control-semantics"
    )
    assert control["occurrence_count"] == 4
    assert len(control["affected_locations"]) == 4
    assert all(item["severity"] != "low" for item in merged)
