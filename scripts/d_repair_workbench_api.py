"""用 H05 原操作记录和回执截图走工作台引擎模式；网络只监听本机。"""
import hashlib
import json
from pathlib import Path
import socket
import sys
import threading
import time

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.api import create_app
from engine.criteria import CriteriaLibrary
from engine.service import ReviewEngine
from engine.stub import StubModel

SOURCE = ROOT/'docs/D-续测证据/模拟评审/实测/AI-03-2-C'
OUT = ROOT/'docs/D-三项修复证据/工作台接口联测'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    src = SOURCE/'网页走查.json'
    image = SOURCE/'02-完成.png'
    steps = json.loads(src.read_bytes())['各步']
    # 首次提交是下午目标；同一记录末尾另有主动改选上午的正常对照。
    idx = next(i for i,s in enumerate(steps) if s['操作']=='提交登记')
    before, after = (steps[i]['明细'] for i in (idx-1,idx))
    assert before != after and '14:00' in before[1] and '09:00' in after[1] and before[2]!=after[2]
    title = '修书登记回执的时段和地点与提交前不符'
    evidence = '提交前：'+'／'.join(before)+'；回执：'+'／'.join(after)
    criteria = CriteriaLibrary.load(ROOT/'判据库_v1.json')
    def stub(provider, model):
        return ReviewEngine(criteria, StubModel(), provider='stub', model_name='contract-stub-v1', is_stub=True)
    # 复用工作台的 /engine 地址；发送实际 HTTP 表单，模型固定以隔离接口行为。
    app = FastAPI()
    app.mount('/engine', create_app(engine_factory=stub))
    app.mount('/', StaticFiles(directory=ROOT/'frontend/dist', html=True))
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        thread = threading.Thread(target=server.run, kwargs={'sockets':[sock]}, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started: break
                time.sleep(0.05)
            assert server.started
            reports = []
            def call(page, button):
                with page.expect_response(lambda r: r.url.endswith('/engine/api/review-audit') and r.request.method=='POST',timeout=30000) as event:
                    button.click()
                response = event.value
                assert response.status == 200, response.text()
                raw = response.json()
                assert raw['model']['is_stub'] and all(f['title']!=title for f in raw['findings'])
                reports.append({'HTTP':response.status,'引擎ID':raw['review_id'],'模型':raw['model']['model'],
                                '原生候选数':len(raw['findings']),'原生候选含补记标题':False})
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                try:
                    page = browser.new_page(locale='zh-CN', accept_downloads=True)
                    page.goto(f'http://127.0.0.1:{port}/')
                    page.locator('#mode').select_option('engine')
                    page.locator('#imageInput').set_input_files(str(image))
                    expect(page.locator('#preview')).to_be_visible()
                    for key, value in [('name','H05 引擎模式补记'),('audience','登记使用者'),('goal','核对完成页的时段和服务台')]:
                        page.locator('#'+key).fill(value)
                    call(page, page.locator('#form button[type=submit]'))
                    expect(page.locator('#version')).to_contain_text('v1')
                    page.locator('#addFinding').click()
                    form = page.locator('#findingForm')
                    for key,value in [('title',title),('steps','选择下午，返回核对，再提交登记。'),('evidence',evidence)]:
                        form.locator('[name='+key+']').fill(value)
                    form.locator('[name=severity]').select_option('high')
                    form.locator('[name=authorType]').select_option('ai_simulation')
                    form.get_by_role('button',name='保存到问题列表').click()
                    card = page.locator('article').filter(has=page.get_by_role('heading',name=title,exact=True))
                    expect(card).to_contain_text(evidence)
                    fid = card.get_attribute('data-id')
                    # 留下一条普通反馈，同时核实同图重评会保留具名补记及原证据。
                    page.locator('#feedback').fill('复看同一张回执。')
                    call(page, page.locator('#revise'))
                    expect(page.locator('#version')).to_contain_text('v2')
                    expect(page.locator('article[data-id="'+fid+'"]')).to_contain_text(evidence)
                    with page.expect_download() as download:
                        page.locator('#export').click()
                    dest = OUT/'引擎模式v2导出.md'
                    download.value.save_as(dest)
                    body = dest.read_text('utf-8-sig').split('## 本轮提交上下文')[0]
                    assert body.count('## '+title)==1 and all(v in body for v in [evidence,'来源：AI 模拟补记','严重度：高','首次记录版本：v1'])
                    assert '## 复看同一张回执。' not in body
                finally:
                    browser.close()
        finally:
            server.should_exit=True
            thread.join(8)
    (OUT/'核对.json').write_text(json.dumps({'材料':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (src,image)},
        '做法':'Chromium 按工作台引擎模式向本机产品 FastAPI 发真实请求；模型为固定契约响应。',
        '请求':reports,'问题编号':fid,'提交前':before,'回执':after,'同图重评保留编号与证据':True,
        'v2正文原补记出现次数':1,'普通反馈生成新问题':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('H05：两次接口返回 200，同图重评后导出正文含原补记一次。')


if __name__ == '__main__':
    main()
