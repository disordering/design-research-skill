"""Canonical evidence objects shared by planning, actions, findings and rechecks."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .session_adapters import Capture
from .session_contracts import Evidence, EvidenceObject, SourceRecord


def object_id(source_id: str, kind: str, key: str) -> str:
    value = f"{source_id}|{kind}|{key}"
    return "obj-" + hashlib.sha256(value.encode()).hexdigest()[:20]


def _as_text(value: Any, limit: int = 1000) -> str:
    return " ".join(str(value or "").split())[:limit]


def _add(
    result: list[EvidenceObject],
    *,
    source: SourceRecord,
    state_id: str,
    kind: str,
    key: str,
    label: str = "",
    role: str = "",
    locator: dict[str, Any] | None = None,
    interactable: bool = False,
    attributes: dict[str, Any] | None = None,
    bbox: dict[str, float] | None = None,
    identity_key: str | None = None,
) -> None:
    stable_key = identity_key or key
    result.append(EvidenceObject(
        object_id=object_id(source.source_id, kind, stable_key),
        identity_key=stable_key,
        kind=kind,
        source_id=source.source_id,
        state_id=state_id,
        label=_as_text(label),
        role=_as_text(role, 100),
        bbox=bbox or {},
        locator=locator or {},
        interactable=interactable,
        attributes=attributes or {},
    ))


def attach_evidence_objects(
    evidence: Evidence,
    source: SourceRecord,
    capture: Capture,
) -> None:
    objects: list[EvidenceObject] = []
    state_id = capture.state_id
    locator = capture.locator
    page_reference = (
        locator.get("url")
        or locator.get("node_id")
        or locator.get("reference")
        or source.source_id
    )
    _add(
        objects,
        source=source, state_id=state_id, kind="page",
        key=str(page_reference),
        label=(
            locator.get("title")
            or locator.get("node_id")
            or source.input.title
            or source.input.reference
        ),
        role=source.input.kind,
        locator={
            key: locator[key]
            for key in ("url", "title", "node_id", "reference", "chunk_index")
            if key in locator
        },
    )

    if source.input.kind == "document":
        _add(
            objects,
            source=source, state_id=state_id, kind="document_section",
            key=f"chunk-{locator.get('chunk_index', 0)}",
            label=source.input.title or source.input.reference,
            role="document",
            locator={
                key: locator[key]
                for key in (
                    "reference", "resolved_reference", "chunk_index",
                    "chunk_count", "start_line", "end_line",
                )
                if key in locator
            },
            attributes={"excerpt": _as_text(capture.content, 500)},
        )
    elif source.input.kind == "image":
        _add(
            objects,
            source=source, state_id=state_id, kind="image",
            key="screenshot",
            label=source.input.title or "uploaded-image",
            role="image",
            locator={"sha256": locator.get("sha256")},
        )

    control_counts: dict[str, int] = {}
    for control in capture.controls[:180]:
        if not isinstance(control, dict):
            continue
        selector = control.get("selector") or ""
        node_id = control.get("node_id") or ""
        label = control.get("label") or control.get("name") or ""
        key = selector or node_id or f"{label}:{control.get('x')}:{control.get('y')}"
        if not key:
            continue
        control_kind = (
            "region"
            if source.input.kind == "figma_board" and control.get("container")
            else "node"
            if source.input.kind == "figma_board"
            else "control"
        )
        if node_id:
            stable_key = f"node:{node_id}"
        elif control.get("testId"):
            stable_key = f"test:{control['testId']}"
        elif control.get("domId"):
            stable_key = f"id:{control['domId']}"
        elif control.get("name"):
            stable_key = (
                f"name:{control.get('tag') or control.get('role') or 'control'}:"
                f"{control['name']}:{control.get('type') or ''}"
            )
        else:
            role_key = _as_text(
                control.get("role") or control.get("tag") or control_kind,
                100,
            )
            label_key = _as_text(
                control.get("ariaLabel") or control.get("label") or control.get("name"),
                500,
            )
            signature = f"{role_key}|{label_key}"
            ordinal = control_counts.get(signature, 0)
            control_counts[signature] = ordinal + 1
            stable_key = (
                f"control:{signature}|{control.get('ancestorPath') or ''}|{ordinal}"
            )
        _add(
            objects,
            source=source, state_id=state_id, kind=control_kind,
            key=str(key),
            label=label,
            role=control.get("role") or control.get("tag") or control.get("kind") or "control",
            locator={
                key_name: control[key_name]
                for key_name in (
                    "selector", "node_id", "label", "name", "tag",
                    "type", "domId", "testId", "ancestorPath",
                    "x", "y", "width", "height",
                )
                if key_name in control
            },
            interactable=control_kind == "control" and not bool(control.get("disabled")),
            attributes={
                key_name: control[key_name]
                for key_name in (
                    "checked", "ariaSelected", "ariaPressed",
                    "ariaExpanded", "ariaLabel", "title",
                    "domId", "name", "testId", "ancestorPath",
                    "fontSizePx", "fontWeight", "color", "backgroundColor",
                    "contrastRatio", "opacity", "textDecoration", "visibility", "role",
                    "value", "hidden", "annotation", "direction",
                )
                if key_name in control
            },
            identity_key=stable_key,
        )

    try:
        data = json.loads(capture.content)
    except (TypeError, ValueError):
        data = None
    if isinstance(data, dict):
        for item in data.get("visible_text", [])[:300]:
            if not isinstance(item, dict) or item.get("hidden"):
                continue
            node_id = str(item.get("node_id") or "")
            text = _as_text(item.get("text"), 2000)
            if not node_id or not text:
                continue
            _add(
                objects,
                source=source, state_id=state_id, kind="text",
                key=node_id,
                label=text,
                role="text",
                locator={
                    "node_id": node_id,
                    "x": item.get("x"), "y": item.get("y"),
                    "width": item.get("width"), "height": item.get("height"),
                },
            )
        for item in data.get("inspection_targets", [])[:120]:
            if not isinstance(item, dict) or item.get("hidden"):
                continue
            node_id = str(item.get("node_id") or "")
            if not node_id:
                continue
            kind = "region" if item.get("container") else "node"
            _add(
                objects,
                source=source, state_id=state_id, kind=kind,
                key=node_id,
                label=item.get("name") or node_id,
                role=item.get("type") or kind,
                locator={
                    "node_id": node_id,
                    "x": item.get("x"), "y": item.get("y"),
                    "width": item.get("width"), "height": item.get("height"),
                },
                attributes={
                    "screen_like": item.get("screen_like"),
                    "slide_like": item.get("slide_like"),
                },
            )

    deduplicated = {}
    for item in objects:
        deduplicated.setdefault(item.object_id, item)
    evidence.objects = list(deduplicated.values())[:400]


def object_index(session) -> dict[str, EvidenceObject]:
    return {
        item.object_id: item
        for evidence in session.evidence
        if not evidence.stale
        for item in evidence.objects
    }


def object_bbox(evidence: Evidence, item: EvidenceObject) -> dict[str, float] | None:
    if item.bbox:
        return item.bbox
    locator = item.locator
    try:
        x = float(locator.get("x"))
        y = float(locator.get("y"))
        width = float(locator.get("width"))
        height = float(locator.get("height"))
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    geometry = evidence.locator.get("image_geometry", {})
    region = geometry.get("region") if isinstance(geometry, dict) else None
    if isinstance(region, dict) and region.get("width") and region.get("height"):
        offset_x = float(region.get("x") or 0)
        offset_y = float(region.get("y") or 0)
        total_width = float(region["width"])
        total_height = float(region["height"])
    elif evidence.locator.get("screenshot_width") and evidence.locator.get("screenshot_height"):
        offset_x = offset_y = 0.0
        total_width = float(evidence.locator["screenshot_width"])
        total_height = float(evidence.locator["screenshot_height"])
    else:
        try:
            data = json.loads(evidence.content)
            node = data.get("node", {}) if isinstance(data, dict) else {}
            total_width = float(node.get("width"))
            total_height = float(node.get("height"))
        except (TypeError, ValueError, AttributeError):
            return None
        offset_x = offset_y = 0.0
    if total_width <= 0 or total_height <= 0:
        return None
    return {
        "x": max(0.0, (x - offset_x) / total_width),
        "y": max(0.0, (y - offset_y) / total_height),
        "width": min(1.0, width / total_width),
        "height": min(1.0, height / total_height),
    }


def match_object_to_bbox(
    evidence: Evidence,
    bbox: dict[str, Any],
) -> EvidenceObject | None:
    try:
        target_x = float(bbox["x"])
        target_y = float(bbox["y"])
        target_w = float(bbox["width"])
        target_h = float(bbox["height"])
    except (KeyError, TypeError, ValueError):
        return None
    if target_w <= 0 or target_h <= 0:
        return None
    target_center_x = target_x + target_w / 2
    target_center_y = target_y + target_h / 2
    best = None
    best_score = 0.0
    for item in evidence.objects:
        if item.kind == "page":
            continue
        candidate = object_bbox(evidence, item)
        if candidate is None:
            continue
        left = max(target_x, candidate["x"])
        top = max(target_y, candidate["y"])
        right = min(
            target_x + target_w,
            candidate["x"] + candidate["width"],
        )
        bottom = min(
            target_y + target_h,
            candidate["y"] + candidate["height"],
        )
        intersection = max(0.0, right - left) * max(0.0, bottom - top)
        union = (
            target_w * target_h
            + candidate["width"] * candidate["height"]
            - intersection
        )
        iou = intersection / union if union else 0.0
        center_inside = (
            candidate["x"] <= target_center_x <= candidate["x"] + candidate["width"]
            and candidate["y"] <= target_center_y <= candidate["y"] + candidate["height"]
        )
        score = iou + (0.1 if center_inside else 0.0)
        if score > best_score:
            best = item
            best_score = score
    return best
