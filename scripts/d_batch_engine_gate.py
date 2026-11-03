"""用冻结请求检查产品会话的真实停点，在没有模型密钥的环境执行。"""
import argparse
import asyncio
import hashlib
import time
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.parse import urlsplit

from d_codex_batch import OUT, SPEC, read, save, utc
from prepare import inputs, json_bytes
from serve import make_server
from engine import session_adapters
from engine.config import config_health, load_reviewer_config
from engine.session_adapters import AdapterHub, BrowserAdapter
from engine.session_contracts import SessionCreate
from engine.session_service import SessionService
from engine.session_store import SessionStore


async def run(original, archive):
    if config_health(load_reviewer_config())['providers']['qwen']['api_key_configured']:
        raise SystemExit('此脚本只测无密钥的产品停点。当前已配置千问，请用独立的正式批次运行。')
    if inputs() != read(SPEC/'frozen-inputs.json'):
        raise SystemExit('输入与冻结清单不匹配。')
    if archive.exists() and any(archive.iterdir()):
        raise SystemExit('请选择空目录保存这批产品会话。')
    rows=[]
    store=SessionStore(archive)
    hub=AdapterHub(browser=BrowserAdapter(allow_local=True))
    service=SessionService(store,adapters=hub)
    default_validate=session_adapters.validate_browser_url
    async def scoped_validate(url,*,allow_local=False):
        dest=urlsplit(url)
        permitted=(dest.scheme,dest.hostname,dest.port)==('http','127.0.0.1',4311)
        return await default_validate(url,allow_local=permitted and allow_local)
    with make_server(4311,quiet=True) as server:
        thread=Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            with patch.object(session_adapters,'validate_browser_url',scoped_validate):
                primary=[r for r in read(original/'slots.json') if r['primary']]
                for row in primary:
                    slot=row['slot']
                    payload=read(original/'requests'/f'{slot}.json')
                    assert hashlib.sha256(json_bytes(payload)).hexdigest()==row['request_sha256']
                    request=SessionCreate.model_validate(payload)
                    started=time.monotonic()
                    session=service.create(request)
                    finished=await service.run(session.session_id)
                    stored=store.get(session.session_id)
                    assert stored.report_version==finished.report_version
                    assert not stored.model_calls
                    assert stored.status=='awaiting_input'
                    sources=[{'类型':s.input.kind,'标题':s.input.title,'读取':s.acquisition_status,
                              '错误':s.error.split(':',1)[0] if s.error else None,
                              '证据数':sum(e.source_id==s.source_id for e in stored.evidence)}
                             for s in stored.sources if not s.input.reference.startswith('user://')]
                    reasons=[q.text for q in stored.questions if q.blocking and not q.answered]
                    assert reasons and sources
                    rows.append({'位置':slot,'原请求指纹':row['request_sha256'],'会话':session.session_id,
                                 '运行':session.run_id,'状态':stored.status,'报告版本':stored.report_version,
                                 '千问调用':len(stored.model_calls),'主要停点':reasons,'来源':sources,
                                 '耗时秒':round(time.monotonic()-started,2)})
                    await hub.browser.close_session(session.session_id)
                    save(OUT/'产品引擎首轮.json',{'时间':utc(),'正式配置':'qwen / qwen3.8-max-0902',
                         '来源':'原批次全部 18 个任务×条件组合的首轮位置','本地会话目录':archive.name,'首轮':rows})
                    print(slot,stored.status,flush=True)
        finally:
            await service.close()
            server.shutdown()
            thread.join()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original',type=Path)
    parser.add_argument('archive',type=Path)
    args=parser.parse_args()
    asyncio.run(run(args.original.resolve(),args.archive.resolve()))
