"""用模拟模型检查：输出字段不合法时，校验流程能否请求修复。"""

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.contracts import EvidenceAnchor, ScreenAnalysis
from engine.criteria import CriteriaLibrary
from engine.errors import EngineError
from engine.model import ModelCallResult
from engine.service import ReviewEngine


class SequenceModel:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.messages = []

    async def complete(self, messages, *, json_mode=True, extra_body=None):
        self.messages.append(messages)
        return ModelCallResult(
            text=next(self.outputs), provider="offline-sequence", model="test-only",
            usage={}, request_id=None, latency_ms=0, json_mode_used=json_mode,
        )


def request(model, schema):
    criteria = CriteriaLibrary.load(Path(__file__).resolve().parents[1] / "判据库_v1.json")
    engine = ReviewEngine(criteria, model, provider="offline-test", model_name="test-only", is_stub=True)
    return asyncio.run(engine._request_validated(
        [], schema, repair_contract="{}", label="test contract",
    ))


def test_valid_json_with_invalid_field_is_repaired():
    model = SequenceModel(['{"page_type": []}', '{"page_type": "repaired-screen"}'])
    result, warnings = request(model, ScreenAnalysis)

    assert result.page_type == "repaired-screen"
    assert len(model.messages) == 2
    assert len(warnings) == 1
    assert "page_type" in json.dumps(model.messages[1])
    assert "string_type" in json.dumps(model.messages[1])


def test_evidence_validator_exception_context_is_serializable_and_repaired():
    invalid = {"x": 0.9, "y": 0, "width": 0.3, "height": 0.1, "description": "visible region"}
    valid = {**invalid, "x": 0.1}
    # 确认此测试样本会触发 Pydantic 错误上下文中包含异常对象的情况。
    with pytest.raises(ValidationError) as error:
        EvidenceAnchor.model_validate(invalid)
    assert isinstance(error.value.errors()[0]["ctx"]["error"], ValueError)

    model = SequenceModel([json.dumps(invalid), json.dumps(valid)])
    result, warnings = request(model, EvidenceAnchor)

    assert result.x == 0.1
    assert result.width == 0.3
    assert len(model.messages) == 2
    assert len(warnings) == 1
    assert "Evidence box must stay inside" in json.dumps(model.messages[1])


def test_two_invalid_structures_return_model_contract_failed():
    invalid = {"x": 0.9, "y": 0, "width": 0.3, "height": 0.1, "description": "visible region"}
    model = SequenceModel([json.dumps(invalid), json.dumps(invalid)])

    with pytest.raises(EngineError) as error:
        request(model, EvidenceAnchor)

    assert len(model.messages) == 2
    assert error.value.code == "model_contract_failed"
    assert error.value.status_code == 502
    assert error.value.retryable is True
    assert "Evidence box must stay inside" in error.value.details["validation_error"]
    # 最终返回的结构化错误也必须能转换为 JSON。
    json.dumps(error.value.details)
