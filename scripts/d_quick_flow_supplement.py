"""AI 操作短流程补测：生产 BrowserAdapter/Action，无模型规划或评分。"""
from pathlib import Path
from datetime import datetime, timezone
import asyncio, functools, hashlib, json, site, subprocess, sys, threading, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import quote
REPO=Path(__file__).resolve().parents[1]
for name in ('d_nov_review_deps','d_nov_mcp'):
    site.addsitedir(str(REPO.parent/'work'/name))
sys.path.insert(0,str(REPO))
from engine.session_adapters import BrowserAdapter
from engine.session_contracts import Action,SourceInput,SourceRecord
MATERIAL=REPO/'docs/D-最终验收证据/新样本/冻结材料'
OUT=REPO/'docs/D-简要补测证据'/('N01-N03-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
def utc():return datetime.now(timezone.utc).isoformat()
def sha(data):return hashlib.sha256(data).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
FACTS="""() => ({title:document.title,text:document.body.innerText,controls:[...document.querySelectorAll('input,select,button')].map(n=>({id:n.id,type:n.type,tag:n.tagName,value:n.value,checked:!!n.checked,disabled:!!n.disabled,invalid:n.getAttribute('aria-invalid'),text:n.innerText})),status:document.querySelector('#status')?.innerText,applied:document.querySelector('#applied')?.innerText,record:document.querySelector('#record')?.innerText,errors:[...document.querySelectorAll('.error')].map(n=>({id:n.id,text:n.innerText})),preview:document.querySelector('#preview')?{fontSize:getComputedStyle(document.querySelector('#preview')).fontSize,lineHeight:getComputedStyle(document.querySelector('#preview')).lineHeight,background:getComputedStyle(document.querySelector('#preview')).backgroundColor}:null})"""
async def main():
    OUT.mkdir(parents=True,exist_ok=False);started=utc();assertions=[];results=[]
    manifest=json.loads((MATERIAL/'冻结清单.json').read_text(encoding='utf-8'))
    assert all(sha((MATERIAL/x['路径']).read_bytes())==x['SHA256'] for x in manifest['文件'])
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(MATERIAL)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    adapter=BrowserAdapter(allow_local=True,headless=True)
    metadata={'开始UTC':started,'来源':'AI 操作补测，真实 Chromium＋生产 BrowserAdapter/Action','不包含':'无 SessionService 规划队列、无模型调用、无自动评审准确性评分；原模型超时成绩不变','代码提交':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'代码SHA256':{n:sha((REPO/n).read_bytes()) for n in ['engine/session_adapters.py','engine/session_contracts.py','engine/session_targets.py']},'脚本SHA256':sha(Path(__file__).read_bytes()),'材料清单SHA256':sha((MATERIAL/'冻结清单.json').read_bytes()),'服务端口':server.server_address[1],'浏览器关闭':False,'服务关闭':False}
    save(OUT/'运行环境.json',metadata);(OUT/'执行脚本.py').write_bytes(Path(__file__).read_bytes());save(OUT/'材料指纹.json',manifest)
    def check(name,ok,actual):assertions.append({'断言':name,'通过':bool(ok),'实际':actual})
    try:
      for sample,folder in [('N01','N01-阅读设置'),('N03','N03-图书编目录入')]:
        out=OUT/sample;out.mkdir();sid='quick-'+sample;events=[];shots=[]
        source=SourceRecord(input=SourceInput(kind='website',reference=f'http://127.0.0.1:{server.server_address[1]}/'+quote(folder)+'/'+quote('打开界面.html'),title=folder,version=sample+'-v1',role='design',declared_by='D AI 操作员'))
        capture=await adapter.read(sid,source);source.acquisition_status='success';page=adapter._pages[(sid,source.source_id)]['page'];errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        async def snap(label,cap=None):
            name=f'{len(shots)+1:02d}-{label}';facts=await page.evaluate(FACTS)
            if cap is not None and cap.image:(out/(name+'.png')).write_bytes(cap.image)
            else:await page.screenshot(path=str(out/(name+'.png')),full_page=True)
            data={'来源':'真实页面读数，AI 操作','时间UTC':utc(),'事实':facts}
            if cap is not None:data['生产观察']={'state_id':cap.state_id,'content':cap.content,'controls':cap.controls,'locator':cap.locator,'partial':cap.partial}
            save(out/(name+'.json'),data);shots.append({'阶段':label,'截图':name+'.png','截图SHA256':sha((out/(name+'.png')).read_bytes()),'观察':name+'.json'});return facts
        async def act(kind,selector,value='',pending=False):
            before=await adapter.capture(sid,source);idx=await page.locator(selector).get_attribute('data-review-control');observed='[data-review-control="'+idx+'"]'
            action=Action(source_id=source.source_id,kind=kind,selector=observed,value=value,expected_state_id=before.state_id,reason='按冻结任务卡执行短流程补测：'+selector,requires_explicit_authorization=False)
            needs=await adapter.action_needs_authorization(sid,source,action);begin=time.monotonic()
            task=asyncio.create_task(adapter.act(sid,source,action,authorized=True))
            if pending:
                await page.wait_for_function("document.querySelector('#save').disabled === true")
                busy=await snap('应用处理中')
                check('N01 处理中显示反馈且两按钮不可重复操作',busy['status']=='正在应用阅读设置，请稍候' and all(c['disabled'] for c in busy['controls'] if c['id'] in ['save','reset']),busy)
            after=await task
            events.append({'时间UTC':utc(),'操作者':'AI','授权范围':'用户要求操作本地冻结样本','适配器要求授权':needs,'authorized':True,'动作':action.model_dump(mode='json'),'前state_id':before.state_id,'后state_id':after.state_id,'结果':after.locator.get('action_outcome'),'耗时秒':round(time.monotonic()-begin,3)})
            return after
        initial=await snap('初始',capture)
        if sample=='N01':
            await act('select','#fontSize','big');await act('select','#spacing','comfort');await act('click','#warm')
            selected=await snap('选择后',await adapter.capture(sid,source));vals={c['id']:c for c in selected['controls']};check('N01 两个原生下拉框和暖色选择生效',vals['fontSize']['value']=='big' and vals['spacing']['value']=='comfort' and vals['warm']['checked'],vals)
            await act('click','#save',pending=True)
            await page.wait_for_function("document.querySelector('#status').textContent === '设置已应用'")
            applied=await snap('应用完成',await adapter.capture(sid,source));check('N01 字号行高背景按选择改变',float(applied['preview']['fontSize'][:-2])>float(initial['preview']['fontSize'][:-2]) and float(applied['preview']['lineHeight'][:-2])>float(initial['preview']['lineHeight'][:-2]) and applied['preview']['background']!=initial['preview']['background'],{'初始':initial['preview'],'应用后':applied['preview']});check('N01 完成反馈与摘要匹配',applied['status']=='设置已应用' and '大字号 · 舒适行距 · 暖色背景' in applied['applied'],applied['applied'])
            restored=await snap('恢复初始',await act('click','#reset'));vals={c['id']:c for c in restored['controls']};check('N01 恢复控件与预览全部回到初始',restored['preview']==initial['preview'] and vals['fontSize']['value']=='normal' and vals['spacing']['value']=='compact' and not vals['warm']['checked'] and restored['status']=='已恢复初始版面',restored)
        else:
            for selector,value in [('#book','城市植物图鉴'),('#author','林叶'),('#year','2029')]:await act('fill',selector,value)
            await snap('错误年份提交前',await adapter.capture(sid,source));failed=await snap('2029校验响应',await act('click','button[type=submit]'));vals={c['id']:c for c in failed['controls']};check('N03 错误年份显示范围反馈且未保存',vals['year']['invalid']=='true' and '1900–2026' in next(e['text'] for e in failed['errors'] if e['id']=='yearError') and failed['record']=='尚未保存图书记录',failed)
            check('N03 复现校验失败清空正确书名',vals['book']['value']=='' and vals['author']['value']=='林叶',{'书名':vals['book']['value'],'作者':vals['author']['value']})
            await act('fill','#year','2021')
            observed=await page.evaluate(FACTS);book=next(c for c in observed['controls'] if c['id']=='book')
            if not book['value']:await act('fill','#book','城市植物图鉴')
            await snap('修正并补回后',await adapter.capture(sid,source));done=await snap('最终保存成功',await act('click','button[type=submit]'));check('N03 修正补回后最终保存字段一致',done['status']=='图书记录已保存' and done['record']=='书名：城市植物图鉴；作者：林叶；出版年份：2021' and not any(e['text'] for e in done['errors']),done)
        check(sample+' 浏览器无脚本异常',not errors,errors);save(out/'操作与截图索引.json',{'来源':'AI 操作补测','动作':events,'截图':shots,'浏览器异常':errors});results.append({'样本':sample,'动作数':len(events),'截图数':len(shots),'浏览器异常':errors});await adapter.close_session(sid)
    except Exception as exc:
        save(OUT/'执行异常.json',{'类型':type(exc).__name__,'信息':str(exc)});raise
    finally:
        await adapter.close();server.shutdown();server.server_close();thread.join(timeout=3);metadata.update({'结束UTC':utc(),'浏览器关闭':True,'服务关闭':True});save(OUT/'运行环境.json',metadata);save(OUT/'断言与结果.json',{'来源':'真实浏览器短流程断言；复现缺陷的通过表示复现成立，不表示产品无缺陷','模型调用':0,'任务':results,'断言':assertions,'通过':sum(x['通过'] for x in assertions),'总数':len(assertions)})
    print(json.dumps({'输出目录':str(OUT),'任务':results,'通过':sum(x['通过'] for x in assertions),'总数':len(assertions),'关闭完成':True},ensure_ascii=False))
if __name__=='__main__':asyncio.run(main())
