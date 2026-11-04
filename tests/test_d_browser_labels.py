"""用真实浏览器核对关联标签命名与错误点击拦截。"""
import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading

import pytest

from engine.errors import EngineError
from engine.session_adapters import BrowserAdapter
from engine.session_contracts import Action, SourceInput, SourceRecord
from engine.session_targets import normalize_label


@contextmanager
def serve(raw):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(raw)
        def log_message(self, *_):
            pass
    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}/'
        finally:
            server.shutdown()
            thread.join(3)


def test_h05_radio_label_accepts_correct_target_and_rejects_wrong_target():
    raw = (Path(__file__).resolve().parents[1] / 'docs/D-新版真人执行/03-匿名原始任务/C-H05/打开界面.html').read_bytes()
    async def run(url):
        browser = BrowserAdapter(allow_local=True)
        source = SourceRecord(input=SourceInput(kind='website', reference=url))
        try:
            before = await browser.read('h05', source)
            afternoon = next(c for c in before.controls if c['type'] == 'radio' and not c['checked'])
            assert normalize_label(afternoon['label']) == normalize_label('周五14:00–14:30 二层服务台')
            wrong = Action(source_id=source.source_id, kind='click', selector=afternoon['selector'],
                           target_label='周五09:00–09:30 一层服务台', expected_state_id=before.state_id,
                           reason='核对错误目标是否仍被拦截', requires_explicit_authorization=False)
            with pytest.raises(EngineError) as error:
                await browser.act('h05', source, wrong, authorized=False)
            assert error.value.code == 'action_target_mismatch'
            correct = wrong.model_copy(update={'target_label': '周五14:00–14:30 二层服务台'})
            assert not await browser.action_needs_authorization('h05', source, correct)
            after = await browser.act('h05', source, correct, authorized=False)
            assert next(c for c in after.controls if c['selector'] == afternoon['selector'])['checked']
        finally:
            await browser.close()
    with serve(raw) as url:
        asyncio.run(run(url))


def test_external_labels_and_aria_names_preserve_distinct_targets():
    raw = '''<!doctype html><meta charset="utf-8"><body>
    <label for="outside">外置的时段标签</label><input id="outside" type="radio" name="slot">
    <span id="date">周五</span><span id="place">二层服务台</span>
    <input id="referenced" type="checkbox" aria-labelledby="date place">
    <label><input id="explicit" type="checkbox" aria-label="自定义可访问名称">页面标签</label>
    <label><input id="sensitive" type="checkbox">提交购买</label>
    <button id="save">保存</button></body>'''.encode('utf-8')
    async def run(url):
        browser = BrowserAdapter(allow_local=True)
        source = SourceRecord(input=SourceInput(kind='website', reference=url))
        try:
            capture = await browser.read('labels', source)
            controls = {c['domId']: c for c in capture.controls}
            assert controls['outside']['label'] == '外置的时段标签'
            assert controls['referenced']['label'] == '周五 二层服务台'
            assert controls['explicit']['label'] == '自定义可访问名称'
            assert controls['save']['label'] == '保存'
            assert await browser.action_needs_authorization('labels', source, Action(
                source_id=source.source_id, kind='click', selector=controls['sensitive']['selector'],
                target_label='提交购买', expected_state_id=capture.state_id,
                reason='核对关联标签仍参与副作用检查', requires_explicit_authorization=False,
            ))
        finally:
            await browser.close()
    with serve(raw) as url:
        asyncio.run(run(url))
