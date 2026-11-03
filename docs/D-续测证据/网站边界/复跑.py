"""用可见控件补测预约找回、价格边界、报修重试和报名取消；不修改样本。"""
import json
from datetime import datetime,timezone
from pathlib import Path
from threading import Thread
import sys
from playwright.sync_api import sync_playwright

here=Path(__file__).resolve().parent
sys.path.insert(0,str(here.parents[2]/'fixtures/d-v02-sites'))
from serve import make_server
out=Path(sys.argv[1]);out.mkdir(parents=True, exist_ok=False)
rows=[]
def rec(name, pg, expected, good, capture=False):
    r={'观察':name,'页面':pg.locator('body').inner_text(),'可见操作':pg.get_by_role('button').all_text_contents(),'预期':expected,'符合':bool(good)}
    if capture: 
        r['截图']=f'{len(rows)+1:02}.png';pg.screenshot(path=str(out/r['截图']))
    rows.append(r)

def click(pg,t):pg.get_by_role('button',name=t,exact=True).click()
def text(pg):return pg.locator('body').inner_text()
def on(pg,i):return pg.locator(i)

with make_server(quiet=True) as server,sync_playwright() as pw:
    worker=Thread(target=server.serve_forever,daemon=True);worker.start()
    bro=pw.chromium.launch()
    try:
        base=f'http://127.0.0.1:{server.server_port}/'
        for n in (1,2):
            ctx=bro.new_context(locale='zh-CN');pg=ctx.new_page();pg.goto(base+'w01/')
            on(pg,'#slot').select_option('16:00–17:00');on(pg,'#people').fill(str(1 if n==1 else 6))
            click(pg,'核对预约');click(pg,'确认预约')
            rec(f'预约第{n}轮：可用时段、边界人数成功',pg,'展示预约号、所选时段、人数','R-204' in text(pg) and f"{1 if n==1 else 6} 人" in text(pg),n==1)
            pg.reload();pg.locator('h1').wait_for()
            rec(f'预约第{n}轮：在同一标签刷新，再凭预约号找回',pg,'入口应可查已有预约或直接展示历史回执',
                ('R-204' in text(pg) or any(x in text(pg) for x in ('查询','我的预约','预约记录'))),n==1)
            ctx.close()
        for pages,copies,side,delivery,amt in [(1,1,'双面',False,'0.20'),(60,5,'单面',True,'63.00'),(59,5,'双面',True,'33.00'),(61,1,'单面',False,None),(2,6,'双面',False,None),(1.5,1,'单面',False,None),(2,0,'单面',False,None)]:
            ctx=bro.new_context();pg=ctx.new_page();pg.goto(base+'w02/')
            on(pg,'#pages').fill(str(pages));on(pg,'#copies').fill(str(copies));on(pg,'#side').select_option(side)
            if delivery:on(pg,'#mode').select_option('校内配送');on(pg,'#address').fill('六号楼')
            click(pg,'查看报价')
            expected=f'合计 ¥{amt}' if amt else '页数须为 1 至 60，份数须为 1 至 5'
            rec(f'打印 {pages} 页 × {copies} 份，{side}，'+('配送' if delivery else '自取'),pg,expected,expected in text(pg))
            ctx.close()
        ctx=bro.new_context();pg=ctx.new_page();pg.goto(base+'w03/')
        on(pg,'#room').fill('R-204');on(pg,'#detail').fill('接通电源后没有画面');click(pg,'核对工单');click(pg,'提交工单')
        pg.reload();on(pg,'#room').wait_for()
        rec('报修：首次提交中断，在错误页刷新',pg,'原房间及描述保留',on(pg,'#room').input_value()=='R-204' and on(pg,'#detail').input_value()=='接通电源后没有画面')
        click(pg,'核对工单');click(pg,'提交工单');pg.reload();pg.locator('h1').wait_for()
        rec('报修：重试后再次刷新',pg,'同一标签页仍显示回执 M-318 和待派单','M-318' in text(pg) and '待派单' in text(pg),True);ctx.close()
        ctx=bro.new_context();pg=ctx.new_page();pg.goto(base+'w04/');click(pg,'查看篆刻入门');click(pg,'报名参加')
        click(pg,'取消报名');pg.reload();click(pg,'我的报名')
        rec('报名：取消确认弹窗中刷新，再查我的报名',pg,'未确认取消，原报名应保留','已报名' in text(pg) and 'A-071' in text(pg))
        click(pg,'取消报名');click(pg,'确认取消');pg.reload();pg.locator('h1').wait_for()
        rec('报名：明确取消并刷新',pg,'恢复两个余位，且没有我的报名入口','余位 2' in text(pg) and pg.get_by_role('button',name='我的报名').count()==0,True);ctx.close()
        data={'日期':datetime.now(timezone.utc).isoformat(),'浏览器':bro.version,'源样本':'D-WEB-1.0，同一版网站，回环端口，仅操作界面','记录':rows}
        (out/'实际记录.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        print(len(rows),'checks;',sum(x['符合'] for x in rows),'met')
    finally:
        bro.close();server.shutdown();worker.join()
