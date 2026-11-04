"""按冻结任务卡进行本地浏览器操作，保存中立事实，不生成判断。"""
from pathlib import Path
import asyncio,hashlib,json,site,sys,time
from datetime import datetime,timezone
from urllib.parse import quote
REPO=Path(__file__).resolve().parents[1]
WORK=REPO.parent/'work'
for x in ('d_nov_review_deps','d_nov_mcp'):site.addsitedir(str(WORK/x))
from playwright.async_api import async_playwright
BASE='http://127.0.0.1:49920/'
ROOT=REPO/'docs/D-最终验收证据/新样本'
DEST=ROOT/'任务操作原始取证'
def save(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
async def run():
    DEST.mkdir(parents=True,exist_ok=False)
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        for ident,folder in [('N01','N01-阅读设置'),('N02','N02-器材借用清单'),('N03','N03-图书编目录入')]:
            out=DEST/ident;out.mkdir();context=await browser.new_context(viewport={'width':1440,'height':900});page=await context.new_page();events=[];screens=[]
            errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
            async def action(desc,fn):
                start=time.time();await fn();events.append({'动作':desc,'时间UTC':datetime.now(timezone.utc).isoformat(),'耗时秒':round(time.time()-start,3)})
            async def snap(label):
                name=f'{len(screens)+1:02d}-{label}';await page.screenshot(path=str(out/(name+'.png')),full_page=True,animations='disabled')
                data=await page.evaluate("""() => ({标题:document.title,文本:document.body.innerText,控件:[...document.querySelectorAll('input,select,button,output')].map(n=>({标签:n.getAttribute('aria-label')||n.labels?.[0]?.innerText||n.innerText||'',id:n.id,类型:n.type||n.tagName,value:n.value||'',checked:!!n.checked,disabled:!!n.disabled,invalid:n.getAttribute('aria-invalid')})),预览:document.querySelector('#preview')?{文字:document.querySelector('#preview').innerText,字号:getComputedStyle(document.querySelector('#preview')).fontSize,行高:getComputedStyle(document.querySelector('#preview')).lineHeight,背景:getComputedStyle(document.querySelector('#preview')).backgroundColor}:null})""")
                save(out/(name+'.json'),{'来源':'AI 操作脚本 / Chromium 实际页面观察','URL':page.url,'时间UTC':datetime.now(timezone.utc).isoformat(),'事实':data})
                screens.append({'阶段':label,'截图':name+'.png','截图SHA256':sha(out/(name+'.png')),'事实文件':name+'.json','事实SHA256':sha(out/(name+'.json'))})
            await action('新建独立页面并打开任务入口',lambda:page.goto(BASE+quote(folder)+'/打开界面.html',wait_until='networkidle'))
            await snap('初始')
            if ident=='N01':
                await action('文字大小选择大字号',lambda:page.locator('#fontSize').select_option('big'))
                await action('段落行距选择舒适行距',lambda:page.locator('#spacing').select_option('comfort'))
                await action('勾选使用暖色背景',lambda:page.locator('#warm').check())
                await snap('选择完成')
                await action('点击应用设置',lambda:page.locator('#save').click())
                await snap('应用响应')
                await action('等待页面反馈800毫秒',lambda:page.wait_for_timeout(800))
                await snap('应用后')
                await action('点击恢复初始',lambda:page.locator('#reset').click())
                await snap('恢复后')
            elif ident=='N02':
                for name,n in [('投影仪',2),('无线麦克风',3),('三脚架',1)]:
                    for _ in range(n):await action('点击增加'+name,lambda name=name:page.get_by_role('button',name='增加'+name,exact=True).click())
                await snap('数量选择后')
                await action('点击生成清单',lambda:page.locator('#build').click());await snap('首次清单')
                await action('点击增加无线麦克风',lambda:page.get_by_role('button',name='增加无线麦克风',exact=True).click());await snap('修改后清单')
            else:
                for label,selector,value in [('书名','#book','城市植物图鉴'),('作者','#author','林叶'),('出版年份','#year','2029')]:
                    await action('填写'+label+'：'+value,lambda selector=selector,value=value:page.locator(selector).fill(value))
                await snap('首次填写后')
                await action('点击保存图书',lambda:page.get_by_role('button',name='保存图书',exact=True).click());await snap('首次保存响应')
                await action('修改出版年份为2021',lambda:page.locator('#year').fill('2021'));await snap('修正年份后')
                await action('点击保存图书',lambda:page.get_by_role('button',name='保存图书',exact=True).click());await snap('再次保存响应')
                if not await page.locator('#book').input_value():
                    await action('按任务卡补填书名城市植物图鉴',lambda:page.locator('#book').fill('城市植物图鉴'))
                    await action('点击保存图书',lambda:page.get_by_role('button',name='保存图书',exact=True).click());await snap('补填后保存响应')
            save(out/'动作与观察索引.json',{'样本':ident,'执行来源':'AI 操作脚本','任务卡SHA256':sha(ROOT/'冻结材料'/folder/'任务卡.txt'),'动作':events,'观察':screens,'浏览器异常':errors})
            await context.close()
        await browser.close()
    save(DEST/'取证说明.json',{'性质':'按冻结任务卡实施的浏览器操作原始事实','操作者':'AI 编写并执行的脚本','材料清单SHA256':sha(ROOT/'冻结材料/冻结清单.json'),'浏览器':'Playwright Chromium / 隔离上下文 / 1440×900','不包含':['预设答案','模型评审输出','作者问题结论'],'文件数':len(list(DEST.rglob('*')))})
asyncio.run(run())

