"""验证 W03 原样本以及 W04 原样本和单处库存变体。输出到新目录。"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright


SITE = Path(__file__).resolve().parents[4] / "fixtures/d-v02-sites"
spec = importlib.util.spec_from_file_location("campus_site", SITE / "serve.py")
campus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(campus)
TYPES = ["陶艺体验", "篆刻入门"]


def snap(page, action, steps, folder):
    number = len(steps)+1
    shot = f"{number:02}.png"
    page.screenshot(path=folder/shot, animations="disabled")
    steps.append({"操作":action, "可见正文":page.locator("main").inner_text(),
                  "截图":shot, "UTC":datetime.now(timezone.utc).isoformat()})


def click(page, label):
    page.get_by_role("button", name=label, exact=True).click()


def repair(browser, url, destination, device, room, detail):
    with browser.new_context(locale="zh-CN") as ctx:
        steps, transmissions = [], []
        page = ctx.new_page()
        page.goto(url)
        expect(page.locator("h1")).to_have_text("填写工单")
        assert page.get_by_label("房间号").input_value() == ""
        page.get_by_label("报修设备").select_option(device)
        page.get_by_label("房间号").fill(room)
        page.get_by_label("故障描述").fill(detail)
        click(page,"核对工单")
        snap(page,"核对输入",steps,destination)
        page.on("request",lambda r:transmissions.append({"方法":r.method,"类型":r.resource_type}))
        click(page,"提交工单")
        expect(page.get_by_role("alert")).to_contain_text("网络暂不可用")
        snap(page,"首次提交",steps,destination)
        click(page,"重新提交")
        expect(page.get_by_role("status")).to_contain_text("M-318")
        expect(page.locator("main")).to_contain_text(room+" · "+device)
        snap(page,"重新提交",steps,destination)
        return {"设备":device,"房间":room,"故障":detail,"浏览器联网状态":page.evaluate("navigator.onLine"),
                "两次提交产生浏览器请求":transmissions,"过程":steps}


def workshop(browser,url,destination,variant,first):
    with browser.new_context(locale="zh-CN") as ctx:
        patch = {}
        if variant:
            def targeted_change(route):
                response = route.fetch()
                raw = response.body()
                src = "name:'陶艺体验',time:'14:00',available:0".encode()
                assert raw.count(src)==1
                modified = raw.replace(src,src[:-1]+b"1")
                assert sum(a!=b for a,b in zip(raw,modified,strict=True))==1
                patch.update({"原响应SHA256":hashlib.sha256(raw).hexdigest(),
                              "实验响应SHA256":hashlib.sha256(modified).hexdigest(),
                              "修改": "14:00 陶艺体验的 available 字段由 0 调为 1，仅此一字节"})
                route.fulfill(response=response, body=modified)
            ctx.route("**/w04/app.js", targeted_change)
        page = ctx.new_page()
        steps = []
        page.goto(url)
        expect(page.get_by_role("heading",name="周末活动")).to_be_visible()
        snap(page,"查看两场及各自余位",steps,destination)
        if not variant:
            click(page,"查看陶艺体验")
            expect(page.locator("main")).to_contain_text("余位 0")
            click(page,"报名参加")
            expect(page.get_by_role("alert")).to_contain_text("本场已满")
            snap(page,"尝试报名14:00陶艺",steps,destination)
            click(page,"返回活动")
            click(page,"查看篆刻入门")
            click(page,"报名参加")
            expect(page.locator(".card")).to_contain_text("16:00 · 已报名")
            snap(page,"报名16:00篆刻",steps,destination)
        else:
            second = next(name for name in TYPES if name != first)
            click(page,"查看"+first)
            click(page,"报名参加")
            expect(page.get_by_role("heading",level=2)).to_have_text(first)
            snap(page,"报名"+first,steps,destination)
            click(page,"返回活动")
            click(page,"查看"+second)
            assert "余位 0" not in page.locator("main").inner_text()
            snap(page,"查看另一时段有余位的"+second,steps,destination)
            click(page,"报名参加")
            expect(page.get_by_role("alert")).to_have_text("请先取消已有报名。")
            snap(page,"在同一浏览器会话内报名另一时段",steps,destination)
            click(page,"返回活动")
            page.reload()
            click(page,"我的报名")
            expect(page.get_by_role("heading",level=2)).to_have_text(first)
            snap(page,"刷新后核对原报名仍在",steps,destination)
        return {"条件":"浏览器内实验变体" if variant else "原样本","拦截记录":patch,"过程":steps}


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    scripts = {x:SITE/f"public/{x}/app.js" for x in ("w03","w04")}
    hashes={x:hashlib.sha256(f.read_bytes()).hexdigest() for x,f in scripts.items()}
    record={"执行者":"AI 浏览器操作","版本":"D-WEB-1.0","原始脚本SHA256":hashes,"会话":{}}
    with campus.make_server(quiet=True) as server, sync_playwright() as pw:
        Thread(target=server.serve_forever,daemon=True).start()
        origin=f"http://127.0.0.1:{server.server_port}"
        browser=pw.chromium.launch(channel="msedge",headless=True)
        record["浏览器"]="Microsoft Edge "+browser.version
        for label, args in [
            ("W03-工单甲",("投影仪","工科楼 C-301","灯亮，无画面")),
            ("W03-工单乙",("打印机","工作室 D-405","卡纸，提示出纸故障")),
        ]:
            folder=out/label
            folder.mkdir()
            record["会话"][label]=repair(browser,origin+"/w03/",folder,*args)
        for label, variant, first in [("W04-原样本",False,None),("W04-实验先陶艺",True,TYPES[0]),
                                      ("W04-实验先篆刻",True,TYPES[1])]:
            folder=out/label
            folder.mkdir()
            record["会话"][label]=workshop(browser,origin+"/w04/",folder,variant,first)
        browser.close()
        server.shutdown()
    assert all(hashlib.sha256(f.read_bytes()).hexdigest()==hashes[x] for x,f in scripts.items())
    assert all(not record["会话"][f"W03-工单{k}"]["两次提交产生浏览器请求"] for k in ("甲","乙"))
    (out/"五个会话.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    main(p.parse_args().out)

