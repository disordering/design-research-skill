"""运行与 42 项验收直接相关的产品测试，并归档实际接口输入输出。"""
from __future__ import annotations
import argparse
import functools
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from d_native_recheck import REPO, WORK, save, utc
import pytest
from engine.session_adapters import BrowserAdapter
from engine.session_service import SessionService
from engine.session_store import SessionStore


TARGETS = {
    "test_d_continuation.py": ["test_static_image_observation_reuses_pixels_without_authorization", "test_legacy_event_retry_keeps_idempotency_and_new_actor_is_not_inferred"],
    "test_session_adapters.py": ["test_figma_snapshot_reads_metadata_and_each_child_screenshot_without_live_tab", "test_figma_without_backend_authorization_is_not_a_successful_read", "test_real_browser_capture_action_and_stale_state_guard"],
    "test_session_browser_flow.py": ["test_canvas_coordinates_same_url_states_and_shell_safety", "test_updated_reference_reloads_browser_instead_of_reusing_old_page"],
    "test_session_service.py": [
        "test_access_failure_is_partial_and_not_a_product_finding",
        "test_goal_change_invalidates_old_results_and_duplicate_event_does_not_repeat",
        "test_action_is_not_executed_until_authorized_and_event_is_idempotent",
        "test_invalid_finding_evidence_cannot_become_a_confirmed_issue",
        "test_new_version_does_not_auto_resolve_old_finding",
        "test_resource_limit_is_reported_not_silently_skipped",
        "test_noop_action_keeps_before_after_evidence_without_a_verified_path",
        "test_noop_prototype_click_does_not_establish_a_dynamic_product_defect",
        "test_compound_goal_cannot_hide_unknown_or_violation",
        "test_planned_not_applicable_check_does_not_turn_missing_execution_into_failure",
        "test_recheck_rejects_unrelated_statement_as_resolution_evidence",
        "test_structured_dynamic_claim_requires_action_without_keyword_in_wording",
    ],
    "test_session_context_pipeline.py": [
        "test_conflict_decision_needs_an_actor_and_is_not_an_implementation_fix",
        "test_unresolved_formal_requirements_block_goal_aggregation",
        "test_requirements_text_alone_does_not_prove_implementation_compliance",
        "test_nonapplicability_requires_source_backed_conditions_with_actionable_feedback",
        "test_rejected_claim_scope_survives_model_renaming_or_omitting_resolved_conflict",
        "test_blocking_formal_conflict_cannot_create_product_nonconformity",
    ],
    "test_d_acceptance_42.py": [],
}


def plain(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, Path):
        return value.name
    return value


class Archive:
    def __init__(self, out):
        self.out, self.rows, self.current, self.count = out, [], None, 0
        self.monkey = None

    def record(self, operation, value):
        self.count += 1
        save(self.current / f"{self.count:03d}-{operation}.json", plain(value))

    def pytest_runtest_setup(self, item):
        name = f"{len(self.rows) + 1:02d}-" + item.name
        self.current = self.out / name
        self.current.mkdir(parents=True)
        self.count = 0
        self.monkey = pytest.MonkeyPatch()
        self.record("用例", {"节点": item.nodeid, "执行者": "AI 编排的程序/浏览器验收", "响应来源": "既有或新增测试中的固定受控响应；不调用真实模型"})
        original_call = SessionService._call
        owner = self

        async def call(service, session, model, schema, operation, payload):
            owner.record("调用输入-" + operation, {"schema": schema.__name__, "payload": payload,
                         "context": service._model_context(session)})
            try:
                result = await original_call(service, session, model, schema, operation, payload)
            except Exception as exc:
                owner.record("调用异常-" + operation, {"类型": type(exc).__name__, "代码": getattr(exc, "code", ""), "说明": str(exc)})
                raise
            owner.record("调用输出-" + operation, result)
            return result
        self.monkey.setattr(SessionService, "_call", call)
        original_save = SessionStore.save

        def save_session(store, session, *args, **kwargs):
            result = original_save(store, session, *args, **kwargs)
            save(owner.current / "最后持久化状态.json", session.model_dump(mode="json"))
            return result
        self.monkey.setattr(SessionStore, "save", save_session)

        # 捕获不一定立即持久化的判断、复审及动作结果。
        for method in ["_judge", "_recheck", "_perform_action"]:
            original = getattr(SessionService, method)
            def make_async(fn, label):
                @functools.wraps(fn)
                async def wrapped(service, session, *args, **kwargs):
                    try:
                        return await fn(service, session, *args, **kwargs)
                    finally:
                        owner.record(label + "-最终状态", session)
                return wrapped
            self.monkey.setattr(SessionService, method, make_async(original, method))
        for method in ["read", "act"]:
            original = getattr(BrowserAdapter, method)
            def make_browser(fn, label):
                @functools.wraps(fn)
                async def wrapped(adapter, *args, **kwargs):
                    result = await fn(adapter, *args, **kwargs)
                    owner.record("浏览器-" + label, {"content": result.content, "locator": result.locator,
                        "state_id": result.state_id, "controls": plain(result.controls), "partial": result.partial})
                    if result.image:
                        (owner.current / f"{owner.count:03d}-浏览器.png").write_bytes(result.image)
                    return result
                return wrapped
            self.monkey.setattr(BrowserAdapter, method, make_browser(original, method))

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or (report.failed and report.when == "setup"):
            row = {"节点": report.nodeid, "结果": report.outcome, "秒": round(report.duration, 3),
                   "目录": self.current.name, "失败说明": str(report.longrepr) if report.failed else ""}
            self.rows.append(row)
            save(self.current / "断言结果.json", row)
            save(self.out / "汇总.json", self.rows)

    def pytest_runtest_teardown(self, item, nextitem):
        if self.monkey:
            self.monkey.undo()


def main(args):
    out = REPO / "docs/D-最终验收证据/42项验收/工程实测" / args.name
    out.mkdir(parents=True, exist_ok=False)
    files = [*REPO.glob("engine/session*.py"), REPO / "tests/test_d_acceptance_42.py"]
    save(out / "环境.json", {"时间": utc(), "git": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "源SHA256": {str(p.relative_to(REPO)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        "执行范围": "42 项验收对应定向测试；不是全套回归", "真实模型调用": 0})
    targets = ["tests/" + file + ("::" + name if name else "") for file, names in TARGETS.items() for name in (names or [""])]
    if args.only_new:
        targets = ["tests/test_d_acceptance_42.py"]
    code = pytest.main([*targets, "-q", "--tb=short", f"--junitxml={out / 'JUnit.xml'}"], plugins=[Archive(out)])
    save(out / "退出码.json", {"pytest": int(code)})
    return code


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="首轮")
    p.add_argument("--only-new", action="store_true")
    sys.exit(main(p.parse_args()))
