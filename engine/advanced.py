"""Ensemble review: OCR, GUI perception, measurable metrics, and criteria retrieval."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, TypeVar

from PIL import Image, ImageDraw
from pydantic import BaseModel, ValidationError

from .advanced_contracts import (
    AdvancedAuditResult,
    AdvancedReviewArtifacts,
    GoalDecomposition,
    GoalCheck,
    OCRResult,
    RelevanceResult,
    RuleRelevance,
    UIResult,
)
from .config import load_reviewer_config
from .contracts import (
    Decision,
    Finding,
    ImageInfo,
    ModelInfo,
    ReviewContext,
    ReviewReport,
    RuleStatus,
    ScreenAnalysis,
)
from .criteria import CriteriaLibrary, heuristic_label
from .cv_metrics import compute_pipeline_metrics
from .errors import EngineError
from .imaging import prepare_image
from .model import ModelSettings, OpenAICompatibleModel
from .parsing import parse_json_object
from .prompting import build_repair_messages
from .service import ReviewEngine, _build_summary, _elapsed_ms

SchemaT = TypeVar("SchemaT", bound=BaseModel)

OCR_CONTRACT = """{
  "blocks": [
    {
      "text": "string",
      "bbox": {"x": 0.0, "y": 0.0, "width": 0.1, "height": 0.1},
      "confidence": 0.0,
      "estimated_height_px": 0
    }
  ],
  "notes": ["string"]
}"""

UI_CONTRACT = """{
  "page_type": "string",
  "summary": "string",
  "elements": [
    {
      "id": "E01",
      "label": "string",
      "role": "primary_button|secondary_button|button|nav|character|reward_card|resource|title|text|panel|other",
      "bbox": {"x": 0.0, "y": 0.0, "width": 0.1, "height": 0.1},
      "interactable": true,
      "visual_importance": 0.0,
      "state": "default",
      "confidence": 0.0
    }
  ],
  "uncertainties": ["string"]
}"""

GOAL_CONTRACT = """{
  "page_summary": "string",
  "constraints": [
    {
      "id": "G01",
      "text": "string",
      "category": "layout|hierarchy|density|style|anti_pattern|readability|interaction|other",
      "metric_hint": "string",
      "target_roles": ["string"],
      "priority": 1
    }
  ]
}"""

RELEVANCE_CONTRACT = """{
  "scene_summary": "string",
  "rankings": [
    {
      "rule_id": "R01",
      "visual": 0.0,
      "text": 0.0,
      "attribute": 0.0,
      "prior": 0.0,
      "final": 0.0,
      "reasons": ["string"]
    }
  ]
}"""

ADVANCED_AUDIT_SCHEMA = """{
  "screen_analysis": {
    "page_type": "string",
    "visible_text": ["string"],
    "regions": ["string"],
    "controls": ["string"],
    "observed_states": ["string"],
    "task_clues": ["string"],
    "uncertainties": ["string"]
  },
  "rule_statuses": [
    {
      "rule_id": "R01",
      "decision": "candidate_issue|no_visible_issue|insufficient_evidence|not_applicable",
      "confidence": 0.0,
      "reason": "string"
    }
  ],
  "findings": [
    {
      "rule_ids": ["R01"],
      "title": "string",
      "severity": "critical|high|medium|low",
      "confidence": 0.0,
      "principle": "string",
      "detection": "string",
      "description": "string",
      "suggestion": "string",
      "evidence": {
        "x": 0.0,
        "y": 0.0,
        "width": 0.1,
        "height": 0.1,
        "description": "string",
        "visible_text": "string"
      }
    }
  ],
  "goal_checks": [
    {
      "constraint_id": "G01",
      "status": "observed_violation|met|insufficient_evidence",
      "title": "string",
      "severity": "critical|high|medium|low",
      "confidence": 0.0,
      "detection": "string",
      "description": "string",
      "suggestion": "string",
      "evidence": {
        "x": 0.0,
        "y": 0.0,
        "width": 0.1,
        "height": 0.1,
        "description": "string",
        "visible_text": "string"
      }
    }
  ]
}"""


class AdvancedReviewEngine:
    def __init__(self, criteria: CriteriaLibrary) -> None:
        config = load_reviewer_config(required=True)
        qwen = config.get("providers", {}).get("qwen", {})
        if not isinstance(qwen, dict) or not qwen.get("enabled", False):
            raise EngineError(
                "qwen_not_configured",
                "Advanced review requires an enabled Qwen provider.",
                status_code=503,
            )
        base = ModelSettings.from_env("qwen", qwen.get("reasoning_model"))
        self.criteria = criteria
        self.reasoning_model_name = str(qwen.get("reasoning_model"))
        self.reasoning = OpenAICompatibleModel(
            replace(base, model=self.reasoning_model_name, max_tokens=12000)
        )
        self.ocr = OpenAICompatibleModel(
            replace(base, model=str(qwen.get("ocr_model")), max_tokens=6000)
        )
        self.gui = OpenAICompatibleModel(
            replace(base, model=str(qwen.get("ui_perception_model")), max_tokens=6000)
        )
        self.review_helper = ReviewEngine(
            criteria,
            self.reasoning,
            provider="qwen",
            model_name=self.reasoning_model_name,
        )
        self.top_k = int(config.get("review", {}).get("top_k_criteria", 8))
        self.artifact_dir = Path(
            config.get("app", {}).get("artifact_dir", "out/debug")
        )
        self.save_artifacts = bool(
            config.get("app", {}).get("debug_artifacts", True)
        )

    async def review(
        self,
        image_bytes: bytes,
        *,
        context: ReviewContext,
        reference_bytes: bytes | None = None,
        filename: str = "screenshot.png",
    ) -> ReviewReport:
        started = time.perf_counter()
        warnings: list[str] = []
        prepared = prepare_image(image_bytes, filename=filename)
        image = _open_image(image_bytes)
        reference_image = _open_image(reference_bytes) if reference_bytes else None
        reference_prepared = (
            prepare_image(reference_bytes, filename="reference.png")
            if reference_bytes
            else None
        )

        semaphore = asyncio.Semaphore(3)

        async def guarded(coro, label: str, fallback):
            try:
                async with semaphore:
                    return await coro, None
            except Exception as exc:
                warnings.append(f"{label} 失败，已降级：{exc}")
                return fallback, exc

        perception_started = time.perf_counter()
        _stage("OCR / GUI elements / design-goal decomposition")
        ocr_task = guarded(
            self._call_schema(
                self.ocr,
                _ocr_messages(prepared.data_url),
                OCRResult,
                OCR_CONTRACT,
                "ocr",
                extra_body={"enable_thinking": False},
            ),
            "OCR",
            OCRResult(),
        )
        ui_task = guarded(
            self._call_schema(
                self.gui,
                _ui_messages(prepared.data_url, "成果截图", context),
                UIResult,
                UI_CONTRACT,
                "ui",
                extra_body={
                    "vl_high_resolution_images": True,
                    "enable_thinking": False,
                },
            ),
            "GUI 元素解析",
            UIResult(page_type="unknown"),
        )
        goal_task = guarded(
            self._call_schema(
                self.reasoning,
                _goal_messages(
                    prepared.data_url,
                    context,
                    reference_prepared.data_url if reference_prepared else None,
                ),
                GoalDecomposition,
                GOAL_CONTRACT,
                "goal",
                extra_body={"enable_thinking": False},
            ),
            "设计目标拆解",
            GoalDecomposition(
                page_summary=context.design_goal or "",
                constraints=_fallback_constraints(context.design_goal or ""),
            ),
        )
        reference_task = (
            guarded(
                self._call_schema(
                    self.gui,
                    _ui_messages(
                        reference_prepared.data_url,
                        "设计原型参考",
                        context,
                    ),
                    UIResult,
                    UI_CONTRACT,
                    "reference_ui",
                    extra_body={
                        "vl_high_resolution_images": True,
                        "enable_thinking": False,
                    },
                ),
                "原型元素解析",
                UIResult(page_type="unknown"),
            )
            if reference_prepared
            else _ready(None)
        )

        (ocr_result, _), (ui_result, _), (goal_result, _), reference_pair = await asyncio.gather(
            ocr_task,
            ui_task,
            goal_task,
            reference_task,
        )
        reference_ui = reference_pair[0] if reference_pair else None
        perception_ms = _elapsed_ms(perception_started)
        _stage(f"perception complete in {perception_ms} ms")

        metrics = compute_pipeline_metrics(
            image,
            ui_result.elements,
            ocr_result.blocks,
            reference_ui.elements if reference_ui else None,
        )

        relevance_started = time.perf_counter()
        _stage("criteria relevance reranking")
        try:
            relevance_result = await self._call_schema(
                self.reasoning,
                _relevance_messages(
                    prepared.data_url,
                    context,
                    goal_result,
                    ui_result,
                    ocr_result,
                    metrics,
                    self.criteria,
                ),
                RelevanceResult,
                RELEVANCE_CONTRACT,
                "criteria_relevance",
                extra_body={"enable_thinking": False},
            )
            relevance_warnings: list[str] = []
        except Exception as exc:
            relevance_result = _fallback_relevance(
                self.criteria,
                context,
                ui_result,
                goal_result,
            )
            relevance_warnings = [f"判据相关性模型失败，使用属性降级排序：{exc}"]
            warnings.extend(relevance_warnings)
        relevance_ms = _elapsed_ms(relevance_started)

        criteria_relevance = _normalize_relevance(
            relevance_result,
            self.criteria,
            self.top_k,
        )
        selected_ids = [
            item["rule_id"] for item in criteria_relevance if item["selected"]
        ]
        if not selected_ids:
            selected_ids = self.criteria.rule_ids[: self.top_k]

        audit_started = time.perf_counter()
        _stage(f"final audit on {', '.join(selected_ids)}")
        raw_audit, audit_warnings = await self.review_helper._request_validated(
            _advanced_audit_messages(
                prepared.data_url,
                context,
                goal_result,
                ui_result,
                ocr_result,
                metrics,
                criteria_relevance,
                self.criteria,
                selected_ids,
            ),
            AdvancedAuditResult,
            repair_contract=ADVANCED_AUDIT_SCHEMA,
            label="advanced criteria audit",
            extra_body={"enable_thinking": True, "thinking_budget": 1800},
        )
        warnings.extend(audit_warnings)
        audit_ms = _elapsed_ms(audit_started)

        _prefill_unselected_statuses(raw_audit, criteria_relevance, self.criteria)
        findings, rule_results, normalize_warnings = self.review_helper._normalize(
            raw_audit
        )
        goal_findings = _goal_findings(raw_audit.goal_checks, goal_result, self.criteria)
        findings = _merge_goal_findings(findings, goal_findings)
        warnings.extend(normalize_warnings)
        summary = _summary_with_goal_findings(rule_results, findings, goal_findings)
        review_id = str(uuid.uuid4())
        screen_analysis = ScreenAnalysis(
            page_type=ui_result.page_type,
            visible_text=[block.text for block in ocr_result.blocks],
            regions=[f"{element.role}: {element.label}" for element in ui_result.elements],
            controls=[
                f"{element.role}: {element.label}"
                for element in ui_result.elements
                if element.interactable
            ],
            observed_states=[element.state for element in ui_result.elements],
            task_clues=[goal_result.page_summary] if goal_result.page_summary else [],
            uncertainties=[*ui_result.uncertainties, *ocr_result.notes],
        )

        artifacts = (
            self._write_artifacts(
                review_id,
                image,
                ui_result,
                ocr_result,
                metrics,
                criteria_relevance,
            )
            if self.save_artifacts
            else AdvancedReviewArtifacts()
        )
        report = ReviewReport(
            review_id=review_id,
            status="partial" if warnings else "completed",
            model=ModelInfo(
                provider="qwen",
                model=self.reasoning_model_name,
                analysis_mode="ensemble",
                is_stub=False,
            ),
            context=context,
            image=ImageInfo(
                sha256=prepared.sha256,
                mime_type=prepared.mime_type,
                width=prepared.width,
                height=prepared.height,
                original_width=prepared.original_width,
                original_height=prepared.original_height,
                resized=prepared.resized,
            ),
            screen_analysis=screen_analysis,
            criteria_version=self.criteria.version,
            criteria_source=self.criteria.source,
            summary=summary,
            findings=findings,
            rule_results=rule_results,
            warnings=list(dict.fromkeys(warnings)),
            timings_ms={
                "perception": perception_ms,
                "criteria_relevance": relevance_ms,
                "final_audit": audit_ms,
                "total": _elapsed_ms(started),
            },
            diagnostics=metrics,
            perception={
                "ocr": ocr_result.model_dump(),
                "elements": ui_result.model_dump(),
                "reference_elements": reference_ui.model_dump() if reference_ui else None,
            },
            criteria_relevance=criteria_relevance,
            goal_constraints=[constraint.model_dump() for constraint in goal_result.constraints],
            goal_checks=[check.model_dump() for check in raw_audit.goal_checks],
            artifacts=artifacts.model_dump(),
        )
        if self.save_artifacts and artifacts.report_json:
            Path(artifacts.report_json).write_text(
                report.model_dump_json(indent=2),
                encoding="utf-8",
            )
        _stage("review complete")
        return report

    async def _call_schema(
        self,
        model: OpenAICompatibleModel,
        messages: list[dict],
        schema: type[SchemaT],
        contract: str,
        label: str,
        *,
        extra_body: dict[str, Any] | None = None,
    ) -> SchemaT:
        result = await model.complete(messages, json_mode=True, extra_body=extra_body)
        try:
            return schema.model_validate(parse_json_object(result.text))
        except (ValueError, ValidationError) as first_error:
            repaired = await model.complete(
                build_repair_messages(result.text, str(first_error), contract),
                json_mode=True,
            )
            try:
                return schema.model_validate(parse_json_object(repaired.text))
            except (ValueError, ValidationError) as second_error:
                raise EngineError(
                    "advanced_stage_contract_failed",
                    f"{label} failed its output contract after repair.",
                    status_code=502,
                    retryable=True,
                    details={"error": str(second_error)},
                ) from second_error

    def _write_artifacts(
        self,
        review_id: str,
        image: Image.Image,
        ui_result: UIResult,
        ocr_result: OCRResult,
        metrics: dict[str, Any],
        criteria_relevance: list[dict[str, Any]],
    ) -> AdvancedReviewArtifacts:
        target = self.artifact_dir / review_id
        target.mkdir(parents=True, exist_ok=True)
        elements_json = target / "elements.json"
        ocr_json = target / "ocr.json"
        metrics_json = target / "metrics.json"
        relevance_csv = target / "criteria_relevance.csv"
        overlay_elements = target / "overlay_elements.png"
        overlay_focus = target / "overlay_focus.png"
        report_json = target / "report.json"

        elements_json.write_text(
            json.dumps(ui_result.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        ocr_json.write_text(
            json.dumps(ocr_result.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        metrics_json.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        with relevance_csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "rule_id",
                    "title",
                    "visual",
                    "text",
                    "attribute",
                    "prior",
                    "final",
                    "selected",
                    "reasons",
                ],
            )
            writer.writeheader()
            for row in criteria_relevance:
                writer.writerow(
                    {
                        **{key: row.get(key) for key in writer.fieldnames if key != "reasons"},
                        "reasons": " | ".join(row.get("reasons", [])),
                    }
                )
        _draw_elements(image, ui_result, overlay_elements)
        _draw_focus(image, metrics, overlay_focus)
        return AdvancedReviewArtifacts(
            report_json=str(report_json.resolve()),
            elements_json=str(elements_json.resolve()),
            ocr_json=str(ocr_json.resolve()),
            metrics_json=str(metrics_json.resolve()),
            criteria_relevance_csv=str(relevance_csv.resolve()),
            overlay_elements=str(overlay_elements.resolve()),
            overlay_focus=str(overlay_focus.resolve()),
        )


async def _ready(value):
    return value


def _open_image(raw: bytes) -> Image.Image:
    with Image.open(io.BytesIO(raw)) as source:
        source.load()
        return source.convert("RGB")


def _ocr_messages(image_data_url: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": "You extract UI text and normalized bounding boxes. Return JSON only.",
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""Extract every meaningful visible text line from this UI screenshot.
For every line, return its normalized bbox (0-1 relative to width/height), OCR confidence,
and estimated rendered text height in source pixels. Ignore decorative gibberish unless readable.
Return exactly this JSON shape:
{OCR_CONTRACT}""",
                },
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        },
    ]


def _ui_messages(
    image_data_url: str,
    image_name: str,
    context: ReviewContext,
) -> list[dict]:
    return [
        {
            "role": "system",
            "content": "You parse UI screenshots into structured elements. Return JSON only.",
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""Parse {image_name} into meaningful UI elements.
Identify navigation, character/hero imagery, titles, primary action, rewards, resources,
panels, and other visible functional regions. Use normalized bbox coordinates.
visual_importance means visual prominence, not user importance.
Platform: {context.platform}; scenario: {context.scenario or 'unknown'}.
Return exactly:
{UI_CONTRACT}""",
                },
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        },
    ]


def _goal_messages(
    image_data_url: str,
    context: ReviewContext,
    reference_data_url: str | None,
) -> list[dict]:
    content: list[dict] = [
        {
            "type": "text",
            "text": f"""Decompose the following design goal into observable constraints.
Do not add requirements the author did not state. Separate layout, hierarchy, density,
style, anti-pattern, readability, and interaction requirements.

Design goal:
{context.design_goal or '未提供'}

Target user:
{context.target_user or '未提供'}

Platform:
{context.platform}

Return exactly:
{GOAL_CONTRACT}""",
        },
        {"type": "image_url", "image_url": {"url": image_data_url}},
    ]
    if reference_data_url:
        content.extend(
            [
                {"type": "text", "text": "The next image is the prototype reference."},
                {"type": "image_url", "image_url": {"url": reference_data_url}},
            ]
        )
    return [
        {
            "role": "system",
            "content": "You convert design goals into testable UI constraints. Return JSON only.",
        },
        {"role": "user", "content": content},
    ]


def _relevance_messages(
    image_data_url: str,
    context: ReviewContext,
    goal: GoalDecomposition,
    ui: UIResult,
    ocr: OCRResult,
    metrics: dict[str, Any],
    criteria: CriteriaLibrary,
) -> list[dict]:
    rules = [
        {
            "id": rule.id,
            "heuristic": heuristic_label(rule.heuristic),
            "title": rule.title,
            "applies_if": rule.applies_if,
            "check": rule.check,
            "mark_issue_if": rule.mark_issue_if,
            "abstain_if": rule.abstain_if,
        }
        for rule in criteria.rules
    ]
    payload = {
        "context": context.model_dump(),
        "goal_constraints": goal.model_dump(),
        "ui_elements": [element.model_dump() for element in ui.elements],
        "ocr_text": [block.text for block in ocr.blocks],
        "metrics": metrics,
        "criteria": rules,
    }
    return [
        {
            "role": "system",
            "content": "You are a retrieval reranker for UX heuristics. Return JSON only.",
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""Rank every criterion by relevance to this screenshot.
visual = visual evidence relevance, text = task/copy relevance,
attribute = platform/control/state applicability, prior = design-goal prior.
final must use:
0.45*visual + 0.25*text + 0.20*attribute + 0.10*prior.
Give compact evidence-based reasons. Do not decide issues yet.

Data:
{json.dumps(payload, ensure_ascii=False)}

Return exactly:
{RELEVANCE_CONTRACT}""",
                },
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        },
    ]


def _advanced_audit_messages(
    image_data_url: str,
    context: ReviewContext,
    goal: GoalDecomposition,
    ui: UIResult,
    ocr: OCRResult,
    metrics: dict[str, Any],
    relevance: list[dict[str, Any]],
    criteria: CriteriaLibrary,
    selected_ids: list[str],
) -> list[dict]:
    rules = [
        {
            **criteria.by_id[rule_id].model_dump(),
            "heuristic_label": heuristic_label(criteria.by_id[rule_id].heuristic),
        }
        for rule_id in selected_ids
        if rule_id in criteria.by_id
    ]
    selected_relevance = [row for row in relevance if row["selected"]]
    data = {
        "context": context.model_dump(),
        "goal": goal.model_dump(),
        "ui": ui.model_dump(),
        "ocr": ocr.model_dump(),
        "metrics": metrics,
        "criteria_relevance": selected_relevance,
    }
    return [
        {
            "role": "system",
            "content": """You are a senior interaction reviewer. Use only visible evidence.
The computed metrics are diagnostic signals; verify them against the screenshot before citing.
Do not treat decorative complexity as a defect when it supports the stated game style.
Combine multiple criteria when they describe the same visible phenomenon.
Return JSON only.""",
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""Review the screenshot against the selected criteria.
Return rule_statuses for these rule IDs only: {', '.join(selected_ids)}.
A finding must cite at least one computed metric or a clearly visible element/text anchor.
Design-goal constraints are additional evidence; they do not replace the general heuristics.
Check every goal constraint separately. A repeated content or naming contradiction that violates
commercial clarity can be reported through a goal check even if no general criterion covers it.

Perception, measurements, goal constraints, and relevance:
{json.dumps(data, ensure_ascii=False)}

Selected criteria:
{json.dumps(rules, ensure_ascii=False)}

Return exactly:
{ADVANCED_AUDIT_SCHEMA}

goal_checks must contain exactly one entry for every goal constraint ID. Use observed_violation
only when the violation is visible and has a precise evidence box.""",
                },
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        },
    ]


def _goal_findings(
    checks: list[GoalCheck],
    goal: GoalDecomposition,
    criteria: CriteriaLibrary,
) -> list[Finding]:
    constraints = {constraint.id: constraint for constraint in goal.constraints}
    findings: list[Finding] = []
    for check in checks:
        constraint = constraints.get(check.constraint_id)
        if (
            constraint is None
            or check.status != "observed_violation"
            or check.evidence is None
        ):
            continue
        findings.append(
            Finding(
                id="pending",
                rule_ids=[check.constraint_id],
                heuristics=["设计目标一致性"],
                title=check.title or constraint.text[:120],
                severity=check.severity,
                confidence=check.confidence,
                principle=f"{constraint.id} {constraint.text}",
                detection=check.detection,
                description=check.description,
                suggestion=check.suggestion,
                evidence=check.evidence,
                sources=[criteria.source],
            )
        )
    return findings


def _prefill_unselected_statuses(
    audit: AdvancedAuditResult,
    relevance: list[dict[str, Any]],
    criteria: CriteriaLibrary,
) -> None:
    existing = {status.rule_id.strip().upper() for status in audit.rule_statuses}
    selected = {
        row["rule_id"] for row in relevance if row.get("selected", False)
    }
    for rule in criteria.rules:
        if rule.id in existing:
            continue
        audit.rule_statuses.append(
            RuleStatus(
                rule_id=rule.id,
                decision=Decision.INSUFFICIENT_EVIDENCE,
                confidence=0.0,
                reason=(
                    "未进入相关性 Top-K，未执行深度检查。"
                    if rule.id not in selected
                    else "模型未返回该已选判据的结论。"
                ),
            )
        )


def _merge_goal_findings(
    findings: list[Finding],
    goal_findings: list[Finding],
) -> list[Finding]:
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    combined = [*findings, *goal_findings]
    combined.sort(
        key=lambda item: (severity_rank[item.severity.value], -item.confidence)
    )
    return [
        finding.model_copy(update={"id": f"F{index:03d}"})
        for index, finding in enumerate(combined, start=1)
    ]


def _summary_with_goal_findings(
    rule_results,
    findings,
    goal_findings: list[Finding],
):
    summary = _build_summary(rule_results, findings)
    # Goal-only findings are already in the merged findings list.
    summary.candidate_issues = len(findings)
    return summary


def _normalize_relevance(
    result: RelevanceResult,
    criteria: CriteriaLibrary,
    top_k: int,
) -> list[dict[str, Any]]:
    by_rule = {
        item.rule_id.strip().upper(): item for item in result.rankings
    }
    rows: list[dict[str, Any]] = []
    for rule in criteria.rules:
        item = by_rule.get(rule.id)
        if item is None:
            rows.append(
                {
                    "rule_id": rule.id,
                    "title": rule.title,
                    "visual": 0.0,
                    "text": 0.0,
                    "attribute": 0.0,
                    "prior": 0.0,
                    "final": 0.0,
                    "reasons": ["模型未返回该判据的相关性评分。"],
                    "selected": False,
                }
            )
            continue
        final = min(
            1.0,
            0.45 * item.visual
            + 0.25 * item.text
            + 0.20 * item.attribute
            + 0.10 * item.prior,
        )
        rows.append(
            {
                "rule_id": rule.id,
                "title": rule.title,
                "visual": round(item.visual, 4),
                "text": round(item.text, 4),
                "attribute": round(item.attribute, 4),
                "prior": round(item.prior, 4),
                "final": round(final, 4),
                "reasons": item.reasons[:5],
                "selected": False,
            }
        )
    rows.sort(key=lambda row: row["final"], reverse=True)
    for row in rows[:top_k]:
        row["selected"] = True
    rows.sort(key=lambda row: row["rule_id"])
    return rows


def _fallback_relevance(
    criteria: CriteriaLibrary,
    context: ReviewContext,
    ui: UIResult,
    goal: GoalDecomposition,
) -> RelevanceResult:
    query = " ".join(
        [
            context.design_goal or "",
            context.target_user or "",
            *(element.role for element in ui.elements),
            *(constraint.text for constraint in goal.constraints),
        ]
    ).lower()
    rankings: list[RuleRelevance] = []
    for rule in criteria.rules:
        text = " ".join(
            [rule.title, rule.applies_if, rule.check, rule.mark_issue_if]
        ).lower()
        tokens = [token for token in _bigrams(query) if token in text]
        lexical = min(1.0, len(tokens) / 8)
        attribute = 0.7
        rankings.append(
            RuleRelevance(
                rule_id=rule.id,
                visual=0.5,
                text=lexical,
                attribute=attribute,
                prior=0.3,
                final=min(1.0, 0.225 + 0.25 * lexical + 0.14 + 0.03),
                reasons=["降级排序：字符二元组匹配与默认属性先验。"],
            )
        )
    return RelevanceResult(
        scene_summary="相关性模型不可用，使用确定性降级排序。",
        rankings=rankings,
    )


def _fallback_constraints(goal: str) -> list[Any]:
    if not goal:
        return []
    from .advanced_contracts import GoalConstraint

    return [
        GoalConstraint(
            id="G01",
            text=goal,
            category="other",
            metric_hint="人工复核文本目标",
            priority=1,
        )
    ]


def _stage(message: str) -> None:
    print(f"[review-v2] {message}", file=sys.stderr, flush=True)


def _bigrams(text: str) -> set[str]:
    compact = "".join(char for char in text if not char.isspace())
    return {compact[index : index + 2] for index in range(max(0, len(compact) - 1))}


def _draw_elements(
    image: Image.Image,
    ui: UIResult,
    output: Path,
) -> None:
    canvas = image.copy()
    draw = ImageDraw.Draw(canvas)
    colors = {
        "primary_button": "#ff3b30",
        "secondary_button": "#ff9500",
        "button": "#ff9500",
        "nav": "#007aff",
        "character": "#af52de",
        "reward_card": "#34c759",
        "resource": "#ffcc00",
    }
    for element in ui.elements:
        x1, y1, x2, y2 = _pixel_box(element.bbox.as_list(), image.size)
        color = colors.get(element.role.lower(), "#8e8e93")
        draw.rectangle((x1, y1, x2, y2), outline=color, width=4)
        label = f"{element.id} {element.role} {element.label}".strip()
        draw.rectangle((x1, max(0, y1 - 24), x1 + min(500, len(label) * 9), y1), fill=color)
        draw.text((x1 + 4, max(1, y1 - 22)), label, fill="white")
    canvas.save(output)


def _draw_focus(
    image: Image.Image,
    metrics: dict[str, Any],
    output: Path,
) -> None:
    canvas = image.copy()
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    focus_rows = metrics.get("focus", {}).get("elements", [])
    max_share = max((row.get("focus_share", 0) for row in focus_rows), default=1)
    for row in focus_rows:
        x1, y1, x2, y2 = _pixel_box(row["bbox"], image.size)
        intensity = int(45 + 150 * (row.get("focus_share", 0) / max(0.0001, max_share)))
        draw.rectangle((x1, y1, x2, y2), fill=(255, 48, 48, min(190, intensity)))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)
    canvas.convert("RGB").save(output)


def _pixel_box(
    box: list[float],
    size: tuple[int, int],
) -> tuple[int, int, int, int]:
    x, y, width, height = box
    return (
        round(x * size[0]),
        round(y * size[1]),
        round((x + width) * size[0]),
        round((y + height) * size[1]),
    )
