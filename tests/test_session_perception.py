"""Deterministic perception signals for session evidence, not model accuracy tests."""

import io
import json

from PIL import Image

from engine.session_adapters import Capture
from engine.session_contracts import SourceInput, SourceRecord
from engine.session_perception import analyze_capture


def test_figma_capture_produces_metrics_ocr_elements_and_overlays():
    raw = io.BytesIO()
    Image.new("RGB", (600, 400), "white").save(raw, "PNG")
    source = SourceRecord(input=SourceInput(
        kind="figma_board",
        reference="https://www.figma.com/design/abc/Test?node-id=1-1",
        role="design",
    ))
    capture = Capture(
        content=json.dumps({
            "node": {"width": "1000", "height": "700", "name": "Decompose"},
            "visible_text": [
                {
                    "text": "分解可得 8888", "hidden": False,
                    "x": 100, "y": 500, "width": 220, "height": 40,
                },
            ],
        }, ensure_ascii=False),
        locator={"node_id": "1:1", "requested_node_id": "1:1"},
        state_id="state-1",
        image=raw.getvalue(),
        controls=[{
            "node_id": "1:2", "name": "分解", "kind": "rounded-rectangle",
            "hidden": False, "x": 700, "y": 520, "width": 180, "height": 80,
        }],
    )
    result = analyze_capture(source, capture)
    assert result is not None
    assert result.summary["element_count"] == 1
    assert result.summary["ocr_block_count"] == 1
    assert result.summary["arrow_count"] == 0
    assert result.summary["global"]["negative_space_proxy"] >= 0
    assert result.metrics["readability"]["text_block_count"] == 1
    assert result.overlays.keys() == {
        "overlay-elements.png", "overlay-focus.png", "overlay-flow.png",
    }
    assert Image.open(io.BytesIO(result.overlays["overlay-elements.png"])).size == (600, 400)


def test_figma_connector_is_extracted_separately_from_ui_controls():
    raw = io.BytesIO()
    Image.new("RGB", (600, 400), "white").save(raw, "PNG")
    source = SourceRecord(input=SourceInput(
        kind="figma_board",
        reference="https://www.figma.com/design/abc/Test?node-id=1-1",
        role="design",
    ))
    capture = Capture(
        content=json.dumps({
            "node": {"width": "1000", "height": "1000", "name": "Flow"},
            "inspection_targets": [{
                "node_id": "1:2", "name": "Screen image", "screen_like": True,
                "container": False, "x": 0, "y": 100, "width": 600, "height": 300,
            }],
            "arrow_annotations": [{
                "node_id": "1:3", "name": "Arrow 1", "direction": "horizontal",
                "x": 50, "y": 200, "width": 400, "height": 0,
                "nearby_targets": ["1:2"],
            }],
        }, ensure_ascii=False),
        locator={"node_id": "1:1", "requested_node_id": "1:1"},
        state_id="state-connector",
        image=raw.getvalue(),
        controls=[
            {
                "node_id": "1:2", "name": "Screen image", "kind": "rounded-rectangle",
                "hidden": False, "container": False, "screen_like": True,
                "x": 0, "y": 100, "width": 600, "height": 300,
            },
            {
                "node_id": "1:3", "name": "Arrow 1", "kind": "vector",
                "hidden": False, "container": False, "annotation": "arrow",
                "direction": "horizontal", "nearby_targets": ["1:2"],
                "x": 50, "y": 200, "width": 400, "height": 0,
            },
        ],
    )
    result = analyze_capture(source, capture)
    assert result is not None
    assert result.summary["arrow_count"] == 1
    assert result.summary["connector_element_count"] == 1
    assert result.summary["element_count"] == 1
    arrow = result.summary["arrow_annotations"][0]
    assert arrow["orientation"] == "horizontal"
    assert arrow["nearby_targets"][0]["name"] == "Screen image"
    assert result.metrics["focus"]["elements"]
    assert all(row["role"] != "connector" for row in result.metrics["focus"]["elements"])
