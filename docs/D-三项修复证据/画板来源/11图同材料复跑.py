"""用 11 张冻结截图检验修前和修后适配器的来源判断。"""
import asyncio
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
from engine import session_adapters
from engine.errors import EngineError
from engine.session_contracts import SessionCreate
from engine.session_service import SessionService
from engine.session_store import SessionStore

FILE_KEY = 'j9Z5Y839AREXf0OPysbbJ7'
WRONG_KEY = 'DWrongFileForTest'
BASELINE = 'ec17fea'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def previous_adapter(directory):
    data = subprocess.check_output(
        ['git', 'show', f'{BASELINE}:engine/session_adapters.py'], cwd=REPO,
    )
    path = directory / 'baseline.py'
    path.write_bytes(data)
    spec = importlib.util.spec_from_file_location('engine._d_baseline_adapters', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, sha(data)


def freeze_inputs(snapshot):
    index = json.loads((REPO / 'docs/D-续测证据/批次/材料索引.json').read_bytes())['任务']
    tasks = json.loads((REPO / 'fixtures/d-v02-batch/tasks.json').read_bytes())['tasks']
    result = []
    manifest = {'file_key': FILE_KEY, 'nodes': {}}
    (snapshot / 'images').mkdir(parents=True)
    for task in (t for t in tasks if t['id'] in {'T07', 'T08'}):
        for node, item in zip(task['nodes'], index[task['id']], strict=True):
            assert item['画面内容或先前动作'] == f'画板视图 {node}'
            data = (REPO / item['文件']).read_bytes()
            assert sha(data) == item['SHA256']
            with Image.open(io.BytesIO(data)) as original:
                rgb = original.convert('RGB')
            new = snapshot / 'images' / f'{node}.png'
            rgb.save(new)
            with Image.open(new) as png:
                assert png.convert('RGB').tobytes() == rgb.tobytes()
            node_id = node.replace('-', ':')
            manifest['nodes'][node_id] = {'name': Path(item['文件']).stem, 'width': rgb.width, 'height': rgb.height}
            result.append({'任务': task['id'], '节点': node_id, '归档': item['文件'], '原图SHA256': sha(data),
                           '清单PNG的SHA256': sha(new.read_bytes()), 'RGB像素SHA256': sha(rgb.tobytes()),
                           '尺寸': list(rgb.size)})
    assert len(result) == len(manifest['nodes']) == 11
    (snapshot / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    return result


def stop_before_model(_):
    raise EngineError('api_key_missing', '本轮只验材料。', status_code=503)


async def exercise(module, root, store_path, inputs):
    service = SessionService(
        SessionStore(store_path), adapters=module.AdapterHub(figma=module.FigmaMCPAdapter(snapshot_root=root)),
        model_factory=stop_before_model,
    )
    matrix = [('原文件', FILE_KEY, i['节点']) for i in inputs]
    matrix += [('错文件同节点', WRONG_KEY, i['节点']) for i in inputs]
    matrix += [('清单无节点', FILE_KEY, '999999:999999')]
    rows = []
    try:
        for kind, key, node in matrix:
            request = SessionCreate(
                purpose='核实归档截图的来源', sources=[{
                    'kind': 'figma_board', 'role': 'design', 'figma_snapshot_id': 'frozen',
                    'reference': f'https://www.figma.com/design/{key}/D?node-id={node.replace(":", "-")}',
                }],
            )
            session = await service.run(service.create(request).session_id)
            source = session.sources[0]
            evidence = [e for e in session.evidence if e.source_id == source.source_id]
            actual = []
            for item in evidence:
                image_hash = pixels = size = None
                if item.artifact_id:
                    artifact, _ = service.store.artifact(session.session_id, item.artifact_id)
                    image_hash = sha(artifact.read_bytes())
                    with Image.open(artifact) as png:
                        pixels, size = sha(png.convert('RGB').tobytes()), list(png.size)
                actual.append({'证据类型': item.kind, '来源键': item.locator.get('file_key'),
                               '来源匹配': item.locator.get('file_identity_verified'), '节点': item.locator.get('node_id'),
                               '范围标记': item.locator.get('file_scope'), '存储PNG的SHA256': image_hash,
                               'RGB像素SHA256': pixels, '尺寸': size})
            rows.append({'场景': kind, '请求文件': key, '请求节点': node, '会话': session.session_id,
                         '状态': source.acquisition_status, '错误': source.error, '证据': actual})
    finally:
        await service.close()
    return rows


async def main(target):
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        inputs = freeze_inputs(root / 'frozen')
        old, old_digest = previous_adapter(root)
        before = await exercise(old, root, root/'before', inputs)
        after = await exercise(session_adapters, root, root/'after', inputs)
    for row, prior, current in zip(inputs, before, after):
        for actual in (prior, current):
            assert actual['状态'] == 'success' and len(actual['证据']) == 1
            image = actual['证据'][0]
            assert image['来源匹配'] and image['节点'] == row['节点']
            assert image['RGB像素SHA256'] == row['RGB像素SHA256'] and image['尺寸'] == row['尺寸']
            assert image['存储PNG的SHA256'] == row['清单PNG的SHA256']
    for row, prior, current in zip(inputs, before[11:22], after[11:22], strict=True):
        assert prior['状态'] == 'success' and prior['证据'][0]['来源匹配'] is False
        assert prior['证据'][0]['RGB像素SHA256'] == row['RGB像素SHA256']
        assert current['状态'] == 'failed' and current['证据'] == [] and 'figma_snapshot_file_mismatch' in current['错误']
    assert before[-1]['状态'] == 'partial' and before[-1]['证据'][0]['范围标记'] == 'verified_snapshot'
    assert after[-1]['状态'] == 'failed' and after[-1]['证据'] == [] and 'figma_snapshot_node_missing' in after[-1]['错误']
    result = {'修前适配器提交': BASELINE, '修前适配器SHA256': old_digest,
              '修后适配器SHA256': sha((REPO/'engine/session_adapters.py').read_bytes()),
              '材料生成': '按 D 批次与组内画板文档登记的文件键、节点与 JPEG 构造临时离线快照。对 JPEG 解码后的 RGB 像素做无损 PNG 封装。清单以外不生成 XML。报告从会话磁盘存储重新读取图片对照原像素。',
              '原文件键': FILE_KEY, '输入': inputs, '修前': before, '修后': after}
    with target.open('x', encoding='utf-8') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
    print('46 个会话完成，22 次正确来源取图逐像素一致。修后 12 个错误来源均为零证据。')


if __name__ == '__main__':
    asyncio.run(main(Path(sys.argv[1])))
