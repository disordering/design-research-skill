import pytest

from engine.parsing import parse_json_object


def test_parses_plain_json():
    assert parse_json_object('{"ok": true}') == {"ok": True}


def test_parses_fenced_json_with_prose():
    text = '说明如下：\n```json\n{"ok": true, "items": [1, 2]}\n```\n请复核。'
    assert parse_json_object(text) == {"ok": True, "items": [1, 2]}


def test_extracts_balanced_json_and_repairs_trailing_comma():
    text = '前缀 {"items": [{"id": "R01"},],} 后缀'
    assert parse_json_object(text) == {"items": [{"id": "R01"}]}


def test_rejects_non_object_json():
    with pytest.raises(ValueError):
        parse_json_object("[1, 2, 3]")
