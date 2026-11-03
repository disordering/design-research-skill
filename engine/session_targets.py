"""Deterministic target matching for actions proposed by review models."""

from __future__ import annotations

import html
import re
from typing import Any


def normalize_label(value: Any) -> str:
    text = html.unescape(str(value or "")).lower()
    return re.sub(r"[\s\u3000\[\](){}<>:：,，。.;；/\\|_-]+", "", text)


def observed_control(
    controls: Any,
    selector: str,
) -> dict[str, Any] | None:
    if not selector or not isinstance(controls, list):
        return None
    return next(
        (
            control
            for control in controls
            if isinstance(control, dict)
            and str(control.get("selector") or "") == selector
        ),
        None,
    )


def control_labels(control: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(
        str(control.get(key) or "").strip()
        for key in (
            "label", "ariaLabel", "name", "title", "placeholder", "value",
        )
        if str(control.get(key) or "").strip()
    ))


def target_label_matches(
    expected: str,
    control: dict[str, Any],
) -> tuple[bool, str]:
    labels = control_labels(control)
    actual = " / ".join(labels) or str(control.get("selector") or "unknown")
    normalized_expected = normalize_label(expected)
    if not normalized_expected:
        return True, actual
    normalized_labels = [normalize_label(label) for label in labels]
    return normalized_expected in normalized_labels, actual


def control_is_available(control: dict[str, Any]) -> bool:
    return not bool(control.get("disabled")) and not bool(control.get("hidden"))
