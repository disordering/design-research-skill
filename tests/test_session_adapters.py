import asyncio
import base64
import io
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PIL import Image

from engine.errors import EngineError
from engine.session_adapters import AdapterHub, BrowserAdapter, FigmaMCPAdapter, figma_target, validate_browser_url
from engine.session_contracts import Action, SourceInput, SourceRecord


@pytest.mark.parametrize("url,expected", [
    ("https://www.figma.com/design/abc/Test?node-id=19-92", ("abc", "19:92")),
    ("https://www.figma.com/proto/xyz/Test", ("xyz", None)),
])
def test_figma_url_parser(url, expected):
    assert figma_target(url) == expected


def test_figma_metadata_extracts_text_screen_and_arrow_as_different_objects():
    metadata = (
        '<frame id="1:1" name="Flow" x="0" y="0" width="1000" height="1000">'
        '<text id="1:2" name="Select a stone" x="20" y="20" width="200" height="30"/>'
        '<rounded-rectangle id="1:3" name="Screen image" x="0" y="100" width="600" height="300"/>'
        '<vector id="1:4" name="Arrow 1" x="50" y="200" width="400" height="0"/>'
        '</frame>'
    )
    tree, texts, visual = FigmaMCPAdapter._structure_index(metadata)
    assert tree is not None
    assert texts[0]["text"] == "Select a stone"
    screen = next(item for item in visual if item["node_id"] == "1:3")
    arrow = next(item for item in visual if item["node_id"] == "1:4")
    assert screen["screen_like"] is True
    assert arrow["annotation"] == "arrow"
    assert arrow["direction"] == "horizontal"
    assert arrow["nearby_targets"] == ["1:3"]


def test_figma_slide_frame_is_treated_as_a_screen_target():
    metadata = (
        '<frame id="1:1" name="交互稿" x="0" y="0" width="4000" height="3000">'
        '<frame id="1:2" name="Slide 16:9 - 1" x="0" y="0" width="1920" height="1080">'
        '<text id="1:3" name="Visible copy" x="100" y="100" width="300" height="40"/>'
        '</frame>'
        '</frame>'
    )
    _, _, visual = FigmaMCPAdapter._structure_index(metadata)
    slide = next(item for item in visual if item["node_id"] == "1:2")
    assert slide["slide_like"] is True
    assert slide["screen_like"] is True
    assert slide["container"] is True


def test_figma_snapshot_reads_metadata_and_each_child_screenshot_without_live_tab(tmp_path):
    snapshot = tmp_path / "fixture-snapshot"
    (snapshot / "metadata").mkdir(parents=True)
    (snapshot / "images").mkdir()
    metadata = (
        '<frame id="1:1" name="Flow" x="0" y="0" width="1000" height="1000">'
        '<text id="1:2" name="Visible requirement" x="20" y="20" width="300" height="30"/>'
        '<rounded-rectangle id="1:3" name="Screen image" x="0" y="100" width="600" height="300"/>'
        '<vector id="1:4" name="Arrow 1" x="50" y="200" width="400" height="0"/>'
        '</frame>'
    )
    (snapshot / "metadata" / "1-1.xml").write_text(metadata, encoding="utf-8")
    raw = io.BytesIO()
    Image.new("RGB", (600, 400), "white").save(raw, "PNG")
    (snapshot / "images" / "1-1.png").write_bytes(raw.getvalue())
    (snapshot / "images" / "1-3.png").write_bytes(raw.getvalue())
    (snapshot / "manifest.json").write_text(json.dumps({
        "file_key": "abc",
        "captured_at": "2026-11-02T00:00:00Z",
        "nodes": {"1:1": {"name": "Flow"}, "1:3": {"name": "Screen image"}},
    }), encoding="utf-8")
    source = SourceRecord(input=SourceInput(
        kind="figma_board",
        reference="https://www.figma.com/design/abc/Test?node-id=1-1",
        figma_snapshot_id="fixture-snapshot",
    ))
    adapter = FigmaMCPAdapter(snapshot_root=tmp_path)
    root = asyncio.run(adapter.read("s", source))
    assert root.locator["source_mode"] == "prefetched_figma_snapshot"
    assert root.locator["file_identity_verified"] is True
    assert len(root.locator["arrow_annotations"]) == 1
    assert "Visible requirement" in root.content
    child = asyncio.run(adapter.read("s", source, "1:3"))
    assert child.image
    assert child.locator["node_id"] == "1:3"
    assert child.locator["requested_node_id"] == "1:1"
    assert child.raw_content is None
    assert child.locator["metadata_status"] == "unavailable"


@pytest.mark.parametrize("manifest,xml,expected_error", [
    ({"file_key": "other", "nodes": {"1:1": {}}}, '<frame id="1:1"/>', "figma_snapshot_file_mismatch"),
    ({"nodes": {"1:1": {}}}, '<frame id="1:1"/>', "figma_snapshot_invalid"),
    ({"file_key": "abc", "nodes": {"1:2": {}}}, '<frame id="1:1"/>', "figma_snapshot_node_missing"),
    ({"file_key": "abc", "nodes": {"1:1": {}}}, None, "figma_snapshot_evidence_missing"),
    ({"file_key": "abc", "nodes": {"1:1": {}}}, '<frame id="1:2"/>', "figma_snapshot_invalid"),
])
def test_snapshot_rejects_mismatched_or_unbacked_node(tmp_path, manifest, xml, expected_error):
    snapshot = tmp_path / "offline"
    (snapshot / "metadata").mkdir(parents=True)
    (snapshot / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if xml is not None:
        (snapshot / "metadata" / "1-1.xml").write_text(xml, encoding="utf-8")
    source = SourceRecord(input=SourceInput(
        kind="figma_board", reference="https://www.figma.com/design/abc/Test?node-id=1-1",
        figma_snapshot_id="offline",
    ))
    with pytest.raises(EngineError) as error:
        asyncio.run(FigmaMCPAdapter(snapshot_root=tmp_path).read("session", source))
    assert error.value.code == expected_error


def test_snapshot_scope_follows_root_and_metadata_only_keeps_observed_ids(tmp_path):
    snapshot = tmp_path / "offline"
    (snapshot / "metadata").mkdir(parents=True)
    nodes = {"1:1": {}, "1:2": {}, "2:1": {}}
    (snapshot / "manifest.json").write_text(json.dumps({"file_key": "abc", "nodes": nodes}), encoding="utf-8")
    for name, xml in [
        ("1-1", "<frame id='1:1'><frame id='1:2'/></frame>"),
        ("1-2", "<frame id='1:2'/>"),
        ("2-1", "<frame id='2:1'/>"),
    ]:
        (snapshot / "metadata" / f"{name}.xml").write_text(xml, encoding="utf-8")
    adapter = FigmaMCPAdapter(snapshot_root=tmp_path)
    source = SourceRecord(input=SourceInput(
        kind="figma_board", reference="https://www.figma.com/design/abc/Test?node-id=1-1",
        figma_snapshot_id="offline",
    ))
    root = asyncio.run(adapter.read("session", source))
    assert root.partial
    assert root.locator["image_status"] == "unavailable"
    assert root.locator["node_ids"] == ["1:1", "1:2"]
    action = Action(source_id=source.source_id, kind="inspect_node", node_id="1:2",
                    expected_state_id=root.state_id, reason="查看已观察到的子节点")
    assert asyncio.run(adapter.act("session", source, action)).locator["node_id"] == "1:2"
    source.input.reference = "https://www.figma.com/design/abc/Test?node-id=2-1"
    with pytest.raises(EngineError) as error:
        asyncio.run(adapter.act("session", source, action))
    assert error.value.code == "figma_node_not_observed"
    asyncio.run(adapter.read("session", source))
    with pytest.raises(EngineError) as error:
        asyncio.run(adapter.act("session", source, action))
    assert error.value.code == "figma_node_not_observed"


def test_snapshot_cannot_take_another_archives_images_through_a_directory_link(tmp_path):
    expected = tmp_path / "expected"
    expected.mkdir()
    (expected / "manifest.json").write_text(json.dumps({"file_key": "abc", "nodes": {"1:1": {}}}), encoding="utf-8")
    other_images = tmp_path / "other" / "images"
    other_images.mkdir(parents=True)
    Image.new("RGB", (8, 6), "red").save(other_images / "1-1.png")
    if sys.platform == "win32":
        import _winapi
        _winapi.CreateJunction(str(other_images), str(expected / "images"))
    else:
        (expected / "images").symlink_to(other_images, target_is_directory=True)
    source = SourceRecord(input=SourceInput(
        kind="figma_board", reference="https://www.figma.com/design/abc/Test?node-id=1-1",
        figma_snapshot_id="expected",
    ))
    with pytest.raises(EngineError) as error:
        asyncio.run(FigmaMCPAdapter(snapshot_root=tmp_path).read("session", source))
    assert error.value.code == "figma_snapshot_invalid"


def test_browser_url_guard_rejects_private_network_and_file_protocol():
    with pytest.raises(EngineError) as error:
        asyncio.run(validate_browser_url("http://127.0.0.1:8000"))
    assert error.value.code == "private_network_blocked"
    with pytest.raises(EngineError):
        asyncio.run(validate_browser_url("file:///secret"))
    asyncio.run(validate_browser_url("http://127.0.0.1:8000", allow_local=True))


def test_figma_without_backend_authorization_is_not_a_successful_read():
    source = SourceRecord(input=SourceInput(kind="figma_board", reference="https://www.figma.com/design/abc/Test?node-id=1-2"))
    with pytest.raises(EngineError) as error:
        asyncio.run(FigmaMCPAdapter().read("s", source))
    assert error.value.code == "figma_mcp_not_configured"


def test_mcp_sdk_error_response_is_not_treated_as_success(monkeypatch):
    from contextlib import asynccontextmanager
    from mcp.types import Tool, ListToolsResult, CallToolResult, TextContent
    import mcp

    @asynccontextmanager
    async def transport(*args, **kwargs):
        yield (None, None)

    class Client:
        def __init__(self, *_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def initialize(self):
            pass

        async def list_tools(self):
            return ListToolsResult(tools=[Tool(name="get_metadata", input_schema={"type": "object"})])

        async def call_tool(self, *_):
            return CallToolResult(content=[TextContent(type="text", text="Access denied")], is_error=True)

    monkeypatch.setattr("engine.session_adapters.mcp_transport", transport)
    monkeypatch.setattr(mcp, "ClientSession", Client)
    source = SourceRecord(input=SourceInput(kind="figma_board", reference="https://www.figma.com/design/abc/Test?node-id=1-2"))
    with pytest.raises(EngineError) as error:
        asyncio.run(FigmaMCPAdapter("http://127.0.0.1:3845/mcp").read("s", source))
    assert error.value.code == "figma_metadata_failed"


@pytest.mark.parametrize("file_targeted", [False, True])
@pytest.mark.parametrize("page_overview", [False, True])
def test_figma_tool_schema_and_page_overview(monkeypatch, file_targeted, page_overview):
    from contextlib import asynccontextmanager
    from mcp.types import Tool, ListToolsResult, CallToolResult, TextContent, ImageContent
    import mcp

    calls = []
    properties = {"nodeId": {"type": "string"}}
    if file_targeted:
        properties["fileKey"] = {"type": "string"}
    tools = [
        Tool(name=name, input_schema={"type": "object", "properties": properties,
                                     "additionalProperties": False})
        for name in ("get_metadata", "get_screenshot")
    ]
    raw = io.BytesIO()
    Image.new("RGB", (96, 64), "red").save(raw, "PNG")
    tag = "canvas" if page_overview else "frame"
    metadata = (
        f'<{tag} id="1:2" name="Sample"><frame id="1:3" name="Child">'
        '<text id="1:4" name="Visible requirement" x="20" y="30" width="300" height="40"/>'
        '<text id="1:5" name="Hidden note" x="20" y="90" width="300" height="40" hidden="true"/>'
        '<rounded-rectangle id="1:6" name="Screen image" x="0" y="150" width="600" height="300"/>'
        f'</frame></{tag}>'
    )

    @asynccontextmanager
    async def transport(*args, **kwargs):
        yield (None, None)

    class Client:
        def __init__(self, *_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def initialize(self):
            pass

        async def list_tools(self):
            return ListToolsResult(tools=tools)

        async def call_tool(self, name, arguments):
            assert set(arguments) <= set(properties)
            assert arguments["nodeId"] == "1:2"
            assert ("fileKey" in arguments) is file_targeted
            calls.append(name)
            if name == "get_metadata":
                return CallToolResult(content=[TextContent(type="text", text=metadata)])
            return CallToolResult(content=[ImageContent(
                type="image", data=base64.b64encode(raw.getvalue()).decode(), mime_type="image/png",
            )])

    monkeypatch.setattr("engine.session_adapters.mcp_transport", transport)
    monkeypatch.setattr(mcp, "ClientSession", Client)
    source = SourceRecord(input=SourceInput(
        kind="figma_board", reference="https://www.figma.com/design/abc/Test?node-id=1-2",
    ))
    capture = asyncio.run(FigmaMCPAdapter("http://127.0.0.1:3845/mcp").read("s", source))
    assert capture.locator["file_identity_verified"] is file_targeted
    assert capture.locator["file_key"] == ("abc" if file_targeted else None)
    assert capture.locator["requested_file_key"] == "abc"
    assert "1:3" in capture.locator["node_ids"]
    assert capture.locator["visible_text_ids"] == ["1:4"]
    assert capture.locator["hidden_text_ids"] == ["1:5"]
    assert any(node["node_id"] == "1:6" for node in capture.locator["inspection_targets"])
    assert any(control["node_id"] == "1:6" for control in capture.controls)
    assert not capture.locator["inspection_targets"][0]["container"]
    assert capture.locator["inspection_targets"][0]["screen_like"]
    assert "Visible requirement" in capture.content and "Hidden note" in capture.content
    assert ("get_screenshot" in calls) is not page_overview
    assert bool(capture.image) is not page_overview
    assert capture.partial is page_overview
    assert capture.locator["image_status"] == ("page_overview_use_inspect_node" if page_overview else "captured")


def test_large_leaf_frame_is_treated_as_screen_without_screen_keyword():
    metadata = (
        '<frame id="1:1" name="Flow board" x="0" y="0" width="2600" height="2000">'
        '<frame id="1:2" name="首页" x="100" y="100" width="1920" height="720"/>'
        '<frame id="1:3" name="装饰面板" x="100" y="900" width="800" height="400"/>'
        '</frame>'
    )
    _, _, visual = FigmaMCPAdapter._structure_index(metadata)
    home = next(item for item in visual if item["node_id"] == "1:2")
    decoration = next(item for item in visual if item["node_id"] == "1:3")
    assert home["screen_like"] is True
    assert decoration["screen_like"] is False


def test_figma_inspection_keeps_observed_siblings_but_clears_scope_on_version_change(monkeypatch):
    from contextlib import asynccontextmanager
    from mcp.types import Tool, ListToolsResult, CallToolResult, TextContent
    import mcp

    metadata = {
        "1:1": '<canvas id="1:1"><frame id="1:2"/><frame id="1:3"/></canvas>',
        "1:2": '<frame id="1:2"><text id="1:4" name="Child"/></frame>',
        "1:3": '<frame id="1:3"><text id="1:5" name="Sibling"/></frame>',
    }

    @asynccontextmanager
    async def transport(*args, **kwargs):
        yield (None, None)

    class Client:
        def __init__(self, *_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def initialize(self):
            pass

        async def list_tools(self):
            return ListToolsResult(tools=[Tool(
                name="get_metadata", input_schema={"type": "object", "properties": {"nodeId": {"type": "string"}}},
            )])

        async def call_tool(self, name, args):
            assert name == "get_metadata"
            return CallToolResult(content=[TextContent(type="text", text=metadata[args["nodeId"]])])

    monkeypatch.setattr("engine.session_adapters.mcp_transport", transport)
    monkeypatch.setattr(mcp, "ClientSession", Client)

    async def run():
        adapter = FigmaMCPAdapter("http://127.0.0.1:3845/mcp")
        source = SourceRecord(input=SourceInput(
            kind="figma_board", reference="https://www.figma.com/design/abc/Test?node-id=1-1",
        ))
        root = await adapter.read("s", source)
        action = Action(source_id=source.source_id, kind="inspect_node", node_id="1:2",
                        expected_state_id=root.state_id, reason="Inspect child")
        child = await adapter.act("s", source, action)
        sibling = await adapter.act("s", source, action.model_copy(update={
            "node_id": "1:3", "expected_state_id": child.state_id,
        }))
        assert "Sibling" in sibling.content
        metadata["1:1"] = '<canvas id="1:1"><frame id="1:2"/></canvas>'
        source.input.version = "v2"
        await adapter.read("s", source)
        with pytest.raises(EngineError) as error:
            await adapter.act("s", source, action.model_copy(update={"node_id": "1:3"}))
        assert error.value.code == "figma_node_not_observed"
    asyncio.run(run())


def test_image_adapter_checks_actual_image_and_returns_normalized_capture():
    raw = io.BytesIO()
    Image.new("RGB", (640, 360), "white").save(raw, "PNG")
    source = SourceRecord(input=SourceInput(kind="image", image_base64=base64.b64encode(raw.getvalue()).decode()))
    hub = AdapterHub()
    capture = asyncio.run(hub.read("s", source))
    assert capture.image and capture.locator["width"] == 640
    bad = SourceRecord(input=SourceInput(kind="image", image_base64=base64.b64encode(b"not an image").decode()))
    with pytest.raises(EngineError) as error:
        asyncio.run(hub.read("s", bad))
    assert error.value.code == "session_image_invalid"


@pytest.mark.parametrize("kind,after_state,verified", [
    ("observe", "new-state", False),
    ("click", "before-state", False),
    ("click", "chrome-only-change", False),
    ("click", "new-state", True),
])
def test_capability_observation_or_noop_is_not_verified_interaction(kind, after_state, verified):
    from engine.session_adapters import Capture

    class Browser:
        async def act(self, *args, **kwargs):
            return Capture(content="captured", locator={"operation_verified": after_state == "new-state"},
                           state_id=after_state)

    source = SourceRecord(input=SourceInput(kind="figma_prototype", reference="https://www.figma.com/proto/abc/Test"))
    hub = AdapterHub(browser=Browser())
    action = Action(source_id=source.source_id, kind=kind, expected_state_id="before-state",
                    x=0.5, y=0.5,
                    reason="Smoke test", requires_explicit_authorization=False)
    asyncio.run(hub.act("s", source, action, authorized=False))
    assert hub.capabilities()["figma_prototype"]["read_verified"]
    assert hub.capabilities()["figma_prototype"]["operation_verified"] is verified


def test_real_browser_capture_action_and_stale_state_guard():
    page = b"""<!doctype html><html><body>
    <h1>Review engine test fixture</h1><input id="name" value="Alice">
    <input type="hidden" name="csrf" value="fixture-hidden-token">
    <div id="state">Step one</div>
    <button type="button" id="next" onclick="document.getElementById('state').textContent='Step two'">Next</button>
        <button type="button" id="delete">Delete item</button>
        <button type="button" id="icon-delete" title="Delete">x</button>
        </body></html>"""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    async def run():
        adapter = BrowserAdapter(allow_local=True)
        source = SourceRecord(input=SourceInput(kind="website", reference=f"http://127.0.0.1:{server.server_port}"))
        try:
            before = await adapter.read("s", source)
            assert "Step one" in before.content
            assert any(c.get("value") == "Alice" for c in before.controls)
            assert not any(c.get("value") == "fixture-hidden-token" for c in before.controls)
            pixels = Image.open(io.BytesIO(before.image)).convert("L")
            assert pixels.getextrema()[0] != pixels.getextrema()[1]
            next_control = next(
                control for control in before.controls
                if control.get("label") == "Next"
            )
            action = Action(
                source_id=source.source_id, kind="click",
                selector=next_control["selector"],
                expected_state_id=before.state_id, reason="Next",
                target_label="Next",
                requires_explicit_authorization=False,
            )
            assert not await adapter.action_needs_authorization("s", source, action)
            after = await adapter.act("s", source, action, authorized=False)
            assert "Step two" in after.content and after.state_id != before.state_id
            with pytest.raises(EngineError) as error:
                await adapter.act("s", source, action, authorized=False)
            assert error.value.code == "browser_state_changed"
            delete_control = next(
                control for control in after.controls
                if control.get("label") == "Delete item"
            )
            destructive = action.model_copy(update={
                "selector": delete_control["selector"],
                "expected_state_id": after.state_id,
                "target_label": "Delete item",
            })
            assert await adapter.action_needs_authorization("s", source, destructive)
            titled_delete = next(
                control for control in after.controls
                if control.get("title") == "Delete"
            )
            assert await adapter.action_needs_authorization(
                "s",
                source,
                action.model_copy(update={
                    "selector": titled_delete["selector"],
                    "expected_state_id": after.state_id,
                    "target_label": "x",
                }),
            )
            with pytest.raises(EngineError) as mismatch:
                await adapter.act(
                    "s",
                    source,
                    destructive.model_copy(update={"target_label": "Next"}),
                    authorized=True,
                )
            assert mismatch.value.code == "action_target_mismatch"
        finally:
            await adapter.close()

    try:
        asyncio.run(run())
    finally:
        server.shutdown()
        server.server_close()
