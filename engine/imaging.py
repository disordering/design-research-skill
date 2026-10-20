"""Safe screenshot normalization for multimodal model input."""

from __future__ import annotations

import base64
import hashlib
import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import EngineError

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_SOURCE_PIXELS = 50_000_000
MAX_MODEL_DIMENSION = 2048
MIN_IMAGE_DIMENSION = 200
SUPPORTED_FORMATS = {"PNG", "JPEG", "WEBP"}

Image.MAX_IMAGE_PIXELS = MAX_SOURCE_PIXELS


@dataclass(frozen=True)
class PreparedImage:
    data_url: str
    mime_type: str
    width: int
    height: int
    original_width: int
    original_height: int
    sha256: str
    resized: bool


def prepare_image(raw: bytes, *, filename: str = "screenshot") -> PreparedImage:
    if not raw:
        raise EngineError("empty_image", "Uploaded image is empty.", status_code=400)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise EngineError(
            "image_too_large",
            f"Image exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
            status_code=413,
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as probe:
                _check_pixel_limit(probe)
                image_format = probe.format
                probe.verify()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise EngineError(
            "image_pixel_limit",
            "Image contains too many pixels to process safely.",
            status_code=413,
        ) from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise EngineError(
            "unsupported_image",
            f"Could not decode {filename} as an image.",
            status_code=415,
        ) from exc

    if image_format not in SUPPORTED_FORMATS:
        raise EngineError(
            "unsupported_image_format",
            f"Supported image formats are PNG, JPEG, and WEBP; received {image_format or 'unknown'}.",
            status_code=415,
        )

    try:
        with Image.open(io.BytesIO(raw)) as source:
            _check_pixel_limit(source)
            source = ImageOps.exif_transpose(source)
            original_width, original_height = source.size
            if min(original_width, original_height) < MIN_IMAGE_DIMENSION:
                raise EngineError(
                    "image_too_small",
                    f"Screenshot must be at least {MIN_IMAGE_DIMENSION}x{MIN_IMAGE_DIMENSION}px.",
                    status_code=422,
                )

            if source.mode in {"RGBA", "LA"} or (
                source.mode == "P" and "transparency" in source.info
            ):
                rgba = source.convert("RGBA")
                flattened = Image.new("RGB", rgba.size, (255, 255, 255))
                flattened.paste(rgba, mask=rgba.getchannel("A"))
                normalized = flattened
            else:
                normalized = source.convert("RGB")

            resized = max(normalized.size) > MAX_MODEL_DIMENSION
            if resized:
                normalized.thumbnail(
                    (MAX_MODEL_DIMENSION, MAX_MODEL_DIMENSION),
                    Image.Resampling.LANCZOS,
                )

            width, height = normalized.size
            output = io.BytesIO()
            normalized.save(output, format="JPEG", quality=90, optimize=True)
    except Image.DecompressionBombError as exc:
        raise EngineError(
            "image_pixel_limit",
            "Image contains too many pixels to process safely.",
            status_code=413,
        ) from exc

    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return PreparedImage(
        data_url=f"data:image/jpeg;base64,{encoded}",
        mime_type="image/jpeg",
        width=width,
        height=height,
        original_width=original_width,
        original_height=original_height,
        sha256=hashlib.sha256(raw).hexdigest(),
        resized=resized,
    )


def _check_pixel_limit(image: Image.Image) -> None:
    # Pillow's own exception starts at twice MAX_IMAGE_PIXELS; enforce our
    # advertised limit explicitly before verification or pixel decoding.
    if image.width * image.height > MAX_SOURCE_PIXELS:
        raise EngineError(
            "image_pixel_limit",
            "Image contains too many pixels to process safely.",
            status_code=413,
        )
