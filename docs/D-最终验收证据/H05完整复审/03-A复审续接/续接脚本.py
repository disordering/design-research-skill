"""模型调用中断后，用已采集的原生观察续做 T10；不补造前段检查成绩。"""
from __future__ import annotations
import argparse
import asyncio
import inspect
import json
import os
from pathlib import Path
import sqlite3
import sys

if os.environ.get("D_FINAL_ENGINE_ROOT"):
    sys.path.insert(0, os.environ["D_FINAL_ENGINE_ROOT"])
    import engine

from d_native_recheck import (
    REPO, WORK, ACTOR, CodexBridge, SessionStore, SessionService, MethodRegistry,
    clone_state, report_hashes, export, save, sha, summary, utc,
)

ROOT = REPO / "docs/D-最终验收证据/H05完整复审"
SID = "session-8e92a333d79d4678bac0b330efcd3e94"


def database_content(path):
    with sqlite3.connect(path / "sessions.sqlite3") as db:
        return {table: sha(json.dumps(db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall(),
            ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            for table in ("sessions", "events", "reports", "artifacts")}


async def run(args):
    origin = WORK / "d_final_h05" / args.base
    destination = WORK / "d_final_h05" / args.name
    stage = ROOT / args.name
    if stage.exists() or destination.exists():
        raise SystemExit("续接名称已存在，原始证据不覆盖。")
    before_database = database_content(origin)
    stage.mkdir(parents=True)
    save(stage / "复制校验.json", clone_state(origin, destination))
    store = SessionStore(destination)
    session = store.get(SID)
    before_reports = report_hashes(store)
    before_checks = [check.model_dump(mode="json") for check in session.checks]
    before_actions = [action.model_dump(mode="json") for action in session.actions]
    bridge = CodexBridge(stage, args.model)
    service = SessionService(store, model_factory=lambda _: bridge,
        registry=MethodRegistry(REPO / "方法专家开发交付-v0.2"))
    code_root = Path(inspect.getfile(SessionService)).parent
    environment = json.loads((ROOT / args.base / "运行环境.json").read_text(encoding="utf-8"))
    for name, expected in environment["代码SHA256"].items():
        actual = (code_root / Path(name).name).read_bytes()
        assert sha(actual) == expected, name
        (stage / Path(name).name).write_bytes(actual)
    save(stage / "启动快照.json", session.model_dump(mode="json"))
    (stage / "续接脚本.py").write_bytes(Path(__file__).read_bytes())
    save(stage / "运行环境.json", environment | {
        "开始": utc(), "运行性质": "原生已取证会话的 T10 单步恢复；不是新独立试验或整份报告全覆盖",
        "来源阶段": args.base, "模型": args.model, "固定响应": False,
        "恢复操作": "仅调用生产 _recheck 和 _finish；没有新浏览器操作，没有重写未执行检查",
        "会话目录": str(destination), "原表内容SHA256": before_database})
    session.messages.append({"at": utc(), "actor": ACTOR, "actor_type": "ai",
        "type": "d_recheck_phase_continued", "run_id": session.run_id,
        "content": {"来源": args.base, "原因": "前段模型调用中断，已有提交后观察可用于旧候选复审；本次只续做 T10。"}})
    store.save(session)
    try:
        await service._recheck(session, bridge)
        session = service._finish(session)
        assert [check.model_dump(mode="json") for check in session.checks] == before_checks
        assert [action.model_dump(mode="json") for action in session.actions] == before_actions
        export(stage, session, store, service.registry)
        after_reports = report_hashes(store)
        assert all(after_reports.get(version) == value for version, value in before_reports.items())
        assert database_content(origin) == before_database
        save(stage / "旧报告保全.json", {"旧报告原字节SHA256": before_reports,
            "旧报告全部保持": True, "原会话旧报告保持": True,
            "原会话四表逻辑内容保持": True, "原四表内容SHA256": before_database,
            "前段检查与动作保持": True})
        save(stage / "运行结果.json", summary(session) | {"结束": utc(), "新增真实CLI调用": bridge.calls})
        print(json.dumps({"阶段": args.name, "复审": [r.model_dump(mode="json") for r in session.rechecks],
            "整份报告完整度": session.report_completeness}, ensure_ascii=False), flush=True)
    finally:
        await service.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--model", default="gpt-6-astra")
    asyncio.run(run(parser.parse_args()))
