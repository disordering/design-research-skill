"""Deterministic screenshot metrics implemented without model judgment."""

from __future__ import annotations

import math
from typing import Any

from PIL import Image, ImageChops, ImageFilter, ImageStat

from .advanced_contracts import (
    NormalizedBox,
    OCRBlock,
    PrototypeMatch,
    UIElement,
)

METRIC_VERSION = "cv-metrics-v1"


def compute_pipeline_metrics(
    image: Image.Image,
    elements: list[UIElement],
    ocr_blocks: list[OCRBlock],
    reference_elements: list[UIElement] | None = None,
) -> dict[str, Any]:
    rgb = image.convert("RGB")
    global_metrics = _global_metrics(rgb)
    focus = _focus_metrics(rgb, elements)
    readability = _readability_metrics(rgb, ocr_blocks)
    density = _density_metrics(rgb, elements, ocr_blocks)
    style = _style_metrics(rgb, elements)
    prototype = _prototype_alignment(elements, reference_elements or [])
    return {
        "metric_version": METRIC_VERSION,
        "image": {
            "width": rgb.width,
            "height": rgb.height,
            "megapixels": round(rgb.width * rgb.height / 1_000_000, 4),
        },
        "global": global_metrics,
        "focus": {
            "metric_type": "visual_focus_proxy",
            "notice": "This is a deterministic saliency proxy, not measured human attention.",
            "elements": focus,
        },
        "readability": readability,
        "density": density,
        "style": style,
        "prototype_alignment": prototype,
    }


def _global_metrics(image: Image.Image) -> dict[str, float]:
    sample = _sample(image, 640)
    gray = sample.convert("L")
    hist = gray.histogram()
    pixels = sum(hist)
    mean = sum(index * count for index, count in enumerate(hist)) / max(1, pixels)
    variance = sum((index - mean) ** 2 * count for index, count in enumerate(hist)) / max(1, pixels)
    p05 = _percentile(hist, 0.05)
    p50 = _percentile(hist, 0.50)
    p95 = _percentile(hist, 0.95)
    edge = gray.filter(ImageFilter.FIND_EDGES)
    edge_hist = edge.histogram()
    edge_pixels = sum(count for value, count in enumerate(edge_hist) if value >= 28)
    highfreq = ImageChops.difference(gray, gray.filter(ImageFilter.GaussianBlur(1.6)))
    highfreq_mean = sum(ImageStat.Stat(highfreq).mean)
    quantized = sample.quantize(colors=24, method=Image.Quantize.MEDIANCUT)
    palette_hist = quantized.histogram()
    total = sum(palette_hist)
    entropy = -sum(
        (count / total) * math.log2(count / total)
        for count in palette_hist
        if count > 0
    )
    saturation = sample.convert("HSV").getchannel("S").histogram()
    saturation_pixels = sum(saturation)
    saturation_mean = (
        sum(index * count for index, count in enumerate(saturation)) / max(1, saturation_pixels)
    )
    saturated_fraction = (
        sum(count for value, count in enumerate(saturation) if value >= 180)
        / max(1, saturation_pixels)
    )
    return {
        "mean_luminance": round(mean / 255, 4),
        "luminance_p05": round(p05 / 255, 4),
        "luminance_p50": round(p50 / 255, 4),
        "luminance_p95": round(p95 / 255, 4),
        "luminance_contrast": round((math.sqrt(variance) / 255), 4),
        "bright_pixel_fraction": round(sum(hist[235:]) / max(1, pixels), 4),
        "dark_pixel_fraction": round(sum(hist[:25]) / max(1, pixels), 4),
        "mean_saturation": round(saturation_mean / 255, 4),
        "high_saturation_fraction": round(saturated_fraction, 4),
        "edge_density": round(edge_pixels / max(1, pixels), 4),
        "high_frequency_mean": round(highfreq_mean / 255, 4),
        "palette_entropy_bits": round(entropy, 4),
        "negative_space_proxy": round(1 - edge_pixels / max(1, pixels), 4),
    }


def _focus_metrics(image: Image.Image, elements: list[UIElement]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total_area = max(1, image.width * image.height)
    for element in elements:
        crop = _crop_box(image, element.bbox)
        region = _region_metrics(crop)
        area_pixels = max(1, int(element.bbox.width * image.width * element.bbox.height * image.height))
        area_ratio = area_pixels / total_area
        center_x = element.bbox.x + element.bbox.width / 2
        center_y = element.bbox.y + element.bbox.height / 2
        center_distance = min(
            1.0,
            math.sqrt((center_x - 0.5) ** 2 + (center_y - 0.5) ** 2) / 0.7071,
        )
        area_signal = min(1.0, math.sqrt(area_ratio / 0.22))
        contrast_signal = min(1.0, region["luminance_contrast"] / 0.45)
        edge_signal = min(1.0, region["edge_density"] / 0.18)
        center_signal = 1.0 - center_distance
        saturation_signal = region["mean_saturation"]
        proxy = (
            0.18 * area_signal
            + 0.18 * contrast_signal
            + 0.14 * edge_signal
            + 0.15 * center_signal
            + 0.10 * saturation_signal
            + 0.25 * element.visual_importance
        )
        rows.append(
            {
                "element_id": element.id,
                "label": element.label,
                "role": element.role,
                "bbox": element.bbox.as_list(),
                "area_ratio": round(area_ratio, 4),
                "center_distance": round(center_distance, 4),
                "model_visual_importance": element.visual_importance,
                "region": region,
                "focus_proxy_raw": round(proxy, 4),
            }
        )
    total = sum(max(0.0001, row["focus_proxy_raw"]) for row in rows)
    for row in rows:
        row["focus_share"] = round(row["focus_proxy_raw"] / total, 4) if total else 0.0
    rows.sort(key=lambda item: item["focus_share"], reverse=True)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def _region_metrics(crop: Image.Image) -> dict[str, float]:
    sample = _sample(crop, 256)
    gray = sample.convert("L")
    hist = gray.histogram()
    pixels = sum(hist)
    p10 = _percentile(hist, 0.10)
    p90 = _percentile(hist, 0.90)
    edge = gray.filter(ImageFilter.FIND_EDGES).histogram()
    edge_pixels = sum(count for value, count in enumerate(edge) if value >= 28)
    sat = sample.convert("HSV").getchannel("S").histogram()
    sat_pixels = sum(sat)
    return {
        "luminance_p10": round(p10 / 255, 4),
        "luminance_p90": round(p90 / 255, 4),
        "luminance_contrast": round((p90 - p10) / 255, 4),
        "mean_saturation": round(
            sum(index * count for index, count in enumerate(sat)) / max(1, sat_pixels) / 255,
            4,
        ),
        "edge_density": round(edge_pixels / max(1, pixels), 4),
        "bright_fraction": round(sum(hist[235:]) / max(1, pixels), 4),
    }


def _readability_metrics(
    image: Image.Image,
    blocks: list[OCRBlock],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    heights: list[float] = []
    contrasts: list[float] = []
    for index, block in enumerate(blocks, start=1):
        crop = _crop_box(image, block.bbox)
        region = _region_metrics(crop)
        estimated_height = block.estimated_height_px or block.bbox.height * image.height
        heights.append(estimated_height)
        contrasts.append(region["luminance_contrast"])
        rows.append(
            {
                "block": index,
                "text": block.text,
                "bbox": block.bbox.as_list(),
                "estimated_height_px": round(estimated_height, 2),
                "local_luminance_contrast": region["luminance_contrast"],
                "low_contrast": region["luminance_contrast"] < 0.25,
                "small_text_candidate": estimated_height < 18,
                "ocr_confidence": block.confidence,
            }
        )
    return {
        "text_block_count": len(blocks),
        "low_contrast_count": sum(1 for row in rows if row["low_contrast"]),
        "small_text_candidate_count": sum(
            1 for row in rows if row["small_text_candidate"]
        ),
        "estimated_height_p10": round(_value_percentile(heights, 0.10), 2),
        "estimated_height_p50": round(_value_percentile(heights, 0.50), 2),
        "local_contrast_p10": round(_value_percentile(contrasts, 0.10), 4),
        "blocks": rows,
    }


def _density_metrics(
    image: Image.Image,
    elements: list[UIElement],
    ocr_blocks: list[OCRBlock],
) -> dict[str, Any]:
    image_area = max(1.0, image.width * image.height)
    interactive_area = sum(
        element.bbox.width * element.bbox.height * image_area
        for element in elements
        if element.interactable
    )
    text_area = sum(
        block.bbox.width * block.bbox.height * image_area for block in ocr_blocks
    )
    megapixels = image_area / 1_000_000
    return {
        "element_count": len(elements),
        "interactive_element_count": sum(1 for element in elements if element.interactable),
        "ocr_text_block_count": len(ocr_blocks),
        "elements_per_megapixel": round(len(elements) / megapixels, 2),
        "interactive_coverage": round(min(1.0, interactive_area / image_area), 4),
        "text_coverage": round(min(1.0, text_area / image_area), 4),
        "crowding_note": "Coverage metrics are proxies; overlapping elements can double-count area.",
    }


def _style_metrics(image: Image.Image, elements: list[UIElement]) -> dict[str, Any]:
    sample = _sample(image, 512)
    controls = [
        element
        for element in elements
        if element.role.lower()
        in {"button", "primary_button", "secondary_button", "nav", "navigation", "chip"}
    ]
    control_rows = []
    for element in controls:
        control_rows.append(_region_metrics(_crop_box(sample, element.bbox)))
    saturation_values = [row["mean_saturation"] for row in control_rows]
    contrast_values = [row["luminance_contrast"] for row in control_rows]
    return {
        "control_count": len(control_rows),
        "control_saturation_dispersion": round(_std(saturation_values), 4),
        "control_contrast_dispersion": round(_std(contrast_values), 4),
        "control_mean_saturation": round(sum(saturation_values) / max(1, len(saturation_values)), 4),
        "control_mean_contrast": round(sum(contrast_values) / max(1, len(contrast_values)), 4),
        "note": "Dispersion measures same-role visual consistency only when roles are correctly labeled.",
    }


def _prototype_alignment(
    result_elements: list[UIElement],
    reference_elements: list[UIElement],
) -> dict[str, Any]:
    if not reference_elements:
        return {"available": False, "matches": [], "mean_iou": None}
    available = list(reference_elements)
    matches: list[PrototypeMatch] = []
    for result in result_elements:
        candidates = [
            ref
            for ref in available
            if _alignment_role(ref) == _alignment_role(result)
        ]
        if not candidates:
            continue
        best = max(
            candidates,
            key=lambda ref: (
                _iou(result.bbox, ref.bbox)
                - 0.5 * _center_distance(result.bbox, ref.bbox)
                - 0.2 * abs(_box_area(result.bbox) - _box_area(ref.bbox))
            ),
        )
        available.remove(best)
        result_area = max(0.000001, _box_area(result.bbox))
        matches.append(
            PrototypeMatch(
                role=result.role,
                result_bbox=result.bbox,
                reference_bbox=best.bbox,
                iou=round(_iou(result.bbox, best.bbox), 4),
                center_offset=round(_center_distance(result.bbox, best.bbox), 4),
                size_ratio_change=round(_box_area(result.bbox) / max(0.000001, _box_area(best.bbox)), 4),
            )
        )
    return {
        "available": True,
        "matches": [match.model_dump() for match in matches],
        "mean_iou": round(sum(match.iou or 0 for match in matches) / len(matches), 4)
        if matches
        else None,
        "mean_center_offset": round(
            sum(match.center_offset or 0 for match in matches) / len(matches), 4
        )
        if matches
        else None,
    }


def _crop_box(image: Image.Image, box: NormalizedBox) -> Image.Image:
    left = max(0, min(image.width - 1, round(box.x * image.width)))
    top = max(0, min(image.height - 1, round(box.y * image.height)))
    right = max(left + 1, min(image.width, round((box.x + box.width) * image.width)))
    bottom = max(top + 1, min(image.height, round((box.y + box.height) * image.height)))
    return image.crop((left, top, right, bottom))


def _sample(image: Image.Image, max_dimension: int) -> Image.Image:
    result = image.copy()
    if max(result.size) > max_dimension:
        result.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    return result.convert("RGB")


def _percentile(histogram: list[int], fraction: float) -> int:
    total = sum(histogram)
    if total <= 0:
        return 0
    target = total * fraction
    cumulative = 0
    for value, count in enumerate(histogram):
        cumulative += count
        if cumulative >= target:
            return value
    return 255


def _value_percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _box_area(box: NormalizedBox) -> float:
    return box.width * box.height


def _iou(first: NormalizedBox, second: NormalizedBox) -> float:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = _box_area(first) + _box_area(second) - intersection
    return intersection / union if union > 0 else 0.0


def _center_distance(first: NormalizedBox, second: NormalizedBox) -> float:
    first_x = first.x + first.width / 2
    first_y = first.y + first.height / 2
    second_x = second.x + second.width / 2
    second_y = second.y + second.height / 2
    return min(1.0, math.sqrt((first_x - second_x) ** 2 + (first_y - second_y) ** 2) / 0.7071)


def _role_family(role: str) -> str:
    normalized = role.strip().lower().replace("-", "_")
    if normalized in {"primary_button", "cta"}:
        return "primary_action"
    if normalized in {"button", "secondary_button"}:
        return "button"
    if normalized in {"nav", "navigation", "tab", "menu"}:
        return "navigation"
    if normalized in {"character", "hero_character", "portrait"}:
        return "character"
    if normalized in {"reward", "reward_card", "rewards"}:
        return "reward"
    return normalized


def _alignment_role(element: UIElement) -> str:
    label = element.label.lower()
    role = _role_family(element.role)
    if any(token in label for token in ("reward", "奖励")):
        return "reward"
    if any(token in label for token in ("character", "角色", "portrait", "hero")):
        return "character"
    if any(token in label for token in ("start", "开始", "cta")):
        return "primary_action"
    if role == "primary_button":
        return "primary_action"
    if any(token in label for token in ("resource", "currency", "资源", "金币")):
        return "resource"
    if any(token in label for token in ("back", "返回", "home", "首页")):
        return "navigation"
    if any(token in label for token in ("tab:", "trial", "skill", "story", "菜单")):
        return "navigation"
    return role
