"""QA30/QA31：实际会话的零覆盖统计及真实表单的补填计时导出。"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time

from d_native_recheck import REPO, WORK, save, utc
from engine.session_contracts import EventInput, SessionCreate, SourceInput
from engine.session_evaluation import EvaluationLabels, evaluate_session
from engine.session_service import SessionService
from engine.session_store import SessionStore
from playwright.sync_api import sync_playwright


def repeatability(sessions):
    tables = [{c.check_id: c.decision for c in s.checks if c.run_id == s.run_id
               and not c.stale and c.execution_status == "executed"} for s in sessions]
    common = set.intersection(*(set(t) for t in tables)) if tables else set()
    matching = sum(len({t[k] for t in tables}) == 1 for k in common)
    return {"共同实际执行项": len(common), "三轮一致项": matching,
            "共同执行项一致率": matching / len(common) if common else None,
            "逐轮实际执行项": [len(t) for t in tables]}


def main(name):
    out = REPO / "docs/D-最终验收证据/42项验收/统计与表单" / name
    out.mkdir(parents=True, exist_ok=False)
    sessions = []
    for index in range(3):
        service = SessionService(SessionStore(WORK / "d_final_acceptance_42" / name / f"empty-{index}"))
        first = service.create(SessionCreate(purpose="QA30 无实际检查的独立会话", actor="D-AI验收", actor_type="ai",
            sources=[SourceInput(kind="document", content="受控材料")], auto_run=False))
        finished, _ = service.apply_event(first.session_id, EventInput(type="finish", event_id=f"QA30-{index}",
            expected_context_version=1, actor="D-AI验收", actor_type="ai"))
        sessions.append(finished)
        save(out / f"QA30-{index + 1}-实际会话.json", finished.model_dump(mode="json"))
        save(out / f"QA30-{index + 1}-引擎评分.json", evaluate_session(finished, EvaluationLabels(dataset="QA30", findings=[])))
    consistency = repeatability(sessions)
    assert consistency["共同实际执行项"] == 0 and consistency["共同执行项一致率"] is None
    save(out / "QA30-统计.json", {**consistency, "统计来源": "D 脚本读取真实 SessionService 结束会话的输出，计算共同执行项", "通过": True})

    form = REPO / "docs/D-新版真人执行/02-体验者/两轮任务体验记录.html"
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(locale="zh-CN", viewport={"width": 1100, "height": 1200}, accept_downloads=True)
        page.goto(form.as_uri())
        page.locator("#participant").select_option("U01")
        page.locator("#round").select_option("2")
        for field, value in {"version": "QA31受控材料", "device": "AI自动操作 / Edge", "build": "QA31本地表单",
            "interruption": "AI工具验收：模拟已体验后补填，计时仅按约1秒。", "product": "已完成体验的受控填表示例",
            "quote": "AI工具验收：保留评分，补填时长不参与效率统计。"}.items():
            page.locator("#" + field).fill(value)
        for field, value in {"timing": "invalid", "outcome": "completed", "understand": "4", "evidence": "4", "saved": "4", "consent": "yes"}.items():
            page.locator("#" + field).select_option(value)
        page.get_by_role("button", name="开始", exact=True).click()
        time.sleep(1.02)
        page.get_by_role("button", name="结束", exact=True).click()
        page.screenshot(path=str(out / "QA31-表单截图.png"), full_page=True)
        with page.expect_download() as download:
            page.get_by_role("button", name="导出正式记录", exact=True).click()
        target = out / "QA31-表单实际导出.json"
        download.value.save_as(target)
        record = json.loads(target.read_text(encoding="utf-8-sig"))
        assert record["timingValid"] is False and record["seconds"] is None
        assert [record[k] for k in ("understand", "evidence", "saved")] == ["4", "4", "4"]
        save(out / "QA31-核对结果.json", {"通过": True, "执行来源": "AI 本地真实浏览器操作；记录为工具验收夹具",
            "正式记录": record["packageKind"], "计时有效": record["timingValid"], "效率秒数": record["seconds"],
            "保留评分": [record[k] for k in ("understand", "evidence", "saved")], "表单SHA256": hashlib.sha256(form.read_bytes()).hexdigest(),
            "口径": "因已知事后补填而选择计时不完整，不以1秒阈值自动推断体验真假；旧schema名称不改变AI来源。"})
        browser.close()
    save(out / "环境.json", {"时间": utc(), "模型调用": 0, "执行者": "AI", "脚本SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    print(json.dumps({"QA30": "通过", "QA31": "通过", "目录": str(out.relative_to(REPO))}, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="首轮")
    main(p.parse_args().name)
