"""从已确认的 H05 v6 报告分支运行原生 A/B 版本复审，保存全部真实调用。"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

if os.environ.get("D_FINAL_ENGINE_ROOT"):
    sys.path.insert(0, os.environ["D_FINAL_ENGINE_ROOT"])
    import engine  # 先固定包搜索路径；后续同名导入保持此冻结版本。

from d_native_recheck import (
    REPO, WORK, MATERIALS, ACTOR, CodexBridge, SessionStore, SessionService,
    MethodRegistry, AdapterHub, BrowserAdapter, EventInput, SourceInput,
    clone_state, sample_server, report_hashes, export, save, sha, summary, utc,
)

ROOT = REPO / "docs/D-最终验收证据/H05完整复审"
BASE = WORK / "d_1104_native_recheck/06-修后原答回放"
SID = "session-8e92a333d79d4678bac0b330efcd3e94"


async def run(args):
    stage = ROOT / args.name
    state = WORK / "d_final_h05" / args.name
    if stage.exists() or state.exists():
        raise SystemExit("本轮名称已使用，请换新名称以保留原始证据。")
    stage.mkdir(parents=True)
    save(stage / "复制校验.json", clone_state(BASE, state))
    original = SessionStore(BASE)
    store = SessionStore(state)
    session = store.get(SID)
    assert session.report_version == 6
    before = report_hashes(original)
    assert report_hashes(store) == before
    old = next(s for s in session.sources if s.active and s.input.kind == "website")
    port = urlsplit(old.input.reference).port
    bridge = CodexBridge(stage, args.model)
    service = SessionService(store, model_factory=lambda _: bridge,
        registry=MethodRegistry(REPO / "方法专家开发交付-v0.2"),
        adapters=AdapterHub(browser=BrowserAdapter(allow_local=True)))
    # 两分支相同预算；保留原任务、判据范围、旧报告、来源 ID 与 URL。
    prior_limits = session.request.limits.model_dump()
    session.request.limits.max_model_calls = 100
    session.request.limits.max_seconds = 5400
    session.request.limits.max_checks = 500
    session.request.limits.max_actions = 16
    store.save(session)
    code_files = ["engine/session_service.py", "engine/session_verification.py", "engine/session_contracts.py"]
    hashes = {}
    for filename in code_files:
        actual = Path(inspect.getfile(SessionService)).parent / Path(filename).name
        content = actual.read_bytes()
        hashes[filename] = sha(content)
        frozen = stage / "冻结代码" / Path(filename).name
        frozen.parent.mkdir(exist_ok=True)
        frozen.write_bytes(content)
    events = []
    source_manifest = Path(inspect.getfile(SessionService)).parent.parent / "源码来源.json"
    source_revision = json.loads(source_manifest.read_text(encoding="utf-8")) if source_manifest.exists() else {}
    with sample_server(port=port, variant=args.variant) as url:
        assert old.input.reference == url + "/v1/"
        replacement = old.input.model_copy(update={"version": "本轮复审稿件", "declared_by": ACTOR})
        event = EventInput(event_id=f"d-final-{args.name}", expected_context_version=session.context_version,
            actor=ACTOR, actor_type="ai", type="recheck", payload={"updates": [
                {"source_id": old.source_id, "input": replacement.model_dump(mode="json")}]})
        session, should_run = service.apply_event(SID, event)
        assert should_run
        events.append(event.model_dump(mode="json"))
        save(stage / "运行环境.json", {"开始": utc(), "性质": "H05 v6 报告的完整原生版本复审",
            "AI来源": "ai", "真实模型": True, "固定响应": False, "答案注入": False,
            "模型": args.model, "基线": str(BASE), "基线报告版本": 6,
            "变体": args.variant, "本机服务": url, "会话目录": str(state),
            "材料SHA256": sha((MATERIALS / args.variant / "打开界面.html").read_bytes()),
            "原预算": prior_limits, "本轮预算": session.request.limits.model_dump(),
            "代码SHA256": hashes, "实际引擎目录": str(Path(inspect.getfile(SessionService)).parent),
            "冻结源码来源": source_revision,
            "git": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
            "控制变量": "相同 v6 初审、URL、来源 ID、任务、规则范围、预算；仅网页内容为对应变体。"})
        save(stage / "启动快照.json", session.model_dump(mode="json"))
        print("START", args.name, session.run_id, flush=True)
        try:
            session = await service.run(SID)
            for round_no in range(4):
                pending = [a for a in session.actions if a.status == "pending"]
                allowed = [a for a in pending if a.kind == "click"
                    and next(s for s in session.sources if s.source_id == a.source_id).input.reference == url + "/v1/"
                    and any(label in (a.observed_target or a.target_label)
                        for label in ["提交登记", "核对信息", "返回选择", "重新开始", "服务台"])]
                if not allowed:
                    break
                folder = stage / f"授权前-{round_no+1}"
                folder.mkdir()
                export(folder, session, store, service.registry)
                for action in allowed:
                    session = store.get(SID)
                    event = EventInput(event_id=f"d-final-{args.name}-{action.action_id}",
                        expected_context_version=session.context_version, actor=ACTOR, actor_type="ai",
                        type="authorize_action", payload={"action_id": action.action_id, "approved": True,
                            "reason": "本机演示页面的 AI 操作测试，登记只影响本页内存。"})
                    session, _ = service.apply_event(SID, event)
                    events.append(event.model_dump(mode="json"))
                session = await service.run(SID)
        finally:
            session = store.get(SID)
            export(stage, session, store, service.registry)
            save(stage / "事件.json", events)
            save(stage / "运行结果.json", summary(session) | {"结束": utc(), "本轮真实CLI调用": bridge.calls})
            after = report_hashes(store)
            assert all(after.get(k) == v for k, v in before.items())
            assert report_hashes(original) == before
            save(stage / "旧报告保全.json", {"旧报告原字节SHA256": before, "旧报告全部保持": True,
                "原会话旧报告保持": True})
            await service.close()
        print(json.dumps({"阶段": args.name, "状态": session.status, "完整度": session.report_completeness,
            "CLI调用": bridge.calls, "复审": [r.model_dump() for r in session.rechecks]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--variant", choices=["A", "B"], required=True)
    parser.add_argument("--model", default="gpt-6-astra")
    asyncio.run(run(parser.parse_args()))
