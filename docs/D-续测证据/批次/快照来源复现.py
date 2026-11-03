"""用临时测试图复现 Figma 文件或节点不匹配时，引擎如何登记材料。"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from engine.errors import EngineError
from engine.session_adapters import AdapterHub, FigmaMCPAdapter
from engine.session_contracts import SessionCreate
from engine.session_service import SessionService
from engine.session_store import SessionStore


def no_paid_model(_):
    raise EngineError('api_key_missing', '隔离测试在模型调用前停止。', status_code=503)


async def main():
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        snap = root / 'sample'
        (snap/'images').mkdir(parents=True)
        (snap/'metadata').mkdir()
        Image.new('RGB', (40, 28), 'blue').save(snap/'images/1-1.png')
        (snap/'metadata/1-1.xml').write_text('<frame id="1:1" name="文件A的测试画面" x="0" y="0" width="40" height="28"/>', encoding='utf-8')
        (snap/'manifest.json').write_text(json.dumps({'file_key':'fileA','nodes':{'1:1':{'name':'测试画面'}}}), encoding='utf-8')
        service = SessionService(SessionStore(root/'sessions'), adapters=AdapterHub(figma=FigmaMCPAdapter(snapshot_root=root)), model_factory=no_paid_model)
        try:
            for title,key,node in [('正确文件及节点','fileA','1-1'),('错文件，同节点号','fileB','1-1'),('正确文件，节点不存在','fileA','9-9')]:
                req = SessionCreate(purpose='核对来源身份。',sources=[{'kind':'figma_board','reference':f'https://www.figma.com/design/{key}/Test?node-id={node}','figma_snapshot_id':'sample','role':'design'}])
                final = await service.run(service.create(req).session_id)
                src = final.sources[0]
                evidence = [e for e in final.evidence if e.source_id==src.source_id]
                results.append({'场景':title,'请求文件':key,'请求节点':node,'会话材料状态':src.acquisition_status,
                    '来源错误':src.error,'证据':[{'证据类型':e.kind,'有截图':bool(e.artifact_id),
                        '文件身份匹配':e.locator.get('file_identity_verified'),'范围标记':e.locator.get('file_scope'),
                        '节点':e.locator.get('node_id'),'登记的节点列表':e.locator.get('node_ids')} for e in evidence]})
        finally:
            await service.close()
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__=='__main__':
    asyncio.run(main())
