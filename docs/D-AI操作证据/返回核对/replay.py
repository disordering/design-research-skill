"""重跑三个 AI 返回核对任务。需要 Python、Playwright 和 Microsoft Edge。"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from playwright.sync_api import sync_playwright


HERE = Path(__file__).resolve().parent
TASKS = HERE.parents[1] / "D-新版真人执行" / "03-匿名原始任务"
TARGETS = {"A-H03": "南区试听间", "B-H04": "东侧工坊", "C-H05": "二层服务台"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def run_case(browser, task, destination, root):
    out = root / task[0]
    out.mkdir(parents=True, exist_ok=True)
    ctx = browser.new_context(viewport={"width": 1200, "height": 900}, locale="zh-CN")
    page = ctx.new_page()
    page.goto((TASKS / task / "打开界面.html").as_uri())
    steps = []

    def record(stage, action):
        radios = page.get_by_role("radio")
        labels = page.get_by_role("term").all_inner_texts()
        values = page.get_by_role("definition").all_inner_texts()
        body = page.locator("body")
        snapshot = body.aria_snapshot()
        image = f"{len(steps) + 1:02d}-{stage}.png"
        page.screenshot(path=out / image, animations="disabled")
        entry = {
            "step": len(steps) + 1, "stage": stage, "action": action, "utc": now(),
            "image": image, "visible_text": body.inner_text(), "accessibility_snapshot": snapshot,
            "radio_options": re.findall(r'(?m)^\s*- radio "([^"]+)"', snapshot),
            "checked_option": next(iter(re.findall(r'(?m)^\s*- radio "([^"]+)" \[checked\]', snapshot)), None),
            "displayed_fields": dict(zip(labels, values, strict=True)),
        }
        if radios.count() and len(entry["radio_options"]) != radios.count():
            raise RuntimeError(f"{task}：选项证据不完整")
        steps.append(entry)
        return entry

    initial = record("初始选项", "从空白浏览器上下文首次打开")
    target = next(label for label in initial["radio_options"] if destination in label)
    target_radio = page.get_by_role("radio", name=target, exact=True)
    target_radio.click()
    selected = record("选择下午", f"点选「{target}」")
    page.get_by_role("button", name="核对信息").click()
    first_review = record("首次核对", "点击「核对信息」")
    page.get_by_role("button", name="返回选择").click()
    returned = record("返回状态", "点击「返回选择」，先观察当前选中项")
    retained = returned["checked_option"] == selected["checked_option"] == target
    corrections = 0
    if not retained:
        target_radio.click()
        record("修正选择", f"重新点选「{target}」")
        corrections += 1
    page.get_by_role("button", name="核对信息").click()
    final_review = record("最终核对", "点击「核对信息」，核实目标后继续")
    expected = target.split(" ", 2)
    if not all(value in final_review["displayed_fields"].values() for value in expected):
        raise RuntimeError(f"{task}：核对页未显示目标，不提交")
    page.get_by_role("button", name="提交登记").click()
    receipt = record("完成结果", "点击「提交登记」")
    options_ok = (
        len(initial["radio_options"]) == 2 and initial["checked_option"] != target
        and selected["checked_option"] == target and all(
            all(part in initial["visible_text"] for part in label.split(" ", 2))
            for label in initial["radio_options"]
        )
    )
    receipt_ok = all(value in receipt["visible_text"] for value in expected)
    result = {
        "run_type": "AI 模拟操作（非真人）", "strategy": "返回后核对已选项，有误先修正，再次核对后提交",
        "task": task[0], "task_material": str(Path(task) / "打开界面.html"), "target": target,
        "browser": f"Microsoft Edge {browser.version}", "viewport": [1200, 900],
        "steps": steps, "clicks_after_open": len(steps) - 1, "extra_reselection_clicks": corrections,
        "counting_rule": "规定路径有 5 次点击（选择下午、核对、返回、再次核对、提交）。只将返回后为恢复下午而重选的点击计为额外操作。",
        "requirements": [
            {"id": 1, "observed": "符合" if options_ok else "需复核", "images": [initial["image"], selected["image"]],
             "detail": f"可见选项：{' / '.join(initial['radio_options'])}。初始勾选「{initial['checked_option']}」，点选后勾选「{selected['checked_option']}」。"},
            {"id": 2, "observed": "符合" if retained else "不符合", "images": [first_review["image"], returned["image"]],
             "detail": f"首次核对显示 {list(first_review['displayed_fields'].values())}。点击返回后画面上勾选「{returned['checked_option']}」。"},
            {"id": 3, "observed": "符合" if receipt_ok else "不符合", "images": [final_review["image"], receipt["image"]],
             "detail": f"最终核对显示 {list(final_review['displayed_fields'].values())}。提交后的完成页正文为「{receipt['visible_text']}」。"},
        ],
    }
    with (out / "逐步记录.json").open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    ctx.close()
    print(task[0], target, [r["observed"] for r in result["requirements"]], corrections)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="新建的证据目录，必须为空")
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error("指定空目录以免混合不同轮次证据")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        for task, destination in TARGETS.items():
            run_case(browser, task, destination, args.out)
        browser.close()
