"""用修前导出的 H04 观察构造旧格式记录，检查历史兼容入口。"""
import importlib.util
import json
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright, expect

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('replay',here/'同材料复跑.py')
replay=importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)
note=json.loads((here/'修前/AI-01-2-B/工作台核对.json').read_text('utf-8'))['复核备注']
legacy={'id':'old-feedback-H04','mode':'mock','version':2,'createdAt':'2026-11-03T18:52:00Z','image':'demo.svg',
        'context':{'name':'旧格式反馈迁移','audience':'首次使用','goal':'核对借用时段'},
        'issues':[],'logs':[{'at':'2026-11-03T18:52:00Z','text':'模拟反馈重评 v2：'+note,'feedback':[]}]}

with ThreadingHTTPServer(('127.0.0.1',0),partial(replay.rounds.QuietFiles,directory=str(replay.REPO/'frontend/dist'))) as server:
    Thread(target=server.serve_forever,daemon=True).start()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(locale='zh-CN')
        page.goto(f'http://127.0.0.1:{server.server_port}/')
        page.evaluate('(record)=>localStorage.setItem("mingjian-reviews-v1",JSON.stringify([record]))',legacy)
        page.reload()
        page.locator('.history-item').click()
        expect(page.locator('#issues article')).to_have_count(0)
        page.get_by_text('操作与版本记录',exact=True).click()
        click=page.get_by_role('button',name='从这条反馈补记问题')
        click.click()
        expect(page.locator('#findingForm [name=steps]')).to_have_value(note)
        page.locator('#cancelFinding').click()
        expect(page.locator('#issues article')).to_have_count(0)
        click.click()
        form=page.locator('#findingForm')
        form.locator('[name=title]').fill('从旧反馈补记：返回后改为默认时段')
        form.locator('[name=evidence]').fill('首次核对为东侧工坊；返回时勾选西侧工坊。')
        form.locator('[name=authorType]').select_option('ai_simulation')
        form.locator('[name=severity]').select_option('medium')
        form.get_by_role('button',name='保存到问题列表').click()
        expect(page.locator('#issues article')).to_have_count(1)
        report=replay.download(page,here/'旧反馈补记后.md')
        body,log=report.split('## 操作记录')
        assert note in body and note in log and '记录来源：AI 模拟补记' in body
        replay.rounds.write_json(here/'旧反馈兼容.json',{'输入':'修前 H04 操作备注，旧格式存储夹具','原问题数':0,'打开后取消的问题数':0,
                         '明确保存后的问题数':1,'正文保留来源和步骤':True,'旧日志保留':True,'浏览器':browser.version})
        browser.close()
    server.shutdown()
