"""针对 D 发现的四项程序缺陷进行离线回归检查。

所有模型回复均使用固定的模拟结果，不调用联网模型。
"""
from __future__ import annotations

import asyncio
import base64
import io
from pathlib import Path
import struct
import zlib

SOURCE = Path(__file__).resolve().parents[1]

from fastapi.testclient import TestClient
from PIL import Image

from engine.api import create_app
from engine.contracts import RawAuditResult, ScreenAnalysis
from engine.criteria import CriteriaLibrary
from engine.model import ModelCallResult
from engine.service import ReviewEngine
from engine.stub import StubModel


class SequenceModel:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    async def complete(self, messages, *, json_mode=True, extra_body=None):
        self.calls += 1
        text = self.outputs.pop(0)
        return ModelCallResult(text=text, provider="offline-sequence", model="test-only",
                               usage={}, request_id=None, latency_ms=0, json_mode_used=True)


def criteria():
    return CriteriaLibrary.load(SOURCE / "判据库_v1.json")


def engine(model=None):
    return ReviewEngine(criteria(), model or StubModel(), provider="offline-test",
                        model_name="test-only", is_stub=True)


def client(model=None):
    instance = engine(model)
    return TestClient(create_app(criteria_path=SOURCE / "判据库_v1.json",
                                engine_factory=lambda provider, model: instance),
                      raise_server_exceptions=False)


def png_bytes():
    out = io.BytesIO()
    Image.new("RGB", (640, 360), "white").save(out, format="PNG")
    return out.getvalue()


def huge_header_png():
    """用小文件声明超大图片尺寸，不分配对应的大块内存。"""
    def chunk(kind, value):
        return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 100000, 100000, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00")) + chunk(b"IEND", b""))


def test_invalid_model_json_can_be_repaired_once():
    model = SequenceModel(["not JSON", '{"page_type":"repaired-screen"}'])
    result, warnings = asyncio.run(engine(model)._request_validated(
        [], ScreenAnalysis, repair_contract="{}", label="test observation"))
    assert model.calls == 2
    assert result.page_type == "repaired-screen"
    assert len(warnings) == 1


def test_twice_invalid_model_json_returns_structured_502():
    model = SequenceModel(["not JSON", "still not JSON"])
    response = client(model).post("/api/review-audit",
        files={"image": ("screen.png", png_bytes(), "image/png")},
        data={"analysis_mode": "single_pass"})
    assert response.status_code == 502, f"actual={response.status_code}, body={response.text}, model_calls={model.calls}"
    assert response.json()["error"]["code"] == "model_contract_failed"
    assert model.calls == 2


def test_duplicate_rule_findings_keep_higher_confidence():
    def finding(confidence, title):
        return {"rule_ids": ["R01"], "title": title, "severity": "medium",
                "confidence": confidence, "detection": "Visible test evidence",
                "description": "Test user consequence", "suggestion": "Test repair suggestion",
                "evidence": {"x": 0, "y": 0, "width": 0.1, "height": 0.1,
                             "description": "Test region"}}
    raw = RawAuditResult.model_validate({
        "rule_statuses": [{"rule_id": "R01", "decision": "candidate_issue", "confidence": 0.9}],
        "findings": [finding(0.2, "low confidence first"), finding(0.9, "high confidence second")]})
    findings, _, warnings = engine()._normalize(raw)
    assert len(findings) == 1
    assert findings[0].confidence == 0.9, f"actual_confidence={findings[0].confidence}, title={findings[0].title}"
    assert findings[0].title == "high confidence second"


def test_excessive_image_dimensions_return_structured_413():
    raw = huge_header_png()
    assert len(raw) < 100, "This test must not allocate a large image."
    response = client().post("/api/review-audit",
        files={"image": ("huge-header.png", raw, "image/png")},
        data={"analysis_mode": "single_pass"})
    assert response.status_code == 413, f"actual={response.status_code}, body={response.text}, input_bytes={len(raw)}"
    assert response.json()["error"]["code"] == "image_pixel_limit"


def test_multipart_design_goal_over_limit_returns_422():
    response = client().post("/api/review-audit",
        files={"image": ("screen.png", png_bytes(), "image/png")},
        data={"design_goal": "a" * 2001, "analysis_mode": "single_pass"})
    assert response.status_code == 422, f"actual={response.status_code}, body={response.text}"


def test_valid_base64_returns_flagged_stub_contract():
    response = client().post("/api/review-audit/base64", json={
        "image_base64": base64.b64encode(png_bytes()).decode("ascii"),
        "analysis_mode": "single_pass"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["model"]["is_stub"] is True
    assert result["summary"]["rules_total"] == 24
    assert len(result["rule_results"]) == 24


def test_invalid_base64_returns_structured_422():
    response = client().post("/api/review-audit/base64", json={"image_base64": "!" * 40})
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_base64_image"


def test_json_design_goal_over_limit_returns_422():
    response = client().post("/api/review-audit/base64", json={
        "image_base64": base64.b64encode(png_bytes()).decode("ascii"),
        "design_goal": "a" * 2001, "analysis_mode": "single_pass"})
    assert response.status_code == 422, response.text
    assert any(item["loc"][-1] == "design_goal" for item in response.json()["detail"])
