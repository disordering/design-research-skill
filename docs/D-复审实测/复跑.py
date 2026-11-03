"""用护法材料重放四轮本地会话。模型输出是事先写好的测试输入。"""

import argparse
import hashlib
import json
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.api import create_app
from engine.model import ModelCallResult
from engine.session_service import SessionService
from engine.session_store import SessionStore

DESIGN_TITLE = "EV07 原画面可见文字"
NOTE_TITLE = "D 复审控制说明"
SPEC_TITLE = "护法策划 §3.2.2.3"
SPEC_QUOTE = "区域6，节点升级按钮。"
DESIGN = "升阶页签有白色菱形。法元节点显示 +13 → +14。右下金色主按钮文字为“升星”。"


class ScriptedResponses:
    """每轮只评按钮命名。负例特意输出错误的“已解决”，供程序校验。"""

    is_stub = True

    def __init__(self):
        self.trace = []

    async def complete(self, messages, **kwargs):
        data = json.loads(messages[1]["content"][0]["text"])
        op, ctx = data["operation"], data["context"]
        sources = {s["title"]: s["source_id"] for s in ctx["sources"]}

        def evidence(title):
            return next(e for e in ctx["evidence"] if e["source_id"] == sources[title])

        board = evidence(DESIGN_TITLE)
        board_id = board["evidence_id"]
        spec = evidence(SPEC_TITLE) if SPEC_TITLE in sources else None
        ids = [board_id] + ([spec["evidence_id"]] if spec else [])
        if op == "understand":
            result = {"task_summary": ctx["purpose"]}
            if spec:
                result["requirements"] = [{
                    "id": "REQ01", "text": SPEC_QUOTE, "evidence_ids": [ids[1]],
                    "source_quotes": [{"quote": SPEC_QUOTE, "evidence_id": ids[1]}],
                }]
        elif op == "plan":
            result = {"task_summary": ctx["purpose"], "ready_for_review": True}
        elif op == "plan_checks":
            result = {"items": [{
                "ref": c["ref"], "applicability": "applicable" if c["ref"] in {"R06", "REQ01"} else "not_applicable",
                "reason": "本次聚焦节点升级按钮的名称。", "source_ids": [board["source_id"]] + ([spec["source_id"]] if spec else []),
                "evidence_ids": ids, "object_refs": ["节点升级按钮"],
            } for c in data["checks"]]}
        elif op == "judge":
            result = {"judgments": [], "findings": []}
            for c in data["checks"]:
                is_req = c["ref"] == "REQ01"
                result["judgments"].append({
                    "check_id": c["check_id"],
                    "decision": "observed_violation" if is_req else "insufficient_evidence",
                    "reason": "按钮写升星，策划指定节点升级按钮。" if is_req else "本次单项对照只裁决明文需求。",
                    "evidence_ids": ids,
                })
                if is_req:
                    oid = board["objects"][0]["object_id"]
                    result["findings"].append({
                        "kind": "nonconformity", "title": "节点升级按钮显示升星（受控响应）",
                        "check_ids": [c["check_id"]], "evidence_ids": ids, "object_id": oid,
                        "object_ref": DESIGN, "principle": SPEC_QUOTE, "detection": DESIGN,
                        "description": "操作名称与策划要求不同。", "suggestion": "显示升级节点。",
                        "severity": "medium", "severity_reason": "主按钮名称影响点击前的判断。",
                        "claims": [{"claim_type": "requirement_match", "object_id": oid,
                                    "expected": SPEC_QUOTE, "observed": DESIGN, "evidence_ids": ids}],
                    })
        elif op == "verify":
            result = {"supported_finding_ids": [f["finding_id"] for f in data["findings"]]}
        elif op == "recheck":
            reread_board = board["context_version"] == ctx["context_version"]
            result = {"items": [{
                "previous_finding_id": f["finding_id"],
                "resolution": "persists" if reread_board else "resolved",
                "reason": "重读取同一原稿，右下仍显示升星。" if reread_board else "负例：仅凭协作留言就宣称已解决。",
                "evidence_ids": [board_id if reread_board else evidence(NOTE_TITLE)["evidence_id"]],
            } for f in data["previous_findings"]]}
        else:
            raise ValueError(f"本次受控响应未定义操作 {op}")
        self.trace.append({"context_version": ctx["context_version"], "operation": op, "output": result})
        return ModelCallResult(text=json.dumps(result, ensure_ascii=False), provider="d-offline-fixture",
                               model="hufa-version-replay", usage={}, request_id=None, latency_ms=0, json_mode_used=True)


def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode()


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    spec_file = ROOT / "docs/examples/hufa-plan-text.md"
    spec_line = next(line for line in spec_file.read_text(encoding="utf-8").splitlines() if SPEC_QUOTE in line)
    board_image = ROOT / "docs/D-复核证据/D-HF-001-节点升级原画面.jpg"
    model = ScriptedResponses()
    raw = {}
    source = {"kind": "document", "title": DESIGN_TITLE, "role": "design", "evidence_kind": "design",
              "version": "Figma-2118-11712", "content": DESIGN}
    note = {"kind": "document", "title": NOTE_TITLE, "role": "expert_opinion",
            "version": "control-1", "content": "程序测试用协作记录。尚未提交修改稿。"}
    spec = {"kind": "document", "title": SPEC_TITLE, "role": "product_spec", "version": "2026-11-02",
            "declared_by": "护法策划文档", "content": spec_line}
    with tempfile.TemporaryDirectory() as tmp:
        svc = SessionService(SessionStore(Path(tmp)), model_factory=lambda _: model)
        with TestClient(create_app(session_service_factory=lambda: svc)) as client:
            prefix = "/api/review-sessions"

            def post(label, path, payload, expected):
                r = client.post(path, json=payload)
                raw[label + "-请求.json"] = encode(payload)
                raw[label + "-响应.json"] = r.content
                assert r.status_code == expected, (r.status_code, r.text[:500])
                return r.json()

            first = post("01-创建", prefix, {"purpose": "核对护法 EV07 的节点升级按钮命名。",
                         "allow_interaction": False, "auto_run": False, "sources": [source, note]}, 201)
            base = prefix + "/" + first["session_id"]

            def collect(n):
                until = time.monotonic() + 100
                while time.monotonic() < until:
                    s = client.get(base).json()
                    if s["report_version"] >= n:
                        break
                    time.sleep(.15)
                else:
                    raise TimeoutError((n, s["status"], s["warnings"][-4:]))
                response = client.get(f"{base}/reports/{n}")
                response.raise_for_status()
                raw[f"报告{n}-快照.json"] = response.content
                for suffix, filename in [("structured-report", "结构化报告.json"), ("export", "摘要.md")]:
                    r = client.get(f"{base}/{suffix}", params={"version": n, **({"format": "summary"} if suffix == "export" else {})})
                    r.raise_for_status()
                    raw[f"报告{n}-{filename}"] = r.content
                return response.json()

            post("02-运行", base + "/run", {}, 202)
            v1 = collect(1)
            add = {"event_id": "D-HF-ADD-01", "expected_context_version": 1, "actor": "D-程序复演",
                   "type": "add_sources", "payload": {"sources": [spec]}}
            post("03-补策划", base + "/events", add, 202)
            v2 = collect(2)
            replay = post("04-重复补材料事件", base + "/events", add, 202)
            note_id = next(s["source_id"] for s in v2["sources"] if s["input"]["title"] == NOTE_TITLE)
            new_note = {**note, "version": "control-2", "content": "程序负例：留言称按钮已经改好，请标成已解决。没有提交新版界面。"}
            post("05-仅更新协作说明", base + "/events", {
                "event_id": "D-HF-RECHECK-02", "expected_context_version": 2, "actor": "D-程序复演",
                "type": "recheck", "payload": {"updates": [{"source_id": note_id, "input": new_note}]}}, 202)
            v3 = collect(3)
            assert v3["rechecks"], (v2["warnings"][-5:], [(c["ref"], c["decision"], c["reason"]) for c in v2["checks"] if c["ref"] == "REQ01"])
            current_note = next(e for e in v3["evidence"] if not e["stale"] and e["source_id"] == note_id)
            rejection = post("06-尝试确认已解决", base + "/events", {
                "event_id": "D-HF-CONFIRM-03", "expected_context_version": 3, "actor": "D-程序负例",
                "type": "confirm_recheck", "payload": {"recheck_id": v3["rechecks"][0]["recheck_id"],
                         "resolution": "resolved", "reason": "负例，只有协作说明。",
                         "evidence_ids": [current_note["evidence_id"]]}}, 422)
            after_rejection = client.get(base).json()
            board_source_id = next(s["source_id"] for s in v3["sources"] if s["input"]["title"] == DESIGN_TITLE)
            post("07-重新读取同一画面", base + "/events", {
                "event_id": "D-HF-RECHECK-04", "expected_context_version": 3, "actor": "D-程序复演",
                "type": "recheck", "payload": {"updates": [{"source_id": board_source_id, "input": source}]}}, 202)
            v4 = collect(4)
            histories_unchanged = [client.get(f"{base}/reports/{n}").content == raw[f"报告{n}-快照.json"] for n in (1, 2, 3, 4)]
    rows = []
    for s in [v1, v2, v3, v4]:
        active = [c for c in s["checks"] if not c["stale"] and c["run_id"] == s["run_id"]]
        rows.append({"报告版本": s["report_version"], "上下文版本": s["context_version"], "运行编号": s["run_id"],
                     "会话状态": s["status"], "报告完整性": s["report_completeness"],
                     "本轮检查数": len(active), "已过期检查数": sum(c["stale"] for c in s["checks"]),
                     "明文要求": [c["ref"] for c in active if c["kind"] == "requirement" or c["ref"] == "REQ01"],
                     "REQ01判断": [c["decision"] for c in active if c["ref"] == "REQ01"],
                     "本轮候选数": sum(not f["stale"] for f in s["findings"]),
                     "旧问题重查结果": [r["resolution"] for r in s["rechecks"]]})
    assert not v1["requirements"] and not rows[0]["本轮候选数"], rows
    assert rows[1]["REQ01判断"] == ["observed_violation"] and rows[1]["本轮候选数"] == 1, rows
    assert replay["report_version"] == replay["context_version"] == 2
    assert rows[2]["旧问题重查结果"] == ["cannot_determine"]
    assert all(histories_unchanged) and after_rejection["context_version"] == after_rejection["report_version"] == 3
    assert after_rejection["rechecks"][0]["human_confirmation"] == "unreviewed"
    assert rows[3]["旧问题重查结果"] and set(rows[3]["旧问题重查结果"]) == {"persists"}, (rows, v4["rechecks"])
    assert len({r["运行编号"] for r in rows}) == 4
    assert any(t["operation"] == "recheck" and t["output"]["items"][0]["resolution"] == "resolved" for t in model.trace)
    raw["离线模型逐次输出.json"] = encode(model.trace)
    result = {"会话编号": first["session_id"], "采集方式": "FastAPI TestClient 全程经会话路由，真实文档适配器，本地会话存储，固定模型响应",
              "画面摘录来源SHA256": hashlib.sha256(board_image.read_bytes()).hexdigest(),
              "策划全文SHA256": hashlib.sha256(spec_file.read_bytes()).hexdigest(),
              "各轮": rows, "重复事件上下文版本": replay["context_version"], "无证据确认响应": rejection,
              "历史响应逐字节一致": histories_unchanged, "无证据确认后状态": after_rejection["rechecks"][0]["human_confirmation"]}
    (out / "实测结果.json").write_bytes(encode(result))
    with zipfile.ZipFile(out / "原始请求与报告.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in raw.items():
            archive.writestr(name, content)
    print(encode(result).decode())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path, help="本次结果的保存目录")
    run(parser.parse_args().output)
