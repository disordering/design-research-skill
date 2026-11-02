"""Live coordinate-grounding probe on a saved image; never executes a UI action."""

import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.session_contracts import Action, SessionCreate, SourceInput
from engine.session_service import SessionService
from engine.session_store import SessionStore


async def main(args):
    service = SessionService(SessionStore(ROOT / "out" / "session-probes"))
    request = SessionCreate(
        purpose="只核对存档截图的点击定位，不运行原型、不点击界面，不作为流程验收。",
        model_name=args.model, sources=[SourceInput(
            kind="image", title="Archived screenshot; grounding-only probe",
            image_base64=base64.b64encode(Path(args.image).read_bytes()).decode(),
        )],
    )
    session = service.create(request)
    try:
        await service._read_sources(session)
        evidence = next(e for e in reversed(session.evidence) if e.source_id == session.sources[0].source_id)
        action = Action(
            source_id=session.sources[0].source_id, kind="click", x=args.x, y=args.y,
            expected_state_id=evidence.state_id, target_label=args.target,
            reason=f"Grounding-only test: intended target {args.target}",
        )
        accepted = await service._ground_action(session, service.model_factory(request), action)
        service.store.save(session)
        result = {
            "probe_kind": "live_archived_image_grounding", "session_id": session.session_id,
            "matches_intent": accepted, "observed_target": action.observed_target,
            "error": action.error, "marker_artifact_id": action.target_marker_artifact_id,
            "model_calls": [{"model": c["model"], "usage": c["usage"], "is_stub": c["is_stub"]}
                            for c in session.model_calls],
            "ui_actions_executed": 0,
        }
        output = service.store.root / session.session_id / "grounding-probe.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({**result, "output": str(output)}, ensure_ascii=False, indent=2))
    finally:
        await service.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--target", required=True)
    parser.add_argument("--x", type=float, required=True)
    parser.add_argument("--y", type=float, required=True)
    parser.add_argument("--model", default="qwen3.8-max-0902")
    asyncio.run(main(parser.parse_args()))
