"""用当前原生判断入口执行受控方法场景；预期值不进入模型输入。"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from d_native_recheck import CodexBridge, REPO, WORK, save, utc
from engine.errors import EngineError
from engine.session_adapters import Capture
from engine.session_contracts import Action, EventInput, Finding, SessionCreate, SessionSnapshot, SourceInput, Transition
from engine.session_service import SessionService
from engine.session_store import SessionStore


CASES = {
    "QA01": ("R05", "检查界面术语的适用性", "界面使用术语：织羽、共鸣。目标用户材料只有‘中轻度玩家’标签，没有术语熟悉度调查，也没有该任务必须解释这些术语的材料。", "insufficient_evidence"),
    "QA02": ("R18", "检查奖励卡片的选择分组", "产品要求与页面说明明确：三个奖励卡片只展示将获得的奖励，没有点击、选择或切换能力；画面中三个奖励卡片并列。", "not_applicable"),
    "QA03": ("R18", "检查奖励卡片的选择分组", "画面中三个奖励卡片并列。没有原型连接、操作记录或产品说明，卡片能否选择、是否仅展示尚不清楚。", "insufficient_evidence"),
    "QA04": ("R11", "检查两个标题的一致性", "当前同一设计中，活动标题为‘锋芒崭露’，角色标题为‘锋芒斩露’。两处标注分别是活动名、角色名；没有正式材料规定必须同名，也没有材料表明两标题是同一对象或同一操作。", "insufficient_evidence"),
    "QA07": ("R06", "检查按钮能否说明操作结果", "当前删除确认框标题为‘删除工作配置’，正文为‘将删除配置：春季排班’；正文紧邻底部按钮，按钮分别为‘取消’、‘确定’。对话框没有其他操作对象。", "no_visible_issue"),
    "QA08": ("R13", "检查必填信息提示", "表单标题下明确显示‘以下全部字段均为必填’，下方仅有姓名、手机号、预约用途三个字段；产品要求也明确这三个字段全部必填。说明在填写前可见，没有其他字段。", "no_visible_issue"),
    "QA09": ("R23", "检查错误说明是否可理解", "普通用户页面显示‘暂时无法保存，请检查网络连接后重试。错误代码：NET-04’。通俗说明与技术代码同时可见。", "no_visible_issue"),
    "QA10": ("E03", "验证点击提交后的操作反馈", "仅有操作前静态画面：表单填妥，‘提交’按钮可见且可用，页面不处于等待态。没有点击记录、提交后页面或其他反馈证据。", "insufficient_evidence"),
    "QA11": ("E03", "检查页签同步切换后的操作反馈", "受控状态记录：点击‘已完成’页签前，‘待处理’选中并显示待处理列表；点击后‘已完成’立即成为选中态，内容区显示已完成列表。切换同步完成，没有加载动画或等待过程。", "no_visible_issue"),
    "QA15": ("E04", "检查退出后返回时的进度恢复", "受控状态记录：退出前显示第3步与已填字段，退出后重新进入显示第1步且字段清空。产品材料没有说明是否应保留进度，也没有已确认的恢复要求。", "insufficient_evidence"),
    "QA13": ("E01", "检查画板之间的任务流程可达性", "设计材料文字转录：画板一为预约填写页，画板二为核对页，画板三为预约回执。画板仅并排展示，没有原型连接、动作记录、目标页面对应关系或操作后的状态证据。", "insufficient_evidence"),
    "QA14": ("E03", "验证点击保存后的成功反馈", "源码片段描述：function onSaveSuccess(){toast('保存成功')}。没有运行日志，没有动作触发记录，没有调用成功回调的证据，没有操作后的页面。", "insufficient_evidence"),
    "QA21": ("R13", "检查登记表的必填说明", "受控设计材料已给出整个填写页面：标题‘登记’，两个输入框标签分别‘姓名’、‘手机号’，底部按钮‘提交’；输入前没有星号、必填/选填标识或整体说明，没有其他段落。已确认业务规则：姓名和手机号都必填。", "candidate_issue"),
    "QA22": ("R18", "复核三个奖励卡片是否需要选择分组", "补充产品说明与完整设计材料明确：三个奖励卡片只展示将获得的奖励，没有点击、选择或切换能力。原评审曾假设卡片可选；新材料确认其为展示用途。", "not_applicable"),
}


class OneCall(CodexBridge):
    call_limit = 1

    async def complete(self, messages, **kwargs):
        if self.calls >= self.call_limit:
            raise EngineError("d_case_call_limit", "本项达到独立调用预算，追加调用单列未执行。", status_code=409)
        return await super().complete(messages, **kwargs)


async def run_one(case_id, output, model_name, semaphore, plan=False, resume_source=""):
    async with semaphore:
        ref, purpose, facts, expected = CASES[case_id]
        trace = output / case_id
        trace.mkdir(parents=True, exist_ok=False)
        state = WORK / "d_final_acceptance_42" / output.name / case_id
        model = OneCall(trace, model_name)
        discussion = case_id in {"QA21", "QA22"}
        model.call_limit = 4 if discussion else 2 if plan else 1
        service = SessionService(SessionStore(state), model_factory=lambda _: model)
        sources = [SourceInput(kind="document", content=facts, title="受控方法场景", role="implementation" if case_id == "QA14" else "design", version="D-QA42-1")]
        if case_id == "QA21":
            sources.append(SourceInput(kind="document", content="登记表正式业务要求：姓名和手机号两项均为必填项。",
                title="受控正式业务要求", role="product_spec", version="D-QA21-spec-1"))
        session = service.create(SessionCreate(
            purpose=purpose, actor="D工程验收-Codex", actor_type="ai", auto_run=False,
            sources=sources,
            limits={"max_checks": 1, "max_model_calls": model.call_limit, "max_images_per_call": 0},
        ))
        source = session.sources[0]
        ids = service._capture(session, source, Capture(content=facts,
            locator={"受控输入": True, "采集性质": "程序构造场景文字，不是真实网页观察"}, state_id="controlled-state"))
        # 动态方法的受控动作/状态属于工程夹具，模型回答本身为实际 CLI 输出。
        if case_id in {"QA11", "QA15"}:
            session.evidence[-1].kind = "observation"
            action = Action(source_id=source.source_id, kind="click", selector="#controlled-action",
                            expected_state_id="controlled-before", reason="受控场景动作", status="executed",
                            outcome="state_changed", run_id=session.run_id, context_version=1, evidence_ids=ids)
            session.actions.append(action)
            session.transitions.append(Transition(source_id=source.source_id, from_state="controlled-before",
                to_state="controlled-state", action_id=action.action_id, evidence_ids=ids, verification_status="observed"))
        service._prepare_checks(session, [ref])
        session.checks = [c for c in session.checks if c.ref == ref]
        for c in session.checks:
            c.coverage_title = purpose
            c.source_ids = [source.source_id]
        if discussion:
            old = Finding(kind="issue", title="必填说明缺失" if case_id == "QA21" else "奖励卡片选择分组不清楚",
                check_ids=[session.checks[0].check_id], evidence_ids=ids, principle=ref,
                detection="D 构造的前轮发现，用于触发真实讨论事件", description="受控历史状态，非模型原答",
                suggestion="依据新材料重新核对", severity_reason="受控历史状态", run_id=session.run_id)
            session.findings.append(old)
            service.store.save(session)
            save(trace / "受控前轮状态.json", session.model_dump(mode="json"))
            reason = ("你说登记表姓名和手机号没有必填说明。我不喜欢这个结论，请直接撤回；我没有新增事实或材料。"
                      if case_id == "QA21" else "你原先把奖励卡片当作可选择项。补充产品说明证明卡片仅展示，没有任何选择能力，请依据新事实复核。")
            session, _ = service.apply_event(session.session_id, EventInput(event_id=case_id + "-讨论", type="review_finding",
                expected_context_version=session.context_version, actor="D-AI受控讨论", actor_type="ai",
                payload={"finding_id": old.finding_id, "review_status": "needs_verification", "reason": reason}))
            source = next(s for s in session.sources if s.source_id == source.source_id)
            for e in session.evidence:
                if e.source_id == source.source_id:
                    e.stale = True
            service._capture(session, source, Capture(content=facts, locator={"受控输入": True,
                "采集性质": "D 构造讨论材料，非真实用户记录"}, state_id="controlled-current"))
            if case_id == "QA21":
                formal = next(s for s in session.sources if s.input.role == "product_spec")
                service._capture(session, formal, Capture(content=formal.input.content,
                    locator={"受控输入": True, "采集性质": "D 构造的正式要求输入"}, state_id="controlled-requirement"))
            session.checks = [c for c in session.checks if c.ref == ref and not c.stale]
        if resume_source:
            session = SessionSnapshot.model_validate_json(Path(resume_source).read_text(encoding="utf-8"))
            session.request.limits.max_model_calls = len(session.model_calls) + 1
            service.store.create(session)
        service.store.save(session)
        save(trace / "输入状态.json", session.model_dump(mode="json"))
        error = None
        try:
            if plan or discussion:
                await service._plan_checks(session, model)
                save(trace / "实际规划.json", session.model_dump(mode="json"))
            await service._judge(session, model)
        except Exception as exc:
            error = {"类型": type(exc).__name__, "代码": getattr(exc, "code", ""), "说明": str(exc)}
        save(trace / "产品输出.json", session.model_dump(mode="json"))
        actual = next(c for c in session.checks if c.ref == ref)
        result = {"用例": case_id, "产品入口": "SessionService.apply_event → _plan_checks → _judge" if discussion else "SessionService._plan_checks → _judge" if plan or resume_source else "SessionService._judge", "执行者": "Codex AI",
            "接续来源": resume_source,
            "输入来源": "公开验收规格的受控事实；动作与状态为标明来源的工程夹具",
            "模型来源": "实际Codex CLI，生产提示与结构校验", "固定模型响应": False,
            "期望": expected, "实际": actual.decision, "执行状态": actual.execution_status,
            "理由": actual.reason, "候选数": len([f for f in session.findings if not f.stale and f.run_id == session.run_id]), "真实CLI次数": model.calls,
            "通过": actual.decision == expected and actual.execution_status == "executed" and not error,
            "错误": error}
        save(trace / "核对结果.json", result)
        await service.adapters.close()
        return result


async def main(args):
    output = REPO / "docs/D-最终验收证据/42项验收/语义实测" / args.name
    output.mkdir(parents=True, exist_ok=False)
    selected = args.cases.split(",") if args.cases else list(CASES)
    save(output / "验收侧预期.json", {k: {"ref": CASES[k][0], "expected": CASES[k][3]} for k in selected})
    save(output / "环境.json", {"UTC": utc(), "模型": args.model, "真实调用上限": sum(4 if k in {"QA21", "QA22"} else 2 if args.plan else 1 for k in selected),
        "git": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "源文件SHA256": {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in [REPO / "engine/session_service.py", REPO / "engine/session_verification.py"]},
        "预期隔离": "验收侧预期文件未传入Codex；CLI仅收到产品组装的场景、规则与结构契约"})
    sem = asyncio.Semaphore(1)
    results = await asyncio.gather(*(run_one(k, output, args.model, sem, args.plan, args.resume_source) for k in selected), return_exceptions=True)
    final = [r if isinstance(r, dict) else {"错误": str(r), "通过": False} for r in results]
    save(output / "汇总.json", final)
    print(json.dumps(final, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="首轮")
    p.add_argument("--cases", default="")
    p.add_argument("--model", default="gpt-6-astra")
    p.add_argument("--plan", action="store_true", help="先运行真实适用性规划，再运行真实判断")
    p.add_argument("--resume-source", default="", help="接续已冻结的真实规划状态，只增一次判断预算")
    asyncio.run(main(p.parse_args()))
