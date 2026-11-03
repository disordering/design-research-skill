"""两个独立的浏览器上下文。可传入空目录保存复跑结果。"""
import argparse
import json
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright


START = (Path(__file__).resolve().parents[2] / "D-新版真人执行" / "04-次批匿名任务"
         / "H06-巡展资料清单" / "打开界面.html").as_uri()
TITLES = ["温度与釉色", "灯下的刻纹"]


def run(browser, output, name, removed, boundary):
    context = browser.new_context(viewport={"width": 1100, "height": 800}, locale="zh-CN")
    page = context.new_page()
    steps = []
    shots = output / "截图" / name
    shots.mkdir(parents=True)

    def record(action, filename=None):
        main = page.get_by_role("main")
        step = {
            "操作": action,
            "页面可见文字": main.inner_text(),
            "当前可访问性树": main.aria_snapshot(),
            "清单或目录中的资料": main.get_by_role("article").get_by_role("strong").all_inner_texts(),
        }
        if filename:
            image = shots / f"{len(steps)+1:02d}-{filename}.png"
            page.screenshot(path=image, full_page=True)
            step["截图"] = image.relative_to(output).as_posix()
        steps.append(step)

    def button(label):
        return page.get_by_role("button", name=label, exact=True)

    def item(title):
        return page.get_by_role("article").filter(has_text=title).first

    try:
        page.goto(START)
        record("新上下文，打开资料目录")
        page.get_by_role("combobox", name="分类").select_option(label="展签")
        record("选择分类“展签”", "只看展签")
        for title in TITLES:
            item(title).get_by_role("button", name="加入清单").click()
            record(f"加入《{title}》", "首份已加入" if title == TITLES[0] else None)
            if boundary and title == TITLES[0]:
                added = item(title).get_by_role("button", name="已加入")
                if added.is_enabled():
                    added.click()
                    record("再点一次同份资料的“已加入”")
                else:
                    record("检查能否再次加入同一份资料：“已加入”按钮禁用")
        button("查看清单（2）").click()
        record("查看清单", "移出前")
        item(removed).get_by_role("button", name="移出").click()
        record(f"移出《{removed}》", "移出后")
        undo = button("撤销刚才移除")
        undo.click()
        record("点一次“撤销刚才移除”", "首次撤销后")
        if boundary:
            if undo.is_visible() and undo.is_enabled():
                undo.click()
                record("再点一次仍可用的“撤销刚才移除”", "再次撤销后")
            else:
                record("查看是否可以再次撤销；当前没有可用的撤销按钮", "重复撤销边界")
        button("返回目录").click()
        record("点“返回目录”，观察分类和列表", "返回目录")
        if not boundary:
            page.get_by_role("combobox", name="分类").select_option(label="导览")
            record("补查另一分类，手动选择“导览”", "改选导览")
            page.get_by_role("button", name="查看清单", exact=False).click()
            record("不操作清单内容，只打开清单")
            button("返回目录").click()
            record("从清单再次返回目录，观察是否保留“导览”", "再次返回")
    finally:
        context.close()
    return {"轮次": name, "步骤": steps}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    output = parser.parse_args().output or Path(tempfile.mkdtemp(prefix="ai-exhibit-"))
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise SystemExit(f"需要空的输出目录：{output}")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            result = {"来源": "AI 在本机 Chromium 操作 D-HOLDOUT-1.1 演示页",
                      "浏览器版本": browser.version, "轮次": [
                run(browser, output, "撤销边界", TITLES[0], True),
                run(browser, output, "分类返回", TITLES[1], False),
            ]}
        finally:
            browser.close()
    (output / "逐步记录.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output.resolve())
