"""用真实 Codex CLI 驱动原生 SessionService，保存 H05 初审及复审证据。

产品适配器实际读取并操作本地网页。模型输入仅含任务卡和当前版本网页。
测试答案、A/B 差异和独立四路径实测不进入模型输入。
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


REPO = Path(__file__).resolve().parents[1]
WORK = REPO.parent / "work"
sys.path.insert(0, str(REPO))
# 本机已有的独立运行依赖；不更改仓库或用户的 Python 环境。
import site
for dependency in ("d_nov_review_deps", "d_nov_mcp"):
    if (WORK / dependency).exists():
        site.addsitedir(str(WORK / dependency))

from engine.errors import EngineError
from engine.model import ModelCallResult
from engine.methods import MethodRegistry
from engine.session_adapters import AdapterHub, BrowserAdapter
from engine.session_contracts import EventInput, SessionCreate, SourceInput
from engine.session_report import write_report_package, zip_report_package
from engine.session_service import SessionService
from engine.session_store import SessionStore


MATERIALS = REPO / "docs/D-本轮续测证据/H05复审材料"
EVIDENCE = REPO / "docs/D-本轮续测证据/原生复审"
ACTOR = "AI模型验收-D"


def utc():
    return datetime.now(timezone.utc).isoformat()


def save(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(data: bytes):
    return hashlib.sha256(data).hexdigest()


class CodexBridge:
    """仅将原生模型消息交给已登录 CLI；没有预设判断或替换模型回答。"""
    supports_images = True
    is_stub = False

    def __init__(self, trace: Path, model: str):
        self.trace, self.model, self.calls = trace, model, 0
        self.cli = shutil.which("codex.exe") or shutil.which("codex")
        if not self.cli:
            raise RuntimeError("找不到已登录的 Codex CLI。")

    async def complete(self, messages, **kwargs):
        self.calls += 1
        return await asyncio.to_thread(self._complete, self.calls, messages)

    def _complete(self, idx, messages):
        tic = time.monotonic()
        request = json.loads(messages[1]["content"][0]["text"])
        operation = request["operation"]
        call_dir = self.trace / "调用" / f"{idx:03d}-{operation}"
        call_dir.mkdir(parents=True, exist_ok=False)
        texts = ["你替一个 JSON 接口作答。按下面原始消息返回一个合法 JSON 对象，不加代码块。只处理给定文字和附图，不调用工具。理由简洁并保留所需编号。"]
        image_records = []
        with tempfile.TemporaryDirectory(prefix="d-native-model-") as temporary:
            cmd = [self.cli, "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
                   "--sandbox", "read-only", "--cd", temporary, "--model", self.model,
                   "-c", "model_reasoning_effort=low", "--json"]
            for message in messages:
                texts.append("[" + message["role"] + "]")
                content = message["content"]
                if isinstance(content, str):
                    texts.append(content)
                    continue
                for part in content:
                    if part["type"] == "text":
                        texts.append(part["text"])
                    elif part["type"] == "image_url":
                        header, data = part["image_url"]["url"].split(",", 1)
                        raw = base64.b64decode(data, validate=True)
                        suffix = ".png" if "png" in header else ".jpeg"
                        image = self.trace / "输入图片" / (sha(raw) + suffix)
                        image.parent.mkdir(parents=True, exist_ok=True)
                        if not image.exists():
                            image.write_bytes(raw)
                        image_records.append({"次序": len(image_records) + 1, "SHA256": sha(raw),
                                              "文件": str(image.relative_to(self.trace))})
                        texts.append(f"[随附图片 {len(image_records)}]")
                        cmd += ["--image", str(image)]
            prompt = "\n".join(texts)
            (call_dir / "原始输入.txt").write_text(prompt, encoding="utf-8")
            marker = {"开始": utc(), "操作": operation, "模型": self.model, "推理设置": "low",
                      "非固定响应": True, "输入SHA256": sha(prompt.encode()), "图片": image_records}
            save(call_dir / "调用记录.json", marker)
            print(f"{utc()} {idx:03d} {operation} 开始 {len(prompt)}字/{len(image_records)}图", flush=True)
            try:
                proc = subprocess.run(cmd + ["-"], cwd=temporary, input=prompt.encode(),
                                      capture_output=True, timeout=180,
                                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except subprocess.TimeoutExpired as error:
                for filename, partial in (("CLI原始事件.jsonl", error.stdout), ("CLI诊断.txt", error.stderr)):
                    data = partial.encode("utf-8") if isinstance(partial, str) else (partial or b"")
                    (call_dir / filename).write_bytes(data)
                marker.update(结束=utc(), 状态="超时", 耗时毫秒=round(1000 * (time.monotonic() - tic)),
                              已保留部分事件=True)
                save(call_dir / "调用记录.json", marker)
                raise EngineError("codex_cli_timeout", "Codex 单次调用超过 180 秒。", status_code=504)
        (call_dir / "CLI原始事件.jsonl").write_bytes(proc.stdout)
        (call_dir / "CLI诊断.txt").write_bytes(proc.stderr)
        events = []
        for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
            if line.startswith("{"):
                with contextlib.suppress(json.JSONDecodeError):
                    events.append(json.loads(line))
        items = [event["item"] for event in events if event.get("type") == "item.completed"]
        response = next((item.get("text") for item in reversed(items) if item.get("type") == "agent_message"), None)
        completed = next((event for event in events if event.get("type") == "turn.completed"), None)
        if proc.returncode or not completed or not response:
            marker.update(结束=utc(), 状态="调用失败", 退出码=proc.returncode)
            save(call_dir / "调用记录.json", marker)
            raise EngineError("codex_cli_failed", "Codex CLI 没有返回完整响应，原始事件已保存。", status_code=502)
        if any(item["type"] not in ("reasoning", "agent_message") for item in items):
            marker.update(结束=utc(), 状态="额外工具调用")
            save(call_dir / "调用记录.json", marker)
            raise EngineError("unexpected_tool", "模型接口回合调用额外工具，停止本轮。", status_code=502)
        sid = next(event["thread_id"] for event in events if event.get("type") == "thread.started")
        elapsed = round(1000 * (time.monotonic() - tic))
        (call_dir / "模型原答.txt").write_text(response, encoding="utf-8")
        marker.update(结束=utc(), 状态="已返回", Codex会话=sid, 耗时毫秒=elapsed, 用量=completed.get("usage", {}))
        save(call_dir / "调用记录.json", marker)
        print(f"{utc()} {idx:03d} {operation} 返回 {elapsed}ms", flush=True)
        return ModelCallResult(text=response, provider="codex_cli", model=self.model,
                               usage=completed.get("usage", {}), request_id=sid,
                               latency_ms=elapsed, json_mode_used=False)


@contextlib.contextmanager
def sample_server(port=0, variant="A"):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            version = {"/v1/": variant, "/v2/": "B"}.get(self.path.split("?", 1)[0])
            if version is None:
                self.send_error(404)
                return
            raw = (MATERIALS / version / "打开界面.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join(3)


def export(stage, session, store, registry):
    package = store.root / f"报告-v{session.report_version}"
    write_report_package(session, store, package, registry=registry)
    zip_report_package(package, stage / "产品报告包.zip")
    save(stage / "会话快照.json", session.model_dump(mode="json"))


def clone_state(original: Path, target: Path):
    """复制已停止的初审，迁移绝对文件路径；两条分支各自保存，不写基线。"""
    shutil.copytree(original, target)
    old_root, new_root = original.resolve(), target.resolve()
    migrated = []
    with sqlite3.connect(target / "sessions.sqlite3") as db:
        for artifact_id, filename, digest in db.execute("SELECT id,path,sha256 FROM artifacts").fetchall():
            relative = Path(filename).resolve().relative_to(old_root)
            copied = new_root / relative
            if sha(copied.read_bytes()) != digest:
                raise RuntimeError("复制后的原始证据指纹不匹配。")
            db.execute("UPDATE artifacts SET path=? WHERE id=?", (str(copied), artifact_id))
            migrated.append({"证据文件": str(relative), "SHA256": digest})
    return migrated


def service_implementation(use_frozen, snapshot_path=None, expected_sha=None):
    if not use_frozen and snapshot_path is None:
        return SessionService, REPO / "engine/session_service.py"
    path = Path(snapshot_path) if snapshot_path else WORK / "d_1104_native_recheck/frozen_service.py"
    if not path.exists() and snapshot_path is None:
        path = EVIDENCE / "冻结引擎/session_service.py"
    expected = expected_sha or json.loads((EVIDENCE / "冻结引擎/冻结说明.json").read_text(encoding="utf-8"))["SHA256"]
    if sha(path.read_bytes()) != expected:
        raise RuntimeError("冻结 Service 指纹不匹配，停止复审。")
    name = "engine._d_native_frozen_service"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.SessionService, path


def report_hashes(store):
    with store.connection() as db:
        return {str(version): sha(body.encode("utf-8")) for version, body in db.execute("SELECT version,body FROM reports ORDER BY version")}


def summary(session):
    current_checks = [c for c in session.checks if c.run_id == session.run_id and not c.stale and c.scope_status == "included"]
    judge_calls = [c for c in session.model_calls if c.get("operation") == "judge" and c.get("run_id") == session.run_id]
    judged_ids = {cid for call in judge_calls for cid in call.get("input", {}).get("check_ids", [])}
    judgment_ids = {j["check_id"] for call in judge_calls if call.get("status") == "validated"
                    for j in call.get("output", {}).get("judgments", [])}
    current_ids = {c.check_id for c in current_checks}
    current_judged = judged_ids & current_ids
    inherited_ids = {c.check_id for c in current_checks if c.execution_status == "executed" and c.check_id not in judged_ids}
    return {"会话": session.session_id, "上下文版本": session.context_version, "报告版本": session.report_version,
            "状态": session.status, "完整度": session.report_completeness,
            "模型调用": len(session.model_calls), "已记录调用状态": dict(Counter(c.get("status") for c in session.model_calls)),
            "本轮已记录调用": sum(c.get("run_id") == session.run_id for c in session.model_calls),
            "本轮有效范围检查": {"总数": len(current_checks), "执行状态": dict(Counter(c.execution_status for c in current_checks))},
            "本轮judge实际输入": {"唯一检查数": len(judged_ids), "检查ID": sorted(judged_ids)},
            "本轮judge输入与当前范围交集": {"唯一检查数": len(current_judged), "检查ID": sorted(current_judged)},
            "当前executed但本轮未进judge": {"唯一检查数": len(inherited_ids), "检查ID": sorted(inherited_ids)},
            "本轮judge有效输出": {"唯一检查数": len(judgment_ids), "检查ID": sorted(judgment_ids)},
            "全部历史检查": {"总数": len(session.checks), "执行状态": dict(Counter(c.execution_status for c in session.checks))},
            "发现": [f.model_dump(mode="json") for f in session.findings],
            "复审": [r.model_dump(mode="json") for r in session.rechecks],
            "动作": [a.model_dump(mode="json") for a in session.actions],
            "问题": [q.model_dump(mode="json") for q in session.questions],
            "警告": session.warnings, "运行说明": session.run_limitations,
            "契约问题": session.contract_violations}


async def run(args):
    stage = EVIDENCE / args.name
    state_root = WORK / "d_1104_native_recheck" / args.name
    if stage.exists() or state_root.exists():
        raise SystemExit("本轮名称已存在。请使用新名称，原证据保留。")
    stage.mkdir(parents=True)
    os.chdir(REPO)
    origin = args.resume_from or args.base
    baseline_environment = None
    old_report_hashes = {}
    if origin:
        base_state = WORK / "d_1104_native_recheck" / origin
        baseline_environment = json.loads((EVIDENCE / origin / "运行环境.json").read_text(encoding="utf-8"))
        expected_verification = baseline_environment.get("校验模块SHA256")
        if args.base and expected_verification:
            actual_verification = sha((REPO / "engine/session_verification.py").read_bytes())
            if expected_verification != actual_verification:
                raise SystemExit("基线的校验模块与当前代码不同。请在对应代码版本中运行复审；修后续查请明确使用 --resume-from。")
        copied_artifacts = clone_state(base_state, state_root)
        save(stage / "基线证据复制校验.json", copied_artifacts)
    store = SessionStore(state_root)
    bridge = CodexBridge(stage, args.model)
    snapshot = (EVIDENCE / baseline_environment["Service快照"]) if args.base and baseline_environment.get("Service快照") else None
    service_class, service_code = service_implementation(bool(args.base) or args.frozen_service, snapshot,
        baseline_environment["引擎文件SHA256"]["engine/session_service.py"] if args.base else None)
    service_digest = sha(service_code.read_bytes())
    archived_service = EVIDENCE / "冻结引擎" / f"session_service-{service_digest[:16]}.py"
    archived_service.parent.mkdir(exist_ok=True)
    if not archived_service.exists():
        archived_service.write_bytes(service_code.read_bytes())
    assert sha(archived_service.read_bytes()) == service_digest
    verification_code = REPO / "engine/session_verification.py"
    verification_digest = sha(verification_code.read_bytes())
    archived_verification = EVIDENCE / "冻结引擎" / f"session_verification-{verification_digest[:16]}.py"
    if not archived_verification.exists():
        archived_verification.write_bytes(verification_code.read_bytes())
    assert sha(archived_verification.read_bytes()) == verification_digest
    service = service_class(store, model_factory=lambda _: bridge,
                            registry=MethodRegistry(REPO / "方法专家开发交付-v0.2"),
                            adapters=AdapterHub(browser=BrowserAdapter(allow_local=True)))
    task_text = (MATERIALS / "A/任务卡.txt").read_text(encoding="utf-8").split("\n", 1)[1].strip()
    events = []
    port = 0
    if origin:
        port = urlsplit(baseline_environment["本机服务"]).port
    if args.resume_from:
        assert sha((MATERIALS / args.variant / "打开界面.html").read_bytes()) == baseline_environment["样本文件SHA256"], "续查保持原样本字节，不替换方案。"
    # 两个分支顺序执行并复用基线URL，只替换网页字节，排除端口/URL改变对象身份的干扰。
    with sample_server(port=port, variant=args.variant) as base_url:
        def website(version, edition):
            return SourceInput(kind="website", reference=base_url + "/v1/",
                               title="修书咨询登记", role="design", version=edition,
                               evidence_kind="observation" if args.runtime else None,
                               declared_by=ACTOR)

        try:
            if not origin:
                purpose = ("本次检查本机演示原型的实际操作；登记只在当前页面生效。\n\n" if args.runtime else "") + task_text
                request = SessionCreate(purpose=purpose, actor=ACTOR, actor_type="ai", provider="generic",
                                        model_name=args.model, allow_interaction=True,
                                        sources=[website("A", "本轮稿件1"), SourceInput(kind="document",
                                            title="修书咨询登记任务要求", content=task_text, role="product_spec",
                                            version="冻结任务卡", declared_by=ACTOR)],
                                        limits={"max_model_calls": 60, "max_actions": 16, "max_checks": args.max_checks,
                                                "max_seconds": 1800, "max_review_rounds": 1,
                                                "max_images_per_call": 10})
                session = service.create(request)
                save(stage / "创建请求.json", request.model_dump(mode="json"))
            elif args.resume_from:
                baseline = json.loads((EVIDENCE / origin / "运行结果.json").read_text(encoding="utf-8"))
                session = store.get(baseline["会话"])
                old_run = session.run_id
                old_report_hashes = report_hashes(store)
                assert old_report_hashes == report_hashes(SessionStore(base_state))
                event = EventInput(event_id=f"d-native-{args.name}-resume", expected_context_version=session.context_version,
                                   actor=ACTOR, actor_type="ai", type="resume",
                                   payload={"reason": "额度恢复后，以当前修后服务继续检查已有原始观察；保持原材料与网址。优先使用会话已取得的观察完成逐项正式判断与报告；仅在关键证据缺失时提出新操作，已观察的路径不重复执行。"})
                session, should_run = service.apply_event(session.session_id, event)
                current = [c for c in session.checks if c.run_id == session.run_id]
                assert session.run_id != old_run and current
                assert all(c.execution_status == "planned" and c.decision is None and not c.evidence_ids for c in current)
                assert report_hashes(store) == old_report_hashes
                events.append({"事件": event.model_dump(mode="json"), "应运行": should_run})
                started = utc()
                save(stage / "续查启动.json", {"来源": origin, "性质": "修后既有会话续查，不是新独立试验", "旧run": old_run,
                    "新run": session.run_id, "新run初始检查": len(current), "新run全部planned且无沿用判断": True,
                    "使用当前修后Service": str(service_code), "ServiceSHA256": service_digest,
                    "旧报告原字节SHA256": old_report_hashes, "事件": event.model_dump(mode="json"),
                    "外部中断": {"开始UTC": baseline["结束"], "恢复UTC": started,
                        "间隔秒": round((datetime.fromisoformat(started) - datetime.fromisoformat(baseline["结束"])).total_seconds(), 3),
                        "性质": "额度等待及用户返回间隔，排除于模型耗时和操作耗时"}})
                save(stage / "续查初始快照.json", session.model_dump(mode="json"))
            else:
                baseline = json.loads((EVIDENCE / args.base / "运行结果.json").read_text(encoding="utf-8"))
                session = store.get(baseline["会话"])
                old = next(s for s in session.sources if s.input.kind == "website" and s.active)
                event = EventInput(event_id=f"d-native-{args.name}", expected_context_version=session.context_version,
                                   actor=ACTOR, actor_type="ai", type="recheck",
                                   payload={"updates": [{"source_id": old.source_id,
                                            "input": website(args.variant, "本轮稿件2").model_dump(mode="json")}]})
                session, should_run = service.apply_event(session.session_id, event)
                events.append({"事件": event.model_dump(mode="json"), "应运行": should_run})
                save(stage / "来源分支.json", {"基线": args.base, "基线报告": baseline["报告版本"],
                                               "基线快照SHA256": sha((EVIDENCE / args.base / "会话快照.json").read_bytes()),
                                               "模型未接收": ["本脚本版本代号", "版本差异与实测答案"],
                                               "对照控制": "复用初审URL和来源ID，只替换该URL返回的页面字节与声明材料版本；两分支顺序执行。"})
            save(stage / "运行环境.json", {"开始": utc(), "执行": "真实 Codex CLI + 原生 SessionService + BrowserAdapter",
                  "AI操作者": ACTOR, "AI来源": "ai", "固定响应": False, "固定答案注入": False,
                  "网页取证口径": "observation：本机原型实际操作" if args.runtime else "design：本机原型设计材料",
                  "样本文件SHA256": sha((MATERIALS / args.variant / "打开界面.html").read_bytes()),
                  "任务卡SHA256": sha((MATERIALS / "A/任务卡.txt").read_bytes()),
                  "git提交": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
                  "实际Service代码": str(service_code), "冻结Service": bool(args.base) or args.frozen_service,
                  "Service快照": archived_service.relative_to(EVIDENCE).as_posix(),
                  "校验模块SHA256": verification_digest,
                  "校验模块快照": archived_verification.relative_to(EVIDENCE).as_posix(),
                  "运行性质": "修后既有会话续查" if args.resume_from else "版本复审" if args.base else "独立初审",
                  "引擎文件SHA256": {p: sha((service_code if p == "engine/session_service.py" else REPO / p).read_bytes()) for p in ["engine/session_service.py", "engine/session_adapters.py", "engine/session_contracts.py"]},
                  "本机服务": base_url, "会话目录": str(state_root), "限额": session.request.limits.model_dump()})
            print("SESSION", session.session_id, "STAGE", args.name, flush=True)
            session = await service.run(session.session_id)
            session = store.get(session.session_id)
            # 保留同一个 BrowserAdapter：授权后仍使用原来已选中的网页状态。
            # 仅处理本脚本自建、无持久副作用的两份本机样本，不批准外部材料操作。
            for approval_round in range(4):
                pending = [a for a in session.actions if a.status == "pending"]
                allowed = []
                for action in pending:
                    source = next(s for s in session.sources if s.source_id == action.source_id)
                    label = action.observed_target or action.target_label
                    if (source.input.reference in {base_url + "/v1/", base_url + "/v2/"}
                        and action.kind == "click"
                        and any(name in label for name in ["提交登记", "核对信息", "返回选择", "重新开始", "服务台"])):
                        allowed.append(action)
                if not allowed:
                    break
                saved = stage / f"授权前-{approval_round + 1}"
                saved.mkdir()
                export(saved, session, store, service.registry)
                for action in allowed:
                    session = store.get(session.session_id)
                    event = EventInput(event_id=f"d-native-{args.name}-approve-{action.action_id}",
                                       expected_context_version=session.context_version,
                                       actor=ACTOR, actor_type="ai", type="authorize_action",
                                       payload={"action_id": action.action_id, "approved": True,
                                                "reason": "AI操作员按已授权的本机原型测试继续；此样本登记只在当前页面中生效。"})
                    session, should_run = service.apply_event(session.session_id, event)
                    events.append({"事件": event.model_dump(mode="json"), "应运行": should_run,
                                   "来源": "本脚本限定路由的本机样本", "当前浏览器": "同一进程、同一适配器"})
                    save(stage / "AI操作事件.json", events)
                    print("AI AUTHORIZE", action.kind, action.observed_target or action.target_label, flush=True)
                session = await service.run(session.session_id)
                session = store.get(session.session_id)
            export(stage, session, store, service.registry)
            if old_report_hashes:
                final_hashes = report_hashes(store)
                assert all(final_hashes.get(version) == digest for version, digest in old_report_hashes.items())
                assert report_hashes(SessionStore(base_state)) == old_report_hashes
                save(stage / "旧报告保全核对.json", {"复制前": old_report_hashes, "续查后旧版本": {version: final_hashes[version] for version in old_report_hashes}, "原会话未改": True})
            save(stage / "运行结果.json", summary(session) | {"结束": utc(), "本轮CLI调用": bridge.calls, "事件": events})
            print(json.dumps({"会话": session.session_id, "报告版本": session.report_version,
                              "状态": session.status, "完整度": session.report_completeness,
                              "模型调用": len(session.model_calls), "发现数": len(session.findings),
                              "复审数": len(session.rechecks), "警告": session.warnings}, ensure_ascii=False), flush=True)
        finally:
            await service.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="唯一证据目录名")
    parser.add_argument("--base", help="从既有初审目录复制状态后启动复审")
    parser.add_argument("--resume-from", help="复制既有会话后用当前修后服务发resume新run续查；保持原观察与旧报告")
    parser.add_argument("--variant", choices=["A", "B"], default="A")
    parser.add_argument("--runtime", action="store_true", help="显式声明网页证据为本机原型实际操作")
    parser.add_argument("--frozen-service", action="store_true", help="使用归档的原生Service；复审分支自动启用")
    parser.add_argument("--max-checks", type=int, default=80, help="新基线单轮检查预算；复审继承原基线预算")
    parser.add_argument("--model", default="gpt-6-astra")
    args = parser.parse_args()
    if args.resume_from and (args.base or args.frozen_service):
        parser.error("--resume-from 使用当前修后服务，不能与 --base 或 --frozen-service 同用。")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
