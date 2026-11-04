"""按用户的限时收尾要求，以生产事件结束 H05 B 追加探索。"""
from pathlib import Path
import sys,site,json,hashlib
repo=Path(__file__).resolve().parents[1]/'design-research-skill'
frozen=repo.parent/'work/d_final_h05/冻结基线'
for name in ('d_nov_review_deps','d_nov_mcp'):site.addsitedir(str(repo.parent/'work'/name))
sys.path.insert(0,str(frozen))
from engine.session_service import SessionService
from engine.session_store import SessionStore
from engine.methods import MethodRegistry
from engine.session_contracts import EventInput
stage=repo/'docs/D-最终验收证据/H05完整复审/02-B修正版'
target=stage/'限时收尾事件.json'
if target.exists():raise SystemExit('收尾事件已留档，不重复操作。')
store=SessionStore(repo.parent/'work/d_final_h05/02-B修正版')
sid='session-8e92a333d79d4678bac0b330efcd3e94'
service=SessionService(store,registry=MethodRegistry(repo/'方法专家开发交付-v0.2'))
session=store.get(sid)
before=session.model_dump(mode='json')
reason='用户要求从12:09 UTC起15分钟内完成测试；已有实际提交回执，结束重复拓展，独立续接旧候选T10复审；保留全部原始调用与未执行检查。'
event=EventInput(event_id='d-h05-b-deadline-finish-20261104',expected_context_version=session.context_version,actor='D 限时收尾 AI 操作员',actor_type='ai',type='finish',payload={'reason':reason})
session,should_run=service.apply_event(sid,event)
after=session.model_dump(mode='json')
checks_unchanged=before['checks']==after['checks']
actions_unchanged=before['actions']==after['actions']
record={'来源':'AI 操作员调用生产 finish，未杀进程、浏览器或在途CLI','范围调整原因':reason,'事件':event.model_dump(mode='json'),'应运行':should_run,'收尾前状态':before['status'],'收尾前revision':before['revision'],'收尾后状态':session.status,'收尾后revision':session.revision,'完整度':session.report_completeness,'检查记录保持':checks_unchanged,'动作记录保持':actions_unchanged}
target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert checks_unchanged and actions_unchanged
print(json.dumps(record,ensure_ascii=False))
