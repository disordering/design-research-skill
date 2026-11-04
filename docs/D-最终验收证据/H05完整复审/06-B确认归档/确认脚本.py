"""复制已结束的 H05 会话，以 AI 身份经原生前端确认复审、导出并读回历史。"""
from __future__ import annotations

import argparse
import contextlib
import inspect
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import zipfile

BOOT_REPO = Path(__file__).resolve().parents[1]
SOURCE_FROZEN = Path(os.environ.get("D_FINAL_ENGINE_ROOT", BOOT_REPO.parent / "work/d_final_h05/冻结基线")).resolve()
FROZEN = BOOT_REPO.parent / "work/d_h05_confirm_runtime/66a0"
# API 模块在导入时创建默认应用，需要同提交的旧版判据库；独立副本不改 B 的运行目录。
FROZEN.mkdir(parents=True, exist_ok=True)
if not (FROZEN / "engine").exists():
    shutil.copytree(SOURCE_FROZEN / "engine", FROZEN / "engine", ignore=shutil.ignore_patterns("__pycache__"))
for source in (SOURCE_FROZEN / "engine").rglob("*"):
    if source.is_file() and "__pycache__" not in source.parts:
        assert (FROZEN / source.relative_to(SOURCE_FROZEN)).read_bytes() == source.read_bytes()
for name, data in {
    "源码来源.json": (SOURCE_FROZEN / "源码来源.json").read_bytes(),
    "判据库_v1.json": subprocess.check_output(["git", "show", "66a0f0919ada6d334565c3451e9f16ea95000bc9:判据库_v1.json"], cwd=BOOT_REPO),
}.items():
    target = FROZEN / name
    if target.exists():
        assert target.read_bytes() == data, name
    else:
        target.write_bytes(data)
sys.path.insert(0, str(FROZEN))
import engine  # 固定整个包的搜索目录，后续导入都沿用 66a0 引擎。

import d_native_recheck as d
import d_h05_final_compare as comparison
import uvicorn
from engine.api import create_app
from playwright.sync_api import expect, sync_playwright

ROOT = d.REPO / "docs/D-最终验收证据/H05完整复审"


def database_content(directory):
    path = (directory / "sessions.sqlite3").resolve()
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        return {table: d.sha(json.dumps(db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall(),
                    ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                for table in ("sessions", "events", "reports", "artifacts")}


def report_bodies(directory, sid):
    path = (directory / "sessions.sqlite3").resolve()
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        return {str(version): body for version, body in db.execute(
            "SELECT version,body FROM reports WHERE session_id=? ORDER BY version", (sid,))}


def file_hashes(directory):
    return {p.relative_to(directory).as_posix(): d.sha(p.read_bytes())
            for p in sorted(directory.rglob("*")) if p.is_file()}


def confirm(args):
    for name in (args.base, args.name):
        if not name or Path(name).name != name or name in {".", ".."}:
            raise ValueError("阶段名称必须是一个目录名。")
    stage, source_stage = ROOT / args.name, ROOT / args.base
    origin = d.WORK / "d_final_h05" / args.base
    destination = d.WORK / "d_final_h05" / args.name
    if stage.exists() or destination.exists():
        raise SystemExit("本阶段名称已存在，原记录不覆盖。")
    frozen_source = json.loads((FROZEN / "源码来源.json").read_text(encoding="utf-8"))
    assert frozen_source["git"] == "66a0f0919ada6d334565c3451e9f16ea95000bc9"
    assert Path(inspect.getfile(d.SessionService)).resolve().is_relative_to(FROZEN)
    prerequisite = comparison.measure(args.base, args.expected)
    assert prerequisite["H05指定旧候选专项通过"], "来源阶段的旧候选专项尚未通过。"
    origin_environment = comparison.read(source_stage / "运行环境.json")
    for filename, digest in origin_environment["代码SHA256"].items():
        assert d.sha((FROZEN / filename).read_bytes()) == digest, filename
    with socket.socket() as available:
        available.bind(("127.0.0.1", 4173))  # 前端的原生 Origin 白名单使用此端口。
    source_files = file_hashes(source_stage)
    source_database = database_content(origin)
    stage.mkdir(parents=True)
    d.save(stage / "复制校验.json", d.clone_state(origin, destination))
    store = d.SessionStore(destination)
    sid = comparison.read(source_stage / "运行结果.json")["会话"]
    before = store.get(sid)
    assert before.status == "completed"
    before_value = before.model_dump(mode="json")
    history = report_bodies(origin, sid)
    hashes_before = {version: d.sha(body.encode("utf-8")) for version, body in history.items()}
    assert d.report_hashes(store) == hashes_before
    decisions = [r.model_dump(mode="json") for r in before.rechecks]
    assert len(decisions) == 2 and all(r["resolution"] == args.expected for r in decisions)
    d.save(stage / "启动快照.json", before_value)
    d.save(stage / "来源专项核对.json", prerequisite)
    d.save(stage / "原模型复审记录.json", decisions)
    (stage / "确认脚本.py").write_bytes(Path(__file__).read_bytes())
    model_attempts = []

    def forbid_model(_):
        model_attempts.append({"时间": d.utc(), "状态": "确认流程不调用模型"})
        raise RuntimeError("此确认归档阶段不允许调用模型。")

    service = d.SessionService(store, model_factory=forbid_model,
                              registry=d.MethodRegistry(d.REPO / "方法专家开发交付-v0.2"))
    network, errors, events = [], [], []
    record = {"来源阶段": args.base, "阶段": args.name, "开始": d.utc(), "会话": sid,
              "操作员": d.ACTOR, "操作者类型": "ai", "运行性质": "既有会话复审确认、导出及历史读回",
              "模型调用": 0, "引擎来源": frozen_source, "实际引擎目录": str(FROZEN / "engine"),
              "冻结引擎原目录": str(SOURCE_FROZEN),
              "运行资源": "独立复制冻结引擎，逐文件字节校验；判据库_v1.json 取自同一 66a0 提交。",
              "来源报告版本": before.report_version, "原报告完整度": before.report_completeness,
              "前端SHA256": {p: d.sha((d.REPO / "frontend" / p).read_bytes())
                              for p in ("server.mjs", "dist/session.html", "dist/session-ui.js", "dist/session-api.js")},
              "HTTP": network, "浏览器异常": errors, "AI确认事件": events,
              "确认来源说明": "前端按钮沿用通用确认文案；实际提交及导出事件均标明 actor_type=ai。"}
    d.save(stage / "运行环境.json", record | {"会话目录": str(destination), "代码SHA256": origin_environment["代码SHA256"]})
    try:
        with contextlib.ExitStack() as stack:
            sock = stack.enter_context(socket.socket())
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            app = create_app(criteria_path=d.REPO / "判据库_v1.json", session_service_factory=lambda: service)
            server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
            thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
            thread.start()

            def stop_backend():
                server.should_exit = True
                thread.join(5)
            stack.callback(stop_backend)
            deadline = time.monotonic() + 10
            while not server.started:
                assert thread.is_alive() and time.monotonic() < deadline, "本地后端未启动。"
                time.sleep(0.05)
            node = subprocess.Popen([shutil.which("node"), "--input-type=module", "-e",
                f"import {{createServer}} from './server.mjs';createServer('http://127.0.0.1:{port}').listen(4173,'127.0.0.1',()=>console.log('ready'));"],
                cwd=d.REPO / "frontend", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

            def stop_frontend():
                if node.poll() is None:
                    node.terminate()
                    node.wait(5)
            stack.callback(stop_frontend)
            assert node.stdout.readline().decode().strip() == "ready", "前端未启动，没有覆盖其他服务。"
            playwright = stack.enter_context(sync_playwright())
            browser = playwright.chromium.launch()
            stack.callback(browser.close)
            context = browser.new_context(locale="zh-CN", viewport={"width": 1440, "height": 1000}, accept_downloads=True)
            stack.callback(context.close)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("response", lambda response: network.append({"方法": response.request.method,
                    "路径": response.url.split("4173", 1)[-1], "HTTP": response.status})
                    if "/engine/" in response.url else None)
            page.goto("http://127.0.0.1:4173/session.html")
            page.locator("#actor").fill(d.ACTOR)
            page.locator("#actorType").select_option("ai")
            page.locator("#restoreId").fill(sid)
            page.locator("#restore").click()
            expect(page.locator("#progress")).to_contain_text(f"报告 v{before.report_version}")
            page.screenshot(path=stage / "01-当前会话读回.png")
            page.locator("#rechecks").scroll_into_view_if_needed()
            page.screenshot(path=stage / "02-复审确认前.png")
            reason = ("AI复核：下午二层核对后提交，回执显示上午一层；本轮错配仍存在。"
                      if args.expected == "persists" else
                      "AI复核：下午二层核对后提交，回执保持下午二层；该旧错配已修复。")
            for index, decision in enumerate(decisions, 1):
                form = page.locator(f'[data-recheck-form="{decision["recheck_id"]}"]')
                form.scroll_into_view_if_needed()
                expect(form).to_be_visible()
                form.locator('[name="resolution"]').select_option(decision["resolution"])
                form.locator('[name="evidence_ids"]').select_option(decision["evidence_ids"])
                form.locator('[name="current_finding_ids"]').select_option(decision["current_finding_ids"])
                form.locator('[name="reason"]').fill(reason)
                with page.expect_response(lambda response: response.url.endswith("/events") and response.request.method == "POST") as response_info:
                    form.locator("button").click()
                response = response_info.value
                assert response.status == 202
                event = response.request.post_data_json
                assert event["type"] == "confirm_recheck" and event["actor_type"] == "ai" and event["actor"] == d.ACTOR
                assert event["payload"]["resolution"] == decision["resolution"]
                assert set(event["payload"]["evidence_ids"]) == set(decision["evidence_ids"])
                assert set(event["payload"]["current_finding_ids"]) == set(decision["current_finding_ids"])
                returned = response.json()
                confirmed = next(r for r in returned["rechecks"] if r["recheck_id"] == decision["recheck_id"])
                assert confirmed["human_confirmation"] == "confirmed" and confirmed["reviewer"] == d.ACTOR
                events.append({"事件": event, "HTTP": response.status, "确认记录": confirmed})
                expect(form.locator("p").first).to_contain_text("已确认")
                page.screenshot(path=stage / f"03-{index}-AI确认复审.png")
                d.save(stage / "AI确认事件.json", events)
            after = store.get(sid)
            after_value = after.model_dump(mode="json")
            protected = ("run_id", "context_version", "status", "report_version", "report_completeness", "request",
                         "model_calls", "evidence", "checks", "actions", "findings", "sources")
            assert all(after_value[key] == before_value[key] for key in protected)
            assert after_value["messages"][:len(before_value["messages"])] == before_value["messages"]
            assert len(after_value["messages"]) == len(before_value["messages"]) + 2
            assert all(m["type"] == "confirm_recheck" and m["actor_type"] == "ai" for m in after_value["messages"][-2:])
            for old, new in zip(decisions, after_value["rechecks"]):
                assert all(new[key] == old[key] for key in ("recheck_id", "previous_finding_id", "resolution"))
                assert set(new["evidence_ids"]) == set(old["evidence_ids"])
                assert set(new["current_finding_ids"]) == set(old["current_finding_ids"])
            assert d.report_hashes(store) == hashes_before and not model_attempts
            d.save(stage / "确认后生成报告前快照.json", after_value)
            page.locator('[data-event="finish"]').scroll_into_view_if_needed()
            with page.expect_response(lambda response: response.url.endswith("/events") and response.request.method == "POST") as finish_info:
                page.locator('[data-event="finish"]').click()
            assert finish_info.value.status == 202
            finish_event = finish_info.value.request.post_data_json
            assert finish_event["type"] == "finish" and finish_event["actor_type"] == "ai" and finish_event["actor"] == d.ACTOR
            after = store.get(sid)
            after_value = after.model_dump(mode="json")
            archived_version = before.report_version + 1
            assert after.report_version == archived_version
            assert all(after_value[key] == before_value[key] for key in protected if key != "report_version")
            assert len(after_value["messages"]) == len(before_value["messages"]) + 3
            assert after_value["messages"][-1]["type"] == "finish" and after_value["messages"][-1]["actor_type"] == "ai"
            expect(page.locator("#progress")).to_contain_text(f"报告 v{archived_version}")
            record["AI归档事件"] = {"事件": finish_event, "HTTP": finish_info.value.status,
                                  "原报告版本": before.report_version, "新报告版本": archived_version}
            d.save(stage / "AI归档事件.json", record["AI归档事件"])
            saved_reports = report_bodies(destination, sid)
            assert all(saved_reports[version] == body for version, body in history.items())
            assert set(saved_reports) == set(history) | {str(archived_version)}
            assert json.loads(saved_reports[str(archived_version)])["rechecks"] == after_value["rechecks"]
            d.save(stage / "会话快照.json", after_value)
            page.locator("#exports").scroll_into_view_if_needed()
            with page.expect_download() as download_info:
                page.locator("#exports a").filter(has_text="完整 ZIP").click()
            zip_path = stage / "界面下载-产品报告包.zip"
            download_info.value.save_as(zip_path)
            with zipfile.ZipFile(zip_path) as archive:
                assert archive.testzip() is None
                report = json.loads(archive.read("report.json"))
                assert report["review_id"] == sid and report["report_version"] == archived_version
                assert report["rechecks"] == after_value["rechecks"]
                event_ids = {item["事件"]["event_id"] for item in events} | {finish_event["event_id"]}
                exported_events = [m for m in report["history"]["messages"] if m.get("event_id") in event_ids]
                assert len(exported_events) == 3 and all(m["actor_type"] == "ai" for m in exported_events)
                assert {c["call_id"] for c in report["model_calls"]}.issubset({c["call_id"] for c in before_value["model_calls"]})
                record["ZIP"] = {"SHA256": d.sha(zip_path.read_bytes()), "成员数": len(archive.namelist()),
                    "报告版本": report["report_version"], "导出对象": "确认后通过原生 finish 生成的新报告版本",
                    "两条确认与当前快照一致": True, "AI事件均保留": True, "AI事件": exported_events,
                    "原模型调用保持": True, "复审": report["rechecks"]}
            page.screenshot(path=stage / "04-当前会话导出.png")
            record["历史读回"] = []
            for version in dict.fromkeys((6, before.report_version, archived_version)):
                with page.expect_response(lambda response: response.url.endswith(f"/reports/{version}") and response.request.method == "GET") as info:
                    page.locator("#versions").select_option(str(version))
                assert info.value.status == 200
                historical = info.value.json()
                saved = json.loads(saved_reports[str(version)])
                assert historical["rechecks"] == saved["rechecks"] and historical["model_calls"] == saved["model_calls"]
                if version == archived_version:
                    assert historical["rechecks"] == after_value["rechecks"]
                    assert all(r["human_confirmation"] == "confirmed" and r["reviewer"] == d.ACTOR for r in historical["rechecks"])
                expect(page.locator("#progress")).to_contain_text("历史只读")
                expect(page.locator("#progress")).to_contain_text(f"报告 v{version}")
                assert not page.locator("#reply").is_visible()
                buttons = page.locator("[data-recheck-form] button")
                assert all(buttons.nth(index).is_disabled() for index in range(buttons.count()))
                page.locator("#progress").scroll_into_view_if_needed()
                page.screenshot(path=stage / f"05-v{version}-历史只读.png")
                record["历史读回"].append({"报告版本": version, "HTTP": info.value.status,
                    "报告正文SHA256": d.sha(saved_reports[str(version)].encode("utf-8")), "复审与保存历史一致": True,
                    "模型调用与原历史一致": True, "历史反馈隐藏": True, "复审按钮禁用": True,
                    "页面状态": page.locator("#progress").inner_text()})
            record["历史版本口径"] = "两条 AI 确认后通过原生 finish 生成新报告；新历史版本与 ZIP 均保留确认状态，旧历史报告原字节保持。"
            assert not errors and not [item for item in network if item["HTTP"] >= 400]
        assert database_content(origin) == source_database
        assert file_hashes(source_stage) == source_files
        final_report_hashes = d.report_hashes(store)
        assert all(final_report_hashes.get(version) == digest for version, digest in hashes_before.items())
        assert set(final_report_hashes) == set(hashes_before) | {str(archived_version)}
        assert not model_attempts
        d.save(stage / "旧报告保全.json", {"原四表内容SHA256": source_database, "原会话四表逻辑内容保持": True,
            "旧报告原字节SHA256": hashes_before, "旧报告全部保持": True, "原会话旧报告保持": True,
            "原阶段文件SHA256": source_files, "原阶段文件保持": True, "模型结论和证据保持": True,
            "检查与动作保持": True, "新增模型调用": 0, "新增确认后报告版本": archived_version,
            "新增报告SHA256": final_report_hashes[str(archived_version)]})
        record.update({"结束": d.utc(), "状态": "确认归档完成", "新增模型调用": 0,
                       "报告版本": archived_version, "报告完整度": before.report_completeness})
        d.save(stage / "运行结果.json", record)
        d.save(stage / "文件校验.json", file_hashes(stage))
        print(json.dumps({"阶段": args.name, "AI确认事件": len(events), "新增模型调用": 0,
            "ZIP成员": record["ZIP"]["成员数"], "历史版本": [item["报告版本"] for item in record["历史读回"]],
            "原四表与旧报告保持": True, "报告完整度": before.report_completeness}, ensure_ascii=False))
    except Exception as error:
        record.update({"结束": d.utc(), "状态": "归档过程未完成", "错误": str(error), "模型入口尝试": model_attempts,
                       "原四表保持": database_content(origin) == source_database,
                       "原阶段文件保持": file_hashes(source_stage) == source_files})
        d.save(stage / "执行异常.json", record)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--expected", choices=("persists", "resolved"), required=True)
    confirm(parser.parse_args())
