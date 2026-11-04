"""真实本地浏览器中的下拉选择、事件和授权边界回归。"""

import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from types import SimpleNamespace

import pytest

from engine.errors import EngineError
from engine.session_adapters import BrowserAdapter
from engine.session_contracts import (
    Action, Evidence, EvidenceObject, Finding, FindingClaim, SourceInput, SourceRecord,
)
from engine.session_verification import finding_location_evidence


HTML = """<!doctype html><meta charset="utf-8"><title>下拉控件回归</title>
<style>body{font:18px sans-serif}label{display:block;margin:12px}select{min-width:180px}</style>
<label>显示模式<select id="mode">
 <option value="normal" selected>标准显示</option>
 <optgroup label="可选模式"><option value=" roomy " label="宽松显示">原始文字</option>
 <option value="">不指定</option></optgroup>
 <option value="locked" disabled>暂不可选</option>
 <optgroup label="禁用模式" disabled><option value="group-locked">组内选项</option></optgroup>
</select></label>
<label>禁用控件<select id="disabled" disabled><option value="a">甲</option><option value="b">乙</option></select></label>
<fieldset disabled><label>禁用字段组<select id="fieldset"><option value="a">甲</option><option value="b">乙</option></select></label></fieldset>
<label>多选控件<select id="multi" multiple><option value="a" selected>甲</option><option value="b">乙</option></select></label>
<label>普通输入<input id="plain" value="normal"></label>
<label>同值选项<select id="duplicate"><option value="a">初始</option><option value="b">乙</option><option value="b">丙</option></select></label>
<label>提交购买方式<select id="sensitive"><option value="a">甲</option><option value="b">乙</option></select></label>
<p id="events">尚无选择事件</p><p id="network">尚无请求</p>
<script>
 window.selectionEvents=[];
 for(const type of ['input','change']) mode.addEventListener(type,()=>{
   selectionEvents.push({type,value:mode.value});
   document.getElementById('events').textContent=JSON.stringify(selectionEvents);
 });
</script>"""


@contextmanager
def serve(html=HTML):
    posts = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def do_POST(self):
            posts.append(self.path)
            self.send_response(204)
            self.end_headers()

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/", posts
        finally:
            server.shutdown()
            thread.join(3)


def action_for(source, capture, dom_id="mode", value=" roomy ", **changes):
    control = next(c for c in capture.controls if c["domId"] == dom_id)
    fields = dict(source_id=source.source_id, kind="select", selector=control["selector"],
                  target_label=control["label"], value=value, expected_state_id=capture.state_id,
                  reason="下拉控件工程回归", requires_explicit_authorization=False)
    fields.update(changes)
    return Action(**fields)


def log_case(name, **facts):
    print(json.dumps({"用例": name, **facts}, ensure_ascii=False))


def test_capture_options_and_native_select_events_preserve_exact_values():
    async def run(url):
        browser = BrowserAdapter(allow_local=True)
        source = SourceRecord(input=SourceInput(kind="website", reference=url))
        try:
            before = await browser.read("select", source)
            control = next(c for c in before.controls if c["domId"] == "mode")
            assert control["label"] == "显示模式"
            assert control["multiple"] is False
            assert control["optionCount"] == 5
            assert control["optionsTruncated"] is False
            assert control["options"] == [
                {"label": "标准显示", "value": "normal", "selected": True, "disabled": False, "optgroup": ""},
                {"label": "宽松显示", "value": " roomy ", "selected": False, "disabled": False, "optgroup": "可选模式"},
                {"label": "不指定", "value": "", "selected": False, "disabled": False, "optgroup": "可选模式"},
                {"label": "暂不可选", "value": "locked", "selected": False, "disabled": True, "optgroup": ""},
                {"label": "组内选项", "value": "group-locked", "selected": False, "disabled": True, "optgroup": "禁用模式"},
            ]
            action = action_for(source, before)
            assert action.value == " roomy "
            assert not await browser.action_needs_authorization("select", source, action)
            after = await browser.act("select", source, action, authorized=False)
            chosen = next(c for c in after.controls if c["domId"] == "mode")
            assert chosen["value"] == " roomy "
            assert chosen["options"][1]["selected"]
            page = browser._pages[("select", source.source_id)]["page"]
            events = await page.evaluate("window.selectionEvents")
            assert events == [{"type": "input", "value": " roomy "}, {"type": "change", "value": " roomy "}]
            assert after.locator["operation_verified"]
            assert after.locator["action_outcome"] == "state_changed"
            assert after.locator["change_signals"]["controls"]
            # 空字符串也是合法的原生 option.value，不用标签或索引替代。
            cleared = await browser.act("select", source, action_for(source, after, value=""), authorized=False)
            assert next(c for c in cleared.controls if c["domId"] == "mode")["options"][2]["selected"]
            log_case("原生选择与事件", before=control, after=chosen, events=events,
                     outcome=after.locator["action_outcome"], empty_value_selected=True)
        finally:
            await browser.close()

    with serve() as (url, _):
        asyncio.run(run(url))


@pytest.mark.parametrize("case,dom_id,value,changes,code", [
    ("未知值", "mode", "missing", {}, "select_option_not_observed"),
    ("标签不是value", "mode", "宽松显示", {}, "select_option_not_observed"),
    ("去空格不能匹配原值", "mode", "roomy", {}, "select_option_not_observed"),
    ("禁用选项", "mode", "locked", {}, "select_option_unavailable"),
    ("禁用optgroup", "mode", "group-locked", {}, "select_option_unavailable"),
    ("禁用控件", "disabled", "b", {}, "action_target_unavailable"),
    ("禁用fieldset", "fieldset", "b", {}, "action_target_unavailable"),
    ("多选控件", "multi", "b", {}, "select_multiple_unsupported"),
    ("非select控件", "plain", "b", {}, "select_target_invalid"),
    ("同值选项不唯一", "duplicate", "b", {}, "select_option_ambiguous"),
    ("未观察selector", "mode", " roomy ", {"selector": "#mode"}, "action_target_not_observed"),
    ("目标名称不符", "mode", " roomy ", {"target_label": "其他控件"}, "action_target_mismatch"),
])
def test_invalid_select_is_rejected_without_changing_page(case, dom_id, value, changes, code):
    async def run(url):
        browser = BrowserAdapter(allow_local=True)
        source = SourceRecord(input=SourceInput(kind="website", reference=url))
        try:
            before = await browser.read("select-negative", source)
            action = action_for(source, before, dom_id, value, **changes)
            with pytest.raises(EngineError) as error:
                await browser.act("select-negative", source, action, authorized=False)
            assert error.value.code == code
            after = await browser.capture("select-negative", source)
            assert after.state_id == before.state_id
            page = browser._pages[("select-negative", source.source_id)]["page"]
            assert await page.evaluate("window.selectionEvents") == []
            log_case(case, code=error.value.code, state_unchanged=True, events=[])
        finally:
            await browser.close()

    with serve() as (url, _):
        asyncio.run(run(url))


def test_changed_option_metadata_invalidates_old_action():
    async def run(url):
        browser = BrowserAdapter(allow_local=True)
        source = SourceRecord(input=SourceInput(kind="website", reference=url))
        try:
            before = await browser.read("select-stale", source)
            action = action_for(source, before)
            page = browser._pages[("select-stale", source.source_id)]["page"]
            await page.locator("#mode").evaluate("node => node.options[1].disabled = true")
            with pytest.raises(EngineError) as error:
                await browser.act("select-stale", source, action, authorized=False)
            assert error.value.code == "browser_state_changed"
            assert await page.locator("#mode").input_value() == "normal"
            assert await page.evaluate("window.selectionEvents") == []
            log_case("选项变化后的旧状态", code=error.value.code, original_value="normal", events=[])
        finally:
            await browser.close()

    with serve() as (url, _):
        asyncio.run(run(url))


@pytest.mark.parametrize("authorized", [False, True])
def test_select_retains_authorization_and_non_read_request_guard(authorized):
    html = HTML + """<script>mode.addEventListener('change',()=>fetch('/save',{method:'POST'})
        .then(()=>document.getElementById('network').textContent='请求完成')
        .catch(()=>document.getElementById('network').textContent='请求被拦截'));</script>"""

    async def run(url, posts):
        browser = BrowserAdapter(allow_local=True)
        source = SourceRecord(input=SourceInput(kind="website", reference=url))
        try:
            before = await browser.read("select-auth", source)
            explicit = action_for(source, before, requires_explicit_authorization=True)
            assert await browser.action_needs_authorization("select-auth", source, explicit)
            sensitive = action_for(source, before, "sensitive", "b")
            assert await browser.action_needs_authorization("select-auth", source, sensitive)
            after = await browser.act("select-auth", source, action_for(source, before), authorized=authorized)
            assert bool(posts) is authorized
            assert bool(after.locator["blocked_requests"]) is not authorized
            assert browser._pages[("select-auth", source.source_id)]["allow_side_effects"] is False
            log_case("选择事件副作用授权", authorized=authorized, received_posts=posts,
                     blocked=after.locator["blocked_requests"])
        finally:
            await browser.close()

    with serve(html) as (url, posts):
        asyncio.run(run(url, posts))


def test_select_stays_inside_observed_prototype_canvas():
    html = """<!doctype html><meta charset="utf-8"><body>
    <label style="position:absolute;left:10px;top:10px">外壳选项<select id="shell"><option value="a">甲</option><option value="b">乙</option></select></label>
    <canvas width="400" height="400" style="position:absolute;left:250px;top:160px"></canvas>
    <label style="position:absolute;left:280px;top:200px">画布选项<select id="inside"><option value="a">甲</option><option value="b">乙</option></select></label>
    <script>const c=document.querySelector('canvas').getContext('2d');c.fillStyle='#ddd';c.fillRect(0,0,400,400);c.fillStyle='#147';c.fillRect(40,120,200,60);</script>
    </body>"""

    async def run(url):
        browser = BrowserAdapter(allow_local=True)
        # 仅本地工程样本使用原型类型，验证生产画布边界而不访问 Figma。
        inp = SourceInput(kind="website", reference=url + "proto/select/Test?node-id=1-2").model_copy(update={"kind": "figma_prototype"})
        source = SourceRecord.model_construct(input=inp)
        try:
            before = await browser.read("select-proto", source)
            assert not before.partial
            assert [c["domId"] for c in before.controls] == ["inside"]
            bad = Action(source_id=source.source_id, kind="select", selector="#shell", value="b",
                         expected_state_id=before.state_id, reason="验证外壳拒绝", requires_explicit_authorization=False)
            with pytest.raises(EngineError) as error:
                await browser.act("select-proto", source, bad, authorized=True)
            assert error.value.code == "prototype_shell_action_blocked"
            after = await browser.act("select-proto", source, action_for(source, before, "inside", "b"), authorized=False)
            page = browser._pages[("select-proto", source.source_id)]["page"]
            assert await page.locator("#shell").input_value() == "a"
            assert next(c for c in after.controls if c["domId"] == "inside")["value"] == "b"
            log_case("原型画布选择边界", shell_rejected=error.value.code, inside_value="b", shell_value="a")
        finally:
            await browser.close()

    with serve(html) as (url, _):
        asyncio.run(run(url))


def test_select_contract_requires_observed_selector_and_exposes_native_kind():
    action = Action(source_id="source", kind="select", value="b", expected_state_id="state", reason="验证契约")
    with pytest.raises(ValueError, match="selector"):
        action.validate_target()
    assert "select" in Action.model_json_schema()["properties"]["kind"]["enum"]


def test_dynamic_finding_location_uses_select_result_before_later_read():
    evidence = [Evidence(
        evidence_id=eid, source_id="source", source_version="v1", context_version=1,
        kind="observation", locator={"url": "https://example.test/"}, content="显示模式的页面结果",
        state_id=eid + "-state", action_id=action_id,
        objects=[EvidenceObject(object_id="mode", kind="control", source_id="source", label="显示模式")],
    ) for eid, action_id in [("after-select", "selected"), ("later-read", "observed")]]
    actions = [
        Action(action_id="selected", source_id="source", kind="select", selector="#mode", value="b",
               expected_state_id="before", reason="选择", status="executed", outcome="state_changed"),
        Action(action_id="observed", source_id="source", kind="observe", expected_state_id="after-select-state",
               reason="随后观察", status="executed", outcome="read"),
    ]
    finding = Finding(kind="issue", title="选择后显示模式不对应", check_ids=["check"],
                      evidence_ids=[e.evidence_id for e in evidence], object_id="mode", object_ref="显示模式",
                      principle="选择结果应对应", detection="动作后模式不同", description="选择后显示不对应",
                      suggestion="核对选择结果", severity_reason="影响操作结果",
                      claims=[FindingClaim(claim_type="action_result", object_id="mode",
                                           evidence_ids=[e.evidence_id for e in evidence])])
    selected = finding_location_evidence(SimpleNamespace(actions=actions, transitions=[]), finding,
                                         {e.evidence_id: e for e in evidence})
    assert selected.evidence_id == "after-select"


@pytest.mark.parametrize("value,tail_duplicate", [("v204", False), ("v1", True)])
def test_long_option_list_reports_capture_limit_and_blocks_incomplete_choices(value, tail_duplicate):
    html = '<!doctype html><meta charset="utf-8"><label>项目<select id="mode">' + ''.join(
        f'<option value="v{1 if tail_duplicate and i == 200 else i}">项目{i}</option>' for i in range(205)
    ) + '</select></label>'

    async def run(url):
        browser = BrowserAdapter(allow_local=True)
        source = SourceRecord(input=SourceInput(kind="website", reference=url))
        try:
            before = await browser.read("select-limit", source)
            control = before.controls[0]
            assert len(control["options"]) == 200
            assert control["optionCount"] == 205
            assert control["optionsTruncated"] is True
            with pytest.raises(EngineError) as error:
                await browser.act("select-limit", source, action_for(source, before, value=value), authorized=False)
            assert error.value.code == "select_options_incomplete"
            assert (await browser.capture("select-limit", source)).state_id == before.state_id
            log_case("选项清单截断", captured=200, total=205, truncated=True, value=value,
                     duplicate_after_limit=tail_duplicate, code=error.value.code)
        finally:
            await browser.close()

    with serve(html) as (url, _):
        asyncio.run(run(url))
