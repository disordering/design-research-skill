# -*- coding: utf-8 -*-
"""在本机浏览器中按控件名称操作。默认将复跑结果写到新的临时目录。"""
import argparse
import json
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


MATERIALS = Path(__file__).resolve().parents[2] / "D-新版真人执行" / "03-匿名原始任务"
TARGETS = {"A-H03": "南区试听间", "B-H04": "东侧工坊", "C-H05": "二层服务台"}


def run_route(browser, folder, destination, return_once, output):
    task = folder.name[0]
    route = "返回不重选" if return_once else "直接提交"
    run_id = f"{task}-{route}"
    screenshots = output / "截图" / run_id
    screenshots.mkdir(parents=True)
    context = browser.new_context(viewport={"width": 1100, "height": 780}, locale="zh-CN")
    page = context.new_page()
    steps = []

    def record(label, action):
        image = screenshots / f"{len(steps) + 1:02d}-{label}.png"
        page.screenshot(path=image, full_page=True, animations="disabled")
        steps.append({
            "操作": action,
            "页面可见文字": page.locator("main").inner_text(),
            "可访问性树": page.locator("main").aria_snapshot(),
            "截图": image.relative_to(output).as_posix(),
        })

    def button(name):
        page.get_by_role("button", name=name, exact=True).click()

    try:
        page.goto((folder / "打开界面.html").as_uri())
        record("初始", "在新浏览器上下文打开任务界面")
        page.get_by_text(destination, exact=True).click()
        record("选下午", f"点选{destination}一行")
        button("核对信息")
        record("首次核对", "点“核对信息”")
        if return_once:
            button("返回选择")
            record("返回后", "点“返回选择”")
            button("核对信息")
            record("再次核对", "保持现有选项，直接点“核对信息”")
        button("提交登记")
        record("提交结果", "点“提交登记”")
    finally:
        context.close()
    return {"任务": task, "路径": route, "步骤": steps}


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--output", type=Path, help="一个空的输出目录")
    output = args.parse_args().output
    if output is None:
        output = Path(tempfile.mkdtemp(prefix="ai-quick-review-"))
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise SystemExit(f"输出目录须为空，以免覆盖上轮证据：{output}")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            report = {"来源": "本机 Chromium / AI 模拟操作", "浏览器": browser.version, "轮次": []}
            for name, destination in TARGETS.items():
                for return_once in [False, True]:
                    result = run_route(browser, MATERIALS / name, destination, return_once, output)
                    report["轮次"].append(result)
                    print(result["任务"], result["路径"], result["步骤"][-1]["页面可见文字"])
            (output / "逐步记录.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        finally:
            browser.close()
    print(output.resolve())


if __name__ == "__main__":
    main()
