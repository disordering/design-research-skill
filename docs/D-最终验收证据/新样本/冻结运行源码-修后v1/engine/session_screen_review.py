"""Per-screen technical review using the original single-image perception chain."""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from dataclasses import replace
from typing import Any

from pydantic import BaseModel, ValidationError

from .advanced import (
    ADVANCED_AUDIT_SCHEMA,
    OCR_CONTRACT,
    UI_CONTRACT,
    AdvancedAuditResult,
    AdvancedReviewEngine,
    GoalDecomposition,
    OCRResult,
    UIResult,
    _advanced_audit_messages,
    _fallback_relevance,
    _normalize_relevance,
    _ocr_messages,
    _ui_messages,
)
from .contracts import ReviewContext
from .config import load_reviewer_config
from .criteria import CriteriaLibrary, heuristic_label
from .cv_metrics import compute_pipeline_metrics
from .imaging import prepare_image
from .model import ModelSettings, OpenAICompatibleModel
from .parsing import parse_json_object
from .prompting import build_repair_messages
from .session_contracts import (
    Evidence,
    ScreenTechnicalIssue,
    ScreenTechnicalReview,
)
from .session_perception import _draw_overlays


SCREEN_RESPONSIBILITY = """
This is a heuristic interaction-design review, not a process checklist and not a
product-data review. Apply usability heuristics such as visibility of system
status, match with the real world, user control, consistency, error prevention,
recognition over recall, efficiency, minimalist presentation, error recovery,
and help. Do not turn missing business facts into UI findings. Exact price,
exchange rate, economic balance, title content, acquisition-source content and
other product decisions belong to planning/data. The interface review may only
assess how such values are presented: digits, overflow, truncation, wrapping,
alignment, hierarchy, legibility, feedback, input behavior, and state clarity.
Every finding must identify a heuristic principle and a concrete user impact.

Run the audit as a visible heuristic inspection:
- trace the user's main task and inspect the current state, selected object,
  primary action, nearby feedback, and competing information;
- inspect number and text containers against the longest visible values, not
  the commercial correctness of those values;
- inspect affordance, state consistency, recognition, error prevention,
  control freedom, visual hierarchy, density, legibility, and recovery;
- do not promote a missing page, missing state, unshown confirmation, or
  undocumented rule to a candidate defect. Record those as insufficient
  evidence unless the visible screen already causes a demonstrable interaction
  failure.

A candidate finding must contain all four parts: heuristic principle; visible
evidence; concrete user consequence; bounded design change. A statement that a
flow is incomplete is not sufficient. Missing business values are not interface
defects; overflow, clipping, ambiguous selection, unreadable output, misleading
affordance, and inconsistent state are.
"""

BUSINESS_ONLY_TERMS = (
    "业务规则", "业务策略", "定价", "价格", "金额", "预算", "成本",
    "经济平衡", "数值表", "计算规则", "内容准确性", "商业正确",
    "营销文案", "产品策略", "规则是否合理", "数据是否正确",
    "business rule", "pricing", "price", "budget", "cost",
    "commercial correctness", "content accuracy",
)
PRESENTATION_TERMS = (
    "位数", "溢出", "截断", "遮挡", "对齐", "换行", "滚动", "宽度",
    "字号", "对比", "层级", "间距", "可读", "选中", "勾选", "高亮",
    "状态不一致", "文案与内容", "图标含义", "加号", "返回入口", "不可见",
    "overflow", "truncat", "wrap", "align", "legib", "contrast",
    "selected", "selection", "highlight", "affordance", "readab",
    "digit", "clipping", "visual hierarchy",
)
SEMANTIC_CONTENT_PATTERNS = (
    "规则是否合理", "内容是否准确", "数值是否正确", "业务规则缺失",
    "价格是否合理", "文案是否符合策略", "数据含义",
    "无单位", "单位缺失", "单位不明",
    "消耗什么", "得到什么", "获得什么", "作用与规则",
    "结果与规则", "规则在点击前",
    "business rule", "content accuracy", "value correctness",
)
STRONG_PRESENTATION_PATTERNS = (
    "对比度", "亮度", "溢出", "截断", "遮挡", "字号", "高亮", "选中态",
    "对齐", "换行", "同形", "重名", "并列", "复用",
    "层级", "接近不可见", "不可读", "数值框", "裁切",
    "contrast", "overflow", "truncat", "clipping", "legib", "highlight",
    "selected", "leading zero", "digit", "same visual",
)


def _screen_audit_messages(
    *, image_data_url, context, goal, ui, ocr, metrics, relevance, criteria,
    selected, heuristic_probes,
):
    messages = _advanced_audit_messages(
        image_data_url, context, goal, ui, ocr, metrics, relevance, criteria, selected,
    )
    messages[0]["content"] += "\n" + SCREEN_RESPONSIBILITY
    messages[1]["content"].insert(0, {
        "type": "text",
        "text": (
            "The review must expose interaction heuristics rather than only checking whether "
            "a flow exists. Keep business values out of the defect list. A number field may be "
            "judged on whether it can display long digits without overflow, but not on the "
            "commercial correctness of its range or amount. Missing states are insufficient "
            "evidence, not automatically defects. Use the deterministic heuristic probes below "
            "as evidence, verify them visually, and cite the relevant H01-H10 principle in "
            "each candidate finding.\n\nDeterministic heuristic probes:\n"
            + json.dumps(heuristic_probes, ensure_ascii=False)
        ),
    })
    return messages


def _outside_screen_responsibility(finding) -> bool:
    if isinstance(finding, dict):
        title = finding.get("title", "")
        detection = finding.get("detection", "")
        description = finding.get("description", "")
        suggestion = finding.get("suggestion", "")
    else:
        title = finding.title
        detection = finding.detection
        description = finding.description
        suggestion = finding.suggestion
    text = " ".join([title, detection, description, suggestion]).lower()
    focus = " ".join([title, detection, description]).lower()
    semantic_content_only = (
        any(term in focus for term in SEMANTIC_CONTENT_PATTERNS)
        and not any(term in focus for term in STRONG_PRESENTATION_PATTERNS)
    )
    return (
        semantic_content_only
        or (
            any(term in text for term in BUSINESS_ONLY_TERMS)
            and not any(term in text for term in PRESENTATION_TERMS)
        )
    )


def _heuristic_ids(finding, criteria: CriteriaLibrary) -> list[str]:
    return list(dict.fromkeys(
        criteria.by_id[rule_id].heuristic
        for rule_id in finding.rule_ids
        if rule_id in criteria.by_id
    ))


def _principle_with_heuristics(
    finding, criteria: CriteriaLibrary,
) -> tuple[list[str], str]:
    heuristic_ids = _heuristic_ids(finding, criteria)
    labels = [heuristic_label(heuristic_id) for heuristic_id in heuristic_ids]
    principle = finding.principle.strip()
    missing = [
        label for label in labels
        if label.split()[0] not in principle
    ]
    if missing:
        principle = "；".join(dict.fromkeys([*missing, principle])).strip("；")
    return heuristic_ids, principle


def _interaction_heuristic_probes(
    image,
    ui_result,
    ocr_result,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic probes that make the heuristic review inspectable."""
    numeric_rows = []
    for block in ocr_result.blocks:
        compact = re.sub(r"[\s,，]", "", block.text)
        if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", compact):
            continue
        digits = sum(character.isdigit() for character in compact)
        if digits == 0:
            continue
        numeric_rows.append({
            "text": block.text,
            "digit_count": digits,
            "all_zero": set(compact.lstrip("+-").replace(".", "")) == {"0"},
            "bbox": block.bbox.as_list(),
        })
    digit_lengths = [row["digit_count"] for row in numeric_rows]
    placeholder_digits = [
        row["digit_count"] for row in numeric_rows if row["all_zero"]
    ]
    max_digits = max(digit_lengths, default=0)
    max_placeholder_digits = max(placeholder_digits, default=0)
    digit_groups = Counter(digit_lengths)

    interactive = [
        element for element in ui_result.elements if element.interactable
    ]
    small_targets = []
    for element in interactive:
        width_px = round(element.bbox.width * image.width, 1)
        height_px = round(element.bbox.height * image.height, 1)
        if width_px < 32 or height_px < 32:
            small_targets.append({
                "element_id": element.id,
                "label": element.label,
                "role": element.role,
                "width_px": width_px,
                "height_px": height_px,
                "bbox": element.bbox.as_list(),
            })

    readability = metrics.get("readability", {})
    text_rows = readability.get("blocks", [])
    text_edge_candidates = [
        row for row in text_rows
        if (
            row["bbox"][0] + row["bbox"][2] >= 0.965
            or row["bbox"][1] + row["bbox"][3] >= 0.965
        )
    ][:10]
    low_contrast = [
        {
            "text": row["text"],
            "bbox": row["bbox"],
            "estimated_height_px": row["estimated_height_px"],
            "local_luminance_contrast": row["local_luminance_contrast"],
            "small_text_candidate": row["small_text_candidate"],
        }
        for row in text_rows
        if row.get("low_contrast")
    ][:12]
    selected = [
        {
            "element_id": element.id,
            "label": element.label,
            "role": element.role,
            "state": element.state,
            "bbox": element.bbox.as_list(),
        }
        for element in ui_result.elements
        if element.state.strip().lower() not in {
            "", "default", "normal", "unselected",
        }
    ][:20]
    primary_actions = [
        {
            "element_id": element.id,
            "label": element.label,
            "role": element.role,
            "bbox": element.bbox.as_list(),
        }
        for element in ui_result.elements
        if element.role.strip().lower() in {
            "primary_button", "cta", "button", "icon_button",
        }
    ][:20]
    return {
        "numeric_adaptation": {
            "max_visible_digits": max_digits,
            "max_placeholder_digits": max_placeholder_digits,
            "digit_length_groups": dict(sorted(digit_groups.items())),
            "length_mismatch": (
                max_placeholder_digits > 0
                and max_digits > max_placeholder_digits
            ),
            "longest_values": sorted(
                numeric_rows,
                key=lambda row: row["digit_count"],
                reverse=True,
            )[:8],
        },
        "state": {
            "selected_or_explicit_state_elements": selected,
            "interactive_element_count": len(interactive),
        },
        "affordance": {
            "primary_actions": primary_actions,
            "small_target_candidates": small_targets[:12],
        },
        "legibility": {
            "low_contrast_candidates": low_contrast,
            "small_text_candidate_count": readability.get(
                "small_text_candidate_count", 0
            ),
            "estimated_height_p10": readability.get("estimated_height_p10"),
            "text_edge_candidates": text_edge_candidates,
        },
        "layout": {
            "element_density": metrics.get("density", {}),
            "focus_top": metrics.get("focus", {}).get("elements", [])[:5],
        },
        "instructions": (
            "These probes are diagnostic, not standalone defects. Verify against "
            "the image. Evaluate whether the longest visible values fit, whether "
            "selection agrees with details/actions, and whether controls and text "
            "remain legible and distinct."
        ),
    }


def _dedupe_screen_issues(
    issues: list[ScreenTechnicalIssue],
) -> list[ScreenTechnicalIssue]:
    result: list[ScreenTechnicalIssue] = []
    for issue in issues:
        duplicate = False
        for existing in result:
            title_similarity = SequenceMatcher(
                None, issue.title.lower(), existing.title.lower(),
            ).ratio()
            same_rules = bool(
                set(issue.rule_ids).intersection(existing.rule_ids)
            )
            if title_similarity >= 0.82 or (
                same_rules and title_similarity >= 0.58
            ):
                duplicate = True
                break
        if not duplicate:
            result.append(issue)
    return result


@dataclass
class ScreenModelCall:
    operation: str
    provider: str
    model: str
    usage: dict[str, Any]
    latency_ms: int | None
    request_id: str | None
    raw_text: str
    status: str
    schema_name: str
    validation_error: str = ""
    is_stub: bool = False


@dataclass
class ScreenReviewOutput:
    review: ScreenTechnicalReview
    artifacts: dict[str, tuple[bytes, str]] = field(default_factory=dict)
    calls: list[ScreenModelCall] = field(default_factory=list)


@dataclass
class ScreenReviewModels:
    ocr: OpenAICompatibleModel
    gui: OpenAICompatibleModel
    reasoning: OpenAICompatibleModel


class QwenScreenTechnicalReviewer:
    """A bounded OCR -> UI -> technical audit chain for one complete screen."""

    def __init__(self, criteria: CriteriaLibrary) -> None:
        self.criteria = criteria
        config = load_reviewer_config(required=True)
        screen_config = config.get("screen_review", {})
        provider = str(screen_config.get("provider", "qwen")).strip().lower()
        if provider == "qwen":
            self.engine = AdvancedReviewEngine(criteria)
        else:
            base = ModelSettings.from_env(
                provider,
                str(screen_config.get("reasoning_model", "")).strip() or None,
            )

            def build_client(model_name: str, max_tokens: int) -> OpenAICompatibleModel:
                return OpenAICompatibleModel(replace(
                    base,
                    model=model_name,
                    max_tokens=max_tokens,
                ))

            self.engine = ScreenReviewModels(
                ocr=build_client(
                    str(screen_config.get("ocr_model", base.model)),
                    12000,
                ),
                gui=build_client(
                    str(screen_config.get("ui_perception_model", base.model)),
                    12000,
                ),
                reasoning=build_client(
                    str(screen_config.get("reasoning_model", base.model)),
                    24000,
                ),
            )

    @staticmethod
    def _extra_body(
        client,
        payload: dict[str, Any],
        *,
        deepseek_effort: str = "high",
    ) -> dict[str, Any] | None:
        settings = getattr(client, "settings", None)
        provider = getattr(settings, "provider", "")
        if provider == "qwen":
            return payload
        if provider == "deepseek":
            return {"reasoning_effort": deepseek_effort}
        return None

    async def review(
        self,
        *,
        evidence: Evidence,
        image_bytes: bytes,
        context: ReviewContext,
        max_calls: int,
    ) -> ScreenReviewOutput:
        started = time.perf_counter()
        calls: list[ScreenModelCall] = []
        warnings: list[str] = []
        prepared = prepare_image(image_bytes, filename=f"{evidence.evidence_id}.png")
        from PIL import Image
        import io

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        async def call_schema(
            *, client, messages: list[dict[str, Any]], schema: type[BaseModel],
            contract: str, operation: str, extra_body: dict[str, Any] | None = None,
        ) -> BaseModel | None:
            remaining = max_calls - len(calls)
            if remaining <= 0:
                warnings.append(f"{operation} 未执行：逐屏模型调用预算不足。")
                return None
            call_started = time.perf_counter()
            try:
                result = await client.complete(messages, json_mode=True, extra_body=extra_body)
            except Exception as exc:
                calls.append(ScreenModelCall(
                    operation=operation,
                    provider=getattr(getattr(client, "settings", None), "provider", "unknown"),
                    model=getattr(getattr(client, "settings", None), "model", "unknown"),
                    usage={}, latency_ms=int((time.perf_counter() - call_started) * 1000),
                    request_id=None, raw_text="", status="failed", schema_name=schema.__name__,
                    validation_error=str(exc)[:1000], is_stub=bool(getattr(client, "is_stub", False)),
                ))
                warnings.append(f"{operation} 模型调用失败：{type(exc).__name__}")
                return None
            validation_error = ""
            try:
                parsed = schema.model_validate(parse_json_object(result.text))
            except (ValueError, ValidationError) as exc:
                validation_error = str(exc)[:2000]
                calls.append(ScreenModelCall(
                    operation=operation, provider=result.provider, model=result.model,
                    usage=result.usage, latency_ms=result.latency_ms, request_id=result.request_id,
                    raw_text=result.text, status="rejected", schema_name=schema.__name__,
                    validation_error=validation_error, is_stub=bool(getattr(client, "is_stub", False)),
                ))
                if max_calls - len(calls) <= 0:
                    warnings.append(f"{operation} 结构修复未执行：预算不足。")
                    return None
                repaired = await client.complete(
                    build_repair_messages(result.text, validation_error, contract),
                    json_mode=True, extra_body=extra_body,
                )
                try:
                    parsed = schema.model_validate(parse_json_object(repaired.text))
                except (ValueError, ValidationError) as repaired_error:
                    calls.append(ScreenModelCall(
                        operation=f"{operation}_repair", provider=repaired.provider,
                        model=repaired.model, usage=repaired.usage, latency_ms=repaired.latency_ms,
                        request_id=repaired.request_id, raw_text=repaired.text, status="rejected",
                        schema_name=schema.__name__, validation_error=str(repaired_error)[:2000],
                        is_stub=bool(getattr(client, "is_stub", False)),
                    ))
                    warnings.append(f"{operation} 结构修复后仍无效。")
                    return None
                calls.append(ScreenModelCall(
                    operation=f"{operation}_repair", provider=repaired.provider,
                    model=repaired.model, usage=repaired.usage, latency_ms=repaired.latency_ms,
                    request_id=repaired.request_id, raw_text=repaired.text, status="validated",
                    schema_name=schema.__name__, is_stub=bool(getattr(client, "is_stub", False)),
                ))
                return parsed
            calls.append(ScreenModelCall(
                operation=operation, provider=result.provider, model=result.model,
                usage=result.usage, latency_ms=result.latency_ms, request_id=result.request_id,
                raw_text=result.text, status="validated", schema_name=schema.__name__,
                is_stub=bool(getattr(client, "is_stub", False)),
            ))
            return parsed

        ocr = await call_schema(
            client=self.engine.ocr, messages=_ocr_messages(prepared.data_url),
            schema=OCRResult, contract=OCR_CONTRACT, operation="screen_ocr",
            extra_body=self._extra_body(
                self.engine.ocr,
                {"enable_thinking": False},
                deepseek_effort="low",
            ),
        )
        ui = await call_schema(
            client=self.engine.gui,
            messages=_ui_messages(prepared.data_url, "单项界面截图", context),
            schema=UIResult, contract=UI_CONTRACT, operation="screen_ui",
            extra_body=self._extra_body(
                self.engine.gui,
                {"vl_high_resolution_images": True, "enable_thinking": False},
                deepseek_effort="low",
            ),
        )
        ocr_result = ocr if isinstance(ocr, OCRResult) else OCRResult()
        ui_result = ui if isinstance(ui, UIResult) else UIResult(page_type="unknown")
        if not (
            ui_result.elements
            or ui_result.page_type.strip()
            or ui_result.summary.strip()
        ):
            warnings.append("专用 GUI 模型返回空结果，已改用多模态审查模型重试元素解析。")
            fallback_ui = await call_schema(
                client=self.engine.reasoning,
                messages=_ui_messages(prepared.data_url, "单项界面截图", context),
                schema=UIResult,
                contract=UI_CONTRACT,
                operation="screen_ui_fallback",
                extra_body=self._extra_body(
                    self.engine.reasoning,
                    {"enable_thinking": False},
                    deepseek_effort="low",
                ),
            )
            if isinstance(fallback_ui, UIResult):
                ui_result = fallback_ui
        if not (
            ui_result.elements
            or ui_result.page_type.strip()
            or ui_result.summary.strip()
        ):
            warnings.append("UI 元素解析未取得有效元素；后续仅使用 OCR 与视觉统计，不能声称完成控件级审查。")
        metrics = compute_pipeline_metrics(
            image, ui_result.elements, ocr_result.blocks,
        )
        heuristic_probes = _interaction_heuristic_probes(
            image, ui_result, ocr_result, metrics,
        )

        goal = GoalDecomposition(page_summary=context.scenario or context.design_goal or "")
        fallback = _fallback_relevance(self.criteria, context, ui_result, goal)
        relevance = _normalize_relevance(fallback, self.criteria, len(self.criteria.rules))
        selected = [row["rule_id"] for row in relevance if row.get("selected")]
        audit = await call_schema(
            client=self.engine.reasoning,
            messages=_screen_audit_messages(
                image_data_url=prepared.data_url, context=context, goal=goal,
                ui=ui_result, ocr=ocr_result, metrics=metrics,
                relevance=relevance, criteria=self.criteria, selected=selected,
                heuristic_probes=heuristic_probes,
            ),
            schema=AdvancedAuditResult, contract=ADVANCED_AUDIT_SCHEMA,
            operation="screen_audit",
            extra_body=self._extra_body(
                self.engine.reasoning,
                {"enable_thinking": True, "thinking_budget": 1200},
                deepseek_effort="high",
            ),
        )
        audit_result = audit if isinstance(audit, AdvancedAuditResult) else None
        issues = []
        rule_results = []
        if audit_result is not None:
            rule_results = [status.model_dump(mode="json") for status in audit_result.rule_statuses]
            statuses = {
                status.rule_id.strip().upper(): status.decision.value
                for status in audit_result.rule_statuses
                if status.rule_id.strip().upper() in self.criteria.by_id
            }
            for finding in audit_result.findings:
                valid_rules = [
                    rule_id.strip().upper()
                    for rule_id in finding.rule_ids
                    if (
                        rule_id.strip().upper() in self.criteria.by_id
                        and statuses.get(rule_id.strip().upper())
                        == "candidate_issue"
                    )
                ]
                valid_rules = list(dict.fromkeys(valid_rules))
                if not valid_rules:
                    warnings.append(
                        f"屏内发现“{finding.title}”没有已知且判为 candidate_issue 的判据支撑，已退回补证。"
                    )
                    continue
                finding = finding.model_copy(update={"rule_ids": valid_rules})
                if _outside_screen_responsibility(finding):
                    warnings.append(
                        f"屏内审查移出职责范围：{finding.title}；业务数值/内容不判为交互缺陷。"
                    )
                    continue
                heuristic_ids, principle = _principle_with_heuristics(
                    finding, self.criteria,
                )
                issues.append(ScreenTechnicalIssue(
                    rule_ids=finding.rule_ids,
                    heuristic_ids=heuristic_ids,
                    title=finding.title,
                    severity=finding.severity.value,
                    confidence=finding.confidence,
                    principle=principle,
                    user_impact=finding.description,
                    detection=finding.detection,
                    description=finding.description,
                    suggestion=finding.suggestion,
                    evidence_bbox=finding.evidence.model_dump(mode="json"),
                    visible_text=finding.evidence.visible_text,
                ))
            issues = _dedupe_screen_issues(issues)
        else:
            warnings.append("逐屏规则审查未返回有效结果；保留 OCR、元素和统计证据。")

        focus = metrics.get("focus", {}).get("elements", [])
        technical_metrics = {
            "image": metrics.get("image", {}),
            "ui_element_count": len(ui_result.elements),
            "interactive_element_count": sum(element.interactable for element in ui_result.elements),
            "ocr_block_count": len(ocr_result.blocks),
            "readability": metrics.get("readability", {}),
            "density": metrics.get("density", {}),
            "style": metrics.get("style", {}),
            "global": metrics.get("global", {}),
            "focus_top": focus[:5],
            "heuristic_probes": heuristic_probes,
        }
        overlays = _draw_overlays(
            image,
            ui_result,
            metrics,
            [],
        )
        artifacts: dict[str, tuple[bytes, str]] = {
            "screen-ocr.json": (
                json.dumps(ocr_result.model_dump(mode="json"), ensure_ascii=False, indent=2).encode("utf-8"),
                "application/json",
            ),
            "screen-elements.json": (
                json.dumps(ui_result.model_dump(mode="json"), ensure_ascii=False, indent=2).encode("utf-8"),
                "application/json",
            ),
            "screen-metrics.json": (
                json.dumps(metrics, ensure_ascii=False, indent=2).encode("utf-8"),
                "application/json",
            ),
            **{name: (content, "image/png") for name, content in overlays.items()},
        }
        if audit_result is not None:
            artifacts["screen-audit.json"] = (
                json.dumps(audit_result.model_dump(mode="json"), ensure_ascii=False, indent=2).encode("utf-8"),
                "application/json",
            )
        summary = (
            f"UI 元素 {len(ui_result.elements)}，OCR 文本块 {len(ocr_result.blocks)}，"
            f"候选技术问题 {len(issues)}。"
        )
        ui_usable = bool(ui_result.elements)
        status = "completed" if audit_result is not None and ui_usable else "partial"
        review = ScreenTechnicalReview(
            evidence_id=evidence.evidence_id,
            source_id=evidence.source_id,
            node_id=str(evidence.locator.get("node_id") or ""),
            page_type=ui_result.page_type,
            status=status,
            summary=summary,
            dimensions={"width": image.width, "height": image.height},
            rule_results=rule_results,
            issues=issues,
            technical_metrics=technical_metrics,
            warnings=list(dict.fromkeys(warnings)),
        )
        return ScreenReviewOutput(review=review, artifacts=artifacts, calls=calls)
