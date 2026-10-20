"""Command-line interface for validation and local review runs."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from .api import DEFAULT_CRITERIA_PATH
from .advanced import AdvancedReviewEngine
from .config import config_health, load_reviewer_config, validate_reviewer_config
from .contracts import ReviewContext
from .criteria import CriteriaLibrary
from .runtime import build_engine
from .staged import STAGE_ORDER, StageRun, init_stage_run, read_manifest

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    _load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(prog="python -m engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate-criteria", help="Validate criteria JSON")
    validate_parser.add_argument("--criteria", default=str(DEFAULT_CRITERIA_PATH))

    config_parser = subparsers.add_parser("validate-config", help="Validate local reviewer config")
    config_parser.add_argument("--config", default=None)

    health_parser = subparsers.add_parser("health", help="Inspect config without paid model calls")
    health_parser.add_argument("--config", default=None)

    review_parser = subparsers.add_parser("review", help="Review one screenshot")
    review_parser.add_argument("image")
    review_parser.add_argument("--output", default=None)
    review_parser.add_argument("--goal", default=None)
    review_parser.add_argument("--scenario", default=None)
    review_parser.add_argument("--target-user", default=None)
    review_parser.add_argument(
        "--platform",
        choices=["web", "ios", "android", "desktop", "game", "unknown"],
        default="unknown",
    )
    review_parser.add_argument("--provider", default=None)
    review_parser.add_argument("--model", default=None)
    review_parser.add_argument(
        "--analysis-mode",
        choices=["two_pass", "single_pass"],
        default="two_pass",
    )
    review_parser.add_argument("--criteria", default=str(DEFAULT_CRITERIA_PATH))

    advanced_parser = subparsers.add_parser(
        "review-v2",
        help="Run OCR + GUI perception + metrics + criterion retrieval",
    )
    advanced_parser.add_argument("image")
    advanced_parser.add_argument("--reference", default=None)
    advanced_parser.add_argument("--output", default=None)
    advanced_parser.add_argument("--goal", default=None)
    advanced_parser.add_argument("--goal-file", default=None)
    advanced_parser.add_argument("--scenario", default=None)
    advanced_parser.add_argument("--target-user", default=None)
    advanced_parser.add_argument(
        "--platform",
        choices=["web", "ios", "android", "desktop", "game", "unknown"],
        default="unknown",
    )
    advanced_parser.add_argument("--criteria", default=str(DEFAULT_CRITERIA_PATH))

    stage_init_parser = subparsers.add_parser(
        "stage-init",
        help="Create a cached run for step-by-step review",
    )
    stage_init_parser.add_argument("image")
    stage_init_parser.add_argument("--reference", default=None)
    stage_init_parser.add_argument("--goal", default=None)
    stage_init_parser.add_argument("--goal-file", default=None)
    stage_init_parser.add_argument("--scenario", default=None)
    stage_init_parser.add_argument("--target-user", default=None)
    stage_init_parser.add_argument(
        "--platform",
        choices=["web", "ios", "android", "desktop", "game", "unknown"],
        default="unknown",
    )
    stage_init_parser.add_argument("--artifact-root", default="out/stages")

    stage_run_parser = subparsers.add_parser(
        "stage",
        help="Run one cached review stage",
    )
    stage_run_parser.add_argument("run_dir")
    stage_run_parser.add_argument("stage", choices=STAGE_ORDER[1:])
    stage_run_parser.add_argument("--criteria", default=str(DEFAULT_CRITERIA_PATH))

    stage_status_parser = subparsers.add_parser(
        "stage-status",
        help="Show a cached run manifest",
    )
    stage_status_parser.add_argument("run_dir")

    serve_parser = subparsers.add_parser("serve", help="Run the FastAPI service")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")

    args = parser.parse_args()
    if args.command == "validate-criteria":
        criteria = CriteriaLibrary.load(args.criteria)
        print(json.dumps({
            "ok": True,
            "version": criteria.version,
            "rule_count": len(criteria.rules),
            "heuristics": sorted({rule.heuristic for rule in criteria.rules}),
        }, ensure_ascii=False, indent=2))
        return

    if args.command == "validate-config":
        config = load_reviewer_config(args.config, required=True)
        errors = validate_reviewer_config(config)
        print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
        if errors:
            raise SystemExit(1)
        return

    if args.command == "health":
        config = load_reviewer_config(args.config, required=True)
        print(json.dumps(config_health(config), ensure_ascii=False, indent=2))
        return

    if args.command == "stage-init":
        goal = args.goal
        if args.goal_file:
            goal = Path(args.goal_file).read_text(encoding="utf-8").strip()
        if not goal:
            raise SystemExit("stage-init requires --goal or --goal-file")
        run_dir = init_stage_run(
            image_path=args.image,
            reference_path=args.reference,
            goal=goal,
            context=ReviewContext(
                design_goal=goal,
                scenario=args.scenario,
                platform=args.platform,
                target_user=args.target_user,
            ),
            artifact_root=args.artifact_root,
        )
        print(json.dumps({"run_dir": str(run_dir)}, ensure_ascii=False, indent=2))
        return

    if args.command == "stage-status":
        print(json.dumps(read_manifest(args.run_dir), ensure_ascii=False, indent=2))
        return

    if args.command == "stage":
        criteria = CriteriaLibrary.load(args.criteria)
        result = asyncio.run(StageRun(args.run_dir, criteria).run(args.stage))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "serve":
        import uvicorn

        uvicorn.run("engine.api:app", host=args.host, port=args.port, reload=args.reload)
        return

    if args.command == "review-v2":
        asyncio.run(_review_v2(args))
        return

    asyncio.run(_review(args))


async def _review(args: argparse.Namespace) -> None:
    criteria = CriteriaLibrary.load(args.criteria)
    engine = build_engine(criteria, args.provider, args.model)

    source = Path(args.image)
    report = await engine.review(
        source.read_bytes(),
        context=ReviewContext(
            design_goal=args.goal,
            scenario=args.scenario,
            platform=args.platform,
            target_user=args.target_user,
        ),
        filename=source.name,
        analysis_mode=args.analysis_mode,
    )
    output_path = (
        Path(args.output)
        if args.output
        else ROOT / "out" / f"{source.stem}.review.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "review_id": report.review_id,
                "status": report.status,
                "findings": len(report.findings),
                "candidate_rules": report.summary.candidate_issues,
                "output": str(output_path),
                "warnings": report.warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


async def _review_v2(args: argparse.Namespace) -> None:
    criteria = CriteriaLibrary.load(args.criteria)
    goal = args.goal
    if args.goal_file:
        goal = Path(args.goal_file).read_text(encoding="utf-8").strip()
    if not goal:
        raise SystemExit("review-v2 requires --goal or --goal-file")
    source = Path(args.image)
    reference = Path(args.reference) if args.reference else None
    engine = AdvancedReviewEngine(criteria)
    report = await engine.review(
        source.read_bytes(),
        context=ReviewContext(
            design_goal=goal,
            scenario=args.scenario,
            platform=args.platform,
            target_user=args.target_user,
        ),
        reference_bytes=reference.read_bytes() if reference else None,
        filename=source.name,
    )
    output_path = (
        Path(args.output)
        if args.output
        else ROOT / "out" / f"{source.stem}.advanced.review.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "review_id": report.review_id,
                "status": report.status,
                "findings": len(report.findings),
                "rules_total": report.summary.rules_total,
                "candidate_rules": report.summary.candidate_issues,
                "selected_criteria": sum(
                    1 for row in report.criteria_relevance if row.get("selected")
                ),
                "output": str(output_path),
                "artifacts": report.artifacts,
                "warnings": report.warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)
