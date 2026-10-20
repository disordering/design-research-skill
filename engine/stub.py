"""Explicit offline model used for UI integration and deterministic tests."""

from __future__ import annotations

import json
import time
from typing import Any

from .model import ModelCallResult


class StubModel:
    """Never use without exposing is_stub=true to downstream consumers."""

    async def complete(
        self,
        messages: list[dict],
        *,
        json_mode: bool = True,
        extra_body: dict[str, Any] | None = None,
    ) -> ModelCallResult:
        text = "\n".join(
            item.get("text", "")
            for message in messages
            if isinstance(message.get("content"), list)
            for item in message["content"]
            if isinstance(item, dict)
        ) or str(messages[-1].get("content", ""))

        if "阶段：视觉理解" in text:
            payload: dict[str, Any] = {
                "page_type": "工作台",
                "visible_text": ["示例标题", "保存", "取消"],
                "regions": ["顶部导航", "中部主内容", "底部操作区"],
                "controls": ["主要按钮位于右下区域"],
                "observed_states": ["普通静态页面"],
                "task_clues": ["用户可能正在编辑或查看内容"],
                "uncertainties": ["示例模型无法做真实视觉理解"],
            }
        else:
            rule_statuses = []
            for number in range(1, 25):
                rule_id = f"R{number:02d}"
                decision = "candidate_issue" if rule_id == "R19" else "insufficient_evidence"
                rule_statuses.append(
                    {
                        "rule_id": rule_id,
                        "decision": decision,
                        "confidence": 0.35,
                        "reason": "离线示例数据，仅用于验证接口契约。",
                    }
                )
            payload = {
                "screen_analysis": {
                    "page_type": "工作台",
                    "visible_text": ["示例标题", "保存", "取消"],
                    "regions": ["顶部导航", "中部主内容", "底部操作区"],
                    "controls": ["主要按钮位于右下区域"],
                    "observed_states": ["普通静态页面"],
                    "task_clues": ["用户可能正在编辑或查看内容"],
                    "uncertainties": ["示例模型无法做真实视觉理解"],
                },
                "rule_statuses": rule_statuses,
                "findings": [
                    {
                        "rule_ids": ["R19"],
                        "title": "示例：主要操作定位不够突出",
                        "severity": "medium",
                        "confidence": 0.35,
                        "principle": "R19 主要任务操作易于定位",
                        "detection": "示例证据：主要按钮位于右下操作区。",
                        "description": "这是离线契约示例，不代表真实截图判断。",
                        "suggestion": "接入真实视觉模型后重新评审。",
                        "evidence": {
                            "x": 0.72,
                            "y": 0.82,
                            "width": 0.18,
                            "height": 0.08,
                            "description": "右下操作区",
                            "visible_text": "保存",
                        },
                    }
                ],
            }
        return ModelCallResult(
            text=json.dumps(payload, ensure_ascii=False),
            provider="stub",
            model="contract-stub-v1",
            usage={},
            request_id=None,
            latency_ms=int(time.perf_counter() * 1000) % 10,
            json_mode_used=True,
        )
