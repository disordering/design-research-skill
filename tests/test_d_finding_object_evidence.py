"""规范对象引用、跨状态定位及既有 claim 引用归并的程序回归。"""
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from engine.session_contracts import (
    Action, CheckItem, Evidence, EvidenceObject, Finding, FindingClaim,
    JudgmentBatch, SessionCreate, SourceInput, Verification,
)
from engine.session_service import SessionService
from engine.session_store import SessionStore
from engine.session_verification import (
    finding_location_evidence, object_is_present, resolve_finding_object,
    verify_finding_claims, verify_finding_support,
)


class FindingObjectEvidenceTests(unittest.TestCase):
    def evidence(self, eid="ev-after", *, kind="observation", source="src-screen", object_id="obj-target"):
        return Evidence(
            evidence_id=eid, source_id=source, source_version="v1", context_version=1,
            kind=kind, locator={"url": "https://example.test/task"}, content="页面可见内容",
            state_id=eid + "-state",
            objects=[EvidenceObject(object_id=object_id, kind="page", source_id=source,
                                    state_id=eid + "-state", label="登记流程")],
        )

    def finding(self, ids=None, **kwargs):
        fields = dict(
            kind="issue", title="任务结果与要求有差异", check_ids=["check-test"],
            evidence_ids=ids or ["ev-after"], principle="结果需对应任务", detection="发现字段差异",
            description="结果确认受到影响", suggestion="修正对应关系", severity_reason="影响结果确认",
            object_id="obj-target", object_ref="BR2：跨状态业务关系",
        )
        fields.update(kwargs)
        return Finding(**fields)

    def session(self, actions=None):
        return SimpleNamespace(actions=actions or [], transitions=[])

    def test_canonical_id_is_authoritative_over_free_description(self):
        evidence = self.evidence()
        finding = self.finding()
        self.assertTrue(object_is_present(finding, evidence))
        self.assertTrue(verify_finding_support(self.session(), finding, {evidence.evidence_id: evidence})[0])

    def test_legacy_without_id_retains_text_matching(self):
        evidence = self.evidence()
        self.assertTrue(object_is_present(self.finding(object_id="", object_ref="页面可见内容"), evidence))

    def test_invalid_explicit_id_cannot_fall_back_to_text_or_preferred_id(self):
        evidence = self.evidence()
        finding = self.finding(object_id="obj-nonexistent", object_ref="页面可见内容")
        self.assertFalse(object_is_present(finding, evidence))
        self.assertIsNone(resolve_finding_object(finding, {evidence.evidence_id: evidence}, ["obj-target"]))

    def test_globally_present_but_unreferenced_object_is_rejected(self):
        referenced = self.evidence(object_id="obj-other")
        unrelated = self.evidence("ev-unrelated")
        finding = self.finding()
        valid = {e.evidence_id: e for e in [referenced, unrelated]}
        self.assertIsNone(resolve_finding_object(finding, valid))
        self.assertFalse(verify_finding_support(self.session(), finding, valid)[0])
        self.assertIsNone(finding_location_evidence(self.session(), finding, valid))

    def test_requirement_only_object_is_rejected_even_with_matching_text(self):
        evidence = self.evidence(kind="requirement")
        finding = self.finding(object_ref="页面可见内容")
        self.assertFalse(object_is_present(finding, evidence))
        self.assertIsNone(resolve_finding_object(finding, {evidence.evidence_id: evidence}))
        self.assertFalse(verify_finding_support(self.session(), finding, {evidence.evidence_id: evidence})[0])

    def test_stale_object_cannot_be_resolved_or_located(self):
        evidence = self.evidence()
        evidence.stale = True
        finding = self.finding()
        valid = {evidence.evidence_id: evidence}
        self.assertFalse(object_is_present(finding, evidence))
        self.assertIsNone(resolve_finding_object(finding, valid))
        self.assertIsNone(finding_location_evidence(self.session(), finding, valid))

    def test_location_uses_latest_referenced_observation_not_global_first_or_last(self):
        evidence = [self.evidence(name) for name in ["ev-initial", "ev-before", "ev-after", "ev-unrelated-latest"]]
        finding = self.finding(["ev-after", "ev-before"])
        selected = finding_location_evidence(self.session(), finding, {e.evidence_id: e for e in evidence})
        self.assertEqual(selected.evidence_id, "ev-after")

    def test_dynamic_location_prefers_executed_action_result_over_later_read(self):
        before, after, later = [self.evidence(name) for name in ["ev-before", "ev-after", "ev-later-read"]]
        after.action_id = "action-submit"
        later.action_id = "action-observe"
        actions = [
            Action(action_id="action-submit", source_id=after.source_id, kind="click", selector="#submit",
                   expected_state_id=before.state_id, reason="提交", status="executed", outcome="state_changed"),
            Action(action_id="action-observe", source_id=later.source_id, kind="observe",
                   expected_state_id=after.state_id, reason="观察", status="executed", outcome="read"),
        ]
        finding = self.finding([e.evidence_id for e in [before, after, later]], claims=[FindingClaim(
            claim_type="action_result", object_id="obj-target", evidence_ids=[after.evidence_id],
        )])
        selected = finding_location_evidence(self.session(actions), finding, {e.evidence_id: e for e in [before, after, later]})
        self.assertEqual(selected.evidence_id, "ev-after")

    def test_dynamic_claim_still_requires_real_action_record(self):
        evidence = self.evidence()
        finding = self.finding(claims=[FindingClaim(claim_type="action_result", object_id="obj-target", evidence_ids=[evidence.evidence_id])])
        self.assertFalse(verify_finding_claims(self.session(), finding, {evidence.evidence_id: evidence})[0])
        self.assertFalse(verify_finding_support(self.session(), finding, {evidence.evidence_id: evidence})[0])

    def test_dynamic_location_does_not_follow_unrelated_later_click(self):
        after, reset = [self.evidence(name) for name in ["ev-after", "ev-reset"]]
        after.action_id, reset.action_id = "action-submit", "action-reset"
        actions = [Action(action_id=e.action_id, source_id=e.source_id, kind="click",
                          selector="#button", expected_state_id="before", reason="实际动作",
                          status="executed", outcome="state_changed") for e in [after, reset]]
        finding = self.finding([after.evidence_id, reset.evidence_id], claims=[FindingClaim(
            claim_type="action_result", object_id="obj-target", evidence_ids=[after.evidence_id],
        )])
        selected = finding_location_evidence(self.session(actions), finding,
                                             {e.evidence_id: e for e in [after, reset]})
        self.assertEqual(selected.evidence_id, after.evidence_id)

    def test_canonical_id_does_not_bypass_visual_metric_requirement(self):
        evidence = self.evidence()
        finding = self.finding(title="文字对比度不足")
        passed, reason = verify_finding_support(self.session(), finding, {evidence.evidence_id: evidence})
        self.assertFalse(passed)
        self.assertIn("可读性指标", reason)

    def run_service_case(self, *, existing_location=False, merge_claim_reference=False, bad_claim=False):
        with tempfile.TemporaryDirectory() as tmp:
            service = SessionService(SessionStore(Path(tmp)))
            session = service.create(SessionCreate(purpose="离线对象证据回归", actor="AI回归", actor_type="ai",
                                      sources=[SourceInput(kind="document", role="design", content="测试材料")]))
            source = session.sources[0]
            first = self.evidence("ev-initial", source=source.source_id)
            after = self.evidence(source=source.source_id)
            requirement = self.evidence("ev-requirement", kind="requirement", source=source.source_id, object_id="obj-requirement")
            session.evidence = [first, requirement, after]
            session.checks = [CheckItem(check_id="check-test", ref="R02", kind="rule", run_id=session.run_id,
                              context_version=1, criteria_version="0.2", applicability="applicable")]
            claim_eid = "ev-missing" if bad_claim else after.evidence_id
            finding = self.finding([requirement.evidence_id] if merge_claim_reference else [after.evidence_id],
                claims=[FindingClaim(claim_type="object_present", object_id="obj-target", evidence_ids=[claim_eid])])
            if existing_location:
                finding.location = {"source_id": source.source_id, "state_id": after.state_id,
                                    "object_id": "obj-target", "url": "https://example.test/task", "note": "模型已有合法定位"}
            expected_location = dict(finding.location)
            verification_inputs = []

            async def fixed_call(_session, model, schema, operation, payload):
                if operation == "judge":
                    return JudgmentBatch.model_validate({"judgments": [{"check_id": "check-test", "decision": "candidate_issue",
                                                          "reason": "固定响应夹具", "evidence_ids": [after.evidence_id]}],
                                                         "findings": [finding.model_dump()]})
                self.assertEqual(operation, "verify")
                verification_inputs.extend(payload["findings"])
                return Verification(supported_finding_ids=[item["finding_id"] for item in payload["findings"]])

            service._call = fixed_call
            asyncio.run(service._judge(session, None))
            if bad_claim:
                self.assertFalse(verification_inputs)
                self.assertFalse(session.findings)
                return
            self.assertEqual(len(session.findings), 1)
            result = session.findings[0]
            self.assertIn(after.evidence_id, result.evidence_ids)
            self.assertEqual(result.location["state_id"], after.state_id)
            self.assertNotEqual(result.location["state_id"], first.state_id)
            if existing_location:
                self.assertEqual(result.location, expected_location)

    def test_production_judge_generates_location_from_referenced_evidence(self):
        self.run_service_case()

    def test_production_judge_preserves_existing_legal_location(self):
        self.run_service_case(existing_location=True)

    def test_production_judge_keeps_valid_explicit_claim_reference_union(self):
        self.run_service_case(merge_claim_reference=True)

    def test_production_judge_rejects_invalid_claim_reference_before_union(self):
        self.run_service_case(merge_claim_reference=True, bad_claim=True)


if __name__ == "__main__":
    unittest.main()
