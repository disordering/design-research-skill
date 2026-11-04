"""浏览器核对新建、等待状态和 AI 操作者来源，模型为固定回归夹具。"""
import argparse
import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extra-site', action='append', default=[])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--sessions', type=Path, required=True)
    args = parser.parse_args()
    import site
    for dep in args.extra_site:
        site.addsitedir(str(Path(dep).resolve()))
    import uvicorn
    from playwright.sync_api import sync_playwright, expect
    from engine.api import create_app
    from engine.session_service import SessionService
    from engine.session_store import SessionStore
    from test_session_service import FixtureModel

    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit('请指定新的存档目录。')
    out.mkdir(parents=True, exist_ok=True)
    result = {'运行方式': '真实浏览器、Node 代理和原生后端，模型使用固定回归夹具',
              '操作者': 'AI回归-D', '模型效果计入': False, '结果': {}, '浏览器异常': []}
    with contextlib.ExitStack() as stack:
        service = SessionService(SessionStore(args.sessions.resolve()), model_factory=lambda _: FixtureModel(question=True))
        app = create_app(session_service_factory=lambda: service)
        sock = stack.enter_context(socket.socket())
        sock.bind(('127.0.0.1', 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        thread.start()
        def stop():
            server.should_exit = True
            thread.join(4)
        stack.callback(stop)
        node = subprocess.Popen([shutil.which('node'), '--input-type=module', '-e',
            f"import {{createServer}} from './server.mjs';createServer('http://127.0.0.1:{sock.getsockname()[1]}').listen(4173,'127.0.0.1',()=>console.log('ready'));"],
            cwd=ROOT/'frontend', stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        def stopnode():
            if node.poll() is None:
                node.terminate()
                node.wait(4)
        stack.callback(stopnode)
        assert node.stdout.readline().decode().strip() == 'ready'
        pw = stack.enter_context(sync_playwright())
        browser = pw.chromium.launch()
        stack.callback(browser.close)
        page = browser.new_page(locale='zh-CN', viewport={'width': 1360, 'height': 900})
        page.on('pageerror', lambda e: result['浏览器异常'].append(str(e)))
        page.goto('http://127.0.0.1:4173/session.html')
        page.locator('#actor').fill('AI回归-D')
        page.locator('#actorType').select_option('ai')
        page.locator('#kind').select_option('document')
        page.locator('#role').select_option('product_spec')
        page.locator('#sourceTitle').fill('回归夹具要求')
        page.locator('#content').fill('保存成功后显示结果。')
        page.locator('#add').click()
        expect(page.locator('#drafts')).to_contain_text('回归夹具要求')
        page.locator('#purpose').fill('检查保存设置')
        page.locator('#model').fill('固定回归夹具')
        with page.expect_response(lambda r: r.url.endswith('/api/review-sessions') and r.request.method == 'POST') as response:
            page.locator('#create button').click()
        created = response.value.json()
        sid = created['session_id']
        endpoint = 'http://127.0.0.1:4173/engine/api/review-sessions/' + sid
        expect(page.locator('#runProgress')).to_contain_text('点击开始运行')
        assert '本轮已结束' not in page.locator('#runProgress').inner_text()
        result['结果']['创建'] = {'状态': created['status'], '提示': page.locator('#runProgress').inner_text(),
                                  '任务消息': created['messages'][0]}
        page.screenshot(path=out/'01-创建.png')
        page.locator('[data-event=resume]').click()
        expect(page.locator('[data-answer-form]').first).to_be_visible(timeout=60000)
        expect(page.locator('#runProgress')).to_contain_text('本轮等待补充')
        state = page.request.get(endpoint).json()
        result['结果']['等待'] = {'状态': state['status'], '提示': page.locator('#runProgress').inner_text()}
        page.screenshot(path=out/'02-等待.png')
        form = page.locator('[data-answer-form]').first
        form.locator('[name=text]').fill('AI回归答复，目标用户是课程案例中的设置页使用者。')
        with page.expect_response(lambda r: r.url.endswith('/events') and r.request.method == 'POST') as response:
            form.locator('button').click()
        replied = response.value.json()
        result['结果']['回答'] = {'HTTP': response.value.status,
                                  '问答': [q for q in replied['questions'] if q['answered']],
                                  '事件': replied['messages'][-1]}
        assert result['结果']['回答']['问答'][0]['answer_actor'] == 'ai'
        # 固定夹具每次实例会再次提问，使用产品结束操作保存已回收的来源与问答。
        expect(page.locator('#runProgress')).to_contain_text('本轮等待补充', timeout=60000)
        with page.expect_response(lambda r: r.url.endswith('/events') and r.request.method == 'POST'):
            page.locator('[data-event=finish]').click()
        expect(page.locator('#runProgress')).to_contain_text('本轮已结束')
        page.screenshot(path=out/'03-结束.png')
        res = page.request.get(endpoint + '/package')
        assert res.status == 200
        raw = res.body()
        (out/'程序验收报告包.zip').write_bytes(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            report = json.loads(archive.read('report.json'))
            messages = [m for m in report['history']['messages'] if m.get('actor') == 'AI回归-D']
            assert messages and all(m['actor_type'] == 'ai' for m in messages)
            result['结果']['导出'] = {'HTTP': res.status, '成员数': len(archive.namelist()),
                                      '消息': messages, 'SHA256': hashlib.sha256(raw).hexdigest()}
        assert not result['浏览器异常']
    (out/'实测.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('创建、等待、回答、结束和导出全部通过。')


if __name__ == '__main__':
    main()
