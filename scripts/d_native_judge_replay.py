"""回放真实 Codex 原答验证程序修复，并仅为缺失的语义核验调用真实模型。

在独立会话副本中重新打开原答对应检查，经原生 _judge、核验与去重保存报告。
录制原答不计为新模型判断；不重新执行网页，不直接写入发现。
"""
from __future__ import annotations

import argparse
import asyncio
import json

import d_native_recheck as d


class RecordedJudge:
    supports_images = True
    is_stub = True

    def __init__(self, origin, stage, recordings):
        self.origin, self.stage, self.recordings = origin, stage, recordings
        self.calls = 0
        self.records = []

    async def complete(self, messages, **kwargs):
        request = json.loads(messages[1]["content"][0]["text"])
        assert request["operation"] == "judge", "录制原答只用于原生 judge 阶段。"
        assert self.calls < len(self.recordings), "原生请求超过已登记的原答，停止回放。"
        folder = self.recordings[self.calls]
        source = self.origin / "调用" / folder
        raw = (source / "模型原答.txt").read_bytes()
        marker = json.loads((source / "调用记录.json").read_text(encoding="utf-8"))
        answer = json.loads(raw)
        actual = [item["check_id"] for item in request["checks"]]
        expected = [item["check_id"] for item in answer["judgments"]]
        assert len(actual) == len(expected) and set(actual) == set(expected), "回放检查与原答不对应。"
        self.calls += 1
        target = self.stage / "原答回放" / folder
        target.mkdir(parents=True)
        (target / "模型原答.txt").write_bytes(raw)
        d.save(target / "当前程序请求.json", request)
        record = {"序号": self.calls, "性质": "真实原答录制回放，不是新增模型判断",
                  "来源": str(source.relative_to(d.EVIDENCE)), "原答SHA256": d.sha(raw),
                  "原CLI线程": marker["Codex会话"], "原模型": marker["模型"],
                  "原调用开始UTC": marker["开始"], "回放UTC": d.utc(),
                  "检查ID": actual, "原答字节未改": True}
        self.records.append(record)
        d.save(target / "回放来源.json", record)
        return d.ModelCallResult(text=raw.decode("utf-8"), provider="recorded_codex",
                                 model="真实Codex原答回放", usage={},
                                 request_id="replay:" + marker["Codex会话"],
                                 latency_ms=0, json_mode_used=True)


class LimitedVerifier(d.CodexBridge):
    async def complete(self, messages, **kwargs):
        request = json.loads(messages[1]["content"][0]["text"])
        assert request["operation"] == "verify", "本阶段新增模型调用仅用于语义核验。"
        if self.calls >= 2:
            raise d.EngineError("replay_verify_budget", "本次回放只补两次真实语义核验。", status_code=409)
        return await super().complete(messages, **kwargs)


async def run(args):
    origin = d.EVIDENCE / args.origin
    stage = d.EVIDENCE / args.name
    source_state = d.WORK / "d_1104_native_recheck" / args.origin
    target_state = d.WORK / "d_1104_native_recheck" / args.name
    if stage.exists() or target_state.exists():
        raise SystemExit("目标记录已存在；请使用新名称，保留既有证据。")
    baseline = json.loads((origin / "运行结果.json").read_text(encoding="utf-8"))
    if baseline["状态"] not in {"completed", "awaiting_input"}:
        raise SystemExit("来源运行尚未结束，不复制正在运行的会话。")
    stage.mkdir(parents=True)
    d.save(stage / "基线证据复制校验.json", d.clone_state(source_state, target_state))
    store = d.SessionStore(target_state)
    session = store.get(baseline["会话"])
    assert not session.findings, "此回放入口针对原批无正式发现的明确停点。"
    old_hashes = d.report_hashes(store)
    source_snapshot_sha = d.sha((origin / "会话快照.json").read_bytes())
    old_calls = len(session.model_calls)
    recordings = ["007-judge", "008-judge"]
    ordered_ids = []
    for folder in recordings:
        raw = json.loads((origin / "调用" / folder / "模型原答.txt").read_text(encoding="utf-8"))
        ordered_ids.extend(j["check_id"] for j in raw["judgments"])
    assert len(ordered_ids) == len(set(ordered_ids)) == 32
    checks = {c.check_id: c for c in session.checks}
    assert all(cid in checks and checks[cid].run_id == session.run_id for cid in ordered_ids)
    before_checks = [checks[cid].model_dump(mode="json") for cid in ordered_ids]
    # 复现原生 judge 的输入前置条件。检查编号、计划与原始证据保持不变。
    # 其他历史检查和已归档报告保留；只有录制原答对应的32项重新进入判断。
    for check in session.checks:
        if check.check_id in ordered_ids:
            check.execution_status = "planned"
            check.decision = None
            check.evidence_ids = []
            check.reason = "程序修复验证：重新核验该检查的真实录制原答。"
            check.reevaluation_requested = True
            check.scope_status = "included"
            check.stale = False
        elif check.run_id == session.run_id and check.execution_status == "planned":
            raise AssertionError("来源尚有计划中的检查，不混入原答回放范围。")
    session.checks = [checks[cid] for cid in ordered_ids] + [c for c in session.checks if c.check_id not in ordered_ids]
    started = d.utc()
    session.messages.append({"at": started, "actor": d.ACTOR, "actor_type": "ai",
        "type": "d_recorded_judge_replay", "run_id": session.run_id,
        "content": {"性质": "程序修复验证；真实Codex录制原答回放，不是新增独立试验",
                    "原阶段": args.origin, "原答": recordings, "重新打开检查": ordered_ids,
                    "新调用仅用于": "两次语义核验", "网页动作": "不执行"}})
    session.status = "checking"
    session.run_limitations.append("本报告在原会话副本中完成程序修复验证；两份judge为真实录制原答回放，新增模型调用仅为语义核验。")
    store.save(session)
    d.save(stage / "回放前置条件.json", {"来源快照SHA256": source_snapshot_sha, "旧报告原字节SHA256": old_hashes,
        "原run": session.run_id, "检查数": 32, "原检查状态": before_checks,
        "操作": "独立会话副本只将对应32项重新置为planned与reevaluation_requested，保留编号和计划。"})
    judge = RecordedJudge(origin, stage, recordings)
    verifier = LimitedVerifier(stage, args.model)
    service = d.SessionService(store, registry=d.MethodRegistry(d.REPO / "方法专家开发交付-v0.2"))
    environment = {"开始": started, "执行": "原生_judge → 程序校验 → 真实Codex语义核验 → 原生去重 → 原生报告",
        "运行性质": "录制原答修后程序回放，不是新增独立模型初审", "AI操作者": d.ACTOR, "AI来源": "ai",
        "旧会话和报告保持原样": True, "真实新模型调用上限": 2,
        "引擎文件SHA256": {p: d.sha((d.REPO / p).read_bytes()) for p in
            ["engine/session_service.py", "engine/session_verification.py", "engine/session_contracts.py"]}}
    environment["引擎快照"] = {}
    for filename in ["session_service.py", "session_verification.py"]:
        raw = (d.REPO / "engine" / filename).read_bytes()
        archived = d.EVIDENCE / "冻结引擎" / (filename[:-3] + "-" + d.sha(raw)[:16] + ".py")
        if not archived.exists():
            archived.write_bytes(raw)
        assert d.sha(archived.read_bytes()) == d.sha(raw)
        environment["引擎快照"][filename] = archived.relative_to(d.EVIDENCE).as_posix()
    d.save(stage / "运行环境.json", environment)
    failure = None
    try:
        await service._judge(session, judge, verifier)
        assert judge.calls == 2
    except Exception as error:
        failure = {"类型": type(error).__name__, "说明": str(error)}
        session.warnings.append("本轮录制原答回放中止：" + str(error))
        d.save(stage / "回放停点.json", failure)
    finally:
        # 原生报告收尾保留未通过的判断，不直接追加或修改发现。
        session = service._finish(session)
        d.export(stage, session, store, service.registry)
        after_hashes = d.report_hashes(store)
        assert all(after_hashes.get(k) == v for k, v in old_hashes.items())
        assert d.report_hashes(d.SessionStore(source_state)) == old_hashes
        assert d.sha((origin / "会话快照.json").read_bytes()) == source_snapshot_sha
        d.save(stage / "旧报告保全核对.json", {"旧报告SHA256": old_hashes, "旧版本保持一致": True,
                                             "原阶段快照与数据库未改": True})
        d.save(stage / "运行结果.json", d.summary(session) | {"结束": d.utc(),
            "运行性质": "真实录制原答的程序回放", "原答回放数": judge.calls,
            "原答来源": judge.records, "真实新增CLI核验调用": verifier.calls,
            "本阶段新增产品记录": session.model_calls[old_calls:], "停点": failure})
        await service.close()
    print(json.dumps({"阶段": args.name, "报告版本": session.report_version, "发现数": len(session.findings),
                      "原答回放": judge.calls, "真实新增核验": verifier.calls, "停点": failure}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="05-修后续查")
    parser.add_argument("--name", default="06-修后原答回放")
    parser.add_argument("--model", default="gpt-6-astra")
    asyncio.run(run(parser.parse_args()))
