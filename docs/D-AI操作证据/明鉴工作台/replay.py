"""明鉴 AI 演练。用 --out 指定空目录以保留原始证据。"""
import argparse
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from threading import Thread
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


DIST = Path(__file__).resolve().parents[3] / "frontend/dist"
FIELD = "示例：输入项缺少清楚的字段名称"
ACTION = "示例：主要操作的视觉层级不足"
WAIT = "示例：等待反馈需要额外证据"
QUICK_NOTE = "AI 演练：第一个输入框仅显示「请输入」，框外没有可见字段名。"
ACTION_NOTE = "AI 演练：创建账号画面上「返回」和「确定」使用相同的浅色按钮，主操作未被突出。"
FIELD_NOTE = "AI 演练：截图显示「请输入」，未展示输入后的画面；先补充填写后的状态。"


class QuietFiles(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def run(browser, origin, root, strategy):
    out = root / strategy
    out.mkdir(parents=True)
    title = f"AI 演练 · {strategy}"
    ctx = browser.new_context(locale="zh-CN", viewport={"width": 1440, "height": 1040}, reduced_motion="reduce")
    external = []

    def local_only(route):
        parts = urlsplit(route.request.url)
        if parts.scheme in ("http", "https") and not route.request.url.startswith(origin + "/"):
            external.append(route.request.url)
            route.abort()
        else:
            route.continue_()

    ctx.route("**/*", local_only)
    page = ctx.new_page()
    by = page.get_by_role
    severity = by("combobox", name="筛选严重度")
    status = by("combobox", name="筛选问题")
    cards = by("article")
    steps = []

    def selected(select):
        return select.locator("option:checked").inner_text()

    def card(heading):
        return cards.filter(has=by("heading", name=heading, exact=True))

    def row_state(row):
        pressed = row.get_by_role("button", pressed=True)
        return {
            "title": row.get_by_role("heading").inner_text(),
            "severity": selected(row.get_by_role("combobox")),
            "review_button": pressed.inner_text() if pressed.count() else None,
            "note": row.get_by_role("textbox", name="审核理由").input_value(),
            "findings": dict(zip(row.get_by_role("term").all_inner_texts(),
                                 row.get_by_role("definition").all_inner_texts(), strict=True)),
        }

    def log(action, image=None, element=None, extra=None):
        state = {
            "step": len(steps) + 1, "utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "action": action, "page_heading": by("heading", level=1).inner_text(),
            "history": by("complementary").get_by_role("button", name=re.compile(r"模拟演示 · v")).all_inner_texts(),
        }
        if severity.is_visible():
            state.update({"filters": [selected(severity), selected(status)],
                          "visible_findings": [row_state(row) for row in cards.all()]})
        if extra:
            state.update(extra)
        if image:
            if element is None:
                page.screenshot(path=out / image, full_page=True, animations="disabled")
            else:
                element.screenshot(path=out / image, animations="disabled")
            state["image"] = image
        steps.append(state)

    page.goto(origin)
    log("空白浏览器上下文打开本机工作台", extra={"source": selected(by("combobox", name="数据来源"))})
    by("button", name="没有截图？使用内置示例 →").click()
    by("textbox", name="评审名称").fill(title)
    log("载入内置注册示例，命名本轮", extra={"core_task": by("textbox", name="核心任务").input_value()})
    by("button", name="开始模拟评审 →").click()
    by("button", name="↓ 导出报告").wait_for()
    log("生成模拟评审并查看初始三项", extra={"source_label": by("banner").inner_text()})
    original = {r["title"]: r for r in steps[-1]["visible_findings"]}
    expected_after_reopen = dict(original)

    def marker(heading):
        pin = by("button", name="定位" + heading)
        number = pin.inner_text()
        pin.click()
        log(f"点击截图编号 {number}，目标为「{heading}」", extra={
            "target_visible": card(heading).is_visible(),
            "target_in_viewport": card(heading).evaluate(
                "(card) => {const r=card.getBoundingClientRect();return r.top<innerHeight&&r.bottom>0}"),
        })

    def annotate(heading, choice, note, level=None):
        target = card(heading)
        if level:
            target.get_by_role("combobox").select_option(label=level)
            log(f"将「{heading}」严重度改为{level}")
        target.get_by_role("button", name=choice, exact=True).click()
        log(f"对「{heading}」选择「{choice}」")
        reason = target.get_by_role("textbox", name="审核理由")
        reason.fill(note)
        reason.press("Tab")
        log("输入审核理由并离开输入框")
        expected_after_reopen[heading] = row_state(target)

    if strategy == "快速":
        marker(FIELD)
        severity.select_option(label="高")
        log("按高严重度筛选", "01-筛选结果.png")
        annotate(FIELD, "确认问题", QUICK_NOTE)
    else:
        severity.select_option(label="高")
        status.select_option(label="待审核")
        log("同时筛选高严重度与待审核", "01-双筛选.png")
        marker(ACTION)
        log("观察点击被筛除发现的截图编号后的筛选及定位状态", "02-编号定位后.png")
        annotate(ACTION, "确认问题", ACTION_NOTE, level="高")
        marker(FIELD)
        annotate(FIELD, "待验证", FIELD_NOTE)
        status.select_option(label="待验证")
        log("用待验证筛选复查列表", "03-待验证结果.png")
    page.reload()
    log("刷新页面，观察是否自动重开评审")
    by("button", name=title + " 模拟演示 · v1").click()
    restored = [row_state(row) for row in cards.all()]
    log("从本机评审记录恢复 AI 演练", "02-历史恢复.png" if strategy == "快速" else "04-历史恢复.png",
        extra={"restored_matches_last_review": {r["title"]: r == expected_after_reopen[r["title"]] for r in restored}})
    with page.expect_download() as download:
        by("button", name="↓ 导出报告").click()
    path = out / "原始导出.md"
    download.value.save_as(path)
    raw = path.read_text(encoding="utf-8-sig")
    report = {}
    for section in raw.split("\n## ")[1:]:
        heading, _, body = section.partition("\n")
        report[heading.strip()] = dict(re.findall(r"(?m)^- ([^：\n]+)：([^\n]*)$", body))
    canonical = {"确认问题": "confirmed", "撤销审核": "pending", "待验证": "verify", "驳回": "dismissed"}
    levels = {"严重": "critical", "高": "high", "中": "medium", "低": "low"}
    comparisons = []
    for row in restored:
        md = report[row["title"]]
        comparisons.append({
            "title": row["title"], "review_matches": canonical[row["review_button"]] == md["人工审核"],
            "level_matches": levels[row["severity"]] == md["严重度"].partition("（")[0],
            "reason_matches": (row["note"] or "未填写") == md["审核理由"],
            "initial_finding_matches": all(md[k] == v for k, v in original[row["title"]]["findings"].items()),
            "md_review": md["人工审核"], "md_reason": md["审核理由"], "md_severity": md["严重度"],
        })
    log("下载 Markdown 并逐条对照页面上的判断、等级、审核理由与检测说明",
        extra={"file": path.name, "download_name": download.value.suggested_filename, "comparisons": comparisons})
    result = {"type": "AI 演练（非真人）", "workflow": strategy, "source": "frontend/dist 内置示例 / 模拟演示",
              "browser": f"Microsoft Edge {browser.version}", "external_requests_blocked": external, "steps": steps}
    (out / "操作记录.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ctx.close()
    print(strategy, "导出对照", comparisons)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    out = parser.parse_args().out
    if out.exists() and any(out.iterdir()):
        parser.error("请指定空的输出目录")
    with ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietFiles, directory=str(DIST))) as server:
        Thread(target=server.serve_forever, daemon=True).start()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            for strategy in ("快速", "细审"):
                run(browser, f"http://127.0.0.1:{server.server_port}", out, strategy)
            browser.close()
        server.shutdown()
