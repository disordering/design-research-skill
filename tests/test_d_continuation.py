"""D 续测发现的静态图读取与操作者来源回归。"""

import asyncio
import base64
import io
import json

import pytest
from PIL import Image

from engine.errors import EngineError
from engine.session_adapters import AdapterHub
from engine.session_contracts import Action, EventInput, Question, SessionCreate, SourceInput
from engine.session_report import structured_report
from engine.session_service import SessionService
from engine.session_store import SessionStore
from test_session_service import FixtureAdapters, FixtureModel, create_service, request


def test_static_image_observation_reuses_pixels_without_authorization(tmp_path):
    async def run():
        raw = io.BytesIO()
        Image.new("RGB", (320, 240), "#3a72da").save(raw, "PNG")
        hub = AdapterHub()
        service = SessionService(SessionStore(tmp_path), adapters=hub)
        try:
            session = service.create(SessionCreate(
                purpose="核对静态图当前可见内容", actor="AI回归-D", actor_type="ai",
                sources=[SourceInput(kind="image", image_base64=base64.b64encode(raw.getvalue()).decode())],
            ))
            source = session.sources[0]
            before = await hub.read(session.session_id, source)
            ids = service._capture(session, source, before)
            action = Action(source_id=source.source_id, kind="observe",
                            expected_state_id=before.state_id, reason="再次核对原图")
            assert await service._perform_action(session, action)
            assert action.status == "executed" and action.outcome == "read"
            assert not session.questions and not session.transitions
            after = [e for e in session.evidence if e.evidence_id in action.evidence_ids]
            assert ids[0] in action.evidence_ids
            assert all(e.state_id == before.state_id for e in after)
            assert all(service.store.artifact(session.session_id, e.artifact_id)[0].read_bytes() == before.image
                       for e in after if e.artifact_id)
            with pytest.raises(EngineError) as error:
                await hub.act(session.session_id, source, Action(
                    source_id=source.source_id, kind="click", expected_state_id=before.state_id,
                    selector="#save", reason="静态图不能点击",
                ), authorized=True)
            assert error.value.code == "source_not_interactive"
        finally:
            await service.close()
    asyncio.run(run())


@pytest.mark.parametrize("actor_type", ["ai", "human", "program", "unknown"])
def test_actor_source_survives_reply_authorization_and_export(tmp_path, actor_type):
    service, _ = create_service(tmp_path, model=FixtureModel(action=True),
                                adapters=FixtureAdapters(require_authorization=True))
    session = service.create(request(website=True, actor="操作员-D", actor_type=actor_type,
                                     design_purpose="保存偏好", target_user="设置页使用者"))
    assert session.messages[0]["actor_type"] == actor_type
    statements = [s for s in session.sources if s.input.reference.startswith("user://")]
    assert len(statements) == 3 and all(s.input.declared_by == "操作员-D" for s in statements)
    first = asyncio.run(service.run(session.session_id))
    action = next(a for a in first.actions if a.status == "pending")
    authorized, _ = service.apply_event(first.session_id, EventInput(
        event_id="authorization", expected_context_version=first.context_version,
        type="authorize_action", actor="操作员-D", actor_type=actor_type,
        payload={"action_id": action.action_id, "approved": True},
    ))
    answered = [q for q in authorized.questions if q.action_id == action.action_id]
    assert answered and all(q.answer_actor == actor_type for q in answered)
    q = Question(text="任务用户是谁", reason="记录任务范围")
    authorized.questions.append(q)
    service.store.save(authorized)
    reply, _ = service.apply_event(first.session_id, EventInput(
        event_id="reply", expected_context_version=authorized.context_version,
        type="reply", actor="操作员-D", actor_type=actor_type,
        payload={"question_id": q.question_id, "text": "课程案例中的预约用户"},
    ))
    saved = service.store.get(first.session_id)
    assert next(x for x in saved.questions if x.question_id == q.question_id).answer_actor == actor_type
    ended, _ = service.apply_event(first.session_id, EventInput(
        event_id="finish", expected_context_version=reply.context_version,
        type="finish", actor="操作员-D", actor_type=actor_type,
    ))
    exported = structured_report(service.store.report(first.session_id, ended.report_version), registry=service.registry)
    messages = exported["history"]["messages"]
    assert all(m["actor_type"] == actor_type for m in messages if m.get("actor") == "操作员-D")
    assert {m["type"] for m in messages if m.get("actor") == "操作员-D"} >= {"purpose", "reply", "authorize_action", "finish"}


def test_legacy_event_retry_keeps_idempotency_and_new_actor_is_not_inferred(tmp_path):
    service, _ = create_service(tmp_path)
    session = service.create(request())
    event = EventInput(event_id="old", expected_context_version=1, type="resume", actor="AI模拟操作员-D")
    service.apply_event(session.session_id, event)
    # 存入旧版本没有 actor_type 的请求体，验证升级后相同请求仍可重试。
    body = event.model_dump(mode="json")
    body.pop("actor_type")
    with service.store.connection() as db:
        db.execute("UPDATE events SET body=? WHERE session_id=? AND event_id=?",
                   (json.dumps(body, sort_keys=True, ensure_ascii=False), session.session_id, event.event_id))
    current, rerun = service.apply_event(session.session_id, event)
    assert not rerun
    assert current.messages[-1]["actor_type"] == "unknown"
    with pytest.raises(EngineError) as error:
        service.apply_event(session.session_id, event.model_copy(update={"actor_type": "ai"}))
    assert error.value.code == "event_id_conflict"
