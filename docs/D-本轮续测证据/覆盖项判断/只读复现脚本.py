"""只读验证规划覆盖项继承旧判断；所有会话均为内存对象，不启动模型。"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "design-research-skill"
for directory in (ROOT / "work/d_nov_review_deps", ROOT / "work/d_nov_mcp", REPO):
    sys.path.insert(0, str(directory))

from engine.session_contracts import CheckItem, PlannedCheck
from engine.session_service import SessionService

OUT = ROOT / "work/d_coverage_clone_probe"
OUT.mkdir(exist_ok=True)
ARCHIVE = REPO / "docs/D-本轮续测证据/原生复审/03-A初审"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def make_check(status="executed", coverage="原选择页"):
    return CheckItem(
        check_id=SessionService._check_id("R02", coverage), ref="R02",
        coverage_id=coverage, coverage_title="原选择页步骤提示", task_id="TASK1",
        kind="rule", run_id="离线复现", context_version=1,
        criteria_version="0.2-method-draft", execution_status=status,
        decision="no_visible_issue" if status == "executed" else None,
        reason="仅确认选择页第1步提示。" if status == "executed" else "",
        evidence_ids=["原选择页证据"] if status == "executed" else [],
        applicability="applicable", source_ids=["本地样本"],
    )


def make_plan(coverage="新核对页", task="TASK2"):
    return PlannedCheck(
        ref="R02", coverage_id=coverage, coverage_title="核对页步骤提示",
        task_id=task, applicability="needs_context", reason="等待核对页的独立判断。",
        source_ids=["本地样本"], evidence_ids=["新核对页证据"],
        object_refs=["核对页步骤提示"], evidence_needed=["新核对页实际判断"],
        required_evidence_kinds=["observation"],
    )


def make_session(checks, budget=10):
    return SimpleNamespace(
        run_id="离线复现", checks=checks, material_understanding=None,
        model_calls=[], request=SimpleNamespace(limits=SimpleNamespace(max_checks=budget)),
    )


class Captured(Exception):
    pass


async def selected_judge_ids(service, session):
    captured = []

    async def capture(*args, **kwargs):
        assert args[3] == "judge"
        captured.extend(item["check_id"] for item in args[4]["checks"])
        raise Captured()

    service._call = capture
    try:
        await service._judge(session, None)
    except Captured:
        pass
    return captured


def minimal_proof():
    service = object.__new__(SessionService)
    service.registry = SimpleNamespace(refs={"R02"}, spec=lambda ref: {"ref": ref})
    service.store = SimpleNamespace(save=lambda session: None)
    cases = []
    for status in ("executed", "planned"):
        old = make_check(status)
        session = make_session([old])
        before = old.model_dump()
        service._apply_check_plan(session, [make_plan()], [old])
        new = session.checks[-1]
        copied = new.model_dump()
        selected = asyncio.run(selected_judge_ids(service, session))
        if status == "executed":
            assert copied["execution_status"] == "executed"
            assert copied["decision"] == before["decision"]
            assert copied["reason"] == before["reason"]
            assert copied["evidence_ids"] == before["evidence_ids"]
            assert new.check_id not in selected
        else:
            assert copied["execution_status"] == "planned" and copied["decision"] is None
            assert new.check_id in selected
        cases.append({"模板状态": status, "新增覆盖项": copied, "实际judge输入ID": selected})

    old = make_check()
    session = make_session([old], budget=2)
    service._apply_check_plan(session, [make_plan()], [old])
    sentinel = make_check("planned", "另一个真正待执行覆盖")
    session.checks.append(sentinel)
    selected = asyncio.run(selected_judge_ids(service, session))
    assert selected == [] and sentinel.execution_status == "not_executed"
    budget_case = {"配置预算": 2, "实际judge历史数": 0,
                   "说明": "内存设置一条已执行模板，相当于已有一次判断；新覆盖复制执行状态后，第二个额度被占用。",
                   "judge输入": selected, "真正待执行项最终状态": sentinel.model_dump()}

    old = make_check()
    session = make_session([old])
    service._apply_check_plan(session, [make_plan()], [old])
    new = session.checks[-1]
    # 只在内存副本验证最小重置策略；没有替换或写回生产函数。
    new.execution_status = "planned"
    new.decision = None
    new.reason = ""
    new.evidence_ids = []
    new.reevaluation_requested = False
    selected = asyncio.run(selected_judge_ids(service, session))
    assert selected == [new.check_id]

    old = make_check()
    session = make_session([old])
    service._apply_check_plan(session, [make_plan(old.coverage_id)], [old])
    assert old.task_id == "TASK2" and old.decision == "no_visible_issue"
    changed_existing = old.model_dump()
    return {"新增覆盖两种模板对照": cases, "预算占用复现": budget_case,
            "内存重置后judge输入": selected,
            "已有coverage被改任务但判断保留": changed_existing,
            "断言结果": "全部通过，确认缺陷存在；这不是修复后产品测试"}


def archive_lineage():
    snapshot = read_json(ARCHIVE / "会话快照.json")
    current = [c for c in snapshot["checks"] if c["run_id"] == snapshot["run_id"]
               and not c["stale"] and c["scope_status"] == "included"]
    judge_ids = set()
    judged = []
    plan_entries = []
    for folder in sorted((ARCHIVE / "调用").iterdir()):
        if not folder.is_dir() or not (folder / "模型原答.txt").exists():
            continue
        operation = folder.name.split("-", 1)[-1]
        response = read_json(folder / "模型原答.txt")
        if operation == "judge":
            raw = (folder / "原始输入.txt").read_text(encoding="utf-8-sig")
            request, _ = json.JSONDecoder().raw_decode(raw.split("[user]\n", 1)[1])
            payload = request.get("payload", request)
            # 原生产请求顶层直接携带 checks。
            specs = {c["check_id"]: c for c in payload["checks"]}
            judge_ids.update(specs)
            for answer in response["judgments"]:
                judged.append({"调用": folder.name, "原输入": specs.get(answer["check_id"]), "原判断": answer})
        elif operation == "plan_checks":
            for item in response["items"]:
                plan_entries.append({"调用": folder.name, "计划": item,
                                     "check_id": SessionService._check_id(item["ref"], item["coverage_id"])})

    missing = [c for c in current if c["execution_status"] == "executed" and c["check_id"] not in judge_ids]
    lineage = []
    for check in missing:
        matches = []
        for item in judged:
            answer = item["原判断"]
            spec = item["原输入"]
            if spec is None or spec["ref"] != check["ref"]:
                continue
            if answer["decision"] == check["decision"] and answer["reason"] == check["reason"] and answer["evidence_ids"] == check["evidence_ids"]:
                matches.append(item)
        stored_matches = [c for c in current if c["check_id"] in judge_ids and c["ref"] == check["ref"]
                          and all(c[k] == check[k] for k in ("execution_status", "decision", "reason", "evidence_ids"))]
        lineage.append({"最终检查": check, "同编号原judge完全相同判断": matches,
                        "同编号已judge项最终结果完全相同": stored_matches,
                        "建立此coverage的规划": [p for p in plan_entries if p["check_id"] == check["check_id"]]})
    result = {"当前included非stale": len(current), "当前executed": sum(c["execution_status"] == "executed" for c in current),
              "judge输入唯一ID": len(judge_ids), "executed未进judge": len(missing),
              "能与同ref原判断逐字匹配数": sum(bool(x["同编号原judge完全相同判断"]) for x in lineage),
              "能与同ref已judge项最终结果逐字匹配数": sum(bool(x["同编号已judge项最终结果完全相同"]) for x in lineage),
              "按ref统计": dict(Counter(c["ref"] for c in missing)), "逐项追溯": lineage}
    return result


def main():
    code = REPO / "engine/session_service.py"
    result = {"执行者": "Codex（AI，只读离线验证）", "使用实际生产方法": True,
              "模型调用": 0, "未连接数据库": True,
              "生产代码SHA256": hashlib.sha256(code.read_bytes()).hexdigest(),
              "最小复现": minimal_proof(), "已归档03追溯": archive_lineage()}
    destination = OUT / "只读复现结果.json"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"文件": str(destination), "断言": result["最小复现"]["断言结果"],
                      "统计": {k: v for k, v in result["已归档03追溯"].items() if k != "逐项追溯"}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
