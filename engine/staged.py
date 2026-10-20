"""Cacheable step-by-step review runner for controlled evaluation."""

from __future__ import annotations

import csv
import hashlib
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
from pydantic import BaseModel, ValidationError

from .advanced_contracts import NarrativeResult
from .advanced import (
    ADVANCED_AUDIT_SCHEMA,
    AdvancedAuditResult,
    GoalDecomposition,
    OCR_CONTRACT,
    OCRResult,
    RELEVANCE_CONTRACT,
    RelevanceResult,
    UI_CONTRACT,
    UIResult,
    AdvancedReviewEngine,
    _advanced_audit_messages,
    _draw_elements,
    _draw_focus,
    _goal_findings,
    _goal_messages,
    _merge_goal_findings,
    _normalize_relevance,
    _ocr_messages,
    _prefill_unselected_statuses,
    _relevance_messages,
    _summary_with_goal_findings,
    _ui_messages,
)
from .contracts import (
    ImageInfo,
    ModelInfo,
    ReviewContext,
    ReviewReport,
    ScreenAnalysis,
)
from .criteria import CriteriaLibrary
from .cv_metrics import compute_pipeline_metrics
from .errors import EngineError
from .imaging import prepare_image
from .parsing import parse_json_object
from .prompting import build_repair_messages
from .service import _elapsed_ms

STAGE_ORDER = [
    "prepare",
    "ocr",
    "ui",
    "reference_ui",
    "goal",
    "metrics",
    "relevance",
    "audit",
    "report",
    "narrative",
]

NARRATIVE_CONTRACT = """{
  "title": "string",
  "executive_summary": "string",
  "stages": [
    {"stage": "string", "purpose": "string", "conclusion": "string"}
  ],
  "metrics": [
    {
      "metric": "string",
      "value": "string",
      "why_measured": "string",
      "interpretation": "string"
    }
  ],
  "findings": [
    {
      "finding_id": "F001",
      "judgment_source": "string",
      "explanation": "string",
      "user_impact": "string",
      "action_rationale": "string"
    }
  ],
  "relevance": [
    {"rule_id": "R01", "why_relevant": "string"}
  ],
  "limitations": ["string"],
  "next_steps": ["string"]
}"""


class StageRun:
    def __init__(self, run_dir: str | Path, criteria: CriteriaLibrary) -> None:
        self.run_dir = Path(run_dir).resolve()
        self.criteria = criteria
        self.manifest_path = self.run_dir / "manifest.json"
        self.manifest = _read_json(self.manifest_path)
        self.helper = AdvancedReviewEngine(criteria)

    async def run(self, stage: str) -> dict[str, Any]:
        if stage not in STAGE_ORDER:
            raise EngineError(
                "invalid_stage",
                f"Unknown stage {stage}. Expected one of: {', '.join(STAGE_ORDER)}",
                status_code=422,
            )
        if stage == "prepare":
            raise EngineError(
                "prepare_requires_init",
                "Create a run with `python -m engine stage-init ...`.",
                status_code=422,
            )
        self._require_dependency(stage)
        started = time.perf_counter()
        self._mark(stage, "running")
        try:
            if stage == "ocr":
                result = await self._run_ocr()
            elif stage == "ui":
                result = await self._run_ui()
            elif stage == "reference_ui":
                result = await self._run_reference_ui()
            elif stage == "goal":
                result = await self._run_goal()
            elif stage == "metrics":
                result = self._run_metrics()
            elif stage == "relevance":
                result = await self._run_relevance()
            elif stage == "audit":
                result = await self._run_audit()
            elif stage == "report":
                result = self._run_report()
            elif stage == "narrative":
                result = await self._run_narrative()
            else:
                raise AssertionError(stage)
        except Exception as exc:
            self._mark(
                stage,
                "failed",
                elapsed_ms=_elapsed_ms(started),
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            raise
        self._mark(
            stage,
            "completed",
            elapsed_ms=_elapsed_ms(started),
            **result,
        )
        if stage == "narrative":
            narrative = NarrativeResult.model_validate(
                _read_json(self.run_dir / "narrative.json")
            )
            report = ReviewReport.model_validate(
                _read_json(self.run_dir / "report.json")
            )
            (self.run_dir / "showcase_report.md").write_text(
                _showcase_markdown(report, narrative, self.manifest),
                encoding="utf-8",
            )
        return self.manifest["stages"][stage]

    async def _run_ocr(self) -> dict[str, Any]:
        image = _load_image(self.run_dir / "image.png")
        prepared = prepare_image((self.run_dir / "image.png").read_bytes())
        parsed, meta = await self._schema_call(
            model=self.helper.ocr,
            messages=_ocr_messages(prepared.data_url),
            schema=OCRResult,
            contract=OCR_CONTRACT,
            label="ocr",
            extra_body={"enable_thinking": False},
        )
        output = self.run_dir / "ocr.json"
        _write_json(output, parsed.model_dump())
        return _result(output, parsed, meta)

    async def _run_ui(self) -> dict[str, Any]:
        prepared = prepare_image((self.run_dir / "image.png").read_bytes())
        context = self._context()
        parsed, meta = await self._schema_call(
            model=self.helper.gui,
            messages=_ui_messages(prepared.data_url, "成果截图", context),
            schema=UIResult,
            contract=UI_CONTRACT,
            label="ui",
            extra_body={"enable_thinking": False},
        )
        output = self.run_dir / "ui.json"
        _write_json(output, parsed.model_dump())
        return _result(output, parsed, meta)

    async def _run_reference_ui(self) -> dict[str, Any]:
        if not (self.run_dir / "reference.png").exists():
            raise EngineError(
                "reference_missing",
                "This run has no prototype reference image.",
                status_code=422,
            )
        prepared = prepare_image((self.run_dir / "reference.png").read_bytes())
        context = self._context()
        parsed, meta = await self._schema_call(
            model=self.helper.gui,
            messages=_ui_messages(prepared.data_url, "设计原型参考", context),
            schema=UIResult,
            contract=UI_CONTRACT,
            label="reference_ui",
            extra_body={"enable_thinking": False},
        )
        output = self.run_dir / "reference_ui.json"
        _write_json(output, parsed.model_dump())
        return _result(output, parsed, meta)

    async def _run_goal(self) -> dict[str, Any]:
        prepared = prepare_image((self.run_dir / "image.png").read_bytes())
        reference_data = None
        if (self.run_dir / "reference.png").exists():
            reference_data = prepare_image(
                (self.run_dir / "reference.png").read_bytes()
            ).data_url
        parsed, meta = await self._schema_call(
            model=self.helper.reasoning,
            messages=_goal_messages(prepared.data_url, self._context(), reference_data),
            schema=GoalDecomposition,
            contract=_contract_from_class(GoalDecomposition),
            label="goal",
            extra_body={"enable_thinking": False},
        )
        output = self.run_dir / "goal.json"
        _write_json(output, parsed.model_dump())
        return _result(output, parsed, meta)

    def _run_metrics(self) -> dict[str, Any]:
        image = _load_image(self.run_dir / "image.png")
        ui = UIResult.model_validate(_read_json(self.run_dir / "ui.json"))
        ocr = OCRResult.model_validate(_read_json(self.run_dir / "ocr.json"))
        reference_ui = None
        reference_path = self.run_dir / "reference_ui.json"
        if reference_path.exists():
            reference_ui = UIResult.model_validate(_read_json(reference_path))
        metrics = compute_pipeline_metrics(
            image,
            ui.elements,
            ocr.blocks,
            reference_ui.elements if reference_ui else None,
        )
        output = self.run_dir / "metrics.json"
        _write_json(output, metrics)
        _draw_elements(image, ui, self.run_dir / "overlay_elements.png")
        _draw_focus(image, metrics, self.run_dir / "overlay_focus.png")
        return {
            "outputs": [str(output), str(self.run_dir / "overlay_elements.png"), str(self.run_dir / "overlay_focus.png")],
            "summary": {
                "elements": len(ui.elements),
                "ocr_blocks": len(ocr.blocks),
                "focus_elements": len(metrics.get("focus", {}).get("elements", [])),
            },
        }

    async def _run_relevance(self) -> dict[str, Any]:
        prepared = prepare_image((self.run_dir / "image.png").read_bytes())
        goal = GoalDecomposition.model_validate(_read_json(self.run_dir / "goal.json"))
        ui = UIResult.model_validate(_read_json(self.run_dir / "ui.json"))
        ocr = OCRResult.model_validate(_read_json(self.run_dir / "ocr.json"))
        metrics = _read_json(self.run_dir / "metrics.json")
        parsed, meta = await self._schema_call(
            model=self.helper.reasoning,
            messages=_relevance_messages(
                prepared.data_url,
                self._context(),
                goal,
                ui,
                ocr,
                metrics,
                self.criteria,
            ),
            schema=RelevanceResult,
            contract=RELEVANCE_CONTRACT,
            label="relevance",
            extra_body={"enable_thinking": False},
        )
        normalized = _normalize_relevance(parsed, self.criteria, self.helper.top_k)
        output = self.run_dir / "relevance.json"
        _write_json(output, normalized)
        csv_path = self.run_dir / "criteria_relevance.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
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
            for row in normalized:
                writer.writerow(
                    {
                        **{key: row.get(key) for key in writer.fieldnames if key != "reasons"},
                        "reasons": " | ".join(row.get("reasons", [])),
                    }
                )
        return {
            "outputs": [str(output), str(csv_path)],
            **meta,
            "summary": {
                "selected": [row["rule_id"] for row in normalized if row["selected"]],
            },
        }

    async def _run_audit(self) -> dict[str, Any]:
        prepared = prepare_image((self.run_dir / "image.png").read_bytes())
        goal = GoalDecomposition.model_validate(_read_json(self.run_dir / "goal.json"))
        ui = UIResult.model_validate(_read_json(self.run_dir / "ui.json"))
        ocr = OCRResult.model_validate(_read_json(self.run_dir / "ocr.json"))
        metrics = _read_json(self.run_dir / "metrics.json")
        relevance = _read_json(self.run_dir / "relevance.json")
        selected_ids = [row["rule_id"] for row in relevance if row["selected"]]
        parsed, meta = await self._schema_call(
            model=self.helper.reasoning,
            messages=_advanced_audit_messages(
                prepared.data_url,
                self._context(),
                goal,
                ui,
                ocr,
                metrics,
                relevance,
                self.criteria,
                selected_ids,
            ),
            schema=AdvancedAuditResult,
            contract=ADVANCED_AUDIT_SCHEMA,
            label="audit",
            extra_body={"enable_thinking": True, "thinking_budget": 1200},
        )
        output = self.run_dir / "audit.json"
        _write_json(output, parsed.model_dump())
        return _result(output, parsed, meta)

    async def _run_narrative(self) -> dict[str, Any]:
        report = ReviewReport.model_validate(_read_json(self.run_dir / "report.json"))
        image_data = prepare_image((self.run_dir / "image.png").read_bytes()).data_url
        overlay_data = prepare_image(
            (self.run_dir / "overlay_elements.png").read_bytes()
        ).data_url
        payload = {
            "model": report.model.model_dump(),
            "status": report.status,
            "summary": report.summary.model_dump(),
            "context": report.context.model_dump(),
            "screen_analysis": report.screen_analysis.model_dump(),
            "goal_constraints": report.goal_constraints,
            "goal_checks": report.goal_checks,
            "findings": [finding.model_dump() for finding in report.findings],
            "criteria_relevance": [
                row for row in report.criteria_relevance if row.get("selected")
            ],
            "diagnostics": report.diagnostics,
            "stages": self.manifest.get("stages", {}),
        }
        parsed, meta = await self._schema_call(
            model=self.helper.reasoning,
            messages=_narrative_messages(payload, image_data, overlay_data),
            schema=NarrativeResult,
            contract=NARRATIVE_CONTRACT,
            label="narrative",
            extra_body={"enable_thinking": False},
            repair=True,
        )
        output = self.run_dir / "narrative.json"
        _write_json(output, parsed.model_dump())
        showcase = self.run_dir / "showcase_report.md"
        showcase.write_text(
            _showcase_markdown(report, parsed, self.manifest),
            encoding="utf-8",
        )
        return {
            "outputs": [str(output), str(showcase), meta.get("raw_output")],
            **meta,
            "summary": {
                "metric_explanations": len(parsed.metrics),
                "finding_explanations": len(parsed.findings),
            },
        }

    def _run_report(self) -> dict[str, Any]:
        audit = AdvancedAuditResult.model_validate(
            _read_json(self.run_dir / "audit.json")
        )
        goal = GoalDecomposition.model_validate(_read_json(self.run_dir / "goal.json"))
        ui = UIResult.model_validate(_read_json(self.run_dir / "ui.json"))
        ocr = OCRResult.model_validate(_read_json(self.run_dir / "ocr.json"))
        metrics = _read_json(self.run_dir / "metrics.json")
        relevance = _read_json(self.run_dir / "relevance.json")
        _prefill_unselected_statuses(audit, relevance, self.criteria)
        findings, rule_results, normalization_warnings = self.helper.review_helper._normalize(
            audit
        )
        goal_findings = _goal_findings(audit.goal_checks, goal, self.criteria)
        findings = _merge_goal_findings(findings, goal_findings)
        image_path = self.run_dir / "image.png"
        with Image.open(image_path) as source:
            source.load()
            width, height = source.size
        raw = image_path.read_bytes()
        screen = ScreenAnalysis(
            page_type=ui.page_type,
            visible_text=[block.text for block in ocr.blocks],
            regions=[f"{element.role}: {element.label}" for element in ui.elements],
            controls=[
                f"{element.role}: {element.label}"
                for element in ui.elements
                if element.interactable
            ],
            observed_states=[element.state for element in ui.elements],
            task_clues=[goal.page_summary] if goal.page_summary else [],
            uncertainties=ui.uncertainties,
        )
        report = ReviewReport(
            review_id=self.run_dir.name,
            status="partial" if normalization_warnings else "completed",
            model=ModelInfo(
                provider="qwen",
                model=self.helper.reasoning_model_name,
                analysis_mode="ensemble",
                is_stub=False,
            ),
            context=self._context(),
            image=ImageInfo(
                sha256=hashlib.sha256(raw).hexdigest(),
                mime_type="image/png",
                width=width,
                height=height,
                original_width=width,
                original_height=height,
                resized=False,
            ),
            screen_analysis=screen,
            criteria_version=self.criteria.version,
            criteria_source=self.criteria.source,
            summary=_summary_with_goal_findings(
                rule_results,
                findings,
                goal_findings,
            ),
            findings=findings,
            rule_results=rule_results,
            warnings=normalization_warnings,
            timings_ms=_stage_timings(self.manifest),
            diagnostics=metrics,
            perception={
                "ocr": ocr.model_dump(),
                "elements": ui.model_dump(),
                "reference_elements": _read_json(self.run_dir / "reference_ui.json")
                if (self.run_dir / "reference_ui.json").exists()
                else None,
            },
            criteria_relevance=relevance,
            goal_constraints=[constraint.model_dump() for constraint in goal.constraints],
            goal_checks=[check.model_dump() for check in audit.goal_checks],
            artifacts={
                "overlay_elements": str(self.run_dir / "overlay_elements.png"),
                "overlay_focus": str(self.run_dir / "overlay_focus.png"),
                "criteria_relevance_csv": str(
                    self.run_dir / "criteria_relevance.csv"
                ),
            },
        )
        output = self.run_dir / "report.json"
        _write_json(output, report.model_dump(mode="json"))
        markdown = self.run_dir / "report.md"
        markdown.write_text(_markdown_report(report), encoding="utf-8")
        return {
            "outputs": [str(output), str(markdown)],
            "summary": {
                "findings": len(findings),
                "candidate_rules": report.summary.candidate_issues,
            },
        }

    async def _schema_call(
        self,
        *,
        model,
        messages: list[dict],
        schema: type[BaseModel],
        contract: str,
        label: str,
        extra_body: dict[str, Any] | None,
        repair: bool = False,
    ) -> tuple[BaseModel, dict[str, Any]]:
        raw_dir = self.run_dir / "raw"
        raw_dir.mkdir(exist_ok=True)
        result = await model.complete(
            messages,
            json_mode=True,
            extra_body=extra_body,
        )
        raw_path = raw_dir / f"{label}.raw.txt"
        raw_path.write_text(result.text, encoding="utf-8")
        meta = {
            "model": result.model,
            "latency_ms": result.latency_ms,
            "usage": result.usage,
            "raw_output": str(raw_path),
        }
        try:
            return schema.model_validate(parse_json_object(result.text)), meta
        except (ValueError, ValidationError) as exc:
            if repair:
                repaired = await model.complete(
                    build_repair_messages(result.text, str(exc), contract),
                    json_mode=True,
                    extra_body=extra_body,
                )
                repaired_path = raw_dir / f"{label}.repair.raw.txt"
                repaired_path.write_text(repaired.text, encoding="utf-8")
                try:
                    parsed = schema.model_validate(parse_json_object(repaired.text))
                    meta["repair_raw_output"] = str(repaired_path)
                    return parsed, meta
                except (ValueError, ValidationError) as repaired_exc:
                    exc = repaired_exc
            raise EngineError(
                "stage_contract_failed",
                f"{label} did not return the required JSON contract.",
                status_code=502,
                retryable=False,
                details={
                    "validation_error": str(exc),
                    "raw_output": str(raw_path),
                },
            ) from exc

    def _context(self) -> ReviewContext:
        return ReviewContext.model_validate(self.manifest["context"])

    def _require_dependency(self, stage: str) -> None:
        dependencies = {
            "ocr": ["prepare"],
            "ui": ["prepare"],
            "reference_ui": ["prepare"],
            "goal": ["prepare"],
            "metrics": ["ocr", "ui"],
            "relevance": ["ocr", "ui", "goal", "metrics"],
            "audit": ["ocr", "ui", "goal", "metrics", "relevance"],
            "report": ["ocr", "ui", "goal", "metrics", "relevance", "audit"],
            "narrative": ["report"],
        }
        missing = [
            dependency
            for dependency in dependencies.get(stage, [])
            if self.manifest.get("stages", {}).get(dependency, {}).get("status")
            != "completed"
        ]
        if missing:
            raise EngineError(
                "stage_dependency_missing",
                f"Stage {stage} requires completed stages: {', '.join(missing)}.",
                status_code=409,
            )

    def _mark(self, stage: str, status: str, **payload: Any) -> None:
        stages = self.manifest.setdefault("stages", {})
        entry = stages.setdefault(stage, {})
        if status == "running":
            entry.clear()
        else:
            entry.pop("error", None)
        entry.update({"status": status, "updated_at": _now(), **payload})
        _write_json(self.manifest_path, self.manifest)


def init_stage_run(
    *,
    image_path: str | Path,
    reference_path: str | Path | None,
    goal: str,
    context: ReviewContext,
    artifact_root: str | Path = "out/stages",
) -> Path:
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    run_dir = Path(artifact_root).resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    image = _load_image(Path(image_path))
    image.save(run_dir / "image.png")
    if reference_path:
        _load_image(Path(reference_path)).save(run_dir / "reference.png")
    manifest = {
        "run_id": run_id,
        "created_at": _now(),
        "goal": goal,
        "context": {
            **context.model_dump(),
            "design_goal": goal,
        },
        "image": str(run_dir / "image.png"),
        "reference": str(run_dir / "reference.png")
        if reference_path
        else None,
        "stages": {
            "prepare": {
                "status": "completed",
                "elapsed_ms": 0,
                "updated_at": _now(),
            }
        },
    }
    _write_json(run_dir / "manifest.json", manifest)
    return run_dir


def read_manifest(run_dir: str | Path) -> dict[str, Any]:
    return _read_json(Path(run_dir).resolve() / "manifest.json")


def _result(output: Path, parsed: BaseModel, meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "outputs": [str(output), meta.get("raw_output")],
        **meta,
        "summary": _model_summary(parsed),
    }


def _model_summary(parsed: BaseModel) -> dict[str, Any]:
    if isinstance(parsed, OCRResult):
        return {"ocr_blocks": len(parsed.blocks)}
    if isinstance(parsed, UIResult):
        return {"elements": len(parsed.elements), "page_type": parsed.page_type}
    if isinstance(parsed, GoalDecomposition):
        return {"constraints": len(parsed.constraints)}
    if isinstance(parsed, AdvancedAuditResult):
        return {
            "rule_statuses": len(parsed.rule_statuses),
            "findings": len(parsed.findings),
        }
    return {}


def _stage_timings(manifest: dict[str, Any]) -> dict[str, int]:
    return {
        stage: int(entry.get("elapsed_ms", 0))
        for stage, entry in manifest.get("stages", {}).items()
    }


def _contract_from_class(model: type[BaseModel]) -> str:
    if model is GoalDecomposition:
        return """{"page_summary":"string","constraints":[{"id":"G01","text":"string","category":"layout|hierarchy|density|style|anti_pattern|readability|interaction|other","metric_hint":"string","target_roles":["string"],"priority":1}]}"""
    return model.model_json_schema().__str__()


def _load_image(path: str | Path) -> Image.Image:
    with Image.open(path) as image:
        image.load()
        return image.convert("RGB")


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, value: Any) -> None:
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _narrative_messages(
    payload: dict[str, Any],
    image_data_url: str,
    overlay_data_url: str,
) -> list[dict]:
    return [
        {
            "role": "system",
                    "content": """You write an evidence-first Chinese UI evaluation report.
Use only the supplied stage outputs. Do not add new findings, coordinates, metrics, or design judgments.
Explain why each selected metric is useful, report its actual value, and connect it to a conclusion only
when the supplied evidence supports that conclusion. Keep the difference between deterministic
visual-focus proxies and measured human attention explicit. Do not mention prompts, reviewers,
conversation context, internal model routing, or how the report was requested. Return JSON only.""",
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""Write a comprehensive showcase report.
The first image is the reviewed screenshot. The second image is the UI-element overlay.
Explain the evaluation process and why the metrics matter in clear professional language.
Return exactly one stage note per stage and no more than 8 metric notes. Keep every string concise.
Every finding note must include judgment_source, explanation, user_impact, and action_rationale.
Escape quotes correctly and return a complete JSON object.

Use the actual data below; never invent numbers:
{json.dumps(payload, ensure_ascii=False)}

Return exactly this JSON shape:
{NARRATIVE_CONTRACT}""",
                },
                {"type": "image_url", "image_url": {"url": image_data_url}},
                {"type": "image_url", "image_url": {"url": overlay_data_url}},
            ],
        },
    ]


def _showcase_markdown(
    report: ReviewReport,
    narrative: NarrativeResult,
    manifest: dict[str, Any],
    file_map: dict[str, str] | None = None,
) -> str:
    file_map = file_map or {}
    lines = [
        f"# {narrative.title}",
        "",
        f"> 运行编号：`{report.review_id}`",
        f"> 状态：`{report.status}`",
        f"> 综合审查模型：`{report.model.provider}/{report.model.model}`",
        f"> 通用判据版本：`{report.criteria_version}`",
        "",
        "## 一、结论摘要",
        "",
        narrative.executive_summary,
        "",
        "## 二、输入材料",
        "",
        "### 成果截图",
        "",
        f"![成果截图]({_mapped_file('image.png', file_map)})",
        "",
        "### 原型参考",
        "",
        f"![原型参考]({_mapped_file('reference.png', file_map)})",
        "",
        "### UI 元素识别叠加图",
        "",
        f"![UI 元素识别]({_mapped_file('overlay_elements.png', file_map)})",
        "",
        "### 视觉焦点代理叠加图",
        "",
        f"![视觉焦点代理]({_mapped_file('overlay_focus.png', file_map)})",
        "",
        "> 焦点图为确定性显著性代理，不等同于真实用户注意力预测。",
        "",
        "## 三、编号说明",
        "",
        f"- `{_goal_range(report.goal_checks)}` 表示本轮评审采用的目标约束编号。",
        "- `F` 系列表示最终问题编号，编号仅在当前报告内有效。",
        "",
        "## 四、处理流程与过程产物",
        "",
        "| 阶段 | 目的 | 模型 | 耗时 | 结论 |",
        "| --- | --- | --- | ---: | --- |",
    ]
    stage_notes = {note.stage: note for note in narrative.stages}
    io_map = _stage_io_map()
    for stage in STAGE_ORDER:
        entry = manifest.get("stages", {}).get(stage)
        if not entry:
            continue
        note = stage_notes.get(stage)
        elapsed = round(int(entry.get("elapsed_ms", 0)) / 1000, 2)
        model = entry.get("model", "deterministic")
        lines.append(
            f"| {stage} | {_md(note.purpose if note else _default_stage_purpose(stage))} | "
            f"{_md(model)} | {elapsed}s | "
            f"{_md(note.conclusion if note and note.conclusion else _manifest_stage_conclusion(stage, entry))} |"
        )

    lines.extend(
        [
            "",
            "### 各阶段输入与输出文件",
            "",
            "| 阶段 | 输入 | 输出 |",
            "| --- | --- | --- |",
        ]
    )
    for stage in STAGE_ORDER:
        if stage not in manifest.get("stages", {}):
            continue
        inputs, outputs = io_map.get(stage, ([], []))
        lines.append(
            f"| {stage} | {_file_links(inputs, file_map)} | {_file_links(outputs, file_map)} |"
        )

    lines.extend(
        [
            "",
            "## 五、关键计算参数及解释",
            "",
            "| 参数 | 实测值 | 为什么计算 | 如何用于结论 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for metric in narrative.metrics:
        lines.append(
            f"| {_md(metric.metric)} | {_md(metric.value)} | "
            f"{_md(metric.why_measured)} | {_md(metric.interpretation)} |"
        )

    lines.extend(
        [
            "",
            "### 目标约束逐项检查",
            "",
            "| 约束 | 状态 | 模型给出的检查结论 | 置信度 |",
            "| --- | --- | --- | ---: |",
        ]
    )
    for check in report.goal_checks:
        lines.append(
            f"| {check.get('constraint_id')} | {check.get('status')} | "
            f"{_md(check.get('description') or check.get('title'))} | "
            f"{check.get('confidence')} |"
        )

    lines.extend(
        [
            "",
            "## 六、判据相关性",
            "",
            "| 判据 | 标题 | 视觉 | 文本 | 属性 | 先验 | 综合 | 相关性说明 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    relevance_notes = {note.rule_id: note for note in narrative.relevance}
    for row in report.criteria_relevance:
        if not row.get("selected"):
            continue
        note = relevance_notes.get(row["rule_id"])
        lines.append(
            f"| {row['rule_id']} | {_md(row['title'])} | {row['visual']} | "
            f"{row['text']} | {row['attribute']} | {row['prior']} | "
            f"{row['final']} | {_md(note.why_relevant if note else ' | '.join(row.get('reasons', [])))} |"
        )

    lines.extend(["", "## 七、问题与修改建议", ""])
    notes = {note.finding_id: note for note in narrative.findings}
    if not report.findings:
        lines.append("本次程序未发现达到证据门槛的问题。")
    for finding in report.findings:
        note = notes.get(finding.id)
        lines.extend(
            [
                f"### {finding.id} · {_md(finding.title)}",
                "",
                f"- **严重度**：`{finding.severity.value}`",
                f"- **置信度**：`{finding.confidence}`",
                "- **判断依据**：目标约束检查与截图证据",
                f"- **原则**：{_md(finding.principle)}",
                f"- **检测**：{_md(finding.detection)}",
                f"- **用户影响**：{_md(note.user_impact if note else finding.description)}",
                f"- **修改建议**：{_md(finding.suggestion)}",
                f"- **建议理由**：{_md(note.action_rationale if note else '')}",
                f"- **证据**：`{json.dumps(finding.evidence.model_dump(), ensure_ascii=False)}`",
                "",
            ]
        )

    lines.extend(["## 八、MVP 边界与限制", ""])
    for item in narrative.limitations:
        lines.append(f"- {_md(item)}")
    if not narrative.limitations:
        lines.append("- 当前只有单张样本，尚不能形成统计层面的召回率与误报率结论。")

    lines.extend(["", "## 九、下一步", ""])
    for item in narrative.next_steps:
        lines.append(f"- {_md(item)}")

    lines.extend(
        [
            "",
            "## 十、源数据文件",
            "",
            "| 内容 | 文件 |",
            "| --- | --- |",
        ]
    )
    for label, filename in _source_files():
        mapped = _mapped_file(filename, file_map)
        lines.append(f"| {label} | [{mapped}]({mapped}) |")
    lines.extend(
        [
            "",
            "## 附：运行耗时",
            "",
            f"总耗时约 `{sum(int(entry.get('elapsed_ms', 0)) for entry in manifest.get('stages', {}).values()) / 1000:.2f}` 秒。",
            "",
        ]
    )
    return "\n".join(lines)


def _stage_io_map() -> dict[str, tuple[list[str], list[str]]]:
    return {
        "prepare": (["image.png", "reference.png"], ["manifest.json"]),
        "ocr": (["image.png"], ["ocr.json", "raw/ocr.raw.txt"]),
        "ui": (["image.png"], ["ui.json", "raw/ui.raw.txt"]),
        "reference_ui": (
            ["reference.png"],
            ["reference_ui.json", "raw/reference_ui.raw.txt"],
        ),
        "goal": (
            ["image.png", "reference.png", "design goal"],
            ["goal.json", "raw/goal.raw.txt"],
        ),
        "metrics": (
            ["image.png", "ui.json", "reference_ui.json", "ocr.json"],
            ["metrics.json", "overlay_elements.png", "overlay_focus.png"],
        ),
        "relevance": (
            ["ocr.json", "ui.json", "goal.json", "metrics.json", "image.png"],
            ["relevance.json", "criteria_relevance.csv", "raw/relevance.raw.txt"],
        ),
        "audit": (
            ["image.png", "ocr.json", "ui.json", "goal.json", "metrics.json", "relevance.json"],
            ["audit.json", "raw/audit.raw.txt"],
        ),
        "report": (
            ["audit.json", "metrics.json", "relevance.json", "goal.json"],
            ["report.json", "report.md"],
        ),
        "narrative": (
            ["report.json", "image.png", "overlay_elements.png"],
            ["narrative.json", "showcase_report.md", "raw/narrative.raw.txt"],
        ),
    }


def _source_files() -> list[tuple[str, str]]:
    return [
        ("成果截图", "image.png"),
        ("原型参考", "reference.png"),
        ("运行清单与各阶段耗时", "manifest.json"),
        ("OCR 解析", "ocr.json"),
        ("UI 元素解析", "ui.json"),
        ("原型元素解析", "reference_ui.json"),
        ("目标约束拆解", "goal.json"),
        ("确定性指标", "metrics.json"),
        ("判据相关性", "relevance.json"),
        ("判据相关性表格", "criteria_relevance.csv"),
        ("最终审查原始结果", "audit.json"),
        ("机器可读汇总报告", "report.json"),
        ("综合展示报告", "showcase_report.md"),
    ]


def _file_links(files: list[str], file_map: dict[str, str]) -> str:
    result = []
    for filename in files:
        if "/" in filename or "." in filename:
            mapped = _mapped_file(filename, file_map)
            result.append(f"[{mapped}]({mapped})")
        else:
            result.append(filename)
    return "<br>".join(result) if result else "—"


def _mapped_file(filename: str, file_map: dict[str, str]) -> str:
    if filename in file_map:
        return file_map[filename]
    if "/" in filename:
        prefix, child = filename.split("/", 1)
        mapped_child = file_map.get(child, child)
        return f"{prefix}/{mapped_child}"
    return filename


def _default_stage_purpose(stage: str) -> str:
    return {
        "prepare": "保存原始输入并建立可复现运行目录",
        "ocr": "提取文字、坐标和可读性所需数据",
        "ui": "识别控件、角色和各功能区域",
        "reference_ui": "解析原型布局用于对照",
        "goal": "把设计目标拆成可观察约束",
        "metrics": "计算确定性视觉、密度、可读性和一致性参数",
        "relevance": "为 24 条通用判据计算相关性",
        "audit": "由综合模型逐项检查高相关判据和目标约束",
        "report": "规范化问题编号和机器可读结果",
        "narrative": "生成综合评审报告",
    }.get(stage, "")


def _manifest_stage_conclusion(stage: str, entry: dict[str, Any]) -> str:
    summary = entry.get("summary", {}) if isinstance(entry, dict) else {}
    if stage == "prepare":
        return "成果截图、原型参考和运行上下文已保存。"
    if stage == "ocr":
        return f"提取 {summary.get('ocr_blocks', '—')} 个文本块。"
    if stage == "ui":
        return f"识别 {summary.get('elements', '—')} 个 UI 元素。"
    if stage == "reference_ui":
        return f"识别 {summary.get('elements', '—')} 个原型元素。"
    if stage == "metrics":
        return (
            f"完成 {summary.get('elements', '—')} 个元素、"
            f"{summary.get('ocr_blocks', '—')} 个文本块的指标计算。"
        )
    if stage == "relevance":
        selected = summary.get("selected", [])
        return f"选择 {len(selected)} 条高相关判据：{', '.join(selected)}。"
    if stage == "report":
        return (
            f"生成 {summary.get('findings', 0)} 条正式问题，"
            "并完成编号规范化。"
        )
    if stage == "narrative":
        return (
            f"解释 {summary.get('metric_explanations', 0)} 个指标、"
            f"{summary.get('finding_explanations', 0)} 条问题。"
        )
    return "阶段完成。"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _markdown_report(report: ReviewReport) -> str:
    lines = [
        f"# 交互方案评审报告 {report.review_id}",
        "",
        f"- 状态：`{report.status}`",
        f"- 模型：`{report.model.provider}/{report.model.model}`",
        f"- 判据版本：`{report.criteria_version}`",
        f"- 发现数量：{len(report.findings)}",
        "",
        "## 目标约束",
        "",
        "| 约束 | 状态 | 标题 | 置信度 |",
        "| --- | --- | --- | --- |",
    ]
    for check in report.goal_checks:
        lines.append(
            f"| {check.get('constraint_id')} | {check.get('status')} | "
            f"{_md(check.get('title', ''))} | {check.get('confidence', '')} |"
        )

    lines.extend(["", "## 问题清单", ""])
    if not report.findings:
        lines.append("未发现通过当前证据门槛的问题。")
    for finding in report.findings:
        lines.extend(
            [
                f"### {finding.id} [{finding.severity.value}] {_md(finding.title)}",
                "",
                f"- 原则：{_md(finding.principle)}",
                f"- 检测：{_md(finding.detection)}",
                f"- 描述：{_md(finding.description)}",
                f"- 建议：{_md(finding.suggestion)}",
                f"- 置信度：{finding.confidence}",
                f"- 证据区域：`{finding.evidence.model_dump()}`",
                "",
            ]
        )

    selected = [row for row in report.criteria_relevance if row.get("selected")]
    lines.extend(
        [
            "## 高相关判据",
            "",
            "| 判据 | 标题 | 视觉 | 文本 | 属性 | 先验 | 综合 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in selected:
        lines.append(
            f"| {row['rule_id']} | {_md(row['title'])} | {row['visual']} | "
            f"{row['text']} | {row['attribute']} | {row['prior']} | {row['final']} |"
        )

    focus = report.diagnostics.get("focus", {}).get("elements", [])[:5]
    global_metrics = report.diagnostics.get("global", {})
    readability = report.diagnostics.get("readability", {})
    lines.extend(
        [
            "",
            "## 关键计算参数",
            "",
            f"- 平均亮度：{global_metrics.get('mean_luminance')}",
            f"- 亮度对比标准差：{global_metrics.get('luminance_contrast')}",
            f"- 高饱和像素比例：{global_metrics.get('high_saturation_fraction')}",
            f"- 边缘密度：{global_metrics.get('edge_density')}",
            f"- 高频细节均值：{global_metrics.get('high_frequency_mean')}",
            f"- 负空间代理：{global_metrics.get('negative_space_proxy')}",
            f"- OCR 文本块：{readability.get('text_block_count')}",
            f"- 低对比文本：{readability.get('low_contrast_count')}",
            f"- 文本高度 P10/P50：{readability.get('estimated_height_p10')} / "
            f"{readability.get('estimated_height_p50')} px",
            "",
            "| 焦点排名 | 元素 | 角色 | 焦点份额 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in focus:
        lines.append(
            f"| {row['rank']} | {_md(row['label'])} | {_md(row['role'])} | "
            f"{row['focus_share']} |"
        )

    lines.extend(["", "## 阶段耗时", "", "| 阶段 | 毫秒 |", "| --- | --- |"])
    for stage, elapsed in report.timings_ms.items():
        lines.append(f"| {stage} | {elapsed} |")
    lines.extend(
        [
            "",
            "> 视觉焦点为确定性 saliency proxy，不等同于真实用户注意力预测。",
            "",
        ]
    )
    return "\n".join(lines)


def _md(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def _goal_range(goal_checks: list[dict[str, Any]]) -> str:
    ids = [str(check.get("constraint_id", "")) for check in goal_checks]
    return f"{ids[0]}–{ids[-1]}" if ids else "G 系列约束"
