"""在 W02 原样本测双面自取的输入边界，保存六次独立会话的页面回读。"""
import json
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

here=Path(__file__).resolve().parent
repo=here.parents[3]
fixture=repo/'fixtures/d-v02-sites'
sys.path.insert(0,str(fixture))
from serve import make_server

def run(out):
    out.mkdir(parents=True,exist_ok=False)
    rows=[]
    def fill(page,pages,copies):
        page.get_by_label('原稿页数').fill(str(pages))
        page.get_by_label('份数',exact=True).fill(str(copies))
        page.get_by_role('button',name='查看报价').click()
    with make_server(quiet=True) as server,sync_playwright() as pw:
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        browser=pw.chromium.launch(headless=True)
        for i,(pages,copies,corrected) in enumerate([(1,1,None),(60,5,None),(0,1,(1,1)),(61,5,(60,5)),(1,0,(1,1)),(60,6,(60,5))]):
            with browser.new_context(locale='zh-CN') as ctx:
                page=ctx.new_page();page.goto(f'http://127.0.0.1:{server.server_port}/w02/')
                page.get_by_label('原稿页数').wait_for()
                text=page.locator('body').inner_text()
                attrs=page.locator('#pages,#copies').evaluate_all("""inputs=>inputs.map(e=>({
                    id:e.id, type:e.type, min:e.getAttribute('min'), max:e.getAttribute('max'),title:e.getAttribute('title'),
                    placeholder:e.getAttribute('placeholder'), describedby:e.getAttribute('aria-describedby')
                }))""")
                if i==0:page.screenshot(path=out/'01-填写前.png')
                rec={'初始页正文':text,'输入属性':attrs,'输入页数':pages,'输入份数':copies,'取件方式':'到店自取','打印方式':'双面'}
                assert all(x['min'] is None and x['max'] is None for x in attrs)
                assert '60' not in text and '至' not in text
                fill(page,pages,copies)
                if corrected is not None:
                    rec['点击报价后提示']=page.get_by_role('alert').inner_text()
                    rec['出错后输入保留']=[page.locator('#pages').input_value(),page.locator('#copies').input_value()]
                    assert rec['点击报价后提示']=='页数须为 1 至 60，份数须为 1 至 5。'
                    assert rec['出错后输入保留']==[str(pages),str(copies)]
                    if i==3:page.screenshot(path=out/'02-61页点击报价后.png')
                    rec['修正值']=list(corrected)
                    fill(page,*corrected)
                quote=page.locator('.card').inner_text()
                valid=corrected or (pages,copies)
                amount=((valid[0]+1)//2)*valid[1]*20
                expected='合计 ¥'+f'{amount//100}.{amount%100:02}'
                assert expected in quote
                rec['报价页实际明细']=quote
                rows.append(rec)
        result={'样本脚本_SHA256':sha256((fixture/'public/w02/app.js').read_bytes()).hexdigest(),
            '需求_SHA256':sha256((fixture/'requirements/w02.md').read_bytes()).hexdigest(),'执行时间UTC':datetime.now(timezone.utc).isoformat(),
            '浏览器':'Chromium '+browser.version,'各组':rows,'合规端点正确报价':2,'越界被拦且修正后正确报价':4,
            '事实':'初始页只提示单价和运费；两项输入均无 min/max。四种越界值在点击查看报价后才显示两个范围，并保留输入。',
            'D裁决':'确认，低。提前显示上下界可省一次往返，价格计算和越界拦截均正常。'}
        (out/'六组实测.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        browser.close();server.shutdown();thread.join()

if __name__=='__main__':run(Path(sys.argv[1]))
