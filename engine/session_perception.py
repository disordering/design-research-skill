"""Deterministic perception metrics for session evidence."""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw

from .advanced_contracts import NormalizedBox, OCRBlock, OCRResult, UIElement, UIResult
from .cv_metrics import compute_pipeline_metrics
from .imaging import MIN_IMAGE_DIMENSION
from .session_adapters import Capture, FigmaMCPAdapter
from .session_contracts import SessionSnapshot, SourceRecord
from .session_objects import attach_evidence_objects


@dataclass
class PerceptionResult:
    metrics: dict[str, Any]
    ui: UIResult
    ocr: OCRResult
    overlays: dict[str, bytes]
    summary: dict[str, Any]


def _box(x: float, y: float, width: float, height: float) -> NormalizedBox | None:
    if width <= 0 or height <= 0:
        return None
    x = min(max(x, 0.0), 0.999)
    y = min(max(y, 0.0), 0.999)
    width = min(width, 1.0 - x)
    height = min(height, 1.0 - y)
    if width <= 0.0001 or height <= 0.0001:
        return None
    return NormalizedBox(x=x, y=y, width=width, height=height)


def _line_box(
    x: float, y: float, width: float, height: float, *,
    min_thickness: float = 0.0015,
) -> NormalizedBox | None:
    """Keep zero-height Figma connectors visible without pretending they are controls."""
    if width <= 0 and height <= 0:
        return None
    if width <= 0:
        x = max(0.0, x - min_thickness / 2)
    if height <= 0:
        y = max(0.0, y - min_thickness / 2)
    return _box(
        x, y,
        max(width, min_thickness),
        max(height, min_thickness),
    )


def _role_for_control(control: dict[str, Any]) -> tuple[str, float, bool]:
    label = str(control.get("name") or control.get("label") or "").lower()
    tag = str(
        control.get("role") or control.get("kind") or control.get("tag") or ""
    ).lower()
    if control.get("annotation") == "arrow":
        return "connector", 0.25, False
    if any(word in label for word in ("image", "截图", "界面", "screen")):
        return "panel", 0.7, False
    if any(word in label for word in (
        "按钮", "button", "确定", "取消", "保存", "提交",
        "继续", "返回", "confirm", "cancel", "save", "submit",
    )):
        return "primary_button", 0.9, True
    if tag in {"a", "button"} or control.get("disabled") is False and tag in {"input", "select"}:
        return "button", 0.7, True
    if any(word in label for word in ("导航", "页签", "nav", "tab")):
        return "nav", 0.65, True
    if any(word in label for word in ("标题", "title")):
        return "title", 0.75, False
    return "other", 0.45, False


def _figma_perception(
    capture: Capture, image: Image.Image,
) -> tuple[list[UIElement], list[OCRBlock], str, list[dict[str, Any]]]:
    try:
        data = json.loads(capture.content)
    except ValueError:
        return [], [], "figma", []
    node = data.get("node") if isinstance(data.get("node"), dict) else {}
    try:
        root_width = float(node.get("width") or image.width)
        root_height = float(node.get("height") or image.height)
    except (TypeError, ValueError):
        root_width, root_height = float(image.width), float(image.height)
    elements: list[UIElement] = []
    ocr_blocks: list[OCRBlock] = []
    target_names = {
        str(item.get("node_id")): str(item.get("name") or item.get("node_id"))
        for item in data.get("inspection_targets", [])
        if isinstance(item, dict) and item.get("node_id")
    }
    arrows: list[dict[str, Any]] = []
    for item in data.get("arrow_annotations", []):
        if not isinstance(item, dict) or item.get("hidden"):
            continue
        bbox = _line_box(
            float(item.get("x", 0)) / root_width,
            float(item.get("y", 0)) / root_height,
            float(item.get("width", 0)) / root_width,
            float(item.get("height", 0)) / root_height,
        )
        if bbox is None:
            continue
        nearby = [str(node_id) for node_id in item.get("nearby_targets", [])]
        arrows.append({
            "node_id": str(item.get("node_id") or ""),
            "name": str(item.get("name") or ""),
            "orientation": str(item.get("direction") or "unknown"),
            "bbox": bbox.as_list(),
            "nearby_targets": [
                {"node_id": node_id, "name": target_names.get(node_id, node_id)}
                for node_id in nearby
            ],
            "semantics": "unclassified",
            "basis": "Figma connector geometry; arrow direction and transition meaning require visual/textual confirmation.",
        })
    for text in data.get("visible_text", []):
        if not isinstance(text, dict) or text.get("hidden"):
            continue
        bbox = _box(
            float(text.get("x", 0)) / root_width,
            float(text.get("y", 0)) / root_height,
            float(text.get("width", 0)) / root_width,
            float(text.get("height", 0)) / root_height,
        )
        if bbox is None or not str(text.get("text", "")).strip():
            continue
        ocr_blocks.append(OCRBlock(
            text=str(text["text"]).strip()[:2000],
            bbox=bbox,
            confidence=0.9,
            estimated_height_px=max(
                1.0,
                float(text.get("height", 0)) / root_height * image.height,
            ),
        ))
    for control in capture.controls:
        if not isinstance(control, dict) or control.get("hidden"):
            continue
        if control.get("container"):
            continue
        box_fn = _line_box if control.get("annotation") == "arrow" else _box
        bbox = box_fn(
            float(control.get("x", 0)) / root_width,
            float(control.get("y", 0)) / root_height,
            float(control.get("width", 0)) / root_width,
            float(control.get("height", 0)) / root_height,
        )
        if bbox is None:
            continue
        role, importance, interactable = _role_for_control(control)
        elements.append(UIElement(
            id=f"E{len(elements) + 1:02d}",
            label=str(control.get("name") or control.get("label") or "")[:500],
            role=role,
            bbox=bbox,
            interactable=interactable,
            visual_importance=importance,
            state="default",
            confidence=0.85,
        ))
    page_type = str(node.get("name") or "figma")
    return elements, ocr_blocks, page_type, arrows


def _browser_perception(
    capture: Capture, image: Image.Image,
) -> tuple[list[UIElement], list[OCRBlock], str]:
    geometry = capture.locator.get("image_geometry", {})
    region = geometry.get("region") if isinstance(geometry, dict) else {}
    region = region if isinstance(region, dict) else {}
    try:
        region_width = float(region.get("width") or image.width)
        region_height = float(region.get("height") or image.height)
        region_x = float(region.get("x") or 0)
        region_y = float(region.get("y") or 0)
    except (TypeError, ValueError):
        region_width, region_height = float(image.width), float(image.height)
        region_x = region_y = 0.0
    elements = []
    for control in capture.controls:
        if not isinstance(control, dict):
            continue
        bbox = _box(
            (float(control.get("x", 0)) - region_x) / region_width,
            (float(control.get("y", 0)) - region_y) / region_height,
            float(control.get("width", 0)) / region_width,
            float(control.get("height", 0)) / region_height,
        )
        if bbox is None:
            continue
        role, importance, interactable = _role_for_control(control)
        elements.append(UIElement(
            id=f"E{len(elements) + 1:02d}",
            label=str(control.get("label") or control.get("name") or "")[:500],
            role=role,
            bbox=bbox,
            interactable=interactable and not bool(control.get("disabled")),
            visual_importance=importance,
            state=(
                "checked" if control.get("checked")
                else "selected" if control.get("ariaSelected") == "true"
                else "expanded" if control.get("ariaExpanded") == "true"
                else "pressed" if control.get("ariaPressed") == "true"
                else "default"
            ),
            confidence=0.9,
        ))
    return elements, [], str(capture.locator.get("title") or "web")


def _draw_overlays(
    image: Image.Image, ui: UIResult, metrics: dict[str, Any],
    arrows: list[dict[str, Any]],
) -> dict[str, bytes]:
    colors = {
        "primary_button": "#ff3b30", "button": "#ff9500", "nav": "#007aff",
        "panel": "#34c759", "title": "#af52de", "connector": "#00b8d9",
        "other": "#8e8e93",
    }
    elements = image.copy()
    draw = ImageDraw.Draw(elements)
    for element in ui.elements:
        x1 = round(element.bbox.x * image.width)
        y1 = round(element.bbox.y * image.height)
        x2 = round((element.bbox.x + element.bbox.width) * image.width)
        y2 = round((element.bbox.y + element.bbox.height) * image.height)
        color = colors.get(element.role, "#8e8e93")
        draw.rectangle((x1, y1, x2, y2), outline=color, width=3)
        draw.text((x1 + 3, max(0, y1 - 12)), f"{element.id} {element.role}", fill=color)
    focus = image.convert("RGBA")
    overlay = Image.new("RGBA", focus.size, (0, 0, 0, 0))
    focus_draw = ImageDraw.Draw(overlay)
    rows = metrics.get("focus", {}).get("elements", [])
    max_share = max((float(row.get("focus_share", 0)) for row in rows), default=1.0)
    for row in rows:
        x, y, width, height = row.get("bbox", [0, 0, 0, 0])
        alpha = int(35 + 145 * float(row.get("focus_share", 0)) / max(0.0001, max_share))
        focus_draw.rectangle(
            (
                round(x * image.width), round(y * image.height),
                round((x + width) * image.width), round((y + height) * image.height),
            ),
            fill=(255, 48, 48, min(180, alpha)),
        )
    focus = Image.alpha_composite(focus, overlay).convert("RGB")
    flow = image.copy()
    flow_draw = ImageDraw.Draw(flow)
    for index, arrow in enumerate(arrows, start=1):
        x, y, width, height = arrow["bbox"]
        x1 = round(x * image.width)
        x2 = round((x + width) * image.width)
        y1 = round(y * image.height)
        y2 = round((y + height) * image.height)
        flow_draw.line((x1, y1, x2, y2), fill="#00b8d9", width=4)
        targets = ", ".join(
            target["node_id"] for target in arrow.get("nearby_targets", [])
        ) or "no adjacent screen"
        flow_draw.text(
            (x1 + 4, max(0, y1 - 14)),
            f"C{index} {arrow.get('orientation', 'unknown')} -> {targets}",
            fill="#00758a",
        )
    result = {}
    for name, canvas in (
        ("overlay-elements.png", elements),
        ("overlay-focus.png", focus),
        ("overlay-flow.png", flow),
    ):
        output = io.BytesIO()
        canvas.save(output, "PNG")
        result[name] = output.getvalue()
    return result


def analyze_capture(
    source: SourceRecord, capture: Capture, *, include_geometry: bool = True,
) -> PerceptionResult | None:
    if not capture.image or capture.partial:
        return None
    try:
        image = Image.open(io.BytesIO(capture.image)).convert("RGB")
    except Exception:
        return None
    if not include_geometry:
        elements, blocks, page_type, arrows = [], [], source.input.kind, []
    elif source.input.kind == "figma_board":
        elements, blocks, page_type, arrows = _figma_perception(capture, image)
    elif source.input.kind in {"website", "figma_prototype"}:
        elements, blocks, page_type = _browser_perception(capture, image)
        arrows = []
    else:
        elements, blocks, page_type, arrows = [], [], source.input.kind, []
    ui = UIResult(page_type=page_type, elements=elements)
    ocr = OCRResult(blocks=blocks)
    metrics = compute_pipeline_metrics(image, elements, blocks)
    overlays = _draw_overlays(image, ui, metrics, arrows)
    focus = [
        item for item in metrics.get("focus", {}).get("elements", [])
        if item.get("role") != "connector"
    ][:5]
    def accessibility_count(node: dict[str, Any] | None) -> int:
        if not isinstance(node, dict):
            return 0
        return 1 + sum(
            accessibility_count(child)
            for child in node.get("children", [])
            if isinstance(child, dict)
        )

    accessibility_nodes = accessibility_count(capture.locator.get("accessibility"))
    summary = {
        "metric_version": metrics.get("metric_version"),
        "geometry_available": include_geometry,
        "geometry_note": (
            "" if include_geometry
            else "旧证据未保存可直接归一化的元素绝对坐标；仅计算不依赖元素框的全局视觉指标。"
        ),
        "element_count": sum(element.role != "connector" for element in elements),
        "connector_element_count": sum(element.role == "connector" for element in elements),
        "ocr_block_count": len(blocks),
        "visible_text_node_count": len(blocks),
        "screen_crop": bool(capture.locator.get("requested_node_id") != capture.locator.get("node_id")),
        "crop_kind": (
            "full_screen"
            if (
                capture.locator.get("requested_node_id") != capture.locator.get("node_id")
                and image.width >= 800 and image.height >= 450
            )
            else "supporting_crop"
            if capture.locator.get("requested_node_id") != capture.locator.get("node_id")
            else "source_capture"
        ),
        "model_image_eligible": min(image.size) >= MIN_IMAGE_DIMENSION,
        "arrow_count": len(arrows),
        "arrow_annotations": arrows,
        "arrow_interpretation_note": (
            "箭头几何只确定画布位置、轴向和邻接画板；具体语义必须结合画面与说明核对，"
            "不能仅凭节点名断言跳转或因果关系。"
        ),
        "source_modalities": [
            *(["figma_metadata_text"] if blocks else []),
            *(["figma_screen_image"] if capture.image else []),
            *(["figma_connector_geometry"] if arrows else []),
            *(["screenshot_pixels"] if capture.image else []),
            *(["browser_accessibility_tree"] if accessibility_nodes else []),
        ],
        "accessibility_node_count": accessibility_nodes,
        "measurement_scale_limited": bool(
            image.width < 700 and image.height / max(1, image.width) > 2
        ),
        "measurement_scale_note": (
            "长流程总图在截图端被整体缩小；小字、局部对比和元素框可作索引，"
            "不能脱离局部高分辨率画面直接判可读性问题。"
            if image.width < 700 and image.height / max(1, image.width) > 2 else ""
        ),
        "focus_top": [
            {
                "rank": item.get("rank"), "element_id": item.get("element_id"),
                "label": item.get("label"), "role": item.get("role"),
                "bbox": item.get("bbox"), "focus_share": item.get("focus_share"),
            }
            for item in focus
        ],
        "readability": {
            key: metrics.get("readability", {}).get(key)
            for key in (
                "text_block_count", "low_contrast_count",
                "small_text_candidate_count", "estimated_height_p10",
                "local_contrast_p10",
            )
        },
        "global": metrics.get("global", {}),
        "density": metrics.get("density", {}),
        "style": metrics.get("style", {}),
    }
    return PerceptionResult(metrics=metrics, ui=ui, ocr=ocr, overlays=overlays, summary=summary)


def attach_missing_perception(session: SessionSnapshot, store) -> int:
    """Backfill deterministic perception for sessions captured before analysis support."""
    sources = {source.source_id: source for source in session.sources}
    attached = 0
    for evidence in session.evidence:
        if evidence.stale or not evidence.artifact_id:
            continue
        if (
            evidence.analysis_artifact_id
            and evidence.analysis.get("geometry_available")
            and "measurement_scale_limited" in evidence.analysis
        ):
            continue
        source = sources.get(evidence.source_id)
        if source is None or not source.active:
            continue
        try:
            path, _ = store.artifact(session.session_id, evidence.artifact_id)
            capture = Capture(
                content=evidence.content,
                locator=evidence.locator,
                state_id=evidence.state_id or evidence.evidence_id,
                image=path.read_bytes(),
                controls=evidence.locator.get("controls", []),
            )
            geometry_rebuilt = False
            if source.input.kind == "figma_board" and evidence.raw_artifact_id:
                raw_path, _ = store.artifact(session.session_id, evidence.raw_artifact_id)
                tree, texts, visual = FigmaMCPAdapter._structure_index(
                    raw_path.read_text(encoding="utf-8"),
                )
                if tree is not None:
                    content = {
                        "node": tree.attrib,
                        "visible_text": [item for item in texts if not item["hidden"]],
                        "hidden_text": [item for item in texts if item["hidden"]],
                        "inspection_targets": visual,
                    }
                    controls = [
                        {
                            "node_id": item["node_id"], "name": item["name"],
                            "kind": item["type"], "hidden": item["hidden"],
                            "container": item["container"], "screen_like": item["screen_like"],
                        "annotation": item.get("annotation", ""),
                        "direction": item.get("direction"),
                        "nearby_targets": item.get("nearby_targets", []),
                            "x": item["x"], "y": item["y"],
                            "width": item["width"], "height": item["height"],
                        }
                        for item in visual
                    ]
                    capture = Capture(
                        content=json.dumps(content, ensure_ascii=False),
                        locator=capture.locator,
                        state_id=capture.state_id,
                        image=capture.image,
                        controls=controls,
                        raw_content=raw_path.read_text(encoding="utf-8"),
                    )
                    geometry_rebuilt = True
            attach_evidence_objects(evidence, source, capture)
            perception = analyze_capture(
                source, capture, include_geometry=geometry_rebuilt,
            )
            if perception is None:
                continue
            evidence.analysis_artifact_id = store.write_artifact(
                session.session_id,
                json.dumps({
                    "source_id": evidence.source_id,
                    "evidence_id": evidence.evidence_id,
                    "state_id": evidence.state_id,
                    "metrics": perception.metrics,
                    "ui": perception.ui.model_dump(mode="json"),
                    "ocr": perception.ocr.model_dump(mode="json"),
                }, ensure_ascii=False, indent=2).encode("utf-8"),
                "application/json",
            )
            evidence.overlay_artifact_ids = {
                name: store.write_artifact(session.session_id, data, "image/png")
                for name, data in perception.overlays.items()
            }
            evidence.analysis = {
                **perception.summary,
                "analysis_source": (
                    "reconstructed_from_original_metadata"
                    if geometry_rebuilt else "backfill_global_only"
                ),
                "analysis_artifact_id": evidence.analysis_artifact_id,
                "overlay_artifact_ids": evidence.overlay_artifact_ids,
            }
            attached += 1
        except Exception:
            continue
    return attached
