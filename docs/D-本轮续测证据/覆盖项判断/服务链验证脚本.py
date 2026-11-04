"""固定响应驱动真实服务、存储与导出；验证程序回归，不衡量模型效果。"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import zipfile
from pathlib import Path

REPO = next(path for path in Path(__file__).resolve().parents if (path / "engine/session_service.py").is_file())
for path in (REPO.parent / "work/d_nov_review_deps", REPO.parent / "work/d_nov_mcp", REPO):
    sys.path.insert(0, str(path))

from engine.methods import MethodRegistry
from engine.model import ModelCallResult
from engine.session_adapters import Capture
from engine.session_contracts import Limits, ReviewTask, SessionCreate, SourceInput
from engine.session_report import write_report_package, zip_report_package
from engine.session_service import SessionService
from engine.session_store import SessionStore


class FixedCoverageModel:
    """只按已提交的覆盖编号返回预先规定结果，不访问网络。"""
    is_stub = True
    supports_images = False

    def __init__(self):
        self.calls = []

    async def complete(self, messages, **kwargs):
        data = json.loads(messages[1]["content"][0]["text"])
        evidence = {item["state_id"]: item for item in data["context"]["evidence"] if item["state_id"]}
        if data["operation"] == "plan_checks":
            items = []
            for state, coverage, title, applicability in (
                ("fixture-select", "coverage-select", "选择页步骤提示", "applicable"),
                ("fixture-confirm", "coverage-confirm", "核对页步骤提示", "needs_context"),
            ):
                if state not in evidence:
                    continue
                item = evidence[state]
                items.append({
                    "ref": "R02", "coverage_id": coverage, "coverage_title": title,
                    "task_id": "TASK-FIXTURE", "applicability": applicability,
                    "reason": "固定响应回归：各页面作为独立覆盖单元。",
                    "source_ids": [item["source_id"]], "evidence_ids": [item["evidence_id"]],
                    "object_refs": [title], "required_evidence_kinds": ["design"],
                    "evidence_needed": ["核对页完整步骤提示"] if applicability == "needs_context" else [],
                })
            answer = {"items": items}
        elif data["operation"] == "judge":
            judgments = []
            for check in data["checks"]:
                old = check["coverage_id"] == "coverage-select"
                item = evidence["fixture-select" if old else "fixture-confirm"]
                judgments.append({
                    "check_id": check["check_id"],
                    "decision": "no_visible_issue" if old else "insufficient_evidence",
                    "reason": "固定响应：选择页第1步提示齐全。" if old else "固定响应：核对页步骤文本不完整，需独立补证。",
                    "evidence_ids": [item["evidence_id"]],
                })
            answer = {"judgments": judgments, "findings": [], "questions": []}
        else:
            raise AssertionError(f"本回归不应进入其他操作：{data['operation']}")
        self.calls.append({"原始消息": messages, "原始结果": answer})
        return ModelCallResult(text=json.dumps(answer, ensure_ascii=False),
                               provider="test-fixture", model="coverage-independent-fixture",
                               usage={}, request_id=None, latency_ms=0, json_mode_used=True)


async def run(out):
    out.mkdir(parents=True, exist_ok=False)
    code_path = REPO / "engine/session_service.py"
    code_bytes = code_path.read_bytes()
    model = FixedCoverageModel()
    store = SessionStore(out / "独立测试存储")
    service = SessionService(store, registry=MethodRegistry(REPO / "方法专家开发交付-v0.2"),
                             model_factory=lambda request: model)
    session = service.create(SessionCreate(
        purpose="固定响应程序回归：先判选择页，再追加核对页，验证独立判断与导出。",
        actor="Codex离线回归脚本", actor_type="ai", auto_run=False,
        sources=[SourceInput(kind="document", title="离线回归设计夹具", role="design",
                             content="两个页面的步骤提示测试数据。", version="fixture-v1")],
        limits=Limits(max_checks=2, max_model_calls=6, max_images_per_call=0),
    ))
    # 该夹具只验证 R02 两个覆盖的生命周期，保留真实规划、判断、存储及导出实现。
    session.checks = [check for check in session.checks if check.ref == "R02"]
    source = session.sources[0]
    ids = service._capture(session, source, Capture(content="选择页：第1步，共2步。",
                           locator={"is_test_fixture": True}, state_id="fixture-select"))
    session.review_tasks = [ReviewTask(task_id="TASK-FIXTURE", text="对照两个页面的步骤提示",
                           success_criteria="各覆盖独立判断", source_ids=[source.source_id], evidence_ids=ids)]
    store.save(session)
    await service._plan_checks(session, model)
    await service._judge(session, model)
    assert len(session.checks) == 1 and session.checks[0].decision == "no_visible_issue"
    old_snapshot = session.checks[0].model_dump()
    (out / "01-旧覆盖判断后.json").write_text(json.dumps(old_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    service._capture(session, source, Capture(content="核对页：步骤提示文本未完整提供。",
                     locator={"is_test_fixture": True}, state_id="fixture-confirm"))
    await service._plan_checks(session, model)
    assert len(session.checks) == 2
    old, new = session.checks
    assert old.model_dump() == old_snapshot
    assert new.execution_status == "planned" and new.decision is None
    assert new.reason == "" and new.evidence_ids == []
    (out / "02-追加新覆盖待判断.json").write_text(json.dumps([c.model_dump() for c in session.checks], ensure_ascii=False, indent=2), encoding="utf-8")
    await service._judge(session, model)
    assert old.model_dump() == old_snapshot
    assert new.execution_status == "executed" and new.decision == "insufficient_evidence"
    assert new.evidence_ids != old.evidence_ids and new.reason != old.reason

    finished = service._finish(session)
    stored = store.get(finished.session_id)
    assert stored.model_dump() == finished.model_dump()
    calls = [call for call in stored.model_calls if call["operation"] == "judge"]
    assert [call["input"]["check_ids"] for call in calls] == [[old.check_id], [new.check_id]]
    assert all(call["is_stub"] and call["status"] == "validated" for call in stored.model_calls)
    package = out / "产品导出"
    write_report_package(stored, store, package, registry=service.registry)
    zipped = zip_report_package(package, out / "产品报告包.zip")
    with zipfile.ZipFile(zipped) as archive:
        checks = json.loads(archive.read("checks.json"))
        report = archive.read("report-details.md").decode("utf-8")
        assert {item["check_id"]: item["decision"] for item in checks} == {
            old.check_id: "no_visible_issue", new.check_id: "insufficient_evidence",
        }
        assert old.reason in report and new.reason in report
        archive_items = len(archive.namelist())
    assert code_path.read_bytes() == code_bytes
    (out / "实际服务会话快照.json").write_text(stored.model_dump_json(indent=2), encoding="utf-8")
    (out / "固定响应输入与输出.json").write_text(json.dumps(model.calls, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "执行者": "Codex（AI程序回归）", "实现": "实际生产SessionService、SessionStore与报告导出",
        "真实模型调用": 0, "固定响应调用数": len(stored.model_calls),
        "固定响应操作顺序": [call["operation"] for call in stored.model_calls],
        "judge实际输入": [call["input"]["check_ids"] for call in calls],
        "旧覆盖": {"check_id": old.check_id, "decision": old.decision, "evidence_ids": old.evidence_ids},
        "新覆盖": {"check_id": new.check_id, "decision": new.decision, "evidence_ids": new.evidence_ids},
        "导出ZIP文件数": archive_items, "断言": "全部通过",
        "生产实现SHA256": hashlib.sha256(code_bytes).hexdigest(),
        "说明": "固定响应验证程序生命周期；不计作真实模型质量或真人体验结果。",
    }
    (out / "服务链验收结果.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.output.resolve()))
