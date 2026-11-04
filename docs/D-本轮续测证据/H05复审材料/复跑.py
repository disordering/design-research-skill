"""在全新的浏览器上下文中跑 H05 的上午、下午路径，保存提交前后可见证据。"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


HERE = Path(__file__).resolve().parent
SLOTS = {"上午": ["周五", "09:00–09:30", "一层服务台"],
         "下午": ["周五", "14:00–14:30", "二层服务台"]}


def fingerprint(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def run_path(browser, version, slot, out):
    page_file = HERE / version / "打开界面.html"
    desired = SLOTS[slot]
    with browser.new_context(locale="zh-CN", viewport={"width": 980, "height": 720}) as context:
        page = context.new_page()
        page.goto(page_file.as_uri())
        choices = page.get_by_role("radio")
        expect(choices).to_have_count(2)
        radio = page.get_by_role("radio", name=desired[2], exact=False)
        radio.check()
        page.get_by_role("button", name="核对信息").click()
        first = page.locator("dd").all_inner_texts()
        page.get_by_role("button", name="返回选择").click()
        expect(radio).to_be_checked()
        page.get_by_role("button", name="核对信息").click()
        before = page.locator("dd").all_inner_texts()
        before_file = out / f"{version}-{slot}-01核对.png"
        page.screenshot(path=before_file)
        page.get_by_role("button", name="提交登记").click()
        expect(page.get_by_role("heading", name="登记完成")).to_be_visible()
        after = page.locator("dd").all_inner_texts()
        after_file = out / f"{version}-{slot}-02回执.png"
        page.screenshot(path=after_file)
    return {"版本": version, "时段": slot, "预期": desired, "首次核对": first,
            "返回已保留选择": True, "提交前": before, "实际回执": after,
            "提交前与预期一致": first == before == desired, "回执与预期一致": after == desired,
            "截图": {f.name: fingerprint(f) for f in [before_file, after_file]}}


def main():
    a, b = (HERE / version / "打开界面.html" for version in ["A", "B"])
    assert a.read_bytes().replace(b"summary(options[0])", b"summary(options[selected])") == b.read_bytes()
    assert (HERE / "A/任务卡.txt").read_bytes() == (HERE / "B/任务卡.txt").read_bytes()
    out = HERE / "实测"
    out.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            traces = [run_path(browser, version, slot, out)
                      for version in ["A", "B"] for slot in SLOTS]
            browser_version = browser.version
        finally:
            browser.close()
    result = {"用途": "D 制作的输入样本，用于复验评审软件识别版本差异的能力。",
              "执行": "Playwright 在 Chromium 操作本地样本，未调用评审引擎或模型。",
              "时间UTC": datetime.now(timezone.utc).isoformat(), "Chromium": browser_version,
              "冻结来源提交": "2157483fb33f4248d2548772840dbaea498d58aa",
              "源文件": "docs/D-新版真人执行/03-匿名原始任务/C-H05/打开界面.html",
              "样本SHA256": {"A": fingerprint(a), "B": fingerprint(b),
                            "共同任务卡": fingerprint(HERE / "A/任务卡.txt")},
              "路径": traces}
    (out / "四组走查.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for r in traces:
        verdict = "一致" if r["回执与预期一致"] else "错配"
        print(r["版本"], r["时段"], "／".join(r["实际回执"]), verdict)
    assert all(r["提交前与预期一致"] for r in traces)
    assert [r["回执与预期一致"] for r in traces] == [True, False, True, True]


if __name__ == "__main__":
    main()
