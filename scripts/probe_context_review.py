"""Run a real model over declared materials; not an accuracy benchmark."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.session_contracts import EventInput, SessionCreate, identifier
from engine.session_report import write_report_package
from engine.session_service import SessionService
from engine.session_store import SessionStore


async def probe(args):
    request = SessionCreate.model_validate_json(Path(args.request).read_text(encoding="utf-8-sig"))
    service = SessionService(SessionStore(ROOT / "out" / "context-probes"))
    try:
        existing_id = args.resume_session or args.audit_session
        if existing_id:
            session = service.store.get(existing_id)
            if session.status not in {"completed", "awaiting_input", "cancelled"}:
                raise RuntimeError("Only a stopped probe may be resumed; do not overwrite an active run.")
            if args.resume_session:
                session.request.limits = request.limits
                service.store.save(session)
                session, _ = service.apply_event(session.session_id, EventInput(
                    event_id=identifier("probe-resume"), expected_context_version=session.context_version,
                    type="resume", actor="integration-probe",
                    payload={"probe_limits": request.limits.model_dump()},
                ))
        else:
            session = service.create(request)
        if args.audit_session:
            service._update_review_mode(session)
            result = service._finish(session, waiting=session.status == "awaiting_input")
        else:
            result = await service.run(session.session_id)
        folder = service.store.root / result.session_id
        folder.mkdir(parents=True, exist_ok=True)
        package = write_report_package(
            result, service.store, folder / f"package-v{result.report_version}",
            registry=service.registry,
        )
        showcase = Path(package["report"]).read_text(encoding="utf-8")
        (folder / "report.md").write_text(showcase, encoding="utf-8")
        (folder / f"report-v{result.report_version}.md").write_text(showcase, encoding="utf-8")
        summary = {
            "session_id": result.session_id, "status": result.status,
            "report_completeness": result.report_completeness,
            "understanding": result.material_understanding.model_dump() if result.material_understanding else None,
            "checks": [{"ref": c.ref, "execution": c.execution_status, "decision": c.decision,
                        "applicability": c.applicability, "evidence_needed": c.evidence_needed}
                       for c in result.checks if c.run_id == result.run_id],
            "findings": [{"title": f.title, "kind": f.kind} for f in result.findings if not f.stale],
            "model_calls": [{"operation": c["operation"], "model": c["model"],
                             "usage": c["usage"], "is_stub": c["is_stub"]} for c in result.model_calls],
            "warnings": result.warnings, "report": str(folder / "report.md"),
            "package": package,
            "assessment": "Integration evidence only. Synthetic materials are not real product/user or accuracy evidence.",
        }
        (folder / "probe.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        await service.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("request")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--resume-session", help="Resume a stopped probe with the request's explicit limits")
    group.add_argument("--audit-session", help="Revalidate bindings of a stopped probe; preserve the prior report without new model calls")
    asyncio.run(probe(parser.parse_args()))
