"""在原预算 T02 会话中模拟一次只读授权，到达已知工具停点后保存版本。"""
import asyncio
import hashlib
from d_codex_batch import OUT, REPO, read, save, utc
import d_engine_codex_probe as probe
from engine.session_contracts import EventInput
from engine.session_service import SessionService
from engine.session_store import SessionStore


async def main():
    parent=OUT/'引擎接Codex原预算'
    record=parent/'授权与澄清'
    if record.exists():
        raise SystemExit('本次授权只执行一次。')
    sid=read(parent/'联调结果.json')['会话']
    store=SessionStore(REPO.parent/'outputs'/'D-引擎Codex单案原预算会话')
    original=store.report(sid,1)
    original_hash=hashlib.sha256(original.model_dump_json().encode()).hexdigest()
    pending=[a for a in original.actions if a.status=='pending']
    assert len(pending)==1 and pending[0].kind=='observe'
    target=pending[0]
    assert next(s for s in original.sources if s.source_id==target.source_id).input.kind=='image'
    assert store.get(sid).report_version==1 and store.get(sid).status=='awaiting_input'
    probe.TRACE=record
    class StopAtKnownToolError(probe.CodexBridge):
        async def complete(self,messages,**kwargs):
            current=store.get(sid)
            if any(a.action_id==target.action_id and a.status=='failed' for a in current.actions):
                # 已经碰到用户约定的停止条件。保持事件循环可用，交给操作员结束。
                await asyncio.Event().wait()
            return await super().complete(messages,**kwargs)
    bridge=StopAtKnownToolError()
    service=SessionService(store,model_factory=lambda _:bridge)
    log=[]
    actor='AI模拟操作员-D'
    def event(name,kind,payload):
        state=store.get(sid)
        msg=EventInput(event_id='d-t02-original-'+name,expected_context_version=state.context_version,
                       actor=actor,type=kind,payload=payload)
        updated,should=service.apply_event(sid,msg)
        log.append({'时刻':utc(),'事件':msg.model_dump(mode='json'),'服务返回':{'应继续运行':should,'会话状态':updated.status,'报告版本':updated.report_version,'上下文版本':updated.context_version}})
        return updated,should
    try:
        _,go=event('observe','authorize_action',{'action_id':target.action_id,'approved':True})
        assert go
        service.submit(sid)
        failure=None
        for _ in range(900):
            current=store.get(sid)
            action=next(a for a in current.actions if a.action_id==target.action_id)
            if action.status=='failed' and 'source_not_interactive' in action.error:
                failure=action
                break
            await asyncio.sleep(0.2)
        if failure is None:
            raise RuntimeError('授权已保留，但本次没有等到预期的工具停点。')
        clarifications=[q for q in current.questions if not q.answered and q.kind=='context' and '作业到期' in q.text]
        assert len(clarifications)==1
        q=clarifications[0]
        reply='任务卡要求检查通知偏好与页面当前状态的表达。设计要求未提供“作业到期”的选中值和可用性，只评画面可见性。'
        event('clarify','reply',{'question_id':q.question_id,'text':reply})
        final,_=event('finish','finish',{})
        historical=store.report(sid,1)
        updated=store.report(sid,final.report_version)
        v1_hash=hashlib.sha256(historical.model_dump_json().encode()).hexdigest()
        old_zip=parent/'产品报告包.zip'
        package_dir=store.root/'原生报告-授权后'
        from engine.session_report import write_report_package, zip_report_package
        record.mkdir(parents=True,exist_ok=True)
        write_report_package(updated,store,package_dir,registry=service.registry)
        zip_report_package(package_dir,record/'授权后产品报告包.zip')
        record_questions=[{'问题':v.text,'已答':v.answered,'答复':v.answer,'程序默认来源字段':v.answer_actor} for v in updated.questions if v.question_id in (q.question_id,*[z.question_id for z in original.questions if z.action_id==target.action_id])]
        assert v1_hash==original_hash and old_zip.exists() and updated.report_version>1
        save(record/'同会话续测.json',{'会话':sid,'实际操作员':actor,'起始版本':1,'授权对象':{'来源':target.source_id,'种类':'静态图','动作':target.action_id,'理由':target.reason},
            '事件轨迹':log,'获批动作实际结果':{'状态':failure.status,'错误':failure.error},
            '澄清':record_questions,'结束动作':'工具明确无法执行，记录事实答复后使用产品 finish 保存本轮，无重复授权。',
            '末版':updated.report_version,'末版状态':updated.status,'末版完整度':updated.report_completeness,
            '新增模型调用':len(updated.model_calls)-len(original.model_calls),'追加问题数':len(updated.findings)-len(original.findings),
            '原版本续测前指纹':original_hash,'原版本续测后指纹':v1_hash,'原版本可回读':True})
        print('v1 ->',updated.report_version,failure.error,'原始版本指纹一致',flush=True)
    finally:
        await service.close()


if __name__=='__main__':
    asyncio.run(main())
