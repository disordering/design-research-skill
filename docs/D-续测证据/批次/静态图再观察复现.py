"""单独复现已读静态图的 observe 是否需要授权，以及授权后的执行结果。"""
import asyncio
import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
from engine.errors import EngineError
from engine.session_adapters import AdapterHub
from engine.session_contracts import Action, SourceInput, SourceRecord


async def main():
    hub = AdapterHub()
    try:
        raw = (REPO/'fixtures/d-v02-static/T02.png').read_bytes()
        src = SourceRecord(input=SourceInput(kind='image', role='design', image_base64=base64.b64encode(raw).decode()))
        capture = await hub.read('d-observe-probe',src)
        action = Action(kind='observe', source_id=src.source_id, expected_state_id=capture.state_id,
                        reason='再观察同一张静态图。', requires_explicit_authorization=False)
        confirm = await hub.needs_authorization('d-observe-probe',src,action)
        evidence = {'来源':'T02 静态图','首次读取取得图像':bool(capture.image),'动作':action.kind,
                    '动作本身要求显式授权':action.requires_explicit_authorization,
                    '适配器返回需要授权':confirm}
        try:
            response = await hub.act('d-observe-probe',src,action,authorized=True)
            evidence['授权后取得图像']=bool(response.image)
        except EngineError as exc:
            evidence['授权后实际错误']={'代码':exc.code,'消息':exc.message}
        (HERE/'静态图再观察实测.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    finally:
        await hub.close()

if __name__=='__main__':
    asyncio.run(main())
