"""用同一张 T02 原图复现重复观察，并核对操作来源如何落入会话。"""
import argparse
import asyncio
import base64
import hashlib
import json
from pathlib import Path
import site
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--sessions', type=Path, required=True)
    parser.add_argument('--extra-site', action='append', default=[])
    args = parser.parse_args()
    root = args.repo.resolve()
    sys.path.insert(0, str(root))
    for dep in args.extra_site:
        site.addsitedir(str(Path(dep).resolve()))
    from engine.session_contracts import Action, EventInput, Question, SessionCreate, SourceInput
    from engine.session_service import SessionService
    from engine.session_store import SessionStore
    from engine.session_report import structured_report

    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit('请使用新的存档目录。')
    out.mkdir(parents=True, exist_ok=True)
    raw = args.image.read_bytes()
    actor = 'AI模拟操作员-D'
    actor_meta = {'actor_type': 'ai'} if 'actor_type' in EventInput.model_fields else {}
    create_meta = {'actor': actor, 'actor_type': 'ai'} if 'actor_type' in SessionCreate.model_fields else {}

    async def run():
        store = SessionStore(args.sessions.resolve())
        service = SessionService(store)
        events = []
        try:
            session = service.create(SessionCreate(
                purpose='从这张设置页判断如何查看与调整通知偏好，检查选项、操作和当前状态的表达。',
                sources=[SourceInput(kind='image', title='T02通知设置', role='design',
                                    image_base64=base64.b64encode(raw).decode())], **create_meta))
            source = session.sources[0]
            capture = await service.adapters.read(session.session_id, source)
            service._capture(session, source, capture)
            action = Action(source_id=source.source_id, kind='observe', expected_state_id=capture.state_id,
                            reason='再次核对同一张通知设置图的当前可见内容')
            await service._perform_action(session, action)
            before_auth = action.model_dump(mode='json')
            if action.status == 'pending':
                event = EventInput(event_id='approve', expected_context_version=session.context_version,
                                   type='authorize_action', actor=actor, **actor_meta,
                                   payload={'action_id': action.action_id, 'approved': True})
                events.append(event.model_dump(mode='json'))
                session, _ = service.apply_event(session.session_id, event)
                await service._execute_authorized(session)
            else:
                session = store.get(session.session_id)
            q = Question(text='请说明当前检查范围', reason='核对操作来源写入')
            session.questions.append(q)
            store.save(session)
            event = EventInput(event_id='reply', expected_context_version=session.context_version,
                               type='reply', actor=actor, **actor_meta,
                               payload={'question_id': q.question_id, 'text': '只核对原图可见选项和当前状态。'})
            events.append(event.model_dump(mode='json'))
            session, _ = service.apply_event(session.session_id, event)
            saved_action = next(a for a in session.actions if a.action_id == action.action_id)
            report = {'原图SHA256': hashlib.sha256(raw).hexdigest(),
                      '代码SHA256': {name: hashlib.sha256((root/'engine'/name).read_bytes()).hexdigest()
                                   for name in ['session_adapters.py', 'session_service.py', 'session_contracts.py']},
                      '首次执行后': before_auth, '最终动作': saved_action.model_dump(mode='json'),
                      '来源字段能力': bool(actor_meta), '提交事件': events,
                      '答复来源': next(x.answer_actor for x in session.questions if x.question_id == q.question_id),
                      '操作消息': [m for m in session.messages if m.get('actor') == actor],
                      '交互转移数': len(session.transitions), '证据状态': [e.state_id for e in session.evidence if e.source_id == source.source_id]}
            (out/'同图实测.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'动作': report['最终动作']['status'], '答复来源': report['答复来源'],
                              '授权问题数': sum(q.kind == 'authorization' for q in session.questions)}, ensure_ascii=False))
        finally:
            await service.close()
    asyncio.run(run())


if __name__ == '__main__':
    main()
