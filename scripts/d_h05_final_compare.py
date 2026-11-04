"""对照 H05 两条指定旧候选的原生复审；专项结论与报告完整度分别记录。"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "docs/D-最终验收证据/H05完整复审"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def field_value(evidence, label):
    """按页面字段读取值，避免把其他段落里出现的时段误当回执字段。"""
    lines = [line.strip() for line in evidence.get("content", "").splitlines() if line.strip()]
    values = [lines[index + 1] for index, line in enumerate(lines[:-1]) if line == label]
    return values[0] if len(values) == 1 else None


def captured_at(evidence):
    try:
        value = datetime.fromisoformat(evidence.get("captured_at", ""))
        return value if value.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def action_label(action):
    return (action.get("observed_target") or action.get("target_label", "")).split(" / ", 1)[0].strip()


def object_ids(evidence):
    return {obj["object_id"] for obj in evidence.get("objects", []) if obj.get("object_id")}


def receipt_chains(state, expected):
    """核对当前版本的实际动作链；同 context 的续接可复用已取得的取证。"""
    if expected not in {"persists", "resolved"}:
        raise ValueError("H05 专项只接受 persists 或 resolved。")
    context = state["context_version"]
    current = [e for e in state["evidence"] if not e["stale"]
               and e["context_version"] == context and e["kind"] == "observation"]
    executed = {a["action_id"]: (index, a) for index, a in enumerate(state["actions"])
                if a["status"] == "executed" and a["context_version"] == context}
    confirm = [e for e in current if "核对信息" in e["content"] and "提交登记" in e["content"]
               and field_value(e, "时段") == "14:00–14:30" and field_value(e, "服务台") == "二层服务台"]
    wanted_time, wanted_place = (("09:00–09:30", "一层服务台") if expected == "persists"
                                 else ("14:00–14:30", "二层服务台"))
    receipts = [e for e in current if "登记完成" in e["content"] and "本次登记信息如下" in e["content"]
                and field_value(e, "时段") == wanted_time and field_value(e, "服务台") == wanted_place]
    chains = []
    for receipt in receipts:
        submitted = executed.get(receipt.get("action_id"))
        if submitted is None:
            continue
        submit_index, submit = submitted
        if (submit["kind"] != "click" or action_label(submit) != "提交登记"
                or submit["source_id"] != receipt["source_id"]
                or receipt["evidence_id"] not in submit["evidence_ids"]):
            continue
        for before in confirm:
            confirmed = executed.get(before.get("action_id"))
            if confirmed is None:
                continue
            confirm_index, confirm_action = confirmed
            before_time, after_time = captured_at(before), captured_at(receipt)
            shared_objects = object_ids(before) & object_ids(receipt)
            if (confirm_action["kind"] != "click" or action_label(confirm_action) != "核对信息"
                    or before["source_id"] != receipt["source_id"]
                    or confirm_action["source_id"] != receipt["source_id"]
                    or before["evidence_id"] not in confirm_action["evidence_ids"]
                    or before["evidence_id"] not in submit["evidence_ids"]
                    or not before.get("state_id") or before["state_id"] != submit["expected_state_id"]
                    or confirm_index >= submit_index or not before_time or not after_time
                    or before_time >= after_time or not shared_objects):
                continue
            # 不能把较早的下午核对与后来另一条路径的提交拼成一条链。
            if any(confirm_index < index < submit_index
                   and action["source_id"] == receipt["source_id"]
                   and action["kind"] not in {"read", "wait", "scroll"}
                   for index, action in executed.values()):
                continue
            transitions = [t for t in state["transitions"]
                           if t["action_id"] == submit["action_id"]
                           and t["source_id"] == receipt["source_id"]
                           and t["verification_status"] == "observed"
                           and t["from_state"] == before["state_id"]
                           and t["to_state"] == receipt["state_id"]
                           and {before["evidence_id"], receipt["evidence_id"]}.issubset(t["evidence_ids"])]
            if transitions:
                chains.append({"source_id": receipt["source_id"], "object_ids": sorted(shared_objects),
                               "核对动作": confirm_action["action_id"], "核对证据": before["evidence_id"],
                               "核对取证时间": before["captured_at"], "提交动作": submit["action_id"],
                               "回执证据": receipt["evidence_id"], "回执取证时间": receipt["captured_at"],
                               "状态转移": [t["transition_id"] for t in transitions]})
    return confirm, receipts, chains


def evaluate(state, initial, preservation, expected):
    run_id, context = state["run_id"], state["context_version"]
    old_ids = {r["previous_finding_id"] for r in initial["rechecks"]}
    rechecks = [r for r in state["rechecks"] if r["previous_finding_id"] in old_ids]
    previous = {f["finding_id"]: f for f in initial["findings"] if f["finding_id"] in old_ids}
    evidence_by_id = {e["evidence_id"]: e for e in state["evidence"]}
    fresh_ids = {e["evidence_id"] for e in state["evidence"] if not e["stale"] and e["context_version"] == context}
    confirm, receipts, chains = receipt_chains(state, expected)
    bindings = []
    for recheck in rechecks:
        old = previous.get(recheck["previous_finding_id"], {})
        source_id = old.get("location", {}).get("source_id")
        if not source_id:
            prior_sources = {evidence_by_id[eid]["source_id"] for eid in old.get("evidence_ids", [])
                             if eid in evidence_by_id and old.get("object_id") in object_ids(evidence_by_id[eid])}
            source_id = next(iter(prior_sources)) if len(prior_sources) == 1 else None
        linked = [chain for chain in chains if source_id and chain["source_id"] == source_id
                  and old.get("object_id") in chain["object_ids"]
                  and chain["回执证据"] in recheck["evidence_ids"]]
        bindings.append({"旧候选ID": recheck["previous_finding_id"], "复审ID": recheck["recheck_id"],
                         "规范对象": old.get("object_id"), "来源": source_id,
                         "已引用同来源同对象的提交回执": bool(linked), "证据链": linked})
    calls = [c for c in state["model_calls"] if c["run_id"] == run_id]
    initial_call_ids = {c["call_id"] for c in initial["model_calls"]}
    stage_calls = [c for c in calls if c["call_id"] not in initial_call_ids]
    native_rechecks = [c for c in stage_calls if c["operation"] == "recheck"
                       and c["status"] == "validated" and not c["is_stub"]
                       and c.get("input", {}).get("context_version") == context]
    native_items = [item for call in native_rechecks for item in call.get("output", {}).get("items", [])]
    findings = [f for f in state["findings"] if f["run_id"] == run_id and not f["stale"]]
    checks = [c for c in state["checks"] if c["run_id"] == run_id and not c["stale"] and c["scope_status"] == "included"]
    # 旧驱动字段名沿用兼容读取；其断言核验的是旧报告正文，输出不称整库验证。
    preservation_key = ("原会话旧报告保持" if "原会话旧报告保持" in preservation else "原会话数据库未修改")
    clauses = {
        "已取得新版下午核对页": bool(confirm),
        "已取得新版预期回执": bool(receipts),
        "核对提交回执顺序与实际状态转移一致": bool(chains),
        "两个指定旧候选均给出预期复审状态": (
            len(old_ids) == 2 and Counter(r["previous_finding_id"] for r in rechecks) == Counter(old_ids)
            and all(r["resolution"] == expected for r in rechecks)),
        "复审逐项引用当前版本证据": bool(rechecks) and all(
            r["evidence_ids"] and set(r["evidence_ids"]).issubset(fresh_ids) for r in rechecks),
        "复审逐项引用同来源同对象的实际提交回执": bool(bindings) and all(
            item["已引用同来源同对象的提交回执"] for item in bindings),
        "旧报告正文保持": preservation.get("旧报告全部保持") is True and preservation.get(preservation_key) is True,
        "本阶段原生复审模型实际执行": bool(native_rechecks),
        "逐项复审结论对应本阶段真实模型输出": bool(rechecks) and all(any(
            item["previous_finding_id"] == r["previous_finding_id"]
            and item["resolution"] == r["resolution"]
            and set(item["evidence_ids"]) == set(r["evidence_ids"])
            for item in native_items) for r in rechecks),
    }
    return {"预期旧问题状态": expected, "H05指定旧候选专项通过": all(clauses.values()), "逐项": clauses,
        "状态": state["status"], "报告完整度": state["report_completeness"],
        "整份报告完整": state["report_completeness"] == "complete", "报告版本": state["report_version"],
        "当前run已记录模型调用数": len(calls), "当前run操作分布": dict(Counter(c["operation"] for c in calls)),
        "本阶段新增已记录模型调用数": len(stage_calls),
        "本阶段新增操作分布": dict(Counter(c["operation"] for c in stage_calls)),
        "检查状态": dict(Counter(c["execution_status"] for c in checks)),
        "下午核对页证据": [e["evidence_id"] for e in confirm],
        "预期回执证据": [e["evidence_id"] for e in receipts],
        "实际操作证据链": chains, "逐条复审证据关联": bindings,
        "旧报告保全口径": {"原记录字段": preservation_key, "核验对象": "原会话及分支中的旧报告正文 SHA256"},
        "复审": rechecks, "当前候选": findings, "运行说明": state["run_limitations"]}


def measure(name, expected):
    folder = ROOT / name
    return {"阶段": name, **evaluate(read(folder / "会话快照.json"), read(folder / "启动快照.json"),
                                   read(folder / "旧报告保全.json"), expected)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a", required=True)
    parser.add_argument("--b", required=True)
    args = parser.parse_args()
    rows = [measure(args.a, "persists"), measure(args.b, "resolved")]
    result = {"来源": "AI 驱动真实原生链；验收答案仅供运行后对照。",
        "验收范围": "H05 两条指定旧候选的版本复审专项；各阶段整份报告完整度单独列示。",
        "结果": rows, "H05指定旧候选专项全部通过": all(row["H05指定旧候选专项通过"] for row in rows)}
    target = ROOT / "原版与修正版对照.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"H05指定旧候选专项全部通过": result["H05指定旧候选专项全部通过"],
        "逐项": [{"阶段": row["阶段"], "报告完整度": row["报告完整度"], **row["逐项"]} for row in rows]}, ensure_ascii=False, indent=2))
