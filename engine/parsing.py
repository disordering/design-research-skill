"""Tolerant parsing for model responses that should be JSON."""

from __future__ import annotations

import ast
import json
import re
from typing import Any


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from common model-output wrappers."""

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Model returned an empty response.")

    candidates = [text.strip()]
    fenced = re.findall(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(block.strip() for block in fenced)

    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value

    object_text = _extract_balanced_object(text)
    if object_text:
        for candidate in (object_text, _repair_common_json(object_text)):
            try:
                value = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        try:
            value = ast.literal_eval(object_text)
        except (ValueError, SyntaxError):
            value = None
        if isinstance(value, dict):
            return value

    raise ValueError("No valid JSON object could be extracted from the model response.")


def _extract_balanced_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _repair_common_json(text: str) -> str:
    repaired = re.sub(r",\s*([}\]])", r"\1", text)
    repaired = repaired.replace("\u201c", '"').replace("\u201d", '"')
    return repaired
