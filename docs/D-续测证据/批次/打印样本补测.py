"""在两个全新的浏览器上下文中，核对漏填楼栋后的焦点和不同订单的回执。"""
import json
import sys
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]/'fixtures/d-v02-sites'))
from serve import make_server

def main():
    results = []
    with make_server(quiet=True) as server, sync_playwright() as pw:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        browser = pw.chromium.launch()
        try:
            for pages,copies in [(13,2),(7,1)]:
                ctx = browser.new_context(locale='zh-CN')
                try:
                    page = ctx.new_page()
                    page.goto(f'http://127.0.0.1:{server.server_port}/w02/')
                    page.get_by_label('原稿页数').fill(str(pages))
                    page.get_by_label('份数').fill(str(copies))
                    page.get_by_label('取件方式').select_option('校内配送')
                    page.get_by_role('button',name='查看报价').click()
                    alert = page.get_by_role('alert').inner_text()
                    focus = page.evaluate("() => ({控件:document.activeElement.tagName,标识:document.activeElement.id})")
                    page.keyboard.press('Tab')
                    tab = page.evaluate("() => document.activeElement.id")
                    page.get_by_label('取件方式').select_option('到店自取')
                    page.get_by_role('button',name='查看报价').click()
                    quote = page.locator('.card').inner_text()
                    page.get_by_role('button',name='提交打印单').click()
                    results.append({'页数':pages,'份数':copies,'楼栋留空后的提示':alert,'此时焦点':focus,
                                    'Tab一次后定位':tab,'自取报价':quote,'实际回执':page.get_by_role('status').inner_text()})
                finally:
                    ctx.close()
        finally:
            browser.close()
            server.shutdown()
            thread.join()
    (HERE/'打印样本补测.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':
    main()
