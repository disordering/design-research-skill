"""在真实 Edge 浏览器中验收体验记录表计时；每次运行写入独立证据目录。"""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time

from playwright.sync_api import expect, sync_playwright


FORM = Path(__file__).resolve().parents[2] / "D-新版真人执行/02-体验者/两轮任务体验记录.html"


def run(form, out):
    if out.exists():
        raise SystemExit("输出目录已存在，请更换目录以保留既有证据。")
    out.mkdir(parents=True)
    checks = []
    result = {
        "执行来源": "AI 本地浏览器自动操作；编号和填写内容均为工具验收数据",
        "浏览器": "Microsoft Edge 无头浏览器",
        "体验表SHA256": hashlib.sha256(form.read_bytes()).hexdigest(),
        "执行时间": datetime.now().astimezone().isoformat(),
        "检查项": checks,
    }

    def check(name, passed, details=None):
        checks.append({"检查": name, "通过": bool(passed), "实测": details})

    def button(page, name):
        return page.get_by_role("button", name=name, exact=True)

    def click(page, name, pause=0.18):
        button(page, name).click()
        time.sleep(pause)

    def save(page, name, final=False):
        with page.expect_download() as download:
            button(page, "导出正式记录" if final else "导出草稿").click()
        dest = out / (name + ".json")
        download.value.save_as(dest)
        return json.loads(dest.read_text(encoding="utf-8-sig")), dest

    def independent(record):
        sums = {"active": 0, "wait": 0, "break": 0}
        for prev, cur in zip(record["events"], record["events"][1:]):
            sums[prev["type"]] += (
                datetime.fromisoformat(cur["at"]) - datetime.fromisoformat(prev["at"])
            ).total_seconds()
        return sums

    def same_totals(record):
        sums = independent(record)
        seconds = record["seconds"]
        return seconds is not None and all(
            abs(sums[a] - seconds[b]) < 0.002
            for a, b in [("active", "操作秒"), ("wait", "工具等待秒"), ("break", "外部中断秒")]
        ) and abs(sums["active"] + sums["wait"] - seconds["扣中断后秒"]) < 0.002

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(locale="zh-CN", viewport={"width": 1100, "height": 1000})
        errors = []

        def open_form(round_number=2):
            page = context.new_page()
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.on("dialog", lambda dialog: dialog.accept())
            page.goto(form.as_uri())
            page.locator("#participant").select_option("U01")
            page.locator("#round").select_option(str(round_number))
            for field, text in {
                "version": "AI-计时工具验收材料",
                "device": "AI 自动操作 / Microsoft Edge",
                "product": "计时工具程序验收记录",
                "quote": "AI 自动检查计时与草稿恢复",
            }.items():
                page.locator("#" + field).fill(text)
            if round_number == 2:
                page.locator("#build").fill("本地计时验收")
            for field, value in {
                "timing": "live", "outcome": "completed", "understand": "na",
                "evidence": "na", "saved": "na", "consent": "yes",
            }.items():
                page.locator("#" + field).select_option(value)
            return page

        def load(page, path):
            page.locator("#load").set_input_files(str(path))
            expect(page.locator("#msg")).to_contain_text("草稿已载入")

        try:
            page = open_form(1)
            click(page, "开始")
            check("人工轮工具等待按钮保持禁用", button(page, "工具等待").is_disabled())
            click(page, "结束")
            manual, _ = save(page, "01-人工轮正式记录", final=True)
            check("人工轮操作时间独立复算一致", manual["timingValid"] and same_totals(manual), manual["seconds"])
            check("结束后禁止再次计时", button(page, "恢复操作").is_disabled() and button(page, "开始").is_disabled())
            page.close()

            page = open_form()
            page.locator("#interruption").fill("AI 自动检查外部中断按钮")
            for action in ["开始", "工具等待", "外部中断", "恢复操作", "结束"]:
                click(page, action)
            mixed, ended_draft_path = save(page, "02-工具轮已结束草稿")
            save(page, "02-工具轮正式记录", final=True)
            check("操作等待中断分段计算与扣除公式一致", same_totals(mixed), {
                "导出秒数": mixed["seconds"], "独立复算": independent(mixed),
            })
            page.close()

            page = open_form()
            click(page, "开始")
            active_draft, active_path = save(page, "03-进行中导出草稿")
            check("进行中草稿在导出时点暂停", active_draft["events"][-1]["type"] == "break", active_draft["events"])
            check("导出草稿后原页面继续操作计时", page.locator("#clock").inner_text().startswith("操作中"))
            click(page, "结束")
            continued, _ = save(page, "03-原页面继续后正式记录", final=True)
            check("保存草稿不向原页面插入中断", [e["type"] for e in continued["events"]] == ["active", "ended"] and same_totals(continued))
            page.close()

            for case, state in [("04-操作草稿关页恢复", "active"), ("05-等待草稿关页恢复", "wait")]:
                page = open_form()
                click(page, "开始")
                if state == "wait":
                    click(page, "工具等待")
                draft, path = save(page, case + "-关闭前")
                page.close()
                closed_at = time.perf_counter()
                time.sleep(1.2)
                page = open_form()
                elapsed = time.perf_counter() - closed_at
                load(page, path)
                clock = page.locator("#clock").inner_text()
                check(case + "载入后保持暂停", clock.startswith("外部中断") and button(page, "恢复操作").is_enabled(), clock)
                time.sleep(0.2)
                if state == "active":
                    page.screenshot(path=str(out / "草稿恢复暂停状态.png"), full_page=True)
                click(page, "结束")
                restored, _ = save(page, case + "-结束后正式记录", final=True)
                # 直接结束恢复的记录，操作与等待必须严格截止在草稿保存时点。
                # 旧版草稿无暂停事件，仍可用实际导出时间独立复算保存前时长。
                closed_draft = {**draft, "events": [dict(e) for e in draft["events"]]}
                if closed_draft["events"][-1]["type"] in ("active", "wait"):
                    closed_draft["events"].append({"type": "break", "at": draft["exportedAt"]})
                expected = independent(closed_draft)[state]
                actual = restored["seconds"]["操作秒" if state == "active" else "工具等待秒"]
                check(case + "离开时间仅计中断", abs(actual - expected) < 0.002 and restored["seconds"]["外部中断秒"] >= 1.2 and same_totals(restored), {
                    "关页到重开间隔秒": elapsed, "保存前该分段秒": expected,
                    "恢复后该分段秒": actual, "导出秒数": restored["seconds"],
                })
                page.close()

            page = open_form()
            page.locator("#interruption").fill("保留的外部中断原因")
            for action in ["开始", "外部中断"]:
                click(page, action)
            paused, path = save(page, "06-原本已中断草稿")
            page.close()
            time.sleep(0.25)
            page = open_form()
            load(page, path)
            click(page, "恢复操作")
            click(page, "结束")
            resumed, _ = save(page, "06-中断后恢复正式记录", final=True)
            check("已中断草稿保持单段中断并可恢复操作", [e["type"] for e in resumed["events"]] == ["active", "break", "active", "ended"] and same_totals(resumed))
            check("恢复保留既有填写与中断说明", "保留的外部中断原因" in resumed["interruption"] and resumed["product"] == paused["product"])
            page.close()

            for case, old_state in [("07-旧版操作草稿", "active"), ("08-旧版等待草稿", "wait")]:
                # 旧版草稿只保留当前运行事件，导出时间仍由原 JSON 提供。
                old = dict(active_draft)
                old["events"] = [dict(e) for e in active_draft["events"] if e.get("source") != "draft_snapshot"]
                if old_state == "wait":
                    old["events"].append({"type": "wait", "at": old["events"][-1]["at"]})
                path = out / (case + "-兼容样例.json")
                path.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
                page = open_form()
                load(page, path)
                loaded_pause = page.locator("#clock").inner_text().startswith("外部中断")
                click(page, "结束")
                legacy, _ = save(page, case + "-恢复后正式记录", final=True)
                pause_events = [e for e in legacy["events"] if e["type"] == "break"]
                check(case + "按原导出时间暂停", loaded_pause and len(pause_events) == 1 and pause_events[0]["at"] == old["exportedAt"] and same_totals(legacy), legacy["events"])
                page.close()

            page = open_form()
            load(page, ended_draft_path)
            ended_again, _ = save(page, "09-已结束草稿再次导出", final=True)
            check("旧版已结束草稿事件和时长原样保留", ended_again["events"] == mixed["events"] and ended_again["seconds"] == mixed["seconds"])
            page.close()

            old_without_time = dict(active_draft)
            old_without_time.pop("exportedAt", None)
            old_without_time["events"] = [dict(e) for e in active_draft["events"] if e.get("source") != "draft_snapshot"]
            path = out / "10-缺导出时间兼容样例.json"
            path.write_text(json.dumps(old_without_time, ensure_ascii=False, indent=2), encoding="utf-8")
            page = open_form()
            load(page, path)
            click(page, "结束")
            invalid, _ = save(page, "10-缺时点草稿恢复后正式记录", final=True)
            check("缺导出时间保留记录并登记计时不完整", invalid["timing"] == "invalid" and invalid["timingValid"] is False and invalid["seconds"] is None and "未记录有效导出时间" in invalid["interruption"], {"计时情况": invalid["timing"], "说明": invalid["interruption"]})
            page.close()
        except Exception as error:
            check("运行过程完成", False, repr(error))
        finally:
            check("浏览器脚本无异常", not errors, errors)
            browser.close()
    result["通过数"] = sum(c["通过"] for c in checks)
    result["总数"] = len(checks)
    result["全部通过"] = all(c["通过"] for c in checks)
    (out / "验收结果.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"通过": result["通过数"], "总数": result["总数"], "全部通过": result["全部通过"], "证据目录": str(out)}, ensure_ascii=False))
    return result["全部通过"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--form", type=Path, default=FORM)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if run(args.form.resolve(), args.out.resolve()) else 1)
