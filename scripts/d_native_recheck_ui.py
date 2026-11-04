"""在原生 Node/FastAPI 工作台读回 D 实际会话，保存截图、静音录像和 UI 导出。"""
from __future__ import annotations

import argparse
import contextlib
import json
import socket
import subprocess
import threading
import zipfile

import d_native_recheck as d
import uvicorn
from playwright.sync_api import expect, sync_playwright
from engine.api import create_app


def inspect(stage_name, decisions_file=None, output_name="UI读回"):
    stage = d.EVIDENCE / stage_name
    result = json.loads((stage / "运行结果.json").read_text(encoding="utf-8"))
    output = stage / output_name
    assert output.resolve().is_relative_to(stage.resolve())
    output.mkdir(exist_ok=False)
    store = d.SessionStore(d.WORK / "d_1104_native_recheck" / stage_name)
    service = d.SessionService(store)
    sid = result["会话"]
    current_version = store.get(sid).report_version
    network, errors = [], []
    record = {"来源": stage_name, "会话": sid, "操作员": d.ACTOR, "操作者类型": "ai",
              "操作": "原 Node 前端 → 原 FastAPI → 实际会话数据库；" +
                      ("AI明确复核、版本核对与导出" if decisions_file else "只读恢复、版本切换与导出"),
              "浏览器异常": errors, "HTTP": network}
    with contextlib.ExitStack() as stack:
        sock = stack.enter_context(socket.socket())
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(create_app(session_service_factory=lambda: service),
                                log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()

        def stop_backend():
            server.should_exit = True
            thread.join(3)
        stack.callback(stop_backend)
        node = subprocess.Popen([d.shutil.which("node"), "--input-type=module", "-e",
            f"import {{createServer}} from './server.mjs';createServer('http://127.0.0.1:{port}').listen(4173,'127.0.0.1',()=>console.log('ready'));"],
            cwd=d.REPO / "frontend", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

        def stop_frontend():
            if node.poll() is None:
                node.terminate()
                node.wait(3)
        stack.callback(stop_frontend)
        assert node.stdout.readline().decode().strip() == "ready", "前端端口未启动；没有覆盖其他服务。"
        playwright = stack.enter_context(sync_playwright())
        browser = playwright.chromium.launch()
        stack.callback(browser.close)
        context = browser.new_context(locale="zh-CN", viewport={"width": 1440, "height": 1000},
                                      record_video_dir=output / "静音演示", record_video_size={"width": 1440, "height": 1000})
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("response", lambda response: network.append({"方法": response.request.method,
                 "URL": response.url.split("4173")[-1], "HTTP": response.status}) if "/engine/" in response.url else None)
        page.goto("http://127.0.0.1:4173/session.html")
        page.locator("#actor").fill(d.ACTOR)
        page.locator("#actorType").select_option("ai")
        page.locator("#restoreId").fill(sid)
        page.locator("#restore").click()
        expect(page.locator("#progress")).to_contain_text(f"报告 v{current_version}")
        record["运行归档版本"] = result["报告版本"]
        record["当前会话版本"] = current_version
        page.screenshot(path=output / "01-会话读回.png")
        page.wait_for_timeout(1200)  # 留出静音演示的阅读时间，不模拟生成进度。
        record["当前会话"] = page.locator("#progress").inner_text()
        page.locator("#findings").scroll_into_view_if_needed()
        page.screenshot(path=output / "02-模型发现.png")
        page.wait_for_timeout(1800)
        record["发现文字"] = page.locator("#findings").inner_text()
        if decisions_file:
            decisions = json.loads(d.Path(decisions_file).read_text(encoding="utf-8"))
            before = store.get(sid)
            hashes_before = d.report_hashes(store)
            record["AI确认事件"] = []
            d.save(output / "AI确认前快照.json", before.model_dump(mode="json"))
            for decision in decisions:
                assert decision["review_status"] == "confirmed", "此入口仅保存已经核实的AI确认，不触发新的模型重查。"
                form = page.locator(f'[data-review-form="{decision["finding_id"]}"]')
                expect(form).to_be_visible()
                form.locator('[name="review_status"]').select_option("confirmed")
                form.locator('[name="severity"]').select_option(decision.get("severity") or "")
                form.locator('[name="disposition"]').select_option(decision.get("disposition") or "")
                form.locator('[name="reason"]').fill(decision["reason"])
                with page.expect_response(lambda response: response.url.endswith("/events") and response.request.method == "POST") as response_info:
                    form.locator("button").click()
                response = response_info.value
                assert response.status == 202
                event = response.request.post_data_json
                assert event["actor_type"] == "ai" and event["actor"] == d.ACTOR
                record["AI确认事件"].append({"事件": event, "HTTP": response.status})
            after = store.get(sid)
            assert after.run_id == before.run_id and len(after.model_calls) == len(before.model_calls)
            assert d.report_hashes(store) == hashes_before
            record["AI确认核对"] = {"未新增模型调用": True, "旧报告原字节SHA256": hashes_before,
                                 "旧报告确认后保持一致": True}
            d.save(output / "AI确认后快照.json", after.model_dump(mode="json"))
            page.locator("#findings").scroll_into_view_if_needed()
            page.screenshot(path=output / "02b-AI明确复核.png")
            page.wait_for_timeout(1800)
        page.locator("#rechecks").scroll_into_view_if_needed()
        page.screenshot(path=output / "03-复审结果.png")
        page.wait_for_timeout(1800)
        record["复审文字"] = page.locator("#rechecks").inner_text()
        page.locator("#exports").scroll_into_view_if_needed()
        with page.expect_download() as download_info:
            page.locator("#exports a").filter(has_text="完整 ZIP").click()
        download = download_info.value
        destination = output / "界面下载-产品报告包.zip"
        download.save_as(destination)
        with zipfile.ZipFile(destination) as archive:
            assert archive.testzip() is None
            report = json.loads(archive.read("report.json"))
            assert report["review_id"] == sid
            assert report["report_version"] == current_version
            if decisions_file:
                exported_findings = {item["finding_id"]: item for item in report.get("findings", [])}
                for decision in decisions:
                    reviewed = exported_findings[decision["finding_id"]]
                    assert reviewed["review_status"] == "confirmed" and reviewed["reviewer"] == d.ACTOR
                record["导出AI确认状态"] = {key: value for key, value in exported_findings.items()
                    if key in {item["finding_id"] for item in decisions}}
            record["ZIP"] = {"SHA256": d.sha(destination.read_bytes()), "成员": len(archive.namelist()),
                             "报告版本": report.get("report_version"), "会话": report.get("review_id"),
                             "模型调用": len(report.get("model_calls", [])), "复审": report.get("rechecks", [])}
            record["ZIP发现状态"] = [{key: item.get(key) for key in
                ["finding_id", "kind", "severity", "review_status", "reviewer", "human_severity", "location"]}
                for item in report.get("findings", [])]
        page.screenshot(path=output / "04-报告导出.png")
        page.wait_for_timeout(1200)
        page.locator("#versions").select_option(str(result["报告版本"]))
        expect(page.locator("#progress")).to_contain_text(f"报告 v{result['报告版本']}")
        expect(page.locator("#progress")).to_contain_text("历史只读")
        record["历史读回"] = page.locator("#progress").inner_text()
        record["历史反馈隐藏"] = not page.locator("#reply").is_visible()
        page.screenshot(path=output / "05-历史只读.png")
        page.wait_for_timeout(1200)
        if current_version != result["报告版本"]:
            page.locator("#versions").select_option(str(current_version))
            expect(page.locator("#progress")).to_contain_text(f"报告 v{current_version}")
            expect(page.locator("#progress")).to_contain_text("历史只读")
            record["最新保存版历史读回"] = page.locator("#progress").inner_text()
            record["最新保存版发现"] = page.locator("#findings").inner_text()
            page.locator("#findings").scroll_into_view_if_needed()
            page.screenshot(path=output / "06-最新保存版历史只读.png")
            page.wait_for_timeout(1200)
        context.close()
        d.save(output / "读回记录.json", record)
        print(json.dumps({"阶段": stage_name, "HTTP失败": [x for x in network if x["HTTP"] >= 400],
                          "异常": errors, "ZIP成员": record["ZIP"]["成员"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stages", nargs="+")
    parser.add_argument("--decisions", help="已核实的AI确认决定JSON；只支持单个阶段")
    parser.add_argument("--output-name", default="UI读回")
    args = parser.parse_args()
    if args.decisions and len(args.stages) != 1:
        parser.error("AI确认只处理一个明确会话阶段。")
    for name in args.stages:
        inspect(name, args.decisions, args.output_name)
