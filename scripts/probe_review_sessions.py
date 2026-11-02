"""Explicit live adapter/model smoke probes. Not an accuracy benchmark."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.errors import EngineError
from engine.session_contracts import SessionCreate, SourceInput
from engine.session_service import SessionService
from engine.session_store import SessionStore
from engine.session_report import write_report_package


async def probe(args) -> None:
    if args.fixture:
        source = SourceInput(
            kind="document", title="Synthetic integration fixture, not a real design",
            evidence_kind="design", version="fixture-v1",
            content="这是明确标注的合成接口验证材料：一个单页设置界面，字段有名称“昵称”，按钮为“保存昵称”。不提供实际运行状态、用户熟悉度或其他页面，不可推断点击结果。",
        )
    else:
        source = SourceInput(kind=args.kind, reference=args.url, title="Explicit live capability probe")
    service = SessionService(SessionStore(ROOT / "out" / "session-probes"))
    request = SessionCreate(
        purpose=args.purpose, sources=[source], provider=args.provider,
        model_name=args.model, allow_interaction=args.allow_interaction,
        limits={"max_checks": args.max_checks, "max_model_calls": args.max_model_calls,
                "max_actions": args.max_actions, "max_seconds": args.max_seconds},
    )
    session = service.create(request)
    action_result = None
    try:
        if args.run_model:
            session = await service.run(session.session_id)
        else:
            record = session.sources[0]
            try:
                capture = await service.adapters.read(session.session_id, record)
                service._capture(session, record, capture)
                if args.kind == "figma_prototype" and capture.partial:
                    from engine.session_contracts import Action
                    for _ in range(args.observe_attempts):
                        observation = Action(
                            source_id=record.source_id, kind="observe",
                            expected_state_id=capture.state_id, reason="Continue observing prototype loading",
                            requires_explicit_authorization=False,
                        )
                        capture = await service.adapters.act(session.session_id, record, observation, authorized=False)
                        service._capture(session, record, capture)
                        if not capture.partial:
                            break
                if args.click_point and not capture.partial:
                    from engine.session_contracts import Action
                    capture = await service.adapters.act(
                        session.session_id, record,
                        Action(source_id=record.source_id, kind="observe",
                               expected_state_id=capture.state_id, reason="Observe after initial rendering",
                               requires_explicit_authorization=False),
                        authorized=False,
                    )
                    service._capture(session, record, capture)
                    before_state = capture.state_id
                    action = Action(
                        source_id=record.source_id, kind="click",
                        x=args.click_point[0], y=args.click_point[1],
                        expected_state_id=before_state,
                        reason="Explicit sample smoke click from inspected screenshot",
                        requires_explicit_authorization=False,
                    )
                    capture = await service.adapters.act(session.session_id, record, action, authorized=False)
                    service._capture(session, record, capture)
                    action_result = {
                        "kind": "click", "point": args.click_point,
                        "before_state": before_state, "after_state": capture.state_id,
                        "state_changed": before_state != capture.state_id,
                        "operation_verified": capture.locator.get("operation_verified", False),
                        "after_url": capture.locator.get("url"),
                    }
                    capture = await service.adapters.act(
                        session.session_id, record,
                        action.model_copy(update={"kind": "observe", "expected_state_id": capture.state_id}),
                        authorized=False,
                    )
                    service._capture(session, record, capture)
            except EngineError as exc:
                record.acquisition_status = "blocked" if exc.status_code in {403, 503} else "failed"
                record.error = f"{exc.code}: {exc.message}"
            service.store.save(session)
        result = {
            "probe_kind": "live_model_synthetic_fixture" if args.fixture else ("live_model" if args.run_model else "live_adapter"),
            "session_id": session.session_id, "status": session.status,
            "source_status": session.sources[0].acquisition_status,
            "error": session.sources[0].error,
            "evidence_count": len(session.evidence),
            "image_artifacts": [e.artifact_id for e in session.evidence if e.artifact_id],
            "model_calls": [{
                "provider": c["provider"], "model": c["model"], "usage": c["usage"],
                "operation": c["operation"], "is_stub": c.get("is_stub"),
            } for c in session.model_calls],
            "executed_checks": sum(c.execution_status == "executed" for c in session.checks if c.run_id == session.run_id),
            "unexecuted_checks": sum(c.execution_status != "executed" for c in session.checks if c.run_id == session.run_id),
            "warnings": session.warnings, "report_completeness": session.report_completeness,
            "action": action_result,
            "actions": [{
                "action_id": a.action_id, "kind": a.kind, "status": a.status,
                "outcome": a.outcome, "reason": a.reason, "error": a.error,
                "evidence_ids": a.evidence_ids,
            } for a in session.actions],
            "observed_transitions": len(session.transitions),
            "findings": len(session.findings),
            "questions": [{"text": q.text, "reason": q.reason, "blocking": q.blocking}
                          for q in session.questions if not q.answered],
            "capabilities": service.adapters.capabilities(),
            "assessment": "Smoke evidence only; not model accuracy or user-effect validation.",
        }
        output = service.store.root / session.session_id / "probe.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        package = write_report_package(
            session, service.store, output.parent / f"package-v{session.report_version}",
            registry=service.registry,
        )
        report = output.with_name("report.md")
        report.write_text(Path(package["report"]).read_text(encoding="utf-8"), encoding="utf-8")
        print(json.dumps({
            **result, "output": str(output), "report": str(report), "package": package,
        }, ensure_ascii=False, indent=2))
    finally:
        await service.close()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=["website", "figma_board", "figma_prototype"], default="website")
    parser.add_argument("--url", default="https://example.com")
    parser.add_argument("--purpose", default="只检查已取得的材料，不推断未运行的状态。")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--run-model", action="store_true", help="Explicitly allow bounded, potentially paid model calls")
    parser.add_argument("--provider", choices=["qwen", "deepseek", "local", "generic"], default="qwen")
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-checks", type=int, default=8)
    parser.add_argument("--max-actions", type=int, default=2)
    parser.add_argument("--max-model-calls", type=int, default=8)
    parser.add_argument("--max-seconds", type=int, default=180)
    parser.add_argument("--allow-interaction", action="store_true",
                        help="Permit ordinary task interactions; sensitive actions still need separate authorization")
    parser.add_argument("--observe-attempts", type=int, default=12)
    parser.add_argument("--click-point", type=float, nargs=2, metavar=("X", "Y"),
                        help="Explicit normalized coordinates relative to the inspected prototype canvas screenshot")
    args = parser.parse_args()
    if not 0 <= args.observe_attempts <= 20:
        parser.error("--observe-attempts must be between 0 and 20")
    if args.click_point and (
        args.kind != "figma_prototype" or args.run_model
        or any(not 0 <= point <= 1 for point in args.click_point)
    ):
        parser.error("--click-point is only for a non-model prototype probe, with coordinates in [0,1]")
    asyncio.run(probe(args))


if __name__ == "__main__":
    main()
