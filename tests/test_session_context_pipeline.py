"""Synthetic business cases for pipeline contracts, never accuracy reference data."""

import asyncio
import json
from dataclasses import replace

import pytest

from engine.errors import EngineError
from engine.model import ModelCallResult
from engine.session_contracts import EventInput, MaterialUnderstanding, SessionCreate, SourceInput
from engine.session_context import sanitize_understanding, validate_understanding
from tests.test_session_service import FixtureModel, create_service


GOAL = "设计目的：让使用者清楚知道取消不会保存。"
SPEC = "策划要求：点击取消后不得保存草稿。"
OPINION = "专家建议：取消时保留用户已填写的草稿。"
DESIGN = "方案标注：取消按钮返回列表，草稿被保留。"


def business_request():
    return SessionCreate(
        purpose="检查添加与取消流程是否符合原设计目的，并对照策划要求和专家建议。",
        sources=[
            SourceInput(kind="document", title="设计目的", content=GOAL, role="design_brief"),
            SourceInput(kind="document", title="策划案", content=SPEC, role="product_spec", declared_by="fixture-planner"),
            SourceInput(kind="document", title="专家意见", content=OPINION, role="expert_opinion", declared_by="fixture-expert"),
            SourceInput(kind="document", title="方案标注", content=DESIGN, role="design", evidence_kind="design"),
        ],
    )


def test_material_understanding_drops_model_self_correction_without_losing_other_material(tmp_path):
    service, _ = create_service(tmp_path)
    session = service.create(SessionCreate(
        purpose="Fixture",
        sources=[SourceInput(kind="document", content="Fixture requirement", role="product_spec")],
    ))
    asyncio.run(service._read_sources(session))
    result = MaterialUnderstanding(
        task_summary="Fixture",
        assumptions=["修正：根据指令，我将删除原REQ10并重新整理。", "缺少数值表。"],
    )
    warnings = sanitize_understanding(session, result, service._valid_evidence(session))
    assert result.assumptions == ["缺少数值表。"]
    assert warnings and "过程性文字" in warnings[0]
    validate_understanding(session, result, service._valid_evidence(session))


class BusinessFixture(FixtureModel):
    def __init__(self, invalid_quote=False, promote_opinion=False):
        super().__init__()
        self.invalid_quote = invalid_quote
        self.promote_opinion = promote_opinion

    async def complete(self, messages, **kwargs):
        data = json.loads(messages[1]["content"][0]["text"])
        context = data["context"]
        by_title = {source["title"]: source["source_id"] for source in context["sources"]}
        by_source = {e["source_id"]: e["evidence_id"] for e in context["evidence"]}
        ids = {title: by_source[sid] for title, sid in by_title.items()}
        if data["operation"] == "understand":
            self.operations.append("understand")
            quote = lambda title, text: [{"evidence_id": ids[title], "quote": text}]
            result = {
                "task_summary": "核对取消后的草稿处理与材料要求",
                "goals": [{"id": "G01", "text": "取消结果需要清楚且不保存",
                           "evidence_ids": [ids["设计目的"]], "source_quotes": quote("设计目的", GOAL)}],
                "requirements": [{"id": "REQ01", "text": "取消不得保存草稿",
                                  "evidence_ids": [ids["策划案"]],
                                  "source_quotes": quote("策划案", "编造的原文" if self.invalid_quote else SPEC)}],
                "opinions": [{"id": "OP01", "text": "专家建议保留草稿",
                              "source_quotes": quote("专家意见", OPINION)}],
                "conflicts": [{"topic": "取消时是否保留草稿", "claim_ids": ["REQ01", "OP01"],
                               "source_quotes": [*quote("策划案", SPEC), *quote("专家意见", OPINION)],
                               "reason": "策划要求不保存，专家建议保留；建议不是自动生效的业务要求。",
                               "status": "needs_clarification"}],
                "unknowns": ["没有运行证据证明当前系统实际处理草稿"],
            }
            if self.promote_opinion:
                result["requirements"][0].update(
                    evidence_ids=[ids["专家意见"]], source_quotes=quote("专家意见", OPINION),
                )
        elif data["operation"] == "judge":
            self.operations.append("judge")
            judgments = []
            findings = []
            for check in data["checks"]:
                decision = "met" if check["kind"] == "goal" else (
                    "no_conflict" if check["kind"] == "conflict" else "no_visible_issue"
                )
                evidence = [ids["方案标注"], ids["策划案"]]
                if check["ref"] == "REQ01":
                    decision = "observed_violation"
                    design_evidence = next(
                        item for item in context["evidence"]
                        if item["source_id"] == by_title["方案标注"]
                    )
                    object_id = design_evidence.get("objects", [{}])[0].get(
                        "object_id", "",
                    )
                    findings.append({
                        "kind": "nonconformity", "title": "取消草稿处理与策划不一致（夹具）",
                        "check_ids": [check["check_id"]], "evidence_ids": evidence,
                        "principle": "策划要求取消不保存", "detection": "方案标注取消后保留",
                        "description": "不符合所提供的业务要求，尚未实际运行",
                        "suggestion": "先确认业务规则，再修改方案或要求",
                        "severity_reason": "夹具业务差异，非真实产品评测",
                        "object_id": object_id,
                        "object_ref": design_evidence["content"][:80],
                        "claims": [{
                            "claim_type": "requirement_match",
                            "object_id": object_id,
                            "expected": "取消不保存草稿",
                            "observed": "方案标注取消后保留草稿",
                            "evidence_ids": evidence,
                        }],
                    })
                judgments.append({"check_id": check["check_id"], "decision": decision,
                                  "reason": "合成材料契约判断，不是准确率成绩", "evidence_ids": evidence})
            result = {"judgments": judgments, "findings": findings}
        else:
            return await super().complete(messages, **kwargs)
        return ModelCallResult(
            text=json.dumps(result, ensure_ascii=False), provider="test-fixture",
            model="business-context-fixture", usage={}, request_id=None, latency_ms=1, json_mode_used=True,
        )


def test_material_goals_requirements_opinions_plan_and_report_share_one_session(tmp_path):
    service, model = create_service(tmp_path, model=BusinessFixture())
    result = asyncio.run(service.run(service.create(business_request()).session_id))
    assert result.material_understanding
    assert result.review_mode == "design"
    assert result.understanding_context_version == result.context_version
    assert len(result.goals) == len(result.requirements) == 1
    assert result.requirements[0].source_quotes[0].quote == SPEC
    assert any(
        branch.basis == "inferred" and "取消" in branch.trigger
        for task in result.review_tasks for branch in task.branches
    )
    assert result.material_understanding.opinions[0].source_quotes[0].quote == OPINION
    assert not result.material_understanding.conflicts[0].blocking
    assert next(c for c in result.checks if c.ref == "E08").decision == "needs_clarification"
    assert next(c for c in result.checks if c.ref == "REQ01").decision == "observed_violation"
    assert next(c for c in result.checks if c.ref == "E07").decision == "observed_violation"
    assert all(c.applicability != "not_assessed" for c in result.checks)
    assert all(c.plan_reason and c.object_refs for c in result.checks)
    assert any(f.kind == "nonconformity" for f in result.findings)
    assert model.operations[:2] == ["understand", "plan_checks"]


@pytest.mark.parametrize("invalid_quote,promote_opinion", [(True, False), (False, True)])
def test_context_extraction_rejects_fake_quotes_and_unapproved_expert_requirements(tmp_path, invalid_quote, promote_opinion):
    service, _ = create_service(tmp_path, model=BusinessFixture(invalid_quote, promote_opinion))
    result = asyncio.run(service.run(service.create(business_request()).session_id))
    if invalid_quote:
        assert result.report_completeness == "partial"
        assert result.material_understanding is None
        assert not result.goals and not result.requirements
        assert len(result.model_calls) == 2
    else:
        assert result.report_completeness == "partial"
        assert any(
            item.get("gap_class") == "unobserved_branch"
            for item in result.required_coverage
        )
        assert result.material_understanding is not None
        assert result.goals
        assert not result.requirements
        assert any("已剔除" in warning for warning in result.warnings)
    assert not result.findings


def test_design_annotation_alone_cannot_become_formal_requirement(tmp_path):
    class PromotedDesign(BusinessFixture):
        async def complete(self, messages, **kwargs):
            data = json.loads(messages[1]["content"][0]["text"])
            result = await super().complete(messages, **kwargs)
            if data["operation"] == "understand":
                output = json.loads(result.text)
                design_id = next(
                    source["source_id"] for source in data["context"]["sources"]
                    if source["title"] == "方案标注"
                )
                evidence_id = next(
                    item["evidence_id"] for item in data["context"]["evidence"]
                    if item["source_id"] == design_id
                )
                output["requirements"][0] = {
                    "id": "REQ01", "text": "取消时保留草稿",
                    "evidence_ids": [evidence_id],
                    "source_quotes": [{"evidence_id": evidence_id, "quote": DESIGN}],
                }
                result = replace(result, text=json.dumps(output, ensure_ascii=False))
            return result

    service, _ = create_service(tmp_path, model=PromotedDesign())
    result = asyncio.run(service.run(service.create(business_request()).session_id))
    assert result.material_understanding is not None
    assert not result.requirements
    assert any("已剔除" in warning for warning in result.warnings)


def test_review_instruction_cannot_be_recorded_as_expert_opinion(tmp_path):
    class ReviewAsOpinion(BusinessFixture):
        async def complete(self, messages, **kwargs):
            data = json.loads(messages[1]["content"][0]["text"])
            result = await super().complete(messages, **kwargs)
            if data["operation"] == "understand":
                output = json.loads(result.text)
                purpose_id = next(
                    source["source_id"] for source in data["context"]["sources"]
                    if source["title"] == "initial_purpose"
                )
                evidence_id = next(
                    item["evidence_id"] for item in data["context"]["evidence"]
                    if item["source_id"] == purpose_id
                )
                output["opinions"][0] = {
                    "id": "OP01", "text": "评审委托被误记为意见",
                    "source_quotes": [{
                        "evidence_id": evidence_id,
                        "quote": data["context"]["purpose"],
                    }],
                }
                result = replace(result, text=json.dumps(output, ensure_ascii=False))
            return result

    service, _ = create_service(tmp_path, model=ReviewAsOpinion())
    result = asyncio.run(service.run(service.create(business_request()).session_id))
    assert result.material_understanding is not None
    assert not result.material_understanding.opinions
    assert any("已剔除" in warning for warning in result.warnings)


def test_quote_validation_identifies_the_exact_invalid_excerpt(tmp_path):
    from engine.session_context import validate_quotes
    from engine.session_contracts import EvidenceQuote
    service, _ = create_service(tmp_path)
    session = service.create(business_request())
    asyncio.run(service._read_sources(session))
    evidence = service._valid_evidence(session)
    quote = EvidenceQuote(evidence_id=session.evidence[0].evidence_id, quote="第一条……第二条")
    with pytest.raises(EngineError) as error:
        validate_quotes([quote], evidence)
    assert error.value.code == "material_quote_invalid"
    assert "不能使用省略号" in error.value.message
    assert quote.quote in error.value.message


def test_conflict_decision_needs_an_actor_and_is_not_an_implementation_fix(tmp_path):
    service, _ = create_service(tmp_path, model=BusinessFixture())
    first = asyncio.run(service.run(service.create(business_request()).session_id))
    conflict = first.material_understanding.conflicts[0]
    payload = {"conflict_id": conflict.conflict_id, "decision": "以策划要求为准",
               "reason": "业务负责人确认取消不保存", "accepted_claim_ids": ["REQ01"],
               "rejected_claim_ids": ["OP01"]}
    with pytest.raises(EngineError):
        service.apply_event(first.session_id, EventInput(
            event_id="no-actor", expected_context_version=1, type="resolve_conflict", payload=payload,
        ))
    changed, rerun = service.apply_event(first.session_id, EventInput(
        event_id="choose-spec", expected_context_version=1, type="resolve_conflict",
        actor="fixture-owner", payload=payload,
    ))
    assert rerun and changed.context_version == 2
    second = asyncio.run(service.run(first.session_id))
    assert second.material_understanding.conflicts[0].status == "resolved"
    assert next(c for c in second.checks if c.run_id == second.run_id and c.ref == "REQ01").decision == "observed_violation"
    assert service.store.report(first.session_id, 1).material_understanding.conflicts[0].status == "needs_clarification"
    assert second.conflict_dispositions[0].actor == "fixture-owner"


def test_context_claims_are_not_rewritten_by_action_planning(tmp_path):
    from engine.session_contracts import AgentStep
    service, _ = create_service(tmp_path, model=BusinessFixture())
    session = asyncio.run(service.run(service.create(business_request()).session_id))
    modified = session.requirements[0].model_copy(update={"text": "取消应保存"})
    with pytest.raises(EngineError) as error:
        service._accept_plan(session, AgentStep(task_summary="Task", requirements=[modified]))
    assert error.value.code == "plan_context_mutation"


def test_unresolved_formal_requirements_block_goal_aggregation(tmp_path):
    from engine.session_contracts import Constraint, EvidenceQuote, MaterialUnderstanding, MaterialConflict
    service, _ = create_service(tmp_path)
    session = asyncio.run(service.run(service.create(business_request()).session_id))
    eid = session.evidence[0].evidence_id
    session.requirements = [
        Constraint(id="REQ01", text="Do not keep", evidence_ids=[eid]),
        Constraint(id="REQ02", text="Keep", evidence_ids=[eid]),
    ]
    session.material_understanding = MaterialUnderstanding(task_summary="Conflict", conflicts=[
        MaterialConflict(topic="Draft", claim_ids=["REQ01", "REQ02"], reason="Incompatible formal requirements",
                         source_quotes=[EvidenceQuote(evidence_id=eid, quote="fixture"),
                                        EvidenceQuote(evidence_id=eid, quote="fixture")],
                         blocking=True, status="open"),
    ])
    service._prepare_checks(session)
    for check in session.checks:
        if check.kind == "goal":
            check.execution_status = "executed"
            check.decision = "met"
            check.evidence_ids = [eid]
    service._aggregate_goals(session)
    assert next(c for c in session.checks if c.ref == "REQ01").decision == "insufficient_evidence"
    assert next(c for c in session.checks if c.ref == "REQ02").decision == "insufficient_evidence"
    assert next(c for c in session.checks if c.ref == "E07").decision == "insufficient_evidence"


def test_requirements_text_alone_does_not_prove_implementation_compliance(tmp_path):
    from engine.session_contracts import Constraint
    service, model = create_service(tmp_path)
    session = service.create(SessionCreate(
        purpose="Review", limits={"max_checks": 1},
        sources=[SourceInput(kind="document", content=SPEC, role="product_spec")],
    ))
    asyncio.run(service._read_sources(session))
    session.requirements = [Constraint(id="REQ01", text="No draft", evidence_ids=[session.evidence[0].evidence_id])]
    service._prepare_checks(session, ["REQ01"])
    asyncio.run(service._judge(session, model))
    assert next(c for c in session.checks if c.ref == "REQ01").decision == "insufficient_evidence"


def test_plan_does_not_silently_drop_unreturned_rule_refs(tmp_path):
    class MissingPlan(FixtureModel):
        async def complete(self, messages, **kwargs):
            data = json.loads(messages[1]["content"][0]["text"])
            result = await super().complete(messages, **kwargs)
            if data["operation"] == "plan_checks":
                output = json.loads(result.text)
                output["items"].pop()
                result = replace(result, text=json.dumps(output))
            return result

    service, _ = create_service(tmp_path, model=MissingPlan())
    result = asyncio.run(service.run(service.create(business_request()).session_id))
    assert result.report_completeness == "partial"
    assert len(result.checks) >= 32
    assert all(c.decision is None for c in result.checks)


def test_opinion_can_link_to_check_plan_without_becoming_scored_requirement(tmp_path):
    from engine.session_context import validate_check_plan
    from engine.session_contracts import CheckPlanBatch, PlannedCheck
    service, _ = create_service(tmp_path, model=BusinessFixture())
    session = asyncio.run(service.run(service.create(business_request()).session_id))
    plan = CheckPlanBatch(items=[PlannedCheck(
        ref="E08", applicability="applicable", reason="Compare requirements with advice",
        source_ids=[session.sources[0].source_id], evidence_ids=[session.evidence[0].evidence_id],
        constraint_refs=["REQ01", "OP01"],
    )])
    validate_check_plan(session, plan, ["E08"], service._valid_evidence(session))
    assert "OP01" not in {c.ref for c in session.checks}
    plan.items[0].constraint_refs = ["OP_UNKNOWN"]
    with pytest.raises(EngineError) as error:
        validate_check_plan(session, plan, ["E08"], service._valid_evidence(session))
    assert "E08.constraint_refs" in error.value.message and "OP_UNKNOWN" in error.value.message


def test_nonapplicability_requires_source_backed_conditions_with_actionable_feedback(tmp_path):
    from engine.session_context import validate_check_plan
    from engine.session_contracts import CheckPlanBatch, PlannedCheck
    service, _ = create_service(tmp_path)
    session = service.create(business_request())
    asyncio.run(service._read_sources(session))
    plan = CheckPlanBatch(items=[PlannedCheck(
        ref="R21", applicability="not_applicable", reason="No errors supplied",
        source_ids=[session.sources[0].source_id],
    )])
    with pytest.raises(EngineError) as error:
        validate_check_plan(session, plan, ["R21"], service._valid_evidence(session))
    assert "R21" in error.value.message and "needs_context" in error.value.message
    plan.items[0].applicability = "needs_context"
    validate_check_plan(session, plan, ["R21"], service._valid_evidence(session))


def test_check_plan_rejects_cartesian_coverage_for_one_rule(tmp_path):
    from engine.session_context import validate_check_plan
    from engine.session_contracts import CheckPlanBatch, PlannedCheck

    service, _ = create_service(tmp_path)
    session = service.create(business_request())
    asyncio.run(service._read_sources(session))
    plan = CheckPlanBatch(items=[PlannedCheck(
        ref="R07",
        coverage_id=f"coverage-{index}",
        applicability="applicable",
        reason="Synthetic coverage unit",
        source_ids=[session.sources[0].source_id],
        evidence_ids=[session.evidence[0].evidence_id],
    ) for index in range(5)])

    with pytest.raises(EngineError) as error:
        validate_check_plan(
            session,
            plan,
            ["R07"],
            service._valid_evidence(session),
        )
    assert error.value.code == "check_plan_coverage_too_broad"
    assert "最多返回4个" in error.value.message


def test_rejected_claim_scope_survives_model_renaming_or_omitting_resolved_conflict(tmp_path):
    from engine.session_context import quote_signature
    from engine.session_contracts import ConflictDisposition
    service, _ = create_service(tmp_path, model=BusinessFixture())
    session = asyncio.run(service.run(service.create(business_request()).session_id))
    claim = session.requirements[0]
    session.conflict_dispositions.append(ConflictDisposition(
        conflict_id=session.material_understanding.conflicts[0].conflict_id,
        decision="Synthetic scope decision", reason="Test only", actor="fixture-owner",
        source_id=session.sources[0].source_id, context_version=2,
        rejected_claim_ids=[claim.id],
        rejected_quote_signatures=[quote_signature(claim.source_quotes, service._valid_evidence(session))],
    ))
    session.material_understanding.conflicts = []
    check = next(c for c in session.checks if c.ref == claim.id)
    check.ref = claim.id = "REQ_RENAMED"
    service._apply_conflict_scope(session)
    assert check.scope_status == "excluded"
    service._aggregate_goals(session)
    assert next(c for c in session.checks if c.ref == "E07").decision != "observed_violation"
    evidence = service._valid_evidence(session)[claim.source_quotes[0].evidence_id]
    evidence.source_version = "changed-version"
    check.scope_status = "included"
    service._apply_conflict_scope(session)
    assert check.scope_status == "included"


def test_blocking_formal_conflict_cannot_create_product_nonconformity(tmp_path):
    from engine.session_contracts import MaterialConflict
    service, model = create_service(tmp_path, model=BusinessFixture())
    session = service.create(business_request())
    asyncio.run(service._read_sources(session))
    asyncio.run(service._understand_materials(session, model))
    session.material_understanding.conflicts = [MaterialConflict(
        topic="Synthetic formal conflict", claim_ids=["G01", "REQ01"], reason="Fixture only",
        source_quotes=session.goals[0].source_quotes + session.requirements[0].source_quotes,
        blocking=True,
    )]
    service._prepare_checks(session)
    asyncio.run(service._plan_checks(session, model))
    asyncio.run(service._judge(session, model))
    assert next(c for c in session.checks if c.ref == "REQ01").decision == "insufficient_evidence"
    assert not any(f.kind == "nonconformity" for f in session.findings)


def test_resuming_completed_session_reuses_plan_when_context_unchanged(tmp_path):
    service, model = create_service(tmp_path)
    first = asyncio.run(service.run(service.create(business_request()).session_id))
    original_plans = model.operations.count("plan_checks")
    service.apply_event(first.session_id, EventInput(
        event_id="resume", expected_context_version=1, type="resume",
    ))
    second = asyncio.run(service.run(first.session_id))
    assert second.run_id != first.run_id
    assert model.operations.count("plan_checks") == original_plans
    assert all(c.applicability == "applicable" for c in second.checks if c.run_id == second.run_id)


def test_scope_wording_from_planner_does_not_repeat_all_check_planning(tmp_path):
    service, model = create_service(tmp_path)
    session = asyncio.run(service.run(service.create(request := business_request()).session_id))
    calls_before = model.operations.count("plan_checks")
    session.scope = "Planner clarified the same task scope without a user context change"
    service.store.save(session)
    asyncio.run(service._plan_checks(session, model))
    assert model.operations.count("plan_checks") == calls_before


def test_candidate_issue_from_goal_is_normalized_to_observed_violation(tmp_path):
    class CandidateGoal(BusinessFixture):
        async def complete(self, messages, **kwargs):
            result = await super().complete(messages, **kwargs)
            data = json.loads(messages[1]["content"][0]["text"])
            if data["operation"] == "judge":
                output = json.loads(result.text)
                for judgment in output["judgments"]:
                    if judgment["check_id"] != check_id:
                        continue
                    judgment["decision"] = "candidate_issue"
                result = replace(result, text=json.dumps(output, ensure_ascii=False))
            return result

    service, _ = create_service(tmp_path, model=CandidateGoal())
    session = service.create(business_request())
    asyncio.run(service._read_sources(session))
    asyncio.run(service._understand_materials(session, service.model_factory(session.request)))
    service._prepare_checks(session)
    asyncio.run(service._plan_checks(session, service.model_factory(session.request)))
    check_id = next(c.check_id for c in session.checks if c.ref == "REQ01")
    model = CandidateGoal()
    service.model_factory = lambda _: model
    asyncio.run(service._judge(session, model))
    check = next(c for c in session.checks if c.ref == "REQ01")
    assert check.execution_status == "executed"
    assert check.decision in {"observed_violation", "insufficient_evidence"}


def test_near_duplicate_questions_under_the_same_check_are_merged(tmp_path):
    service, _ = create_service(tmp_path)
    session = service.create(business_request())
    check_id = "check-fixture"
    service._question(
        session, "请提供积分商店的高清设计图，以确认获取途径入口。",
        "缺少入口视觉证据", blocking=False, check_ids=[check_id],
    )
    service._question(
        session, "积分商店高清界面还有吗？需要确认获取途径按钮的位置。",
        "当前缩略图无法核对按钮位置", blocking=False, check_ids=[check_id],
    )
    service._finish(session)
    assert len([q for q in session.questions if not q.answered]) == 1
    assert "按钮的位置" in session.questions[0].text


def test_same_question_topic_merges_across_related_check_ids(tmp_path):
    service, _ = create_service(tmp_path)
    session = service.create(business_request())
    service._question(
        session, "交互案中的通用积分商店界面具体长什么样？请提供高清设计图，确认获取途径按钮的位置。",
        "缺少商店画面", blocking=False, check_ids=["check-g02"],
    )
    service._question(
        session, "交互案中吴山石积分商店的设计图缺失，能否补充高清界面，以评审获取途径入口？",
        "商店入口证据不足", blocking=False, check_ids=["check-req09", "check-req10"],
    )
    service._finish(session)
    assert len([q for q in session.questions if not q.answered]) == 1


def test_interrupted_verification_does_not_export_unverified_violation(tmp_path):
    class InterruptedVerification(BusinessFixture):
        async def complete(self, messages, **kwargs):
            data = json.loads(messages[1]["content"][0]["text"])
            if data["operation"] == "verify":
                raise EngineError("verification_unavailable", "Synthetic interruption", status_code=502)
            return await super().complete(messages, **kwargs)

    service, _ = create_service(tmp_path, model=InterruptedVerification())
    session = asyncio.run(service.run(service.create(business_request()).session_id))
    assert session.report_completeness == "partial"
    assert not session.findings
    assert next(c for c in session.checks if c.ref == "REQ01").decision == "insufficient_evidence"
    assert next(c for c in session.checks if c.ref == "E07").decision == "insufficient_evidence"


def test_aggregate_violation_cannot_support_issue_for_insufficient_concrete_goal(tmp_path):
    service, _ = create_service(tmp_path, model=BusinessFixture())
    session = asyncio.run(service.run(service.create(business_request()).session_id))
    goal = next(c for c in session.checks if c.ref == "G01")
    goal.decision = "insufficient_evidence"
    overall = next(c for c in session.checks if c.ref == "E07")
    incorrect = session.findings[0].model_copy(update={
        "finding_id": "unsupported-goal-issue", "kind": "issue", "title": "Unproven missing mechanism",
        "check_ids": [goal.check_id, overall.check_id],
    })
    session.findings.append(incorrect)
    fixed = service._finish(session)
    assert any(f.kind == "nonconformity" for f in fixed.findings)
    assert not any(f.finding_id == incorrect.finding_id for f in fixed.findings)
    rejected = next(m for m in fixed.messages if m.get("type") == "finding_binding_rejected")
    assert rejected["content"]["candidate"]["finding_id"] == incorrect.finding_id
    assert service.store.report(session.session_id, 1).material_understanding
