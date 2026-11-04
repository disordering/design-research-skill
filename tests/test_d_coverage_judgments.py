"""新增覆盖项必须拥有独立判断，重复同一覆盖保持已有判断。"""
import asyncio
import unittest
from types import SimpleNamespace

from engine.session_contracts import CheckItem, PlannedCheck
from engine.session_service import SessionService as Service

class Captured(Exception):
    pass


class CoverageRegression(unittest.TestCase):
    def setUp(self):
        self.service = object.__new__(Service)
        self.service.registry = SimpleNamespace(refs={"R02", "E01", "REQ1", "E08"}, spec=lambda ref: {"ref": ref})
        self.service.store = SimpleNamespace(save=lambda session: None)

    def check(self, kind="rule", coverage="选择页", status="executed"):
        ref, decision = {
            "rule": ("R02", "no_visible_issue"), "method": ("E01", "no_visible_issue"),
            "goal": ("REQ1", "met"), "conflict": ("E08", "no_conflict"),
        }[kind]
        return CheckItem(
            check_id=Service._check_id(ref, coverage), ref=ref, kind=kind,
            coverage_id=coverage, coverage_title="选择页", task_id="TASK1",
            run_id="离线候选补丁回归", context_version=1, criteria_version="0.2-method-draft",
            execution_status=status, decision=decision if status == "executed" else None,
            reason="模板旧判断或失败说明", evidence_ids=["旧证据"],
            source_ids=["样本"], applicability="applicable", plan_reason="原计划",
            plan_evidence_ids=["旧证据"], required_evidence_kinds=["design"],
        )

    def plan(self, check, coverage="核对页"):
        return PlannedCheck(
            ref=check.ref, coverage_id=coverage, coverage_title="核对页", task_id="TASK2",
            applicability="needs_context", reason="等待新覆盖的独立审查",
            source_ids=["样本"], evidence_ids=["新证据"], object_refs=["核对页标题"],
            evidence_needed=["核对页的实际判断"], required_evidence_kinds=["observation"],
        )

    def session(self, checks, budget=10):
        return SimpleNamespace(run_id="离线候选补丁回归", checks=checks,
                               material_understanding=None, model_calls=[],
                               request=SimpleNamespace(limits=SimpleNamespace(max_checks=budget)))

    def selected(self, session):
        captured = []
        async def capture(*args, **kwargs):
            self.assertEqual(args[3], "judge")
            captured.extend(row["check_id"] for row in args[4]["checks"])
            raise Captured()
        self.service._call = capture
        try:
            asyncio.run(self.service._judge(session, None))
        except Captured:
            pass
        return captured

    def assert_new(self, kind):
        old_check = self.check(kind)
        before = old_check.model_dump()
        session = self.session([old_check])
        self.service._apply_check_plan(session, [self.plan(old_check)], [old_check])
        fresh = session.checks[1]
        self.assertEqual(old_check.model_dump(), before)
        self.assertEqual(fresh.execution_status, "planned")
        self.assertIsNone(fresh.decision)
        self.assertEqual(fresh.reason, "")
        self.assertEqual(fresh.evidence_ids, [])
        self.assertFalse(fresh.reevaluation_requested)
        self.assertEqual(fresh.plan_evidence_ids, ["新证据"])
        self.assertEqual(fresh.required_evidence_kinds, ["observation"])
        self.assertEqual(fresh.kind, kind)
        self.assertEqual(fresh.run_id, before["run_id"])
        CheckItem.model_validate(fresh.model_dump())
        self.assertEqual(self.selected(session), [fresh.check_id])

    def test_new_rule_has_own_judgment(self):
        self.assert_new("rule")

    def test_new_method_has_own_judgment(self):
        self.assert_new("method")

    def test_new_goal_has_own_judgment(self):
        self.assert_new("goal")

    def test_new_conflict_has_own_judgment(self):
        self.assert_new("conflict")

    def test_identical_existing_coverage_preserves_judgment(self):
        old_check = self.check()
        before = old_check.model_dump()
        session = self.session([old_check])
        same = PlannedCheck(
            ref=old_check.ref, coverage_id=old_check.coverage_id,
            coverage_title=old_check.coverage_title, task_id=old_check.task_id,
            applicability=old_check.applicability, reason=old_check.plan_reason,
            source_ids=old_check.source_ids, evidence_ids=old_check.plan_evidence_ids,
            required_evidence_kinds=old_check.required_evidence_kinds,
        )
        self.service._apply_check_plan(session, [same], [old_check])
        self.assertEqual(session.checks, [old_check])
        self.assertEqual(old_check.model_dump(), before)
        self.assertEqual(self.selected(session), [])

    def test_repeated_same_plan_does_not_duplicate_coverage(self):
        old_check = self.check()
        session = self.session([old_check])
        plan = self.plan(old_check)
        self.service._apply_check_plan(session, [plan], [old_check])
        new_check = session.checks[1]
        self.service._apply_check_plan(session, [plan], [old_check, new_check])
        self.assertEqual(len(session.checks), 2)
        self.assertIs(session.checks[1], new_check)
        self.assertEqual(self.selected(session), [new_check.check_id])

    def test_no_inherited_budget_consumption(self):
        old_check = self.check()
        session = self.session([old_check], budget=2)
        session.model_calls = [{"run_id": session.run_id, "operation": "judge", "input": {"check_ids": [old_check.check_id]}}]
        self.service._apply_check_plan(session, [self.plan(old_check)], [old_check])
        new_check = session.checks[1]
        later_check = self.check(coverage="另一个新覆盖", status="planned")
        session.checks.append(later_check)
        self.assertEqual(self.selected(session), [new_check.check_id])
        self.assertEqual(later_check.execution_status, "not_executed")

    def test_new_coverage_does_not_inherit_reevaluation_bypass(self):
        old_check = self.check()
        old_check.reevaluation_requested = True
        session = self.session([old_check], budget=1)
        self.service._apply_check_plan(session, [self.plan(old_check)], [old_check])
        new_check = session.checks[1]
        self.assertFalse(new_check.reevaluation_requested)
        self.assertEqual(self.selected(session), [])
        self.assertEqual(new_check.execution_status, "not_executed")

    def test_unscoped_base_gets_new_identity_without_judgment(self):
        old_check = self.check(coverage="")
        old_id = old_check.check_id
        session = self.session([old_check])
        self.service._apply_check_plan(session, [self.plan(old_check)], [old_check])
        self.assertEqual(len(session.checks), 1)
        self.assertNotEqual(old_check.check_id, old_id)
        self.assertEqual(old_check.execution_status, "planned")
        self.assertIsNone(old_check.decision)
        self.assertEqual(old_check.evidence_ids, [])
        self.assertEqual(self.selected(session), [old_check.check_id])

    def test_template_nonexecuted_status_does_not_block_new_coverage(self):
        for status in ("failed", "not_executed", "blocked"):
            with self.subTest(status=status):
                old_check = self.check(status=status)
                session = self.session([old_check])
                self.service._apply_check_plan(session, [self.plan(old_check)], [old_check])
                self.assertEqual(session.checks[1].execution_status, "planned")
                self.assertEqual(self.selected(session), [session.checks[1].check_id])


if __name__ == "__main__":
    unittest.main()
