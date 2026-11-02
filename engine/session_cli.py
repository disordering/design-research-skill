"""Explicit CLI operations; creating a session never makes a paid model call."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .config import load_reviewer_config
from .session_contracts import EventInput, SessionCreate
from .session_report import (
    audit_report, markdown_report, markdown_summary,
    write_report_package, zip_report_package,
)
from .session_service import SessionService
from .session_store import SessionStore


def add_parsers(subparsers) -> None:
    parser = subparsers.add_parser("session-capabilities", help="Inspect capabilities without model calls")
    parser = subparsers.add_parser("session-create", help="Create a collaborative session from JSON")
    parser.add_argument("request_file")
    for name in ("session-run", "session-status", "session-export"):
        parser = subparsers.add_parser(name)
        parser.add_argument("session_id")
        if name == "session-export":
            parser.add_argument("--output", default=None)
            parser.add_argument("--summary", action="store_true")
            parser.add_argument("--audit", action="store_true")
            parser.add_argument("--package", action="store_true")
            parser.add_argument("--zip", action="store_true")
    parser = subparsers.add_parser("session-event")
    parser.add_argument("session_id")
    parser.add_argument("event_file")
    parser.add_argument("--run", action="store_true")
    parser = subparsers.add_parser("figma-login", help="Authorize the backend MCP client independently")
    parser.add_argument("--timeout", type=int, default=300)


async def execute(args, root: Path) -> None:
    config = load_reviewer_config(required=False)
    storage = Path(config.get("sessions", {}).get("storage_dir", "out/sessions"))
    service = SessionService(SessionStore(storage if storage.is_absolute() else root / storage))
    try:
        if args.command == "figma-login":
            from .figma_auth import interactive_login
            if not service.adapters.figma.endpoint:
                raise ValueError("Configure tools.figma_mcp.url before login.")
            result = await interactive_login(service.adapters.figma.endpoint, timeout=args.timeout)
        elif args.command == "session-capabilities":
            result = service.capabilities()
        elif args.command == "session-create":
            request = SessionCreate.model_validate_json(Path(args.request_file).read_text(encoding="utf-8-sig"))
            result = service.create(request).model_dump(mode="json")
        elif args.command == "session-run":
            result = (await service.run(args.session_id)).model_dump(mode="json")
        elif args.command == "session-event":
            event = EventInput.model_validate_json(Path(args.event_file).read_text(encoding="utf-8-sig"))
            snapshot, should_run = service.apply_event(args.session_id, event)
            if should_run and args.run:
                snapshot = await service.run(args.session_id)
            result = snapshot.model_dump(mode="json")
        elif args.command == "session-export":
            snapshot = service.store.get(args.session_id)
            if args.zip and not args.package:
                raise ValueError("--zip requires --package")
            if args.summary and args.audit:
                raise ValueError("--summary and --audit are mutually exclusive")
            if args.package:
                directory = Path(args.output) if args.output else (
                    service.store.root / args.session_id / f"package-v{snapshot.report_version}"
                )
                result = write_report_package(
                    snapshot, service.store, directory, registry=service.registry,
                )
                if args.zip:
                    zip_path = directory.with_suffix(".zip")
                    zip_report_package(directory, zip_path)
                    result["archive"] = str(zip_path.resolve())
            else:
                output = Path(args.output) if args.output else service.store.root / args.session_id / "report.md"
                output.parent.mkdir(parents=True, exist_ok=True)
                if args.summary:
                    text = markdown_summary(snapshot, registry=service.registry)
                elif args.audit:
                    text = audit_report(
                        snapshot, registry=service.registry,
                        artifact_loader=service.store.artifact,
                    )
                else:
                    text = markdown_report(
                        snapshot, registry=service.registry,
                        artifact_loader=service.store.artifact,
                    )
                output.write_text(text, encoding="utf-8")
                result = {"output": str(output.resolve()), "report_version": snapshot.report_version}
        else:
            result = service.store.get(args.session_id).model_dump(mode="json")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        await service.close()
