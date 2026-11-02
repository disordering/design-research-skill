import asyncio
import json

import pytest
from pydantic import ValidationError

from engine.errors import EngineError
from engine.methods import MethodRegistry
from engine.session_contracts import CheckItem, EventInput, SessionCreate, SessionSnapshot, SourceInput
from engine.session_store import SessionStore


def request():
    return SessionCreate(
        purpose="完成设置保存",
        sources=[SourceInput(kind="document", content="已知要求：保存后说明结果。")],
    )


def test_method_assets_have_complete_rule_supplements_and_new_methods():
    registry = MethodRegistry()
    assert registry.version == "0.2-method-draft"
    assert len(registry.criteria.rules) == len(registry.supplements) == 24
    assert list(registry.methods) == [f"E{i:02}" for i in range(1, 9)]
    assert "熟悉度" in registry.spec("R05")["check"]
    assert registry.spec("R18")["execution"]["examples"]["insufficient_evidence"]
    assert registry.spec("E08")["kind"] == "conflict"
    fingerprints = registry.fingerprints()
    assert len(fingerprints) == 14
    assert "05-判据库-v0.2.json" in fingerprints
    assert "07-会话变更重查与复审规则.md" in fingerprints
    assert "08-问题表达严重度与评价验收.md" in fingerprints
    assert registry.delivery_validation["mismatches"] == 0
    assert registry.delivery_validation["checked_files"] == 12


@pytest.mark.parametrize("reference", ["file:///etc/passwd", "javascript:alert(1)", "https://user:pass@example.com/"])
def test_web_sources_reject_unsafe_protocols_and_embedded_credentials(reference):
    with pytest.raises(ValidationError):
        SourceInput(kind="website", reference=reference)


def test_figma_source_rejects_non_figma_domain():
    with pytest.raises(ValidationError):
        SourceInput(kind="figma_board", reference="https://attacker.example/design/abc/")


@pytest.mark.parametrize("kind,decision,execution", [
    ("rule", "met", "executed"), ("goal", "not_applicable", "executed"),
    ("conflict", "candidate_issue", "executed"), ("method", "no_visible_issue", "blocked"),
])
def test_execution_and_decision_types_cannot_be_mixed(kind, decision, execution):
    with pytest.raises(ValidationError):
        CheckItem(check_id="c", ref="R01", kind=kind, run_id="r", context_version=1,
                  criteria_version="0.2", execution_status=execution, decision=decision)


def test_unexecuted_check_has_no_decision():
    check = CheckItem(check_id="c", ref="R01", kind="rule", run_id="r",
                      context_version=1, criteria_version="0.2", execution_status="not_executed")
    assert check.decision is None


def test_immutable_report_and_optimistic_snapshot_revision(tmp_path):
    store = SessionStore(tmp_path)
    session = SessionSnapshot(request=request())
    store.create(session)
    obsolete = store.get(session.session_id)
    session.report_version = 1
    store.save(session, report=True)
    session.request.purpose = "改变任务"
    store.save(session)
    assert store.report(session.session_id, 1).request.purpose == "完成设置保存"
    with pytest.raises(EngineError, match="会话已更新"):
        store.save(obsolete)


def test_event_idempotency_is_canonical_and_conflicting_payload_rejected(tmp_path):
    store = SessionStore(tmp_path)
    session = SessionSnapshot(request=request())
    store.create(session)
    event = EventInput(event_id="evt", expected_context_version=1, type="reply", payload={"text": "yes", "x": 1})
    store.save(session, event=event)
    reordered = EventInput(event_id="evt", expected_context_version=1, type="reply", payload={"x": 1, "text": "yes"})
    assert store.existing_event(session.session_id, reordered)
    with pytest.raises(EngineError) as error:
        store.existing_event(session.session_id, event.model_copy(update={"payload": {"text": "no"}}))
    assert error.value.code == "event_id_conflict"


def test_artifacts_cannot_be_read_from_another_session(tmp_path):
    store = SessionStore(tmp_path)
    a, b = SessionSnapshot(request=request()), SessionSnapshot(request=request())
    store.create(a)
    store.create(b)
    artifact = store.write_artifact(a.session_id, b"raw evidence", "text/plain")
    assert store.artifact(a.session_id, artifact)[0].read_bytes() == b"raw evidence"
    with pytest.raises(EngineError) as error:
        store.artifact(b.session_id, artifact)
    assert error.value.code == "artifact_not_found"


@pytest.mark.parametrize("fields", [
    {"kind": "click"},
    {"kind": "click", "x": 0.5},
    {"kind": "fill"},
    {"kind": "scroll"},
    {"kind": "inspect_node", "node_id": "guessed"},
    {"kind": "navigate", "url": "https://user:pass@example.com"},
])
def test_incomplete_action_targets_are_rejected_before_execution(fields):
    from engine.session_contracts import Action
    action = Action(source_id="fixture", expected_state_id="state", reason="Contract test", **fields)
    with pytest.raises(ValueError):
        action.validate_target()
