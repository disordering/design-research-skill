"""新样本独立原生验收：每次新会话、真实 Codex、冻结生产源码。"""
from __future__ import annotations
import argparse,asyncio,hashlib,importlib.util,json,os,site,sys,time
from pathlib import Path
from urllib.parse import quote
REPO=Path(__file__).resolve().parents[1]
WORK=REPO.parent/'work'
ROOT=REPO/'docs/D-最终验收证据/新样本'
FROZEN=ROOT/'冻结运行源码'
for name in ('d_nov_review_deps','d_nov_mcp'):site.addsitedir(str(WORK/name))
sys.path.insert(0,str(FROZEN))
import engine
assert Path(engine.__file__).resolve().parent==FROZEN/'engine'
def helper(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
native=helper('_d_final_native',REPO/'scripts/d_native_recheck.py')
screen=helper('_d_final_screen',REPO/'scripts/d_screen_codex_probe.py')
from engine.methods import MethodRegistry
from engine.session_adapters import AdapterHub,BrowserAdapter
from engine.session_contracts import EventInput,SessionCreate,SourceInput
from engine.session_service import SessionService
from engine.session_store import SessionStore
save,sha,utc=native.save,native.sha,native.utc
FOLDERS={'N01':'N01-阅读设置','N02':'N02-器材借用清单','N03':'N03-图书编目录入'}
ACTOR='D 新样本 AI 操作员'
def verify_manifest(root,name):
    data=json.loads((root/name).read_text(encoding='utf-8'))
    for row in data['文件']:
        if sha((root/row['路径']).read_bytes())!=row['SHA256']:
            raise RuntimeError('冻结文件发生变化：'+row['路径'])
    return sha((root/name).read_bytes())
async def run(args):
    material_sha=verify_manifest(ROOT/'冻结材料','冻结清单.json')
    engine_sha=verify_manifest(FROZEN,'源码冻结清单.json')
    # 只接收参考冻结摘要，不读取参考判断，模型只能得到网页及任务卡。
    receipt_path=WORK/'d_final_acceptance_reference/冻结回执.json'
    if not receipt_path.exists():raise SystemExit('独立参考尚未冻结，停止模型运行。')
    receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    stage=ROOT/'原生评审'/('原版试点-'+args.sample if args.pilot else f'{args.sample}-第{args.round}轮')
    state_root=WORK/'d_final_new_samples_state'/stage.name
    if stage.exists() or state_root.exists():raise SystemExit('本轮已存在，保留证据，不重复覆盖。')
    stage.mkdir(parents=True);state_root.mkdir(parents=True)
    store=SessionStore(state_root)
    bridge=native.CodexBridge(stage/'主任务链',args.model)
    transport=screen.CodexScreenTransport(stage/'逐屏链',args.model,100)
    registry=MethodRegistry(FROZEN/'方法专家开发交付-v0.2')
    reviewer=screen.CodexScreenReviewer(registry.criteria,transport)
    service=SessionService(store,registry=registry,model_factory=lambda _:bridge,
        adapters=AdapterHub(browser=BrowserAdapter(allow_local=True)),screen_reviewer=reviewer)
    folder=FOLDERS[args.sample]
    card=(ROOT/'冻结材料'/folder/'任务卡.txt').read_text(encoding='utf-8')
    url='http://127.0.0.1:49920/'+quote(folder)+'/'+quote('打开界面.html')
    request=SessionCreate(purpose='本次检查本机演示原型的实际操作。按以下任务卡执行评审：\n'+card,
        actor=ACTOR,actor_type='ai',provider='generic',model_name=args.model,allow_interaction=True,
        sources=[SourceInput(kind='website',reference=url,title=folder,role='design',
            evidence_kind='observation',version=args.sample+'-v1',declared_by=ACTOR),
            SourceInput(kind='document',title=folder+'任务要求',content=card,role='product_spec',
                version='冻结任务卡-v1',declared_by=ACTOR)],
        limits={'max_model_calls':100,'max_actions':24,'max_checks':160,'max_seconds':7200,
            'max_review_rounds':1,'max_images_per_call':10,'max_parallel_screens':1})
    session=service.create(request)
    save(stage/'创建请求.json',request.model_dump(mode='json'))
    save(stage/'运行环境.json',{'开始':utc(),'来源':'AI 使用真实 Codex CLI + 原生 SessionService / BrowserAdapter / 逐屏生产 review',
        '样本':args.sample,'轮次':args.round,'原版能力试点':args.pilot,'固定响应':False,'答案注入':False,'独立性':'新会话、新浏览器上下文、新状态库，每个模型调用为新的 ephemeral CLI',
        '材料冻结清单SHA256':material_sha,'源码冻结清单SHA256':engine_sha,
        '参考冻结回执SHA256':sha(receipt_path.read_bytes()),'参考回执':receipt,
        '模型':args.model,'运行脚本SHA256':sha(Path(__file__).read_bytes()),
        '主任务桥接SHA256':sha((REPO/'scripts/d_native_recheck.py').read_bytes()),
        '逐屏桥接SHA256':sha((REPO/'scripts/d_screen_codex_probe.py').read_bytes()),
        '源码位置':str(FROZEN),'会话状态库':str(state_root),'会话ID':session.session_id,
        '限额':request.limits.model_dump(),'屏幕审查与任务判断':'独立列出原始输出，不把两类候选简单相加'})
    events=[];started=time.monotonic();print('SESSION',session.session_id,stage.name,flush=True)
    try:
        session=await service.run(session.session_id)
        for index in range(6):
            session=store.get(session.session_id)
            pending=[a for a in session.actions if a.status=='pending']
            allowed=[a for a in pending if any(s.source_id==a.source_id and s.input.reference==url for s in session.sources) and a.kind in {'click','fill','observe','select'}]
            if not allowed:break
            before=stage/f'授权前-{index+1}';before.mkdir();native.export(before,session,store,registry)
            for action in allowed:
                session=store.get(session.session_id)
                event=EventInput(event_id=f'd-new-{stage.name}-{action.action_id}',expected_context_version=session.context_version,
                    actor=ACTOR,actor_type='ai',type='authorize_action',
                    payload={'action_id':action.action_id,'approved':True,'reason':'按已授权任务卡继续本机独立原型操作；只影响当前页面，无外部提交。'})
                session,should_run=service.apply_event(session.session_id,event)
                events.append({'事件':event.model_dump(mode='json'),'应运行':should_run})
                save(stage/'AI操作事件.json',events)
            session=await service.run(session.session_id)
        session=store.get(session.session_id)
        native.export(stage,session,store,registry)
        result=native.summary(session)|{'结束':utc(),'墙钟秒':round(time.monotonic()-started,3),
            '执行来源':'AI 真实模型验收','主任务CLI调用':bridge.calls,'逐屏CLI调用':transport.calls,
            '全部CLI调用':bridge.calls+transport.calls,'逐屏审查':[s.model_dump(mode='json') for s in session.screen_reviews],
            '事件':events}
        save(stage/'运行结果.json',result)
        print(json.dumps({k:result[k] for k in ['状态','完整度','全部CLI调用','墙钟秒','警告']},ensure_ascii=False),flush=True)
    finally:
        await service.close()
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--sample',choices=FOLDERS,required=True)
    parser.add_argument('--round',type=int,choices=[1,2,3],required=True);parser.add_argument('--model',default='gpt-6-astra')
    parser.add_argument('--pilot',action='store_true',help='单列原版能力试点，不并入修后同版三轮')
    asyncio.run(run(parser.parse_args()))

