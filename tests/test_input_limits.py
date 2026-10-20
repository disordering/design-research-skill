"""Input boundaries checked without external models or large image allocations."""

import io
from pathlib import Path
import struct
import zlib

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from engine.api import create_app
from engine.criteria import CriteriaLibrary
from engine.errors import EngineError
from engine import imaging
from engine.service import ReviewEngine
from engine.stub import StubModel


ROOT = Path(__file__).resolve().parent.parent
CONTEXT_LIMITS = [("design_goal", 2000), ("scenario", 2000), ("target_user", 1000)]


@pytest.fixture
def client():
    criteria = CriteriaLibrary.load(ROOT / "判据库_v1.json")
    engine = ReviewEngine(
        criteria, StubModel(), provider="stub", model_name="input-limit-test", is_stub=True
    )
    return TestClient(
        create_app(
            criteria_path=ROOT / "判据库_v1.json",
            engine_factory=lambda provider, model: engine,
        )
    )


def _small_png():
    output = io.BytesIO()
    Image.new("RGB", (200, 200), "white").save(output, format="PNG")
    return output.getvalue()


def _png_header(width, height):
    """A valid container header only; never build the advertised pixel buffer."""
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    raw = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b""))
        + chunk(b"IEND", b"")
    )
    assert len(raw) < 100
    return raw


def _upload(client, field, value):
    return client.post(
        "/api/review-audit",
        files={"image": ("screen.png", _small_png(), "image/png")},
        data={field: value, "analysis_mode": "single_pass"},
    )


@pytest.mark.parametrize(("field", "limit"), CONTEXT_LIMITS)
@pytest.mark.parametrize("padded", [False, True])
def test_multipart_context_accepts_exact_trimmed_limit(client, field, limit, padded):
    value = "目" * limit
    submitted = f" \t{value}\n " if padded else value
    response = _upload(client, field, submitted)
    assert response.status_code == 200, response.text
    assert response.json()["context"][field] == value
    assert response.json()["model"]["is_stub"] is True


@pytest.mark.parametrize(("field", "limit"), CONTEXT_LIMITS)
def test_multipart_context_over_limit_after_trimming_has_field_error(client, field, limit):
    response = _upload(client, field, f" \t{'目' * (limit + 1)}\n ")
    assert response.status_code == 422, response.text
    assert any(
        error["loc"] == ["body", field] and error["type"] == "string_too_long"
        for error in response.json()["detail"]
    )


@pytest.mark.parametrize(("field", "limit"), CONTEXT_LIMITS)
def test_multipart_whitespace_is_trimmed_before_length_validation(client, field, limit):
    response = _upload(client, field, " " * (limit + 1))
    assert response.status_code == 200, response.text
    assert response.json()["context"][field] == ""


def test_image_between_pillow_warning_and_error_thresholds_returns_413(client):
    # Pillow normally only warns here; the engine's actual limit is 50 Mpx.
    response = client.post(
        "/api/review-audit",
        files={"image": ("header.png", _png_header(10001, 5000), "image/png")},
        data={"analysis_mode": "single_pass"},
    )
    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "image_pixel_limit"


def test_explicit_pixel_limit_works_without_pillow_guard(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", None)
    with pytest.raises(EngineError) as caught:
        imaging.prepare_image(_png_header(10001, 5000))
    assert caught.value.status_code == 413
    assert caught.value.code == "image_pixel_limit"


def test_exact_pixel_limit_reaches_decode_without_allocating_pixels(monkeypatch):
    class DecodeReached(Exception):
        pass

    def stop_before_decode(source):
        assert source.size == (10000, 5000)
        raise DecodeReached

    monkeypatch.setattr(imaging.ImageOps, "exif_transpose", stop_before_decode)
    with pytest.raises(DecodeReached):
        imaging.prepare_image(_png_header(10000, 5000))


def test_normal_small_image_still_prepares():
    prepared = imaging.prepare_image(_small_png())
    assert (prepared.width, prepared.height) == (200, 200)
    assert (prepared.original_width, prepared.original_height) == (200, 200)
    assert prepared.mime_type == "image/jpeg"
    assert prepared.resized is False
