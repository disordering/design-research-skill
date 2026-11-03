"""只读输入连通检查，不创建评审会话，不配置或调用模型。"""
import asyncio
import hashlib
import io
import ipaddress
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from PIL import Image
from prepare import HERE, WEB, assemble, write_json
from engine import session_adapters
from engine.errors import EngineError
from engine.imaging import prepare_image
from engine.session_adapters import BrowserAdapter, FigmaMCPAdapter
from engine.session_contracts import SourceInput, SourceRecord
from engine.session_materials import DocumentReader

sys.path.insert(0, str(WEB))
from serve import make_server

EVIDENCE = HERE / 'access-evidence'
EXPECTED = {'T03': '预约讨论室', 'T04': '设置打印单', 'T05': '填写工单', 'T06': '周末活动'}


def wrap(value):
    return SourceRecord(input=SourceInput.model_validate(value))


def describe_error(exc):
    return {'result':'blocked', 'error': getattr(exc, 'code', type(exc).__name__),
            'message': str(exc)[:280]}


def record_capture(task, capture):
    loc = capture.locator
    sample = {'partial':capture.partial, 'state_id':capture.state_id,
              'title':loc.get('title'), 'url':loc.get('url'), 'render':loc.get('render_state'),
              'canvas':loc.get('prototype_canvas'), 'control_count':len(capture.controls),
              'text':capture.content[:650], 'bytes':len(capture.image or b'')}
    if capture.image:
        with Image.open(io.BytesIO(capture.image)) as im:
            sample['dimensions'] = list(im.size)
            sample['image_extrema'] = [list(pair) for pair in im.convert('RGB').getextrema()]
        sample['sha256'] = hashlib.sha256(capture.image).hexdigest()
        filename = task + ('.jpg' if capture.image.startswith(b'\xff\xd8') else '.png')
        (EVIDENCE / filename).write_bytes(capture.image)
        sample['image'] = filename
    return sample


async def local_browser(matrix):
    samples = []
    real_validate = session_adapters.validate_browser_url
    blocked = BrowserAdapter()
    try:
        try:
            await blocked.read('guard-default', wrap(matrix['T03-A-01']['sources'][0]))
            raise AssertionError('默认保护未阻止本机 URL')
        except EngineError as error:
            if error.code != 'private_network_blocked':
                raise
            guard = describe_error(error)
    finally:
        await blocked.close()

    async def fixture_only(url, *, allow_local=False):
        parsed = urlsplit(url)
        if (parsed.scheme, parsed.hostname, parsed.port) != ('http', '127.0.0.1', 4311):
            raise EngineError('outside_fixture', '地址超出受控测试站点。', status_code=403)
        await real_validate(url, allow_local=allow_local)

    try:
        server = make_server(4311, quiet=True)
    except OSError as exc:
        return guard, [dict(task=k, **describe_error(exc)) for k in EXPECTED]
    with server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        adapter = BrowserAdapter(allow_local=True)
        try:
            with patch.object(session_adapters, 'validate_browser_url', fixture_only):
                for task, expected in EXPECTED.items():
                    src = wrap(matrix[f'{task}-A-01']['sources'][0])
                    try:
                        captured = await adapter.read('input-only-'+task, src)
                        row = record_capture(task, captured)
                        ok = (expected in captured.content and row['bytes'] > 0 and
                              captured.locator['url'] == src.input.reference and not captured.partial)
                        samples.append({'task':task, 'result':'verified' if ok else 'partial', **row})
                    except Exception as exc:
                        samples.append(dict(task=task, **describe_error(exc)))
        finally:
            await adapter.close()
            server.shutdown()
            thread.join()
    return guard, samples


async def prototype(task, entry):
    adapter = BrowserAdapter()
    try:
        source = wrap(entry)
        cap = await asyncio.wait_for(adapter.read('input-only-'+task, source), 55)
        if cap.partial or not cap.locator.get('prototype_canvas'):
            # Figma shell may appear before the canvas. Reobserve the existing page.
            for seconds in (2, 4):
                await asyncio.sleep(seconds)
                cap = await asyncio.wait_for(adapter.capture('input-only-'+task, source), 18)
                if not cap.partial and cap.locator.get('prototype_canvas'):
                    break
        row = record_capture(task, cap)
        node = lambda url: parse_qs(urlsplit(url).query).get('node-id', [])
        pixel_varies = any(hi > lo for lo, hi in row.get('image_extrema', []))
        ok = (node(row['url']) == node(source.input.reference) and bool(row['canvas']) and
              pixel_varies and row['render'] == 'captured' and not cap.partial)
        return {'task':task, 'result':'entry_capture' if ok else 'partial', **row}
    except Exception as exc:
        return dict(task=task, **describe_error(exc))
    finally:
        await adapter.close()


async def desktop_board(entry):
    endpoint = 'http://127.0.0.1:3845/mcp'
    try:
        conn = await asyncio.wait_for(asyncio.open_connection('127.0.0.1',3845), 2)
        conn[1].close()
        await conn[1].wait_closed()
    except (OSError, asyncio.TimeoutError) as exc:
        return {'endpoint':endpoint,'tcp':'unreachable', 'node_verified':False,
                'error':type(exc).__name__, 'os_error':getattr(exc, 'errno', None)}
    adapter = FigmaMCPAdapter(endpoint=endpoint, token='')
    try:
        cap = await asyncio.wait_for(adapter.read('input-only-board', wrap(entry)), 55)
        locator = cap.locator
        target = parse_qs(urlsplit(entry['reference']).query)['node-id'][0].replace('-',':')
        return {'endpoint':endpoint, 'tcp':'reachable', 'target':target, 'partial':cap.partial,
                'actual_node':locator.get('node_id'), 'file_identity_verified':locator.get('file_identity_verified'),
                'node_verified':locator.get('node_id') == target and bool(locator.get('file_identity_verified')),
                'image_bytes':len(cap.image or b'')}
    except Exception as exc:
        return dict(endpoint=endpoint, tcp='reachable', node_verified=False, **describe_error(exc))


async def inline_materials(matrix):
    docs = []
    reader = DocumentReader(allow_local=False)
    for task in EXPECTED:
        for src in matrix[task+'-C-01']['sources'][1:]:
            cap = await reader.read('input-only-doc', wrap(src))
            docs.append({'task':task, 'source':src['title'], 'characters':len(cap.content),
                         'partial':cap.partial, 'state_id':cap.state_id})
    imgs = []
    for task in ('T01', 'T02'):
        path = HERE.parent / 'd-v02-static' / (task+'.png')
        output = prepare_image(path.read_bytes(), filename=path.name)
        imgs.append({'task':task,'width':output.width,'height':output.height,'sha256':output.sha256})
    return imgs, docs


def figma_dns():
    hostname = 'www.figma.com'
    try:
        rows = socket.getaddrinfo(hostname, 443)
        addresses = sorted({row[4][0] for row in rows})
        return {'host':hostname, 'addresses':[
            {'address':addr, 'is_global':ipaddress.ip_address(addr).is_global}
            for addr in addresses]}
    except OSError as exc:
        return {'host':hostname, **describe_error(exc)}


async def main():
    spec, matrix, _ = assemble({'provider':'qwen','model_name':'qwen3.8-max-0902'})
    EVIDENCE.mkdir(exist_ok=True)
    guard, websites = await local_browser(matrix)
    proto, board, material = await asyncio.gather(
        asyncio.gather(*(prototype(t,matrix[t+'-A-01']['sources'][0]) for t in ('T09','T10'))),
        desktop_board(matrix['T07-A-01']['sources'][0]), inline_materials(matrix))
    results = {'batch':spec['version'], 'utc':datetime.now(timezone.utc).isoformat(),
               'scope':'只读取输入；无正式评审会话、模型调用或账号登录',
               'default_private_guard':guard,'websites':websites,'prototypes':proto,
               'prototype_host_dns':figma_dns(),
               'desktop_mcp':board,'static_images':material[0],'inline_documents':material[1]}
    write_json(EVIDENCE / 'access.json', results)
    print(json.dumps({'web':[(x['task'],x['result']) for x in websites],
                      'proto':[(x['task'],x['result']) for x in proto],
                      'board':board,'static':len(material[0]),'docs':len(material[1])}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
