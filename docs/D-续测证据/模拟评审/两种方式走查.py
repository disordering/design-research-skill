"""按交叉次序执行 AI 开发走查。指定新的 --out，保留以往原始结果。"""
import argparse
import csv
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MATERIALS = REPO / "docs/D-新版真人执行"
TARGETS = {"A": "南区试听间", "B": "东侧工坊", "C": "二层服务台"}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class QuietFiles(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def inspect_task(page, task, variant, out):
    material = next((MATERIALS / "03-匿名原始任务").glob(task + "-*"))
    path = material / "打开界面.html"
    page.goto(path.as_uri())
    steps = []
    def record(action):
        options = page.locator("label.option")
        step = {
            "序号": len(steps)+1, "操作": action, "标题": page.locator("h1").inner_text(),
            "选项": options.all_inner_texts(),
            "勾选": page.locator("label.option:has(input:checked)").all_inner_texts(),
            "明细": page.locator("dd").all_inner_texts(),
        }
        steps.append(step)
        return step

    def press(label):
        page.get_by_role("button", name=label, exact=True).click()
        return record(label)

    def select(label):
        page.get_by_role("radio", name=label).check()
        return record("选择" + label)

    def capture(name):
        path = out / (name + ".png")
        page.screenshot(path=path, animations="disabled")
        return path

    first = record("打开任务")
    target = TARGETS[task]
    other = first["选项"][0].splitlines()[-1]
    selected = select(target)
    evidence = capture("01-选择")
    expected = press("核对信息")
    returned = press("返回选择")
    if target not in "".join(returned["勾选"]):
        select(target)
    before = press("核对信息")
    after = press("提交登记")
    capture("02-完成")
    # 主任务交付后再试两种反例，以区分“任何回执都会错”和“回执固定默认项”。
    press("重新开始")
    if variant == "主动改选上午":
        select(target)
        press("核对信息")
        press("返回选择")
        select(other)
    else:
        select(target)
    extra_check = press("核对信息")
    extra_done = press("提交登记")
    conclusions = {
        "R1可选项": len(first["选项"]) == 2 and [s for s in selected["勾选"] if target in s] != [],
        "R2返回保留": selected["勾选"] == returned["勾选"],
        "R3回执匹配": before["明细"] == after["明细"],
        "附加路径回执匹配": extra_check["明细"] == extra_done["明细"],
    }
    note = (
        f"任务{task}。首次核对为{'／'.join(expected['明细'])}。返回时勾选"
        f"{'／'.join(returned['勾选'][0].splitlines())}。提交前为{'／'.join(before['明细'])}，"
        f"回执为{'／'.join(after['明细'])}。"
    )
    raw = {"材料哈希": hashlib.sha256(path.read_bytes()).hexdigest(),
           "任务卡": (material / "任务卡.txt").read_text(encoding="utf-8-sig"),
           "各步": steps, "检查结果": conclusions, "工作备注": note,
           "附加路径": variant, "选择截图哈希": hashlib.sha256(evidence.read_bytes()).hexdigest()}
    write_json(out / "网页走查.json", raw)
    return raw, evidence


def check_workbench(page, origin, task, evidence, task_result, out):
    page.goto(origin)
    page.locator("#imageInput").set_input_files(str(evidence))
    expect(page.locator("#preview")).to_be_visible()
    name = f"AI 任务{task} · {out.name}"
    page.locator("#name").fill(name)
    page.locator("#audience").fill("首次办理登记的使用者")
    page.locator("#goal").fill("选择下午的" + TARGETS[task] + "，返回核对所选时段及地点，提交后核对回执。")
    page.locator("#intent").fill("选择时并列显示时段和地点，返回时保留选择，回执反映最终确认的信息。")
    page.locator("button[type=submit]").click()
    expect(page.locator("#export")).to_be_visible()
    cards = page.locator("article[data-id]")
    titles = cards.get_by_role("heading").all_inner_texts()
    # 上传图是时段单选页。对当前可见图排除两个不符的示例，等待状态需要时序证据。
    for locator, decision, reason in [
        ("issue-01", "驳回", "选择页只有一个实心“核对信息”主按钮。"),
        ("issue-02", "驳回", "这个页面是时段单选，两项都直接显示时间和地点。"),
        ("issue-03", "待验证", "本轮核对选项、返回和回执，未测等待过程。"),
    ]:
        card = page.locator(f"article[data-id='{locator}']")
        card.get_by_role("button", name=decision, exact=True).click()
        card.locator("textarea").fill(reason)
        card.locator("textarea").press("Tab")
    page.locator("#feedback").fill(task_result["工作备注"])
    page.locator("#revise").click()
    expect(page.locator("#version")).to_contain_text("2")
    after = cards.get_by_role("heading").all_inner_texts()
    actions = page.get_by_role("button").all_inner_texts()
    with page.expect_download() as event:
        page.locator("#export").click()
    result_path = out / "工作台原始导出.md"
    event.value.save_as(result_path)
    report = result_path.read_text(encoding="utf-8-sig")
    before_log, marker, log = report.partition("## 操作记录")
    evidence_uploaded = page.locator("#reviewImage").evaluate(
        "(img) => [img.naturalWidth, img.naturalHeight, img.src.startsWith('data:image/png')]")
    outcome = {
        "工作台来源": page.locator(".mode").inner_text(), "题目截图": evidence.name,
        "截图尺寸与类型": evidence_uploaded, "初始卡片": titles, "反馈重评后卡片": after,
        "可见操作按钮": actions, "复核备注": task_result["工作备注"],
        "反馈在操作记录": bool(marker) and task_result["工作备注"] in log,
        "反馈在正文": task_result["工作备注"] in before_log,
        "审核状态读回": before_log.count("人工审核：rejected") == 2 and before_log.count("人工审核：verify") == 1,
    }
    write_json(out / "工作台核对.json", outcome)
    return outcome


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    with (MATERIALS / "00-仅主持人/体验轮次.csv").open(encoding="utf-8-sig", newline="") as f:
        schedule = list(csv.DictReader(f))
    seen = {}
    summary = []
    with ThreadingHTTPServer(("127.0.0.1",0), partial(QuietFiles, directory=str(REPO / "frontend/dist"))) as server:
        Thread(target=server.serve_forever, daemon=True).start()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            for row in schedule:
                task = row["任务"]
                method = "工作台模拟模式" if row["方式"] == "工具" else "只看原始页面"
                cell = (task, method)
                variant = "主动改选上午" if cell not in seen else "重开再选下午"
                seen[cell] = seen.get(cell,0)+1
                run_id = "AI-" + row["匿名编号"][1:] + "-" + row["轮次"] + "-" + task
                destination = out / run_id
                destination.mkdir()
                started = datetime.now(timezone.utc).isoformat()
                with browser.new_context(locale="zh-CN", viewport={"width": 1152, "height": 840}) as ctx:
                    page = ctx.new_page()
                    task_result, image = inspect_task(page, task, variant, destination)
                    tool = (check_workbench(ctx.new_page(), f"http://127.0.0.1:{server.server_port}",
                                            task, image, task_result, destination)
                            if row["方式"] == "工具" else None)
                summary.append({"编号": run_id, "方式": method, "任务": task, "附加路径": variant,
                                "浏览器": browser.version, "开始UTC": started,
                                "结束UTC": datetime.now(timezone.utc).isoformat(),
                                "三要求及附加路径": task_result["检查结果"],
                                "工作台导出读回": tool["审核状态读回"] if tool else None})
            browser.close()
        server.shutdown()
    write_json(out / "12轮汇总.json", {"执行者": "同一套 AI 编排自动化，6 个顺序槽位",
                                    "材料版本": "D-HOLDOUT-1.0", "原始记录": summary})
    print("完成", len(summary), "轮；每格运行", list(seen.values()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    main(parser.parse_args().out)

