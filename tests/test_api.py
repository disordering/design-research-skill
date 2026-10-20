import io

from fastapi.testclient import TestClient
from PIL import Image

from engine.api import create_app
from engine.criteria import CriteriaLibrary
from engine.service import ReviewEngine
from engine.stub import StubModel


def _image_bytes() -> bytes:
    image = Image.new("RGB", (640, 360), "white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _factory(provider, model):
    criteria = CriteriaLibrary.load("判据库_v1.json")
    return ReviewEngine(
        criteria,
        StubModel(),
        provider="stub",
        model_name="contract-stub-v1",
        is_stub=True,
    )


def test_health_and_upload_endpoint():
    client = TestClient(create_app(engine_factory=_factory))
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["criteria_rules"] == 24
    assert "config" in health.json()

    response = client.post(
        "/api/review-audit",
        files={"image": ("screen.png", _image_bytes(), "image/png")},
        data={
            "design_goal": "完成设置保存",
            "platform": "web",
            "analysis_mode": "single_pass",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == "1.0"
    assert body["model"]["is_stub"] is True
    assert body["summary"]["rules_total"] == 24
    assert body["findings"][0]["evidence"]["description"]


def test_rejects_invalid_upload():
    client = TestClient(create_app(engine_factory=_factory))
    response = client.post(
        "/api/review-audit",
        files={"image": ("screen.png", b"not-an-image", "image/png")},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_image"


def test_rejects_invalid_platform_value():
    client = TestClient(create_app(engine_factory=_factory))
    response = client.post(
        "/api/review-audit",
        files={"image": ("screen.png", _image_bytes(), "image/png")},
        data={"platform": "toaster"},
    )
    assert response.status_code == 422
