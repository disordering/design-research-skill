"""使用体验表的草稿导出测量状态切换、入表时长和跨关闭恢复。"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from playwright.sync_api import expect, sync_playwright


FORM = Path(__file__).resolve().parents[2] / "D-新版真人执行/02-体验者/两轮任务体验记录.html"


def main(result_file):
    if result_file.exists():
        raise SystemExit("请换一个输出文件名以保留原记录")
    result = {"来源":"AI 本地操作体验表，使用草稿导出读回",
              "体验表SHA256":hashlib.sha256(FORM.read_bytes()).hexdigest()}
    def open_form(ctx):
        tab = ctx.new_page()
        tab.goto(FORM.as_uri())
        return tab
    def by(tab,name):
        return tab.get_by_role("button",name=name,exact=True)
    def assign(tab, num):
        tab.locator("#participant").select_option("U01")
        tab.locator("#round").select_option(str(num))
        tab.locator("#version").fill("AI-计时器-程序验收")
        tab.locator("#timing").select_option("live")
    def export(tab,path):
        with tab.expect_download() as event:
            by(tab,"导出草稿").click()
        event.value.save_as(path)
        return json.loads(path.read_text(encoding="utf-8-sig"))
    with sync_playwright() as pw, TemporaryDirectory() as tmp:
        browser = pw.chromium.launch(channel="msedge",headless=True)
        context = browser.new_context(locale="zh-CN")
        page = open_form(context)
        assign(page,1)
        by(page,"开始").click()
        result["无辅助轮等待按钮禁用"] = by(page,"工具等待").is_disabled()
        by(page,"结束").click()
        result["已结束轮不可继续"] = by(page,"恢复操作").is_disabled()
        page.close()
        page = open_form(context)
        assign(page,2)
        for a in ["开始","工具等待","外部中断","恢复操作","结束"]:
            by(page,a).click()
        snapshot = export(page,Path(tmp)/"closed.json")
        events = snapshot["events"]
        totals = snapshot["seconds"]
        recompute = {"active":0,"break":0,"wait":0}
        for prev,cur in zip(events,events[1:]):
            recompute[prev["type"]] += (datetime.fromisoformat(cur["at"])-datetime.fromisoformat(prev["at"])).total_seconds()
        pairs = [("active","操作秒"),("wait","工具等待秒"),("break","外部中断秒")]
        result["工具轮"]={"事件":events, "草稿实际秒":totals,
                       "按时间戳独立复算":recompute,
                       "三类时长吻合":all(abs(recompute[a]-totals[b]) < 0.002 for a,b in pairs),
                       "扣中断公式吻合":abs(recompute["wait"]+recompute["active"]-totals["扣中断后秒"]) < 0.002}
        page.close()
        page = open_form(context)
        assign(page,1)
        by(page,"开始").click()
        active_file = Path(tmp)/"active.json"
        draft = export(page,active_file)
        page.close()
        closed_at = time.perf_counter()
        time.sleep(1.25)
        gap = time.perf_counter()-closed_at
        page = open_form(context)
        page.on("dialog",lambda d:d.accept())
        page.locator("#load").set_input_files(str(active_file))
        expect(page.locator("#msg")).to_contain_text("草稿已载入")
        clock = page.locator("#clock").inner_text()
        by(page,"结束").click()
        restored = export(page,Path(tmp)/"restored.json")
        result["关闭后重载进行中草稿"] = {
            "关闭前草稿事件":draft["events"],"关闭后到新建页前实际间隔秒":gap,
            "导入后状态":clock,"结束后事件":restored["events"],"草稿显示有效计时":restored["timingValid"],
            "草稿秒数":restored["seconds"],
            "关页间隔计入活跃操作":restored["timingValid"] and restored["seconds"]["操作秒"]>=gap
                                      and [v["type"] for v in restored["events"]] == ["active","ended"]}
        browser.close()
    result_file.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",required=True,type=Path)
    main(p.parse_args().out)

