"""Source-backed task interpretation and executable check plans."""

from __future__ import annotations

import hashlib
import html
import json
import re
from difflib import SequenceMatcher
from graphlib import CycleError, TopologicalSorter

from .errors import EngineError


def quote_matches(evidence, quote: str) -> bool:
    texts = [evidence.content]
    try:
        data = json.loads(evidence.content)
        if isinstance(data, dict) and isinstance(data.get("metadata"), str):
            texts.append(data["metadata"])
    except ValueError:
        pass
    normalized = lambda text: " ".join(html.unescape(text).split())
    return any(normalized(quote) in normalized(text) for text in texts)


def repair_source_quotes(result, evidence) -> list[str]:
    """Extend a near-verbatim prefix to the complete visible sentence."""
    warnings: list[str] = []
    claims = [*result.goals, *result.requirements, *result.opinions]
    quote_groups = [claim.source_quotes for claim in claims]
    quote_groups.extend(conflict.source_quotes for conflict in result.conflicts)
    for quotes in quote_groups:
        for item in quotes:
            origin = evidence.get(item.evidence_id)
            if origin is None or quote_matches(origin, item.quote):
                continue
            normalized_text = " ".join(html.unescape(origin.content).split())
            core = item.quote.strip().rstrip("。！？；;，,")
            if len(core) < 8:
                continue
            start = normalized_text.find(core)
            if start >= 0:
                tail = normalized_text[start:start + 500]
                suffix_start = len(core)
                endings = [
                    index for index, character in enumerate(
                        tail[suffix_start:], start=suffix_start,
                    )
                    if character in "。！？；;"
                ]
                if endings:
                    repaired = tail[:endings[0] + 1]
                    if quote_matches(origin, repaired):
                        item.quote = repaired
                        warnings.append(
                            f"原文引用已由可验证前缀补全至完整句子：{item.evidence_id}"
                        )
                        continue
            sentences = [
                sentence.strip()
                for sentence in re.split(r"(?<=[。！？])|\n+", origin.content)
                if 8 <= len(sentence.strip()) <= 500
            ]
            scored = []
            for sentence in sentences:
                matcher = SequenceMatcher(None, item.quote, sentence)
                block = matcher.find_longest_match(
                    0, len(item.quote), 0, len(sentence),
                )
                scored.append((block.size / max(1, len(item.quote)), sentence))
            if scored:
                score, sentence = max(scored, key=lambda pair: pair[0])
                if score >= 0.65 and quote_matches(origin, sentence):
                    item.quote = sentence
                    warnings.append(
                        f"原文引用已按最长连续匹配校正为完整句子：{item.evidence_id}"
                    )
    return warnings


def validate_quotes(quotes, evidence, allowed_ids=None):
    invalid = []
    for item in quotes:
        if (
            item.evidence_id not in evidence
            or (allowed_ids is not None and item.evidence_id not in allowed_ids)
            or not quote_matches(evidence[item.evidence_id], item.quote)
        ):
            invalid.append(
                f"evidence_id={item.evidence_id}; quote={item.quote[:120]!r}"
            )
    if invalid:
        raise EngineError(
            "material_quote_invalid",
            "材料引用必须是单段、连续、逐字来自本次有效证据的原文；不能使用省略号拼接不相邻句子。"
            + " 无效引用：" + " | ".join(invalid),
            status_code=502,
        )


def quote_signature(quotes, evidence):
    return hashlib.sha256(json.dumps(sorted(
        (evidence[q.evidence_id].source_id, evidence[q.evidence_id].source_version, " ".join(q.quote.split()))
        for q in quotes
    ), ensure_ascii=False).encode()).hexdigest()


def sanitize_understanding(session, result, evidence) -> list[str]:
    """Drop recoverable invalid items while preserving the rest of the material model."""
    sources = {source.source_id: source for source in session.sources if source.active}
    warnings: list[str] = []
    known_pages = {state.page_id for state in session.page_states}
    known_states = {state.state_id for state in session.page_states}
    kept_tasks = []
    for task in result.review_tasks:
        if not task.evidence_ids or not set(task.evidence_ids).issubset(evidence):
            warnings.append(f"评审任务 {task.task_id} 缺少本次有效证据，已剔除覆盖规划。")
            continue
        dropped_pages = set(task.page_ids) - known_pages
        dropped_states = set(task.state_ids) - known_states
        if dropped_pages or dropped_states:
            warnings.append(
                f"评审任务 {task.task_id} 引用了尚未观察的页面/状态，"
                "已从覆盖声明中移除，后续须通过实际证据补入。"
            )
        task.page_ids = [
            page_id for page_id in task.page_ids if page_id in known_pages
        ]
        task.state_ids = [
            state_id for state_id in task.state_ids if state_id in known_states
        ]
        kept_branches = []
        seen_branches = set()
        for branch in task.branches:
            if (
                branch.branch_id in seen_branches
                or not branch.evidence_ids
                or not set(branch.evidence_ids).issubset(evidence)
            ):
                warnings.append(
                    f"评审任务 {task.task_id} 的分支 {branch.branch_id} 编号重复"
                    "或缺少有效材料证据，已剔除。"
                )
                continue
            seen_branches.add(branch.branch_id)
            kept_branches.append(branch)
        task.branches = kept_branches
        task.source_ids = list(dict.fromkeys(
            evidence[eid].source_id for eid in task.evidence_ids
        ))
        kept_tasks.append(task)
    result.review_tasks = kept_tasks
    allowed_opinions = []
    for opinion in result.opinions:
        roles: set[str] = set()
        missing = False
        for item in opinion.source_quotes:
            origin = evidence.get(item.evidence_id)
            source = sources.get(origin.source_id) if origin else None
            if source is None:
                missing = True
                break
            roles.add(source.input.role)
        if missing or not roles or not roles.issubset({"expert_opinion", "user_statement"}):
            warnings.append(f"材料意见 {opinion.id} 的来源不是专家/用户说明，已剔除，未作为评审依据。")
            continue
        allowed_opinions.append(opinion)
    result.opinions = allowed_opinions
    for field in ("unknowns", "assumptions"):
        kept = []
        for text in getattr(result, field):
            normalized = " ".join(text.split())
            if len(normalized) > 600 or any(
                marker in normalized
                for marker in ("修正：", "根据指令", "我将删除", "此处选择", "原REQ")
            ):
                warnings.append(f"材料理解 {field} 中的模型过程性文字已剔除。")
                continue
            kept.append(normalized)
        setattr(result, field, kept)
    authority_roles = {"design_brief", "product_spec", "user_statement"}
    for field in ("goals", "requirements"):
        kept_constraints = []
        for claim in getattr(result, field):
            roles = set()
            missing = False
            for item in claim.source_quotes:
                origin = evidence.get(item.evidence_id)
                source = sources.get(origin.source_id) if origin else None
                if source is None:
                    missing = True
                    break
                roles.add(source.input.role)
            if not claim.is_assumption and (
                missing or not claim.source_quotes or not roles.intersection(authority_roles)
            ):
                warnings.append(
                    f"正式约束 {claim.id} 缺少策划/产品/设计目的或用户说明来源，已剔除。"
                )
                continue
            kept_constraints.append(claim)
        setattr(result, field, kept_constraints)
    valid_claim_ids = {
        claim.id for claim in [*result.goals, *result.requirements, *result.opinions]
    }
    kept_conflicts = []
    for conflict in result.conflicts:
        if len(set(conflict.claim_ids)) < 2 or not set(conflict.claim_ids).issubset(valid_claim_ids):
            warnings.append(
                f"材料冲突 {conflict.topic} 依赖已剔除或无来源的声明，已移除，未作为正式冲突。"
            )
            continue
        kept_conflicts.append(conflict)
    result.conflicts = kept_conflicts
    return warnings


def validate_understanding(session, result, evidence):
    sources = {source.source_id: source for source in session.sources if source.active}
    task_ids = [task.task_id for task in result.review_tasks]
    if len(task_ids) != len(set(task_ids)):
        raise EngineError("material_task_duplicate", "评审任务编号重复。", status_code=502)
    for task in result.review_tasks:
        if not task.evidence_ids or not set(task.evidence_ids).issubset(evidence):
            raise EngineError(
                "material_task_evidence_invalid",
                "评审任务必须引用本次有效材料证据。",
                status_code=502,
            )
        allowed_sources = {evidence[eid].source_id for eid in task.evidence_ids}
        if task.source_ids and not set(task.source_ids).issubset(allowed_sources):
            raise EngineError(
                "material_task_source_invalid",
                "评审任务来源必须来自其任务证据。",
                status_code=502,
            )
        known_pages = {state.page_id for state in session.page_states}
        known_states = {state.state_id for state in session.page_states}
        if (
            not set(task.page_ids).issubset(known_pages)
            or not set(task.state_ids).issubset(known_states)
        ):
            raise EngineError(
                "material_task_state_invalid",
                "评审任务只能声明本次已经观察到的页面和状态；未观察部分应作为证据缺口。",
                status_code=502,
            )
        branch_ids = [branch.branch_id for branch in task.branches]
        if len(branch_ids) != len(set(branch_ids)):
            raise EngineError(
                "material_task_branch_duplicate",
                "同一评审任务的分支编号必须唯一。",
                status_code=502,
            )
        for branch in task.branches:
            if not set(branch.evidence_ids).issubset(evidence):
                raise EngineError(
                    "material_task_branch_invalid",
                    "评审任务分支必须引用本次有效材料证据。",
                    status_code=502,
                )
    for field in ("unknowns", "assumptions"):
        for text in getattr(result, field):
            normalized = " ".join(text.split())
            if len(normalized) > 600 or any(
                marker in normalized
                for marker in ("修正：", "根据指令", "我将删除", "此处选择", "原REQ")
            ):
                raise EngineError(
                    "material_meta_reasoning_invalid",
                    f"{field} 只能写面向读者的未知项或假设，不得包含模型的自我修正、"
                    "草稿比较或“我将/此处选择”等过程性文字。",
                    status_code=502,
                )
    claims = [*result.goals, *result.requirements, *result.opinions]
    ids = [claim.id for claim in claims]
    if len(ids) != len(set(ids)):
        raise EngineError("material_claim_duplicate", "材料声明编号重复。", status_code=502)
    for claim in claims:
        validate_quotes(claim.source_quotes, evidence)
    for opinion in result.opinions:
        roles = {
            sources[evidence[item.evidence_id].source_id].input.role
            for item in opinion.source_quotes
        }
        if not roles.intersection({"expert_opinion", "user_statement"}):
            raise EngineError(
                "material_opinion_authority_invalid",
                "opinions 只能引用明确标注的专家意见或用户说明；评审委托、方案标注和实现描述不是专家意见。",
                status_code=502,
            )
    for group, prefix in ((result.goals, "G"), (result.requirements, "REQ")):
        for claim in group:
            if not claim.id.startswith(prefix) or not set(claim.evidence_ids).issubset(evidence):
                raise EngineError("material_constraint_invalid", "目标和业务要求编号/引用不一致。", status_code=502)
            if not claim.is_assumption:
                if not claim.source_quotes or set(claim.evidence_ids) != {quote.evidence_id for quote in claim.source_quotes}:
                    raise EngineError("material_constraint_quote_required", "正式目标/要求必须保留每个来源的原文摘录。", status_code=502)
                roles = {sources[evidence[item.evidence_id].source_id].input.role for item in claim.source_quotes}
                if roles.issubset({"design", "expert_opinion", "implementation", "review_instruction"}):
                    raise EngineError(
                        "material_authority_invalid",
                        "方案标注、评审委托、专家建议或实现描述不能单独成为正式产品目标/要求；正式要求需有策划案、设计目的或明确用户说明。",
                        status_code=502,
                    )
    graph = {claim.id: {claim.parent_id} if claim.parent_id else set()
             for claim in [*result.goals, *result.requirements]}
    if any(parent not in graph for parents in graph.values() for parent in parents):
        raise EngineError("material_parent_invalid", "复合目标父编号不在本次目标/要求中。", status_code=502)
    try:
        list(TopologicalSorter(graph).static_order())
    except CycleError as exc:
        raise EngineError("goal_dependency_cycle", "目标/要求存在循环依赖。", status_code=502) from exc
    for relation in result.relationships:
        if relation.from_evidence_id not in evidence or relation.to_evidence_id not in evidence:
            raise EngineError("material_relation_invalid", "页面关系引用未知证据；不能把猜测当作实际跳转。", status_code=502)
    formal_ids = {claim.id for claim in [*result.goals, *result.requirements] if not claim.is_assumption}
    for conflict in result.conflicts:
        if not set(conflict.claim_ids).issubset(ids) or len(set(conflict.claim_ids)) < 2:
            raise EngineError("material_conflict_invalid", "材料冲突必须关联至少两个已提取声明。", status_code=502)
        validate_quotes(conflict.source_quotes, evidence)
        signatures = sorted(
            (evidence[q.evidence_id].source_id, evidence[q.evidence_id].source_version, q.quote)
            for q in conflict.source_quotes
        )
        conflict.conflict_id = "conflict-" + hashlib.sha256(json.dumps(signatures, ensure_ascii=False).encode()).hexdigest()[:20]
        if conflict.status == "resolved":
            raise EngineError("material_conflict_resolution_invalid", "模型不能自行裁决职能冲突，需明确业务决定。", status_code=502)
        conflict.blocking = len(set(conflict.claim_ids) & formal_ids) >= 2


def validate_check_plan(session, batch, requested_refs, evidence):
    tasks = {task.task_id: task for task in session.review_tasks}
    for index, item in enumerate(batch.items):
        if not item.task_id and len(tasks) == 1:
            item.task_id = next(iter(tasks))
        if not item.coverage_id:
            key = f"{item.ref}|{item.task_id}|{index}|{','.join(item.object_refs)}"
            item.coverage_id = "coverage-" + hashlib.sha256(
                key.encode()
            ).hexdigest()[:16]
        if not item.coverage_title:
            task = tasks.get(item.task_id)
            item.coverage_title = (
                task.text if task else "；".join(item.object_refs) or item.ref
            )
    refs = [item.ref for item in batch.items]
    if set(refs) != set(requested_refs):
        raise EngineError(
            "check_plan_incomplete",
            f"检查计划必须覆盖本批每个编号。缺少：{sorted(set(requested_refs) - set(refs))}；"
            f"多余：{sorted(set(refs) - set(requested_refs))}。",
            status_code=502,
        )
    coverage_keys = [(item.ref, item.coverage_id) for item in batch.items if item.coverage_id]
    if len(coverage_keys) != len(set(coverage_keys)):
        raise EngineError(
            "check_plan_coverage_duplicate",
            "同一判据下的 coverage_id 必须唯一；不同判据可共享同一任务/页面覆盖单元。",
            status_code=502,
        )
    counts: dict[str, int] = {}
    for item in batch.items:
        counts[item.ref] = counts.get(item.ref, 0) + 1
    too_broad = {
        ref: count for ref, count in counts.items() if count > 4
    }
    if too_broad:
        raise EngineError(
            "check_plan_coverage_too_broad",
            "同一判据最多返回4个代表覆盖单元，不能枚举所有任务与状态的笛卡尔积："
            f"{too_broad}。请保留最相关的页面/任务，多个状态可在同一覆盖单元内说明。",
            status_code=502,
        )
    for item in batch.items:
        if item.task_id and item.task_id not in tasks:
            raise EngineError(
                "check_plan_task_invalid",
                f"{item.ref} 引用了不存在的评审任务 {item.task_id}。",
                status_code=502,
            )
    source_ids = {source.source_id for source in session.sources if source.active}
    object_ids = {
        item.object_id
        for evidence in evidence.values()
        for item in evidence.objects
    }
    constraint_ids = {claim.id for claim in [*session.goals, *session.requirements]}
    opinion_ids = {claim.id for claim in session.material_understanding.opinions} if session.material_understanding else set()
    context_ids = constraint_ids | opinion_ids
    errors = []
    for item in batch.items:
        for label, actual, allowed in (
            ("source_ids", item.source_ids, source_ids),
            ("evidence_ids", item.evidence_ids, set(evidence)),
            ("constraint_refs", item.constraint_refs, context_ids),
            ("object_ids", item.object_ids, object_ids),
        ):
            unknown = set(actual) - allowed
            if unknown:
                errors.append(f"{item.ref}.{label} 未知编号 {sorted(unknown)}，允许 {sorted(allowed)}")
        if item.applicability == "not_applicable" and not item.evidence_ids:
            errors.append(
                f"{item.ref}: not_applicable 缺少适用条件的证据。没有看到相关对象/错误截图不证明不适用；"
                "无法确定时改为 needs_context，并列出 evidence_needed，不得补造引用"
            )
    if errors:
        raise EngineError("check_plan_reference_invalid", "；".join(errors), status_code=502)
