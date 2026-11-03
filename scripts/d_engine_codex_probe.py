"""用登录的 Codex 在真实 SessionService 上试跑一个静态图会话。"""
import asyncio
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from d_codex_batch import OUT, MODEL, read, save, utc
from prepare import assemble
from engine.config import config_health, load_reviewer_config
from engine.errors import EngineError
from engine.model import ModelCallResult
from engine.session_contracts import SessionCreate
from engine.methods import MethodRegistry
from engine.session_report import write_report_package, zip_report_package
from engine.session_service import SessionService
from engine.session_store import SessionStore

FULL='--full' in sys.argv[1:]
TRACE=OUT/('引擎接Codex原预算' if FULL else '引擎接Codex')
ARCHIVE_NAME='D-引擎Codex单案原预算会话' if FULL else 'D-引擎Codex单案会话'


def export_package(session, store, registry):
    directory=store.root/'原生报告'
    write_report_package(session,store,directory,registry=registry)
    zip_report_package(directory,TRACE/'产品报告包.zip')


class CodexBridge:
    supports_images=True
    is_stub=False

    def __init__(self):
        self.calls=0

    async def complete(self,messages,**kwargs):
        self.calls+=1
        return await asyncio.to_thread(self.complete_sync,self.calls,messages)

    def complete_sync(self,idx,messages):
        tic=time.monotonic()
        texts=['你替一个 JSON 接口作答。根据下面原始消息，回复单个合法 JSON 对象，不加代码块。只处理给定文字和附图，不调用工具。建议和理由请简短，保留所需编号。']
        op=json.loads(messages[1]['content'][0]['text'])['operation']
        with tempfile.TemporaryDirectory(prefix='d-engine-') as t:
            cwd=Path(t)
            cmd=[os.environ['CODEX_APP_RUNTIME_CLI_PATH'],'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check',
                 '--sandbox','read-only','--cd',t,'--model',MODEL,'-c','model_reasoning_effort=low','--json']
            image_hashes=[]
            for message in messages:
                texts.append('['+message['role']+']')
                content=message['content']
                if isinstance(content,str):
                    texts.append(content)
                    continue
                for part in content:
                    if part['type']=='text':
                        texts.append(part['text'])
                    elif part['type']=='image_url':
                        header,data=part['image_url']['url'].split(',',1)
                        raw=base64.b64decode(data,validate=True)
                        path=cwd/f"screen-{len(image_hashes)+1}.{'png' if 'png' in header else 'jpeg'}"
                        path.write_bytes(raw)
                        image_hashes.append(hashlib.sha256(raw).hexdigest())
                        texts.append(f'[随附图片 {len(image_hashes)}]')
                        cmd+=['--image',str(path)]
            prompt='\n'.join(texts)
            marker={'次序':idx,'操作':op,'输入文本字符':len(prompt),'输入文本SHA256':hashlib.sha256(prompt.encode()).hexdigest(),'图片指纹':image_hashes,'开始':utc()}
            path=TRACE/'调用'/f'{idx:02d}-{op}.json'
            save(path,marker)
            try:
                proc=subprocess.run(cmd+['-'],cwd=t,input=prompt.encode(),capture_output=True,timeout=100)
            except subprocess.TimeoutExpired:
                raise EngineError('codex_cli_timeout','Codex 单次调用超过 100 秒。',status_code=504)
            events=[json.loads(line) for line in proc.stdout.decode('utf-8',errors='replace').splitlines() if line.startswith('{')]
            items=[e['item'] for e in events if e.get('type')=='item.completed']
            response=next((i.get('text') for i in reversed(items) if i.get('type')=='agent_message'),None)
            completed=next((e for e in events if e.get('type')=='turn.completed'),None)
            if proc.returncode or not completed or not response:
                raise EngineError('codex_cli_failed','本次 Codex CLI 未返回完整响应。',status_code=502)
            if any(i['type'] not in ('reasoning','agent_message') for i in items):
                raise EngineError('unexpected_tool','该模型回合调用了额外工具。',status_code=502)
            sid=next(e['thread_id'] for e in events if e.get('type')=='thread.started')
            took=round(1000*(time.monotonic()-tic))
            marker.update(Codex会话=sid,模型原答=response,实际耗时毫秒=took)
            save(path,marker)
            print(idx,op,'received',flush=True)
            return ModelCallResult(text=response,provider='codex_cli',model=MODEL,usage=completed.get('usage',{}),
                                   request_id=sid,latency_ms=took,json_mode_used=False)


async def main():
    if config_health(load_reviewer_config())['providers']['qwen']['api_key_configured']:
        raise SystemExit('该离线联调要求千问未配置，以隔离逐屏模型。')
    if TRACE.exists() and any(TRACE.iterdir()):
        raise SystemExit('本次联调只跑一次。')
    from d_codex_batch import REPO
    archive=REPO.parent/'outputs'/ARCHIVE_NAME
    req=assemble({'provider':'generic','model_name':MODEL})[1]['T02-A-01']
    if not FULL:
        req['limits'].update(max_model_calls=12,max_seconds=540,max_checks=4,max_review_rounds=1)
    store=SessionStore(archive)
    bridge=CodexBridge()
    service=SessionService(store,model_factory=lambda _:bridge)
    try:
        session=service.create(SessionCreate.model_validate(req))
        final=await service.run(session.session_id)
        saved=store.get(session.session_id)
        assert saved.report_version==final.report_version
        export_package(saved,store,service.registry)
        save(TRACE/'联调结果.json',{'任务':'T02 静态图','运行类型':'SessionService 注入本地 Codex CLI 适配器',
            '日期':utc(),'模型':MODEL,'会话':saved.session_id,'报告版本':saved.report_version,'会话状态':saved.status,
            '完整度':saved.report_completeness,'限制':req['limits'],'引擎模型回合':saved.model_calls,
            '警告':saved.warnings,'限制说明':saved.run_limitations,'契约问题':saved.contract_violations,
            '问题数':len(saved.findings),'问题':[f.title for f in saved.findings]})
        print(saved.status,saved.report_version,len(saved.model_calls),len(saved.findings),flush=True)
    finally:
        await service.close()


if __name__=='__main__':
    if 'export' in sys.argv[1:]:
        from d_codex_batch import REPO
        store=SessionStore(REPO.parent/'outputs'/ARCHIVE_NAME)
        saved_result=read(TRACE/'联调结果.json')
        session=store.report(saved_result['会话'],saved_result['报告版本'])
        export_package(session,store,MethodRegistry(REPO/'方法专家开发交付-v0.2'))
    else:
        asyncio.run(main())
