"""重放已归档模型原答的确定性校验，不调用模型、不读取运行数据库。"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "engine/session_service.py").exists())
for path in (REPO.parent / "work/d_nov_review_deps", REPO.parent / "work/d_nov_mcp", REPO):
    sys.path.insert(0, str(path))
from engine.session_contracts import Finding, SessionSnapshot
from engine.session_service import SessionService
from engine import session_verification as verification


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(phase):
    evidence_dir = Path(__file__).resolve().parent
    output = evidence_dir / f"{phase}-原答回放.json"
    if output.exists():
        raise FileExistsError(output)
    source = REPO / "docs/D-本轮续测证据/原生复审/05-修后续查"
    snapshot_path = source / "续查初始快照.json"
    session = SessionSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8-sig"))
    valid = object.__new__(SessionService)._valid_evidence(session)
    results = []
    for call in ("007-judge", "008-judge"):
        answer_path = source / "调用" / call / "模型原答.txt"
        raw = json.loads(answer_path.read_text(encoding="utf-8-sig"))
        finding = Finding.model_validate(raw["findings"][0])
        # 与生产既有行为一致：有效的 claim 明确引用归并为发现的证据范围。
        claim_ids = [eid for claim in finding.claims for eid in claim.evidence_ids]
        assert set(claim_ids).issubset(valid)
        finding.evidence_ids = list(dict.fromkeys([*finding.evidence_ids, *claim_ids]))
        resolved = verification.resolve_finding_object(finding, valid)
        assert resolved is not None
        claims = verification.verify_finding_claims(session, finding, valid)
        supported = verification.verify_finding_support(session, finding, valid)
        if phase == "修前":
            # 旧生产定位分支的原表达式；实际退回事件还保存了同样的错误 state_id。
            located = next((e for e in valid.values() if resolved.object_id in {o.object_id for o in e.objects}), valid[finding.evidence_ids[0]])
            assert claims[0] and not supported[0]
        else:
            located = verification.finding_location_evidence(session, finding, valid)
            assert claims[0] and supported[0]
            assert located is not None and located.evidence_id in finding.evidence_ids
            assert located.state_id == "cae2b537eea57be43e8207a7"
        results.append({
            "原调用": call, "原答SHA256": digest(answer_path),
            "规范对象": resolved.object_id, "自由文本对象说明": finding.object_ref,
            "claim校验": claims, "发现支持校验": supported,
            "自动定位证据": located.evidence_id, "自动定位状态": located.state_id,
            "定位证据在引用内": located.evidence_id in finding.evidence_ids,
            "原候选严重度": finding.severity, "原模型置信度": finding.confidence,
            "结构化claims": [claim.model_dump() for claim in finding.claims],
        })
    frozen = REPO / "docs/D-本轮续测证据/原生复审/冻结引擎"
    baseline_paths = [frozen / "session_service-b2452a0232cbdbee.py", frozen / "session_verification-9f5d740fe515413f.py"]
    report = {"执行者": "Codex（AI，原答程序回放）", "真实模型调用": 0,
              "阶段": phase, "初始快照SHA256": digest(snapshot_path),
              "修前原字节": [{"路径": str(p.relative_to(REPO)), "SHA256": digest(p)} for p in baseline_paths],
              "当前实现": {name: digest(REPO / "engine" / name) for name in ("session_service.py", "session_verification.py")},
              "结果": results,
              "范围": "原模型候选经过对象、claim、动作支持及定位的确定性校验；未启动新的语义模型核验。"}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"文件": str(output), "结果": [{k:v for k,v in row.items() if k != "结构化claims"} for row in results]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["修前", "修后", "修后-定位补强"])
    run(parser.parse_args().phase)
