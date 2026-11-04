"""Build a stable Figma publishing plan from a completed review session."""

from __future__ import annotations

import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .session_contracts import SessionSnapshot
from .session_report import structured_report


COLORS = {
    "issue": "#C62828",
    "gap": "#9A6700",
    "review": "#0B63CE",
    "pass": "#18794E",
    "report_bg": "#F6F8FB",
    "panel_bg": "#FFFFFF",
    "text": "#172033",
    "muted": "#56637A",
    "border": "#C9D2E0",
}


def _normal(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", value.lower())


def _semantic_anchor_overlap(first: str, second: str) -> int:
    anchors = (
        "全选", "绑定", "数量", "0000000", "分解可得", "拥有",
        "高亮", "选中", "12级", "15级", "对比度", "截断", "溢出",
    )
    first_text = first.lower()
    second_text = second.lower()
    return sum(
        anchor in first_text and anchor in second_text
        for anchor in anchors
    )


def _target_geometry(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for evidence in report["evidence"]:
        locator = evidence.get("locator", {})
        for node in locator.get("inspection_targets", []):
            node_id = str(node.get("node_id") or "")
            if node_id:
                result[node_id] = {
                    "node_id": node_id,
                    "name": node.get("name") or node_id,
                    "x": float(node.get("x") or 0),
                    "y": float(node.get("y") or 0),
                    "width": max(1.0, float(node.get("width") or 1)),
                    "height": max(1.0, float(node.get("height") or 1)),
                }
    return result


def _gap_target(text: str, fallback: str) -> str:
    lower = text.lower()
    if "npc" in lower or "npc" in text:
        return fallback
    if "数值" in text or "定价" in text or "折损" in text or "经济" in text:
        return "173:7680"
    if "获取途径" in text or "11-15" in text:
        return "173:7695"
    if "二次确认" in text or "不可逆" in text:
        return "173:7677"
    if "筛选" in text or "存储" in text or "跨设备" in text:
        return "173:7674"
    if "反馈" in text or "异常" in text or "空状态" in text:
        return "173:7677"
    if "排序" in text or "绑定" in text:
        return "173:7674"
    return fallback


def _gap_category(text: str) -> str:
    lower = text.lower()
    if "npc" in lower or "npc" in text:
        return "npc-entry"
    if "二次确认" in text or "不可逆" in text:
        return "confirmation"
    if "获取途径" in text or "11-15" in text:
        return "acquisition"
    if "排序" in text or "绑定优先" in text:
        return "mixed-sort"
    if "数值" in text or "定价" in text or "折损" in text or "经济" in text:
        return "pricing"
    if "筛选" in text or "存储" in text or "跨设备" in text:
        return "filter-persistence"
    if "反馈" in text or "异常" in text or "空状态" in text:
        return "feedback-errors"
    if "回退" in text or "返回" in text or "逆向" in text:
        return "reverse-path"
    if "强化套装" in text or "术语" in text:
        return "terminology"
    return _normal(text)


def _dedupe_gaps(questions: list[dict[str, Any]], fallback: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen_categories: set[str] = set()
    for question in questions:
        if question.get("answered"):
            continue
        text = str(question.get("text") or "").strip()
        if not text:
            continue
        category = _gap_category(text)
        duplicate = category in seen_categories or any(
            SequenceMatcher(None, _normal(text), _normal(item["text"])).ratio() >= 0.82
            for item in result
        )
        if duplicate:
            continue
        seen_categories.add(category)
        result.append({
            "category": category,
            "text": text[:500],
            "reason": str(question.get("reason") or "")[:400],
            "check_refs": question.get("check_refs") or [],
            "target_node_id": _gap_target(text, fallback),
        })
        if len(result) >= 10:
            break
    return result


def build_figma_report_plan(
    session: SessionSnapshot, *, registry=None,
) -> dict[str, Any]:
    report = structured_report(session, registry=registry)
    design_source = next(
        (source for source in report["sources"] if source.get("role") == "design" and source.get("active")),
        None,
    )
    reference = design_source.get("reference", "") if design_source else ""
    match = re.search(r"node-id=(\d+)-(\d+)", reference)
    root_node_id = f"{match.group(1)}:{match.group(2)}" if match else ""
    file_match = re.search(r"figma\.com/(?:design|file)/([A-Za-z0-9]+)/", reference)
    file_key = file_match.group(1) if file_match else ""
    if not root_node_id:
        root_node_id = next(
            (
                str(node.get("node_id"))
                for evidence in report["evidence"]
                for node in evidence.get("locator", {}).get("inspection_targets", [])
                if evidence.get("locator", {}).get("requested_node_id") == evidence.get("locator", {}).get("node_id")
            ),
            "",
        )
    geometry = _target_geometry(report)
    fallback = root_node_id or next(iter(geometry), "")

    annotations: list[dict[str, Any]] = []
    screen_issues = [
        (issue.get("node_id"), issue)
        for issue in report.get("systemic_screen_issues", [])
    ]
    consumed_screen_issues: set[str] = set()
    for finding in report.get("findings", []):
        finding_rules = set(finding.get("check_refs") or [])
        first_evidence = (finding.get("evidence_ids") or [None])[0]
        first_evidence_payload = next(
            (item for item in report["evidence"] if item["evidence_id"] == first_evidence),
            {},
        )
        first_evidence_node = str(
            first_evidence_payload.get("locator", {}).get("node_id") or ""
        )
        match_issue = None
        for node_id, issue in screen_issues:
            if issue.get("issue_id") in consumed_screen_issues:
                continue
            rule_overlap = finding_rules.intersection(issue.get("rule_ids") or [])
            similarity = SequenceMatcher(
                None, _normal(finding.get("title", "")), _normal(issue.get("title", "")),
            ).ratio()
            semantic_overlap = _semantic_anchor_overlap(
                " ".join([
                    finding.get("title", ""),
                    finding.get("detection", ""),
                    finding.get("description", ""),
                ]),
                " ".join([
                    issue.get("title", ""),
                    issue.get("detection", ""),
                    issue.get("description", ""),
                ]),
            )
            if (
                (rule_overlap and similarity >= 0.35)
                or (
                    node_id == first_evidence_node
                    and (similarity >= 0.45 or semantic_overlap >= 2)
                )
                or semantic_overlap >= 3
            ):
                match_issue = (node_id, issue)
                break
        if match_issue:
            node_id, issue = match_issue
            consumed_screen_issues.add(issue["issue_id"])
            annotations.append({
                "kind": "issue",
                "scope": "screen+global",
                "target_node_id": node_id,
                "title": issue.get("title") or finding.get("title"),
                "detail": issue.get("description") or finding.get("description"),
                "action": issue.get("suggestion") or finding.get("suggestion"),
                "heuristic_ids": issue.get("heuristic_ids") or [],
                "user_impact": issue.get("user_impact") or issue.get("description"),
                "occurrence_count": issue.get("occurrence_count", 1),
                "affected_locations": issue.get("affected_locations", []),
                "severity": issue.get("severity") or finding.get("severity"),
                "bbox_hint": issue.get("evidence_bbox"),
            })
        else:
            evidence = next(
                (item for item in report["evidence"] if item["evidence_id"] == first_evidence),
                {},
            )
            annotations.append({
                "kind": "issue",
                "scope": "global",
                "target_node_id": evidence.get("locator", {}).get("node_id") or fallback,
                "title": finding.get("title"),
                "detail": finding.get("description"),
                "action": finding.get("suggestion"),
                "heuristic_ids": [],
                "user_impact": finding.get("description"),
                "occurrence_count": 1,
                "affected_locations": [],
                "severity": finding.get("severity"),
                "bbox_hint": None,
            })
    for node_id, issue in screen_issues:
        if issue.get("issue_id") in consumed_screen_issues:
            continue
        annotations.append({
            "kind": "issue",
            "scope": "screen",
            "target_node_id": node_id,
            "title": issue.get("title"),
            "detail": issue.get("description"),
            "action": issue.get("suggestion"),
            "heuristic_ids": issue.get("heuristic_ids") or [],
            "user_impact": issue.get("user_impact") or issue.get("description"),
            "occurrence_count": issue.get("occurrence_count", 1),
            "affected_locations": issue.get("affected_locations", []),
            "severity": issue.get("severity"),
            "bbox_hint": issue.get("evidence_bbox"),
        })

    gaps = _dedupe_gaps(report.get("questions", []), fallback)
    for annotation in annotations:
        target = geometry.get(annotation["target_node_id"], geometry.get(fallback, {}))
        annotation.update({
            "target_name": target.get("name") or annotation["target_node_id"],
            "target_x": target.get("x", 0),
            "target_y": target.get("y", 0),
            "target_width": target.get("width", 1),
            "target_height": target.get("height", 1),
            "color": COLORS["issue"] if annotation["kind"] == "issue" else COLORS["gap"],
        })

    screen_summary = [
        {
            "node_id": review.get("node_id"),
            "page_type": review.get("page_type"),
            "status": review.get("status"),
            "ui_element_count": review.get("technical_metrics", {}).get("ui_element_count", 0),
            "ocr_block_count": review.get("technical_metrics", {}).get("ocr_block_count", 0),
            "issue_count": len(review.get("issues", [])),
        }
        for review in report.get("screen_reviews", [])
    ]
    summary = report["summary"]
    heuristic_counts = Counter(
        heuristic_id
        for annotation in annotations
        if annotation["kind"] == "issue"
        for heuristic_id in annotation.get("heuristic_ids", [])
    )
    return {
        "schema_version": "figma-review-report-1.0",
        "session_id": session.session_id,
        "run_id": session.run_id,
        "generated_at": session.updated_at,
        "file_key": file_key,
        "source_root_node_id": root_node_id,
        "source_title": design_source.get("title", "交互案") if design_source else "交互案",
        "duplicate_name": f"{design_source.get('title', '交互案') if design_source else '交互案'} · AI审查标注副本",
        "report_name": f"{design_source.get('title', '交互案') if design_source else '交互案'} · AI评审报告",
        "title": f"{design_source.get('title', '交互案') if design_source else '交互案'} · AI评审报告",
        "subtitle": "基于完整交互流程与逐屏技术审查",
        "summary": {
            "checks_total": summary.get("checks_total", 0),
            "executed": summary.get("execution", {}).get("executed", 0),
            "design_met": summary.get("decisions", {}).get("met", 0),
            "candidate_issues": summary.get("finding_count", 0),
            "screen_candidate_issues": len([
                annotation for annotation in annotations
                if annotation["kind"] == "issue"
            ]),
            "insufficient_evidence": summary.get("decisions", {}).get("insufficient_evidence", 0),
            "screen_reviews": len(screen_summary),
            "screen_complete": sum(item["status"] == "completed" for item in screen_summary),
            "screen_partial": sum(item["status"] == "partial" for item in screen_summary),
            "screen_ui_elements": sum(item["ui_element_count"] for item in screen_summary),
            "screen_ocr_blocks": sum(item["ocr_block_count"] for item in screen_summary),
        },
        "findings": [
            {
                "title": item["title"],
                "scope": item["scope"],
                "severity": item["severity"],
                "detail": item["detail"],
                "action": item["action"],
                "heuristic_ids": item["heuristic_ids"],
                "user_impact": item["user_impact"],
                "occurrence_count": item["occurrence_count"],
                "affected_locations": item["affected_locations"],
                "target_node_id": item["target_node_id"],
            }
            for item in annotations if item["kind"] == "issue"
        ],
        "heuristic_summary": dict(sorted(heuristic_counts.items())),
        "gaps": gaps,
        "screen_summary": screen_summary,
        "annotations": annotations,
        "colors": COLORS,
    }


def write_figma_plan(
    session: SessionSnapshot, directory: str | Path, *, registry=None,
) -> tuple[Path, dict[str, Any]]:
    plan = build_figma_report_plan(session, registry=registry)
    target = Path(directory) / "figma-report-plan.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return target, plan


def build_figma_plugin_script(plan: dict[str, Any]) -> str:
    """Return a top-level-await script for the official Figma MCP use_figma tool."""
    def clip(value: Any, limit: int) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        return text if len(text) <= limit else text[:limit - 1] + "…"

    annotations = []
    for annotation in plan.get("annotations", []):
        bbox = annotation.get("bbox_hint") or {}
        annotations.append({
            "kind": annotation.get("kind"),
            "scope": annotation.get("scope"),
            "target_node_id": annotation.get("target_node_id"),
            "target_name": annotation.get("target_name"),
            "target_x": annotation.get("target_x", 0),
            "target_y": annotation.get("target_y", 0),
            "target_width": annotation.get("target_width", 1),
            "target_height": annotation.get("target_height", 1),
            "title": clip(annotation.get("title"), 80),
            "detail": clip(annotation.get("detail"), 140),
            "action": clip(annotation.get("action"), 100),
            "heuristic_ids": annotation.get("heuristic_ids", []),
            "severity": annotation.get("severity"),
            "color": annotation.get("color"),
            "bbox_hint": {
                key: bbox.get(key) for key in ("x", "y", "width", "height")
            } if bbox else None,
        })
    script_plan = {
        "source_root_node_id": plan.get("source_root_node_id"),
        "source_title": plan.get("source_title"),
        "report_name": plan.get("report_name"),
        "title": plan.get("title"),
        "subtitle": plan.get("subtitle"),
        "summary": plan.get("summary", {}),
        "screen_summary": plan.get("screen_summary", []),
        "gaps": [
            {"text": clip(gap.get("text"), 160)}
            for gap in plan.get("gaps", [])
        ],
        "annotations": annotations,
        "heuristic_summary": plan.get("heuristic_summary", {}),
        "colors": plan.get("colors", COLORS),
        "session_id": plan.get("session_id"),
        "run_id": plan.get("run_id"),
    }
    payload = json.dumps(
        script_plan, ensure_ascii=False, separators=(",", ":"),
    )
    return f"""const plan = {payload};
const reportFonts = {{
  regular: {{ family: "Noto Sans SC", style: "Regular" }},
  medium: {{ family: "Noto Sans SC", style: "Medium" }},
  bold: {{ family: "Noto Sans SC", style: "Bold" }}
}};
await Promise.all(Object.values(reportFonts).map(font => figma.loadFontAsync(font)));

const original = await figma.getNodeByIdAsync(plan.source_root_node_id);
if (!original || original.type !== "FRAME") throw new Error("Source interaction frame not found");
const page = original.parent;
if (!page || page.type !== "PAGE") throw new Error("Source frame must be on a page");
await figma.setCurrentPageAsync(page);

const duplicateName = `${{plan.source_title}} · AI审查标注副本`;
const reuseWrapper = page.findOne(n =>
  n.type === "FRAME" &&
  n.name.includes(plan.source_title) &&
  n.name.includes("AI审查标注稿")
);
let duplicate = reuseWrapper
  ? reuseWrapper.findOne(n => n.name.includes("AI审查标注副本"))
  : page.findOne(n => n.name === duplicateName);
if (!duplicate) {{
  duplicate = original.clone();
  duplicate.name = duplicateName;
  duplicate.x = original.x + original.width + 320;
  duplicate.y = original.y;
  page.appendChild(duplicate);
}}
if (duplicate.type !== "FRAME") throw new Error("Annotated copy must be a frame");
if (duplicate.layoutMode !== "NONE") {{
  duplicate.primaryAxisSizingMode = "FIXED";
  duplicate.counterAxisSizingMode = "FIXED";
}}
duplicate.resize(original.width, original.height);
const reviewWrapper = duplicate.parent && duplicate.parent.type === "FRAME"
  ? duplicate.parent : null;
const reviewBounds = duplicate.absoluteBoundingBox || {{
  x: duplicate.x,
  y: duplicate.y,
  width: duplicate.width,
  height: duplicate.height
}};
const wrapperBounds = reviewWrapper && reviewWrapper.absoluteBoundingBox
  ? reviewWrapper.absoluteBoundingBox
  : {{ x: reviewBounds.x, y: reviewBounds.y, width: reviewBounds.width, height: reviewBounds.height }};

const oldPanel = page.findOne(n => n.name === "交互案 · AI审查说明栏");
if (oldPanel) oldPanel.remove();
const oldLayer = reviewWrapper
  ? reviewWrapper.findOne(n => n.name.includes("AI彩色标注层"))
  : null;
if (oldLayer) oldLayer.remove();
const annotationPrefix = `AI审查批注 · ${{plan.source_title}} · `;
for (const child of [...duplicate.children]) {{
  if (child.name.startsWith(annotationPrefix)) child.remove();
}}
for (const child of [...page.children]) {{
  if (child.name.startsWith(annotationPrefix)) child.remove();
}}

function rgba(hex, opacity = 1) {{
  const clean = hex.replace("#", "");
  return {{
    type: "SOLID",
    color: {{
      r: parseInt(clean.slice(0, 2), 16) / 255,
      g: parseInt(clean.slice(2, 4), 16) / 255,
      b: parseInt(clean.slice(4, 6), 16) / 255
    }},
    opacity
  }};
}}

function addText(parent, content, font, size, color, width) {{
  const node = figma.createText();
  node.fontName = font;
  node.fontSize = size;
  node.fills = [rgba(color)];
  node.characters = content;
  node.resize(width, node.height);
  node.textAutoResize = "HEIGHT";
  parent.appendChild(node);
  node.layoutSizingHorizontal = "FILL";
  return node;
}}

function shortText(value, limit = 220) {{
  const text = String(value || "").replace(/\\s+/g, " ").trim();
  return text.length > limit ? text.slice(0, limit - 1) + "…" : text;
}}

const occupiedNotes = [];
function overlaps(first, second) {{
  return !(
    first.x + first.width <= second.x ||
    second.x + second.width <= first.x ||
    first.y + first.height <= second.y ||
    second.y + second.height <= first.y
  );
}}
const numberedNodes = duplicate.findAll(node =>
  node.type === "TEXT" &&
  node.visible &&
  /^\\s*\\d+[.、]/.test(node.characters || "")
);
function nearestNumbered(highlightAbs) {{
  let best = null;
  let bestDistance = Infinity;
  const hx = highlightAbs.x + highlightAbs.width / 2;
  const hy = highlightAbs.y + highlightAbs.height / 2;
  for (const node of numberedNodes) {{
    const box = node.absoluteBoundingBox;
    if (!box) continue;
    const nx = box.x + box.width / 2;
    const ny = box.y + box.height / 2;
    const distance = Math.hypot(nx - hx, ny - hy);
    if (distance < bestDistance) {{
      bestDistance = distance;
      best = {{ node, box }};
    }}
  }}
  return best;
}}
const annotationNodeIds = [];
for (let index = 0; index < plan.annotations.length; index++) {{
  const annotation = plan.annotations[index];
  const target = {{
    x: annotation.target_x,
    y: annotation.target_y,
    width: annotation.target_width,
    height: annotation.target_height
  }};
  let highlight = target;
  if (annotation.bbox_hint) {{
    highlight = {{
      x: target.x + target.width * Number(annotation.bbox_hint.x || 0),
      y: target.y + target.height * Number(annotation.bbox_hint.y || 0),
      width: Math.max(18, target.width * Number(annotation.bbox_hint.width || 0)),
      height: Math.max(18, target.height * Number(annotation.bbox_hint.height || 0))
    }};
  }}
  const outline = figma.createRectangle();
  outline.name = `${{annotationPrefix}}目标框 ${{index + 1}} · ${{annotation.title}}`;
  outline.x = reviewBounds.x + highlight.x;
  outline.y = reviewBounds.y + highlight.y;
  outline.resize(highlight.width, highlight.height);
  outline.fills = [rgba(annotation.color, 0.05)];
  outline.strokes = [rgba(annotation.color)];
  outline.strokeWeight = 4;
  outline.strokeAlign = "INSIDE";
  page.appendChild(outline);
  annotationNodeIds.push(outline.id);

  const highlightAbs = {{
    x: reviewBounds.x + highlight.x,
    y: reviewBounds.y + highlight.y,
    width: highlight.width,
    height: highlight.height
  }};
  const nearest = nearestNumbered(highlightAbs);
  const anchorBox = nearest ? nearest.box : highlightAbs;
  let noteX = anchorBox.x;
  let noteY = anchorBox.y + anchorBox.height + 8;
  const noteWidth = 360;
  if (noteX + noteWidth > reviewBounds.x + reviewBounds.width - 20) {{
    noteX = Math.max(
      reviewBounds.x + 20,
      reviewBounds.x + reviewBounds.width - noteWidth - 20
    );
  }}
  const noteBg = figma.createRectangle();
  noteBg.name = `${{annotationPrefix}}底色 ${{index + 1}} · ${{annotation.title}}`;
  noteBg.cornerRadius = 8;
  noteBg.fills = [rgba(plan.colors.panel_bg, 0.96)];
  noteBg.strokes = [rgba(annotation.color)];
  noteBg.strokeWeight = 2;
  noteBg.strokeAlign = "INSIDE";
  page.appendChild(noteBg);
  annotationNodeIds.push(noteBg.id);
  const header = figma.createText();
  header.name = `${{annotationPrefix}}标题 ${{index + 1}} · ${{annotation.title}}`;
  header.fontName = reportFonts.bold;
  header.fontSize = 18;
  header.fills = [rgba(annotation.color)];
  header.characters = `AI${{String(index + 1).padStart(2, "0")}} · ${{annotation.heuristic_ids.join("/") || "无判据"}}`;
  header.resize(noteWidth, header.height);
  header.textAutoResize = "HEIGHT";
  page.appendChild(header);
  annotationNodeIds.push(header.id);

  const body = figma.createText();
  body.name = `${{annotationPrefix}}正文 ${{index + 1}} · ${{annotation.title}}`;
  body.fontName = reportFonts.medium;
  body.fontSize = 15;
  body.fills = [rgba(plan.colors.text)];
  body.characters = `${{annotation.title}}\n${{annotation.detail}}`;
  body.resize(noteWidth, body.height);
  body.textAutoResize = "HEIGHT";
  page.appendChild(body);
  annotationNodeIds.push(body.id);

  const action = figma.createText();
  action.name = `${{annotationPrefix}}建议 ${{index + 1}} · ${{annotation.title}}`;
  action.fontName = reportFonts.regular;
  action.fontSize = 13;
  action.fills = [rgba(plan.colors.muted)];
  action.characters = `建议：${{shortText(annotation.action, 120)}}`;
  action.resize(noteWidth, action.height);
  action.textAutoResize = "HEIGHT";
  page.appendChild(action);
  annotationNodeIds.push(action.id);

  const noteHeight = header.height + body.height + action.height + 18;
  for (let attempt = 0; attempt < 30; attempt++) {{
    const box = {{ x: noteX, y: noteY, width: noteWidth, height: noteHeight }};
    const hit = occupiedNotes.find(item => overlaps(item, box));
    if (!hit) break;
    noteY = hit.y + hit.height + 12;
  }}
  if (noteY + noteHeight > reviewBounds.y + reviewBounds.height - 20) {{
    noteY = Math.max(
      reviewBounds.y + 20,
      reviewBounds.y + reviewBounds.height - noteHeight - 20
    );
  }}
  noteBg.x = noteX - 8;
  noteBg.y = noteY - 8;
  noteBg.resize(noteWidth + 16, noteHeight + 12);
  header.x = noteX;
  header.y = noteY;
  body.x = noteX;
  body.y = noteY + header.height + 4;
  action.x = noteX;
  action.y = body.y + body.height + 4;
  occupiedNotes.push({{ x: noteX, y: noteY, width: noteWidth, height: noteHeight }});
}}

const existingReport = page.findOne(n => n.name === plan.report_name);
if (existingReport) existingReport.remove();

const report = figma.createAutoLayout("VERTICAL", {{
  name: plan.report_name,
  itemSpacing: 22
}});
report.resize(1080, 100);
report.paddingTop = 44;
report.paddingBottom = 44;
report.paddingLeft = 44;
report.paddingRight = 44;
report.cornerRadius = 24;
report.fills = [rgba(plan.colors.report_bg)];
report.strokes = [rgba(plan.colors.border)];
report.strokeWeight = 2;
report.x = reviewBounds.x;
report.y = wrapperBounds.y + wrapperBounds.height + 420;

function section(title, accent) {{
  const frame = figma.createAutoLayout("VERTICAL", {{ name: title, itemSpacing: 14 }});
  frame.paddingTop = 22;
  frame.paddingBottom = 22;
  frame.paddingLeft = 24;
  frame.paddingRight = 24;
  frame.cornerRadius = 12;
  frame.fills = [rgba(plan.colors.panel_bg)];
  frame.strokes = [rgba(accent, 0.8)];
  frame.strokeWeight = 2;
  report.appendChild(frame);
  frame.layoutSizingHorizontal = "FILL";
  addText(frame, title, reportFonts.bold, 24, accent, 980);
  return frame;
}}

addText(report, plan.title, reportFonts.bold, 42, plan.colors.text, 980);
addText(report, plan.subtitle, reportFonts.regular, 18, plan.colors.muted, 980);
addText(
  report,
  `评审完成 · 检查 ${{plan.summary.executed}}/${{plan.summary.checks_total}} · 跨项发现 ${{plan.summary.candidate_issues}} · 系统性问题 ${{plan.summary.screen_candidate_issues}} · 证据不足 ${{plan.summary.insufficient_evidence}}`,
  reportFonts.medium, 18, plan.colors.review, 980
);

const overview = section("01 · 评审摘要", plan.colors.review);
addText(
  overview,
  `逐屏技术审查 ${{plan.summary.screen_reviews}} 个完整界面，其中完整完成 ${{plan.summary.screen_complete}} 个、部分完成 ${{plan.summary.screen_partial}} 个；累计识别 UI 元素 ${{plan.summary.screen_ui_elements}} 个、OCR 文本块 ${{plan.summary.screen_ocr_blocks}} 个。`,
  reportFonts.regular, 17, plan.colors.text, 980
);
addText(
  overview,
  "完整完成表示 OCR、元素、统计和屏内规则审查均已产出；部分完成会保留具体限制，不把空元素结果当作通过。",
  reportFonts.regular, 15, plan.colors.muted, 980
);
const heuristicRows = Object.entries(plan.heuristic_summary || {{}});
addText(
  overview,
  heuristicRows.length
    ? `命中启发式维度：${{heuristicRows.map(([id, count]) => `${{id}} × ${{count}}`).join(" · ")}}`
    : "本轮候选问题未绑定可识别的启发式维度，不能把流程缺项冒充交互结论。",
  reportFonts.regular, 16, plan.colors.text, 980
);

const findingsSection = section("02 · 候选问题", plan.colors.issue);
for (let i = 0; i < plan.annotations.length; i++) {{
  const item = plan.annotations[i];
  addText(findingsSection, `F${{String(i + 1).padStart(3, "0")}} · ${{item.title}}`, reportFonts.bold, 20, plan.colors.issue, 940);
  addText(findingsSection, shortText(item.detail, 360), reportFonts.regular, 16, plan.colors.text, 940);
  addText(findingsSection, `建议：${{shortText(item.action, 220)}}`, reportFonts.medium, 15, plan.colors.muted, 940);
}}

const screensSection = section("03 · 逐屏技术审查", plan.colors.review);
for (const screen of plan.screen_summary) {{
  addText(
    screensSection,
    `${{screen.page_type || screen.node_id}} · ${{screen.status === "completed" ? "完整完成" : "部分完成"}} · UI ${{screen.ui_element_count}} · OCR ${{screen.ocr_block_count}} · 屏内问题 ${{screen.issue_count}}`,
    reportFonts.regular, 16, screen.status === "completed" ? plan.colors.text : plan.colors.gap, 940
  );
}}

const gapsSection = section("04 · 待补证据与业务确认", plan.colors.gap);
for (let i = 0; i < plan.gaps.length; i++) {{
  addText(
    gapsSection,
    `G${{String(i + 1).padStart(2, "0")}} · ${{shortText(plan.gaps[i].text, 300)}}`,
    reportFonts.regular, 16, plan.colors.text, 940
  );
}}

const legendSection = section("05 · 标注说明", plan.colors.pass);
addText(legendSection, "红色：副本编号、目标框与系统性问题；黄色与青色：仅用于报告中的证据缺口和审查统计。", reportFonts.regular, 16, plan.colors.text, 940);
addText(legendSection, "标注位于原交互案的独立副本上，原稿未修改。", reportFonts.medium, 16, plan.colors.pass, 940);
addText(legendSection, `会话：${{plan.session_id}} · 运行：${{plan.run_id}}`, reportFonts.regular, 13, plan.colors.muted, 940);

return {{
  success: true,
  reportId: report.id,
  duplicateId: duplicate.id,
  annotationCount: plan.annotations.length,
  reportBounds: {{ x: report.x, y: report.y, width: report.width, height: report.height }},
  createdNodeIds: [report.id, ...annotationNodeIds]
}};
"""


def write_figma_plugin_script(
    session: SessionSnapshot, directory: str | Path, *, registry=None,
) -> tuple[Path, Path, dict[str, Any]]:
    plan_path, plan = write_figma_plan(session, directory, registry=registry)
    script_path = Path(directory) / "figma-report-plugin.js"
    script_path.write_text(build_figma_plugin_script(plan), encoding="utf-8")
    return plan_path, script_path, plan
