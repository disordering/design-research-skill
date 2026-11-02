"""Real browser fixtures for coordinates and safety, not Figma or model efficacy."""

import asyncio
import io
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PIL import Image
from PIL import ImageDraw

from engine.errors import EngineError
from engine.session_adapters import BrowserAdapter, prototype_navigation_allowed
from engine.session_contracts import Action, SourceInput, SourceRecord


@pytest.mark.parametrize("change_url", [False, True])
def test_canvas_coordinates_same_url_states_and_shell_safety(change_url):
    navigation = "history.replaceState(null,'','?node-id=3-4');" if change_url else ""
    html = ("""<!doctype html><html><body>
    <button id="shell" style="position:absolute;left:20px;top:20px"
      onclick="this.textContent='Shared'">Share design</button>
    <canvas id="prototype" width="400" height="600"
      style="position:absolute;left:250px;top:160px"></canvas>
    <script>
    const canvas=document.getElementById('prototype'),ctx=canvas.getContext('2d');
    ctx.fillStyle='#eeeeee';ctx.fillRect(0,0,400,600);
    ctx.fillStyle='#2277aa';ctx.fillRect(80,200,180,60);
    canvas.onclick=e=>{
      const r=canvas.getBoundingClientRect(),x=e.clientX-r.x,y=e.clientY-r.y;
      if(x>=80&&x<=260&&y>=200&&y<=260){
        ctx.fillStyle='#229944';ctx.fillRect(80,200,180,60);
        NAVIGATION
      }
    };
    canvas.onwheel=e=>{ctx.fillStyle='#cc8844';ctx.fillRect(80,200,180,60);e.preventDefault()};
    </script></body></html>""").replace("NAVIGATION", navigation).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    async def run():
        browser = BrowserAdapter(allow_local=True)
        # Only this controlled local fixture bypasses the public Figma hostname contract.
        input_source = SourceInput(
            kind="website", reference=f"http://127.0.0.1:{server.server_port}/proto/fixture/Test?node-id=1-2",
        ).model_copy(update={"kind": "figma_prototype"})
        source = SourceRecord.model_construct(input=input_source)
        try:
            before = await browser.read("fixture", source)
            assert not before.partial
            assert before.locator["image_geometry"]["region"] == {
                "x": 250, "y": 160, "width": 400, "height": 600,
            }
            assert Image.open(io.BytesIO(before.image)).size == (400, 600)
            assert not before.controls
            assert "Share design" not in before.content
            page = browser._pages[("fixture", source.source_id)]["page"]
            await page.locator("#shell").evaluate("n => n.textContent='Changed shell'")
            assert (await browser.capture("fixture", source)).state_id == before.state_id
            shell = Action(
                source_id=source.source_id, kind="click", selector="#shell",
                expected_state_id=before.state_id, reason="Must never touch the host",
                requires_explicit_authorization=False,
            )
            with pytest.raises(EngineError) as error:
                await browser.act("fixture", source, shell, authorized=True)
            assert error.value.code == "prototype_shell_action_blocked"
            assert await page.locator("#shell").inner_text() == "Changed shell"
            click = shell.model_copy(update={"selector": "", "x": 0.45, "y": 0.385})
            after = await browser.act("fixture", source, click, authorized=False)
            assert after.locator["action_outcome"] == "state_changed"
            assert after.locator["operation_verified"]
            assert after.locator["change_signals"]["image"]
            assert after.locator["change_signals"]["url"] is change_url
            assert after.state_id != before.state_id
            noop = click.model_copy(update={"x": 0.05, "y": 0.05, "expected_state_id": after.state_id})
            same = await browser.act("fixture", source, noop, authorized=False)
            assert same.locator["action_outcome"] == "no_observed_change"
            assert not same.locator["operation_verified"]
            assert same.state_id == after.state_id
            scroll = Action(
                source_id=source.source_id, kind="scroll", scroll_y=400,
                expected_state_id=same.state_id, reason="Read more", requires_explicit_authorization=False,
            )
            scrolled = await browser.act("fixture", source, scroll, authorized=False)
            assert scrolled.locator["action_outcome"] == "state_changed"
            assert scrolled.locator["change_signals"]["image"]
        finally:
            await browser.close()

    try:
        asyncio.run(run())
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("target,allowed", [
    ("https://www.figma.com/proto/abc/Test?node-id=2-3", True),
    ("https://www.figma.com/proto/other/Test?node-id=2-3", False),
    ("https://www.figma.com/design/abc/Test?node-id=2-3", False),
    ("https://www.figma.com/oauth/mcp", False),
    ("https://other.example/proto/abc/Test", False),
])
def test_prototype_navigation_is_limited_to_the_submitted_file(target, allowed):
    assert prototype_navigation_allowed("https://www.figma.com/proto/abc/Test?node-id=1-2", target) is allowed


def test_uniform_padding_trim_retains_all_visible_content_and_coordinate_origin():
    pixels = Image.new("RGB", (1000, 1000), "black")
    draw = ImageDraw.Draw(pixels)
    draw.rectangle((300, 100, 699, 899), fill="red")
    draw.point((200, 700), fill="yellow")
    raw = io.BytesIO()
    pixels.save(raw, "PNG")
    cropped, region = BrowserAdapter._trim_canvas(raw.getvalue(), {
        "x": 48, "y": 60, "width": 1000, "height": 1000,
    })
    assert region == {"x": 240, "y": 152, "width": 516, "height": 816}
    result = Image.open(io.BytesIO(cropped))
    assert result.size == (516, 816)
    assert result.getpixel((8, 608)) == (255, 255, 0)
