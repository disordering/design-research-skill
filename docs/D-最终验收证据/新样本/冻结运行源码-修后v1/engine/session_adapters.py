"""Real browser/MCP adapters. Missing capabilities never fall back to mock."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib.util
import ipaddress
import json
import os
import re
import socket
import io
import math
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

from .errors import EngineError
from .config import load_reviewer_config
from .imaging import prepare_image
from .session_contracts import Action, SourceRecord, identifier
from .session_targets import (
    control_is_available,
    observed_control,
    target_label_matches,
)


# 读取控件关联的标签，单选框等没有 innerText 的元素也使用页面命名。
CONTROL_LABEL_JS = r"""node => {
    const ids=(node.getAttribute('aria-labelledby')||'').trim().split(/\s+/).filter(Boolean);
    const referenced=ids.map(id=>document.getElementById(id)?.textContent||'').join(' ').trim();
    const associated=Array.from(node.labels||[]).map(label=>{
        // 嵌套在 label 中的 select，其选项文字不属于字段名称。
        if(node.tagName==='SELECT'){
            const copy=label.cloneNode(true);
            copy.querySelectorAll('select').forEach(item=>item.remove());
            return copy.textContent||'';
        }
        return label.innerText||label.textContent||'';
    }).join(' ').trim();
    return (referenced||node.getAttribute('aria-label')||associated||node.innerText||
            node.getAttribute('placeholder')||node.name||'').trim().slice(0,200);
}"""


@dataclass
class Capture:
    content: str
    locator: dict[str, Any]
    state_id: str
    image: bytes | None = None
    controls: list[dict[str, Any]] = field(default_factory=list)
    partial: bool = False
    raw_content: str | None = None
    image_mime_type: str = "image/png"
    original_bytes: bytes | None = None
    original_mime_type: str = "application/octet-stream"


def figma_target(reference: str) -> tuple[str, str | None]:
    parsed = urlparse(reference)
    match = re.match(r"/(?:design|file|proto)/([A-Za-z0-9]+)/", parsed.path)
    if not match:
        raise EngineError("figma_url_invalid", "无法识别 Figma 文件链接。", status_code=422)
    branch = re.search(r"/branch/([A-Za-z0-9]+)(?:/|$)", parsed.path)
    file_key = branch[1] if branch else match[1]
    node = parse_qs(parsed.query).get("node-id", [None])[0]
    if node:
        node = node.replace("-", ":")
        if not re.fullmatch(r"\d+:\d+", node):
            raise EngineError("figma_node_invalid", "Figma 节点 ID 无效。", status_code=422)
    return file_key, node


async def validate_browser_url(reference: str, *, allow_local: bool = False) -> None:
    parsed = urlparse(reference)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise EngineError("unsafe_browser_url", "仅允许不含凭据的 HTTP(S) 链接。", status_code=422)
    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, parsed.port or 443)
    except OSError as exc:
        raise EngineError("browser_dns_failed", "目标域名无法解析。", status_code=502) from exc
    if not allow_local and any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise EngineError("private_network_blocked", "默认不访问本机/内网地址；测试环境需显式启用。", status_code=403)


def prototype_navigation_allowed(reference: str, target: str) -> bool:
    before, after = urlparse(reference), urlparse(target)
    if after.hostname != before.hostname:
        return False
    try:
        return after.path.startswith("/proto/") and figma_target(reference)[0] == figma_target(target)[0]
    except EngineError:
        return False


def _inside(rect: dict[str, Any], region: dict[str, Any]) -> bool:
    return (
        rect["width"] > 0 and rect["height"] > 0
        and rect["x"] >= region["x"] and rect["y"] >= region["y"]
        and rect["x"] + rect["width"] <= region["x"] + region["width"]
        and rect["y"] + rect["height"] <= region["y"] + region["height"]
    )


class BrowserAdapter:
    def __init__(self, *, allow_local: bool = False, headless: bool = True) -> None:
        self.allow_local = allow_local
        self.headless = headless
        self._playwright: Any = None
        self._browser: Any = None
        self._pages: dict[tuple[str, str], dict[str, Any]] = {}
        self._start_lock = asyncio.Lock()

    async def _start(self) -> None:
        async with self._start_lock:
            if self._browser is not None:
                return
            try:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=self.headless)
            except Exception as exc:
                if self._playwright:
                    await self._playwright.stop()
                    self._playwright = None
                raise EngineError(
                    "browser_unavailable",
                    "浏览器不可用；安装 requirements-session.txt 后执行 python -m playwright install chromium。",
                    status_code=503,
                ) from exc

    async def read(self, session_id: str, source: SourceRecord) -> Capture:
        await validate_browser_url(source.input.reference, allow_local=self.allow_local)
        await self._start()
        key = (session_id, source.source_id)
        fingerprint = hashlib.sha256(
            source.input.model_dump_json().encode("utf-8")
        ).hexdigest()
        prior = self._pages.get(key)
        if prior and (
            prior.get("source_fingerprint") != fingerprint
            or source.acquisition_status == "pending"
        ):
            await prior["context"].close()
            self._pages.pop(key, None)
        if key not in self._pages:
            context = await self._browser.new_context(
                viewport={"width": 1440, "height": 900},
                service_workers="block",
            )
            page = await context.new_page()
            state: dict[str, Any] = {
                "context": context, "page": page, "source": source,
                "source_fingerprint": fingerprint,
                "state_id": "", "allow_side_effects": False, "blocked_requests": [],
            }
            host = urlparse(source.input.reference).hostname

            async def route_request(route: Any) -> None:
                url = route.request.url
                try:
                    await validate_browser_url(url, allow_local=self.allow_local)
                    if route.request.is_navigation_request() and route.request.frame == page.main_frame:
                        if urlparse(url).hostname != host:
                            raise EngineError("navigation_scope_blocked", "跨域导航不在当前入口授权范围。", status_code=403)
                        if source.input.kind == "figma_prototype" and not prototype_navigation_allowed(source.input.reference, url):
                            raise EngineError("prototype_editor_blocked", "原型操作只限当前文件，不进入编辑器或其他文件。", status_code=403)
                    if (
                        source.input.kind == "website"
                        and route.request.method not in {"GET", "HEAD", "OPTIONS"}
                        and not state["allow_side_effects"]
                    ):
                        raise EngineError("request_authorization_needed", "非只读请求需要明确授权。", status_code=403)
                    await route.continue_()
                except (EngineError, OSError):
                    state["blocked_requests"].append({"method": route.request.method, "url": url.split("?")[0]})
                    await route.abort()

            await context.route("**/*", route_request)
            self._pages[key] = state
            try:
                response = await page.goto(source.input.reference, wait_until="domcontentloaded", timeout=30000)
                if response and response.status in {401, 403}:
                    raise EngineError("browser_access_denied", "入口要求登录或访问权限。", status_code=403)
                if response and response.status >= 400:
                    raise EngineError("browser_http_error", f"入口返回 HTTP {response.status}。", status_code=502)
                if source.input.kind == "figma_prototype":
                    try:
                        await page.wait_for_function(
                            "() => document.querySelector('canvas') || (document.body && document.body.innerText.trim().length > 0)",
                            timeout=15000,
                        )
                    except Exception:
                        pass
                    await page.wait_for_timeout(1000)
            except Exception as exc:
                await context.close()
                self._pages.pop(key, None)
                if isinstance(exc, EngineError):
                    raise
                raise EngineError("browser_navigation_failed", "入口加载失败或超时，未验证该路径。", status_code=502) from exc
        return await self.capture(session_id, source)

    @staticmethod
    async def _prototype_region(page: Any) -> dict[str, int] | None:
        regions = await page.locator("canvas").evaluate_all("""nodes => nodes.map(n => {
            const r=n.getBoundingClientRect();
            return {x:r.x,y:r.y,width:r.width,height:r.height,
                visible:getComputedStyle(n).visibility!=='hidden' && getComputedStyle(n).display!=='none'};
        }).filter(r=>r.visible && r.width>0 && r.height>0)""")
        viewport = page.viewport_size
        bounded = []
        for rect in regions:
            left, top = max(0, math.ceil(rect["x"])), max(0, math.ceil(rect["y"]))
            right = min(viewport["width"], math.floor(rect["x"] + rect["width"]))
            bottom = min(viewport["height"], math.floor(rect["y"] + rect["height"]))
            if right > left and bottom > top:
                bounded.append({"x": left, "y": top, "width": right - left, "height": bottom - top})
        return max(bounded, key=lambda r: r["width"] * r["height"], default=None)

    @staticmethod
    def _trim_canvas(image: bytes, region: dict[str, int]) -> tuple[bytes, dict[str, int]]:
        from PIL import Image, ImageChops
        pixels = Image.open(io.BytesIO(image)).convert("RGB")
        corners = [pixels.getpixel(point) for point in (
            (0, 0), (pixels.width - 1, 0), (0, pixels.height - 1), (pixels.width - 1, pixels.height - 1),
        )]
        if len(set(corners)) != 1:
            return image, region
        box = ImageChops.difference(pixels, Image.new("RGB", pixels.size, corners[0])).getbbox()
        if not box or box[2] - box[0] < 200 or box[3] - box[1] < 200:
            return image, region
        left, top = max(0, box[0] - 8), max(0, box[1] - 8)
        right, bottom = min(pixels.width, box[2] + 8), min(pixels.height, box[3] + 8)
        if (left, top, right, bottom) == (0, 0, pixels.width, pixels.height):
            return image, region
        # Trim only exact uniform padding; every non-background pixel is retained.
        output = io.BytesIO()
        pixels.crop((left, top, right, bottom)).save(output, "PNG")
        return output.getvalue(), {
            "x": region["x"] + left, "y": region["y"] + top,
            "width": right - left, "height": bottom - top,
        }

    @staticmethod
    def _bounded_accessibility(node: Any, *, limit: int = 300) -> dict[str, Any] | None:
        if not isinstance(node, dict):
            return None
        count = 0

        def visit(value: dict[str, Any], depth: int) -> dict[str, Any]:
            nonlocal count
            count += 1
            result = {
                key: value.get(key)
                for key in ("role", "name", "value", "disabled", "checked", "expanded", "pressed")
                if value.get(key) is not None
            }
            children = value.get("children")
            if depth < 6 and count < limit and isinstance(children, list):
                result["children"] = [
                    visit(child, depth + 1)
                    for child in children[:60]
                    if isinstance(child, dict) and count < limit
                ]
            elif isinstance(children, list) and children:
                result["children_omitted"] = len(children)
            return result

        return visit(node, 0)

    async def capture(self, session_id: str, source: SourceRecord) -> Capture:
        state = self._pages.get((session_id, source.source_id))
        if not state:
            return await self.read(session_id, source)
        page = state["page"]
        try:
            text = (await page.locator("body").inner_text(timeout=10000))[:30000]
            controls = await page.evaluate("""() => {
                const controlLabel = __CONTROL_LABEL__;
                const parseColor = value => {
                    const m=String(value||'').match(/rgba?\\(([^)]+)\\)/);
                    if(!m) return null;
                    const p=m[1].split(',').map(v=>parseFloat(v.trim()));
                    return {r:p[0]||0,g:p[1]||0,b:p[2]||0,a:p.length>3?p[3]:1};
                };
                const channel = value => {
                    const v=value/255;
                    return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);
                };
                const luminance = color =>
                    0.2126*channel(color.r)+0.7152*channel(color.g)+0.0722*channel(color.b);
                const background = node => {
                    let current=node;
                    while(current){
                        const color=parseColor(getComputedStyle(current).backgroundColor);
                        if(color&&color.a>0.1) return color;
                        current=current.parentElement;
                    }
                    return {r:255,g:255,b:255,a:1};
                };
                const contrast = (foreground,back) => {
                    if(!foreground) return null;
                    const a=luminance(foreground),b=luminance(back);
                    return Math.round(((Math.max(a,b)+0.05)/(Math.min(a,b)+0.05))*100)/100;
                };
                const ancestorPath = node => {
                    const parts=[];
                    let current=node.parentElement;
                    while(current&&parts.length<5){
                        parts.push(current.tagName.toLowerCase()+
                            (current.id?'#'+current.id:'')+
                            (current.getAttribute('data-testid')?'[data-testid="'+current.getAttribute('data-testid')+'"]':''));
                        current=current.parentElement;
                    }
                    return parts.join('>');
                };
                const nodes = [...document.querySelectorAll('a,button,input,textarea,select,[role="button"]')]
                    .filter(n => { const r=n.getBoundingClientRect(),s=getComputedStyle(n);
                        return n.type!=='hidden' && r.width>0 && r.height>0
                            && s.display!=='none' && s.visibility!=='hidden'; });
                return nodes.slice(0,100).map((n,i) => {
                    n.setAttribute('data-review-control', String(i));
                    const r=n.getBoundingClientRect();
                    const s=getComputedStyle(n);
                    const foreground=parseColor(s.color), back=background(n);
                    return {selector:'[data-review-control="'+i+'"]',
                        label:controlLabel(n),
                        tag:n.tagName.toLowerCase(),type:n.type||'',
                        disabled:!!n.disabled||(n.tagName==='SELECT'&&n.matches(':disabled')),
                        role:n.getAttribute('role')||n.tagName.toLowerCase(),
                        ariaLabel:n.getAttribute('aria-label')||'',
                        domId:n.id||'',
                        name:n.getAttribute('name')||'',
                        testId:n.getAttribute('data-testid')||n.getAttribute('data-test-id')||'',
                        ancestorPath:ancestorPath(n),
                        value:n.type==='password'?'':String(n.value||'').slice(0,500),
                        ...(n.tagName==='SELECT'?{
                            multiple:!!n.multiple,
                            optionCount:n.options.length,
                            optionsTruncated:n.options.length>200,
                            options:Array.from(n.options).slice(0,200).map(o=>({
                                label:o.label,value:o.value,selected:!!o.selected,
                                disabled:!!o.disabled||!!o.closest('optgroup')?.disabled||n.matches(':disabled'),
                                optgroup:o.closest('optgroup')?.label||'',
                            })),
                        }:{}),
                        checked:!!n.checked,ariaSelected:n.getAttribute('aria-selected'),
                        ariaPressed:n.getAttribute('aria-pressed'),
                        ariaExpanded:n.getAttribute('aria-expanded'),
                        title:n.getAttribute('title')||'',
                        fontSizePx:parseFloat(s.fontSize)||null,
                        fontWeight:s.fontWeight,
                        color:s.color,
                        backgroundColor:s.backgroundColor,
                        contrastRatio:contrast(foreground,back),
                        opacity:parseFloat(s.opacity),
                        textDecoration:s.textDecorationLine,
                        visibility:s.visibility,
                        x:r.x,y:r.y,width:r.width,height:r.height};
                });
            }""".replace("__CONTROL_LABEL__", CONTROL_LABEL_JS))
            viewport = page.viewport_size
            region = {"x": 0, "y": 0, **viewport}
            prototype = source.input.kind == "figma_prototype"
            canvas = await self._prototype_region(page) if prototype else None
            if canvas:
                region = canvas
                controls = [control for control in controls if _inside(control, canvas)]
                text = (
                    "Figma 可交互原型（不是生产系统）。画面仅包含原型画布，未取得产品 DOM 文本，"
                    "须依据本次截图判断。点击坐标 x/y 是相对此截图的 [0,1] 比例，不是屏幕像素。"
                )
            elif prototype:
                controls = []
                text = "原型画布尚未出现。Figma 外壳的登录/菜单/评论不属于被评审产品，不能据此判产品内容。"
            accessibility = None
            if not prototype:
                try:
                    accessibility = self._bounded_accessibility(
                        await page.accessibility.snapshot(interesting_only=True),
                    )
                except Exception:
                    accessibility = None
                if accessibility is None:
                    accessibility = {
                        "role": "document",
                        "name": await page.title(),
                        "source": "dom_control_fallback",
                        "children": [
                            {
                                "role": control.get("role") or control.get("tag"),
                                "name": control.get("ariaLabel") or control.get("label"),
                                "pressed": control.get("ariaPressed"),
                                "expanded": control.get("ariaExpanded"),
                                "checked": control.get("checked"),
                            }
                            for control in controls[:80]
                        ],
                    }
            image = await page.screenshot(
                type="png", full_page=False, clip=region, timeout=15000,
                animations="disabled", caret="hide",
            )
            from PIL import Image
            pixels = Image.open(io.BytesIO(image)).convert("L")
            blank = pixels.getextrema()
            empty_render = not text.strip() and not controls and blank[1] - blank[0] < 2
            if prototype:
                dominant = max(pixels.histogram()) / (pixels.width * pixels.height)
                empty_render = empty_render or not canvas or dominant > 0.98
            if empty_render:
                text = "当前画面近乎单色，可能空白或仍在加载；DOM 文字不证明原型已渲染，也不能据此判断产品无内容。请继续观察或补充访问条件。\n" + text
            if canvas and not empty_render:
                image, region = self._trim_canvas(image, region)
                pixels = Image.open(io.BytesIO(image)).convert("L")
            state_id = hashlib.sha256((page.url + text + json.dumps(controls)).encode() + image).hexdigest()[:24]
            state["state_id"] = state_id
            return Capture(
                content=text or "画面没有可提取 DOM 文字，请检查截图，不要据此认定页面空白。",
                locator={
                    "url": page.url, "title": await page.title(),
                    "viewport": viewport,
                    "image_geometry": {"width": pixels.width, "height": pixels.height, "region": region},
                    "prototype_canvas": canvas,
                    "accessibility": accessibility,
                    "environment_session": session_id, "provided_version": source.input.version,
                    "render_state": "loading_or_sparse" if empty_render else "captured",
                    "blocked_requests": state["blocked_requests"][-10:],
                },
                state_id=state_id, image=image, controls=controls,
                partial=bool(state["blocked_requests"]) or empty_render,
            )
        except Exception as exc:
            raise EngineError("browser_capture_failed", "未能取得当前画面和状态。", status_code=502) from exc

    async def action_needs_authorization(self, session_id: str, source: SourceRecord, action: Action) -> bool:
        if action.kind in {"observe"}:
            return action.requires_explicit_authorization
        if source.input.kind == "figma_prototype":
            if action.kind == "fill" and action.selector:
                state = self._pages.get((session_id, source.source_id))
                if state and (await state["page"].locator(action.selector).first.get_attribute("type")) == "password":
                    return True
            return action.requires_explicit_authorization
        if action.kind in {"click", "select"}:
            if not action.selector:
                return True
            state = self._pages.get((session_id, source.source_id))
            if not state:
                return True
            target = state["page"].locator(action.selector).first
            try:
                if await target.count() == 0:
                    return True
                label_parts = [
                    await target.evaluate(CONTROL_LABEL_JS),
                    await target.inner_text(timeout=5000),
                    await target.get_attribute("aria-label"),
                    await target.get_attribute("title"),
                    await target.get_attribute("name"),
                    await target.get_attribute("data-testid"),
                    await target.get_attribute("value"),
                ]
                target_type = await target.get_attribute("type") or ""
                label = " ".join(part for part in label_parts if part)
                if re.search(
                    r"删除|清空|支付|购买|领取|发送|提交|发布|"
                    r"delete|purchase|pay|submit|send",
                    label,
                    re.I,
                ):
                    return True
                if target_type.lower() == "submit":
                    return True
            except Exception:
                return True
        if action.kind == "fill" and action.selector:
            state = self._pages.get((session_id, source.source_id))
            if state and (await state["page"].locator(action.selector).first.get_attribute("type")) == "password":
                return True
        return action.requires_explicit_authorization

    async def act(
        self, session_id: str, source: SourceRecord, action: Action, *, authorized: bool,
    ) -> Capture:
        current = await self.capture(session_id, source)
        if action.kind != "observe" and current.state_id != action.expected_state_id:
            raise EngineError("browser_state_changed", "外部页面状态已变，需重新观察和规划，未执行旧动作。", status_code=409)
        if (
            source.input.kind != "figma_prototype"
            and action.kind in {"click", "fill", "select"}
            and action.selector
        ):
            control = observed_control(
                current.controls,
                action.selector,
            )
            if control is None:
                raise EngineError(
                    "action_target_not_observed",
                    "selector 不在当前状态已观察控件中，未执行动作。",
                    status_code=409,
                )
            if not control_is_available(control):
                raise EngineError(
                    "action_target_unavailable",
                    "目标控件当前不可用或已隐藏，未执行动作。",
                    status_code=409,
                )
            matches, actual_target = target_label_matches(
                action.target_label,
                control,
            )
            if not matches:
                raise EngineError(
                    "action_target_mismatch",
                    f"模型目标 {action.target_label!r} 与 selector 实际目标 "
                    f"{actual_target!r} 不一致，未执行动作。",
                    status_code=409,
                )
            action.target_label = action.target_label or actual_target
            action.observed_target = actual_target
        state = self._pages[(session_id, source.source_id)]
        page = state["page"]
        state["allow_side_effects"] = authorized
        try:
            if source.input.kind == "figma_prototype" and action.kind in {"click", "fill", "select", "scroll"}:
                canvas = current.locator["prototype_canvas"]
                if not canvas or current.partial:
                    raise EngineError("prototype_not_ready", "原型画布未可靠呈现，请先观察，不能点外壳。", status_code=409)
                if action.selector:
                    target = page.locator(action.selector).first
                    rect = await target.bounding_box()
                    if not rect or not _inside(rect, canvas) or action.selector not in {c["selector"] for c in current.controls}:
                        raise EngineError("prototype_shell_action_blocked", "只允许已观察到的原型内控件，不操作 Figma 外壳。", status_code=403)
                    control = observed_control(
                        current.controls,
                        action.selector,
                    )
                    if control is None or not control_is_available(control):
                        raise EngineError(
                            "action_target_unavailable",
                            "目标原型控件当前不可用或已隐藏，未执行动作。",
                            status_code=409,
                        )
                    matches, actual_target = target_label_matches(
                        action.target_label,
                        control,
                    )
                    if not matches:
                        raise EngineError(
                            "action_target_mismatch",
                            f"模型目标 {action.target_label!r} 与 selector 实际目标 "
                            f"{actual_target!r} 不一致，未执行动作。",
                            status_code=409,
                        )
                    action.target_label = action.target_label or actual_target
                    action.observed_target = actual_target
            if action.kind == "observe":
                await page.wait_for_timeout(1500)
                if authorized and state["blocked_requests"]:
                    state["blocked_requests"].clear()
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
            elif action.kind == "navigate":
                await validate_browser_url(action.url, allow_local=self.allow_local)
                if urlparse(action.url).hostname != urlparse(source.input.reference).hostname:
                    raise EngineError("navigation_scope_blocked", "跨域链接须作为新材料提交。", status_code=403)
                if source.input.kind == "figma_prototype" and not prototype_navigation_allowed(source.input.reference, action.url):
                    raise EngineError("prototype_editor_blocked", "原型操作不能切入编辑器或其他文件。", status_code=403)
                await page.goto(action.url, wait_until="domcontentloaded", timeout=30000)
            elif action.kind == "back":
                await page.go_back(wait_until="domcontentloaded", timeout=30000)
            elif action.kind == "fill":
                if not action.selector:
                    raise EngineError("action_target_missing", "填写动作需要控件定位。", status_code=422)
                await page.locator(action.selector).first.fill(action.value, timeout=10000)
            elif action.kind == "select":
                if not action.selector:
                    raise EngineError("action_target_missing", "下拉选择需要已观察控件定位。", status_code=422)
                control = observed_control(current.controls, action.selector)
                if control is None:
                    raise EngineError("action_target_not_observed", "下拉控件不在当前已观察状态中。", status_code=409)
                if control.get("tag") != "select":
                    raise EngineError("select_target_invalid", "select 动作只支持原生下拉控件。", status_code=422)
                if control.get("multiple"):
                    raise EngineError("select_multiple_unsupported", "当前选择动作不支持多选列表。", status_code=422)
                if control.get("optionsTruncated"):
                    raise EngineError("select_options_incomplete", "当前选项清单超过观察上限，不能确认完整选项范围，未执行选择。", status_code=409)
                options = [option for option in control.get("options", []) if option.get("value") == action.value]
                if not options:
                    raise EngineError("select_option_not_observed", "value 不在当前已观察选项中，未执行选择。", status_code=409)
                if len(options) != 1:
                    raise EngineError("select_option_ambiguous", "多个选项使用同一 value，无法唯一定位选择。", status_code=409)
                if options[0].get("disabled"):
                    raise EngineError("select_option_unavailable", "目标选项或所属选项组已禁用，未执行选择。", status_code=409)
                # 使用浏览器原生选择，让页面原有 input/change 处理继续执行。
                await page.locator(action.selector).first.select_option(value=action.value, timeout=10000)
            elif action.kind == "scroll":
                region = current.locator["image_geometry"]["region"]
                await page.mouse.move(
                    region["x"] + (action.x if action.x is not None else 0.5) * max(region["width"] - 1, 0),
                    region["y"] + (action.y if action.y is not None else 0.5) * max(region["height"] - 1, 0),
                )
                await page.mouse.wheel(action.scroll_x, action.scroll_y)
            elif action.kind == "click":
                if action.selector:
                    await page.locator(action.selector).first.click(timeout=10000)
                elif action.x is not None and action.y is not None:
                    region = current.locator["image_geometry"]["region"]
                    await page.mouse.click(
                        region["x"] + action.x * max(region["width"] - 1, 0),
                        region["y"] + action.y * max(region["height"] - 1, 0),
                    )
                else:
                    raise EngineError("action_target_missing", "点击动作需要控件或坐标。", status_code=422)
            else:
                raise EngineError("browser_action_unsupported", "浏览器不支持该动作。", status_code=422)
            await page.wait_for_timeout(400)
            captured = await self.capture(session_id, source)
            if source.input.kind == "figma_prototype" and action.kind != "observe":
                # Canvas transitions run outside CSS animation control; observe until stable.
                stable = False
                for index in range(8):
                    await page.wait_for_timeout(200)
                    next_capture = await self.capture(session_id, source)
                    stable = next_capture.state_id == captured.state_id
                    captured = next_capture
                    if stable and index >= 3:
                        break
                if not stable:
                    captured.partial = True
                    captured.locator["render_state"] = "unstable_after_action"
            changed = captured.state_id != current.state_id
            outcome = (
                "observation_incomplete" if captured.partial else
                "read" if action.kind == "observe" else
                "state_changed" if changed else "no_observed_change"
            )
            captured.locator["action_outcome"] = outcome
            captured.locator["operation_verified"] = outcome == "state_changed"
            captured.locator["change_signals"] = {
                "url": captured.locator["url"] != current.locator["url"],
                "image": captured.image != current.image,
                "controls": captured.controls != current.controls,
            }
            return captured
        except EngineError:
            raise
        except Exception as exc:
            # A timed-out click may have taken effect; never retry the click automatically.
            raise EngineError("browser_action_failed", "动作失败或超时；请先重新观察，不能自动重复点击。", status_code=502) from exc
        finally:
            state["allow_side_effects"] = False

    async def close_session(self, session_id: str) -> None:
        for key in [k for k in self._pages if k[0] == session_id]:
            await self._pages.pop(key)["context"].close()

    async def close(self) -> None:
        for state in self._pages.values():
            await state["context"].close()
        self._pages.clear()
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None


@asynccontextmanager
async def mcp_transport(endpoint: str, headers: dict[str, str], *, auth=None):
    from mcp.client.streamable_http import streamable_http_client, create_mcp_http_client
    async with create_mcp_http_client(headers=headers, auth=auth) as http_client:
        async with streamable_http_client(endpoint, http_client=http_client) as streams:
            yield streams


class FigmaMCPAdapter:
    def __init__(
        self, endpoint: str = "", token: str = "", *,
        snapshot_root: Path | str | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.token = token
        self.snapshot_root = Path(snapshot_root) if snapshot_root else None
        self._states: dict[tuple[str, str], Capture] = {}
        self._known_nodes: dict[tuple[str, str], set[str]] = {}

    @staticmethod
    def _same_source(capture: Capture, source: SourceRecord) -> bool:
        file_key, root_node = figma_target(source.input.reference)
        locator = capture.locator
        return (
            locator.get("requested_file_key") == file_key
            and locator.get("requested_node_id") == root_node
            and locator.get("provided_version") == source.input.version
            and locator.get("snapshot_id", "") == source.input.figma_snapshot_id
        )

    def _remember_capture(self, session_id: str, source: SourceRecord, capture: Capture) -> Capture:
        cache_key = (session_id, source.source_id)
        prior = self._states.get(cache_key)
        if prior is None or not self._same_source(prior, source):
            self._known_nodes[cache_key] = set()
        self._known_nodes[cache_key].update(capture.locator["node_ids"])
        self._states[cache_key] = capture
        return capture

    @staticmethod
    def _snapshot_path(directory: Path, *parts: str) -> Path:
        path = directory.joinpath(*parts)
        # 快照内的节点、截图和清单都必须来自所指定的归档位置。
        if path.resolve() != path:
            raise EngineError("figma_snapshot_invalid", "快照路径重定向到了其他归档位置。", status_code=422)
        return path

    @staticmethod
    def _arguments(tool: Any, arguments: dict[str, Any]) -> dict[str, Any]:
        properties = tool.input_schema.get("properties")
        if properties is None:
            return arguments
        return {key: value for key, value in arguments.items() if key in properties}

    @staticmethod
    def _bounded_json(data: dict[str, Any], limit: int = 40000) -> str:
        """Serialize within the evidence limit without cutting through JSON."""
        encoded = json.dumps(data, ensure_ascii=False)
        if len(encoded) <= limit:
            return encoded
        bounded = dict(data)
        bounded["content_truncated"] = True
        bounded["metadata_excerpt"] = str(bounded.get("metadata_excerpt", ""))[:2000]
        for field in ("visible_text", "hidden_text", "inspection_targets", "arrow_annotations"):
            items = bounded.get(field)
            if not isinstance(items, list):
                continue
            while items and len(json.dumps(bounded, ensure_ascii=False)) > limit:
                items.pop()
                bounded[f"{field}_omitted"] = int(bounded.get(f"{field}_omitted", 0)) + 1
        encoded = json.dumps(bounded, ensure_ascii=False)
        if len(encoded) > limit:
            raise EngineError(
                "figma_content_too_large",
                "Figma 元数据在保留节点索引后仍超过证据上限，未写入截断的无效 JSON。",
                status_code=422,
            )
        return encoded

    @staticmethod
    def _structure_index(text: str) -> tuple[ElementTree.Element | None, list[dict[str, Any]], list[dict[str, Any]]]:
        try:
            start, end = text.index("<"), text.rindex(">") + 1
            tree = ElementTree.fromstring(text[start:end])
        except (ValueError, ElementTree.ParseError):
            return None, [], []
        texts: list[dict[str, Any]] = []
        visual: list[dict[str, Any]] = []

        def geometry(element: ElementTree.Element) -> dict[str, float]:
            result = {}
            for key in ("x", "y", "width", "height"):
                try:
                    result[key] = round(float(element.attrib.get(key, "0")), 2)
                except ValueError:
                    result[key] = 0.0
            return result

        def walk(
            element: ElementTree.Element, depth: int, parents: list[str],
            offset_x: float = 0.0, offset_y: float = 0.0,
        ) -> None:
            for child in element:
                node_id = child.attrib.get("id", "")
                name = child.attrib.get("name", "")
                rect = geometry(child)
                absolute = {
                    **rect,
                    "x": round(offset_x + rect["x"], 2),
                    "y": round(offset_y + rect["y"], 2),
                }
                hidden = child.attrib.get("hidden", "").lower() == "true"
                slide_like = bool(re.match(
                    r"slide\s*16\s*:\s*9", name, flags=re.IGNORECASE,
                ))
                annotation = bool(
                    child.tag in {"vector", "line", "connector"}
                    and re.search(r"arrow|connector|flow|link|箭头|连线|流程", name, flags=re.IGNORECASE)
                )
                if child.tag == "text" and name.strip():
                    texts.append({
                        "node_id": node_id, "text": name.strip(), "hidden": hidden,
                        "depth": depth, "parents": parents[-4:], **absolute,
                    })
                elif annotation and node_id:
                    visual.append({
                        "node_id": node_id, "name": name or child.tag, "type": child.tag,
                        "hidden": hidden, "container": bool(len(child)), "screen_like": False,
                        "slide_like": False,
                        "annotation": "arrow",
                        "direction": (
                            "horizontal" if rect["width"] >= rect["height"] else "vertical"
                        ),
                        "depth": depth, "parents": parents[-4:], **absolute,
                    })
                elif (
                    node_id and (
                        (
                            rect["width"] >= 240 and rect["height"] >= 160
                            and rect["width"] * rect["height"] >= 40_000
                        )
                        or (
                            rect["width"] >= 100 and rect["height"] >= 40
                            and rect["width"] * rect["height"] >= 4_000
                            and re.search(
                                r"image|截图|界面|流程|页面|screen|dialog|modal|图\s*\d|列表",
                                name, flags=re.IGNORECASE,
                            )
                        )
                    )
                ):
                    named_screen = bool(re.search(
                        r"(?:^|\s)image(?:\s|$)|截图|界面|流程|页面|screen|dialog|modal|图\s*\d|列表",
                        name, flags=re.IGNORECASE,
                    ))
                    large_leaf_frame = (
                        child.tag in {"frame", "section"}
                        and not len(child)
                        and depth <= 2
                        and rect["width"] >= 1200
                        and rect["height"] >= 500
                    )
                    screen_like = slide_like or named_screen or large_leaf_frame
                    visual.append({
                        "node_id": node_id, "name": name or child.tag, "type": child.tag,
                        "hidden": hidden, "container": bool(len(child)), "screen_like": screen_like,
                        "slide_like": slide_like,
                        "annotation": "",
                        "depth": depth, "parents": parents[-4:], **absolute,
                    })
                next_parents = [*parents, name] if name else parents
                walk(
                    child, depth + 1, next_parents,
                    offset_x + rect["x"], offset_y + rect["y"],
                )

        walk(tree, 0, [])
        visual.sort(key=lambda item: (
            item["hidden"], not item["slide_like"], not item["screen_like"],
            item["container"], item["y"], item["x"],
            -item["width"] * item["height"],
        ))
        targets = [
            item for item in visual
            if item["screen_like"] and (not item["container"] or item["slide_like"])
        ]
        for item in visual:
            if item["annotation"] != "arrow":
                continue
            center_x = item["x"] + item["width"] / 2
            center_y = item["y"] + item["height"] / 2
            item["nearby_targets"] = [
                target["node_id"] for target in targets
                if target["x"] <= center_x <= target["x"] + target["width"]
                and target["y"] <= center_y <= target["y"] + target["height"]
            ][:10]
        return tree, texts, visual

    async def _read_snapshot(
        self, session_id: str, source: SourceRecord, node_id: str | None,
    ) -> Capture:
        if not self.snapshot_root:
            raise EngineError(
                "figma_snapshot_not_configured",
                "请求指定了 Figma 快照，但后端没有配置快照目录。",
                status_code=503,
            )
        key, original_node = figma_target(source.input.reference)
        target = node_id or original_node
        if not target or not re.fullmatch(r"\d+:\d+", target):
            raise EngineError("figma_node_invalid", "Figma 快照必须指定有效节点 ID。", status_code=422)
        snapshot_id = source.input.figma_snapshot_id
        directory = self._snapshot_path(self.snapshot_root.resolve(), snapshot_id)
        if directory.parent != self.snapshot_root.resolve():
            raise EngineError("figma_snapshot_invalid", "Figma 快照路径无效。", status_code=422)
        try:
            manifest = json.loads(self._snapshot_path(directory, "manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise EngineError(
                "figma_snapshot_missing",
                f"找不到 Figma 快照清单：{snapshot_id}。",
                status_code=503,
            ) from exc
        if not isinstance(manifest, dict) or not manifest.get("file_key"):
            raise EngineError("figma_snapshot_invalid", "快照清单缺少文件键，无法核对来源。", status_code=422)
        if manifest["file_key"] != key:
            raise EngineError("figma_snapshot_file_mismatch", "快照文件键与请求的 Figma 文件不符。", status_code=422)
        nodes = manifest.get("nodes")
        if not isinstance(nodes, dict):
            raise EngineError("figma_snapshot_invalid", "快照清单缺少节点索引。", status_code=422)
        if target not in nodes:
            raise EngineError("figma_snapshot_node_missing", f"快照清单未登记节点 {target}。", status_code=422)
        node_meta = nodes[target]
        if not isinstance(node_meta, dict):
            raise EngineError("figma_snapshot_invalid", f"节点 {target} 的清单记录无效。", status_code=422)
        node_name = target.replace(":", "-")
        metadata_path = self._snapshot_path(directory, "metadata", f"{node_name}.xml")
        image_path = self._snapshot_path(directory, "images", f"{node_name}.png")
        raw_text = None
        tree = None
        texts = []
        visual_nodes = []
        node_attributes = {"id": target}
        node_attributes.update({field: node_meta[field] for field in ("name", "width", "height") if field in node_meta})
        if metadata_path.is_file():
            raw_text = metadata_path.read_text(encoding="utf-8")
            tree, texts, visual_nodes = self._structure_index(raw_text)
            if tree is None or tree.get("id") != target:
                raise EngineError("figma_snapshot_invalid", f"快照元数据无法对应节点 {target}。", status_code=422)
            node_attributes = tree.attrib
        image = image_path.read_bytes() if image_path.is_file() else None
        if tree is None and not image:
            raise EngineError("figma_snapshot_evidence_missing", f"节点 {target} 缺少归档元数据和截图。", status_code=422)
        inspection_targets = [
            {
                "node_id": node["node_id"], "name": node["name"], "type": node["type"],
                "hidden": node["hidden"], "container": node["container"],
                "screen_like": node["screen_like"],
                "slide_like": node["slide_like"],
                **{field: node[field] for field in ("x", "y", "width", "height")},
            }
            for node in visual_nodes[:80]
        ]
        arrows = [node for node in visual_nodes if node["annotation"] == "arrow"]
        visible_texts = [node for node in texts if not node["hidden"]]
        hidden_texts = [node for node in texts if node["hidden"]]
        content_data = {
            "file_scope": "verified_snapshot",
            "scope_note": "已核对快照文件键与节点。截图与元数据的读取状态分别记录。",
            "node": node_attributes,
            "top_level_nodes": [
                dict(node.attrib) for node in tree if node.tag in {"frame", "section", "canvas"}
            ] if tree is not None else [],
            "visible_text": visible_texts[:250],
            "hidden_text": hidden_texts[:80],
            "inspection_targets": inspection_targets,
            "arrow_annotations": arrows,
            "reading_note": (
                "text 节点名称是设计材料原文；局部截图 evidence 是独立 nodeId 的真实画面。"
                "箭头仅表示画布几何连线，不直接断言交互跳转。"
            ),
            "snapshot_id": snapshot_id,
        }
        screenshot_width = screenshot_height = None
        if image:
            from PIL import Image
            try:
                with Image.open(io.BytesIO(image)) as pixels:
                    screenshot_width, screenshot_height = pixels.size
                    pixels.verify()
            except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
                raise EngineError("figma_snapshot_invalid", f"节点 {target} 的归档截图无效。", status_code=422) from exc
        state_text = raw_text if raw_text is not None else json.dumps(node_attributes, sort_keys=True)
        state_id = hashlib.sha256(state_text.encode() + (image or b"")).hexdigest()[:24]
        capture = Capture(
            content=self._bounded_json(content_data),
            controls=[
                {
                    "node_id": node["node_id"], "name": node["name"], "kind": node["type"],
                    "hidden": node["hidden"], "container": node["container"],
                    "screen_like": node["screen_like"], "annotation": node["annotation"],
                    "slide_like": node["slide_like"],
                    "direction": node.get("direction"),
                    "nearby_targets": node.get("nearby_targets", []),
                    "x": node["x"], "y": node["y"],
                    "width": node["width"], "height": node["height"],
                }
                for node in visual_nodes[:80]
            ],
            locator={
                "file_key": manifest["file_key"],
                "requested_file_key": key,
                "file_identity_verified": True,
                "requested_node_id": original_node,
                "provided_version": source.input.version,
                "node_id": target,
                "node_ids": list(dict.fromkeys(
                    node.get("id") for node in tree.iter() if re.fullmatch(r"\d+:\d+", node.get("id", ""))
                )) if tree is not None else [target],
                "metadata_status": "captured" if tree is not None else "unavailable",
                "visible_text_ids": [node["node_id"] for node in visible_texts[:250]],
                "hidden_text_ids": [node["node_id"] for node in hidden_texts[:80]],
                "inspection_targets": inspection_targets,
                "arrow_annotations": arrows,
                "screenshot_width": screenshot_width,
                "screenshot_height": screenshot_height,
                "image_status": "captured" if image else "unavailable",
                "source_mode": "prefetched_figma_snapshot",
                "snapshot_id": snapshot_id,
                "snapshot_captured_at": manifest.get("captured_at"),
                "file_scope": "verified_snapshot",
            },
            state_id=state_id,
            image=image,
            partial=not image,
            raw_content=raw_text,
        )
        return self._remember_capture(session_id, source, capture)

    async def read(self, session_id: str, source: SourceRecord, node_id: str | None = None) -> Capture:
        if source.input.figma_snapshot_id:
            return await self._read_snapshot(session_id, source, node_id)
        if not self.endpoint:
            raise EngineError("figma_mcp_not_configured", "后端未配置 Figma MCP 地址与授权；当前聊天的连接不能自动继承。", status_code=503)
        key, original_node = figma_target(source.input.reference)
        target = node_id or original_node
        try:
            from mcp import ClientSession
            headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
            auth = None
            if not self.token and urlparse(self.endpoint).hostname not in {"localhost", "127.0.0.1", "::1"}:
                from .figma_auth import OAuthStorage, oauth_provider
                storage = OAuthStorage(self.endpoint)
                if await storage.get_tokens() is None:
                    raise EngineError(
                        "figma_mcp_authorization_required",
                        "后端需要独立 Figma 授权，请执行 python -m engine figma-login。", status_code=503,
                    )
                auth = oauth_provider(self.endpoint, storage)
            async with asyncio.timeout(50):
                async with mcp_transport(self.endpoint, headers, auth=auth) as transport:
                    async with ClientSession(transport[0], transport[1]) as client:
                        await client.initialize()
                        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
                        session_args: dict[str, Any] = {}
                        if "create_session" in tools:
                            created = await client.call_tool("create_session", {
                                "fileKey": key, "description": "只读方案评审，读取节点与画面，不修改设计。",
                            })
                            text = self._text(created)
                            try:
                                data = getattr(created, "structured_content", None) or json.loads(text)
                                session_args["sessionId"] = data["sessionId"]
                            except (ValueError, KeyError):
                                raise EngineError("figma_mcp_session_failed", "MCP 未返回有效文件会话。", status_code=502)
                        if "get_metadata" not in tools:
                            raise EngineError("figma_mcp_tool_missing", "连接未提供 get_metadata。", status_code=503)
                        args = {"fileKey": key, **session_args}
                        if target:
                            args["nodeId"] = target
                        file_targeted = "fileKey" in tools["get_metadata"].input_schema.get("properties", {})
                        metadata = await client.call_tool(
                            "get_metadata", self._arguments(tools["get_metadata"], args),
                        )
                        if getattr(metadata, "is_error", False):
                            raise EngineError("figma_metadata_failed", "Figma 节点读取失败或无权限。", status_code=403)
                        text = self._text(metadata)
                        top_nodes = []
                        texts = []
                        visual_nodes = []
                        page_overview = False
                        tree, texts, visual_nodes = self._structure_index(text)
                        try:
                            if tree is None:
                                raise ElementTree.ParseError("metadata is not XML")
                            page_overview = tree.tag == "canvas"
                            top_nodes = [dict(node.attrib) for node in tree if node.tag in {"frame", "section", "canvas"}][:100]
                        except ElementTree.ParseError:
                            pass
                        image = None
                        if target and not page_overview and "get_screenshot" in tools:
                            shot_args = {"fileKey": key, "nodeId": target, **session_args}
                            properties = tools["get_screenshot"].input_schema.get("properties", {})
                            if "maxDimension" in properties:
                                shot_args["maxDimension"] = 1600
                            shot = await client.call_tool(
                                "get_screenshot", self._arguments(tools["get_screenshot"], shot_args),
                            )
                            if not getattr(shot, "is_error", False):
                                image = await self._image(shot)
                        screenshot_width = screenshot_height = None
                        if image:
                            from PIL import Image
                            with Image.open(io.BytesIO(image)) as pixels:
                                screenshot_width, screenshot_height = pixels.size
                        inspection_targets = [
                            {
                                "node_id": node["node_id"], "name": node["name"], "type": node["type"],
                                "hidden": node["hidden"], "container": node["container"],
                                "screen_like": node["screen_like"],
                                "slide_like": node["slide_like"],
                                **{key: node[key] for key in ("x", "y", "width", "height")},
                            }
                            for node in visual_nodes[:80]
                        ]
                        arrow_annotations = [
                            node for node in visual_nodes if node["annotation"] == "arrow"
                        ]
                        visible_texts = [node for node in texts if not node["hidden"]]
                        hidden_texts = [node for node in texts if node["hidden"]]
                        omitted_texts = max(0, len(texts) - 250)
                        omitted_targets = max(0, len(visual_nodes) - 80)
                        content_data = {
                                "file_scope": "requested_file" if file_targeted else "active_desktop_document",
                                "scope_note": "" if file_targeted else "桌面 MCP 不接受 fileKey；请保持目标设计文件在桌面端打开，文件身份未由 MCP 验证。",
                                "node": tree.attrib if tree is not None else {},
                                "top_level_nodes": top_nodes,
                                "visible_text": visible_texts[:250],
                                "hidden_text": hidden_texts[:80],
                                "inspection_targets": inspection_targets,
                                "arrow_annotations": arrow_annotations,
                                "text_nodes_omitted": omitted_texts,
                                "visual_targets_omitted": omitted_targets,
                                "reading_note": (
                                    "text节点名称是设计材料原文；hidden文本不属于当前可见方案。"
                                    "长画板/流程总图的文字可能过小，可对inspection_targets中的node_id继续inspect_node取得局部画面。"
                                ),
                                "metadata_excerpt": text[:12000],
                        }
                        capture = Capture(
                            content=self._bounded_json(content_data),
                            controls=[
                                {
                                    "node_id": node["node_id"], "name": node["name"], "kind": node["type"],
                                    "hidden": node["hidden"], "container": node["container"],
                                    "screen_like": node["screen_like"],
                                    "slide_like": node["slide_like"],
                                    "annotation": node["annotation"],
                                    "direction": node.get("direction"),
                                    "nearby_targets": node.get("nearby_targets", []),
                                    "x": node["x"], "y": node["y"],
                                    "width": node["width"], "height": node["height"],
                                }
                                for node in visual_nodes[:80]
                            ],
                            locator={
                                "file_key": key if file_targeted else None,
                                "requested_file_key": key, "file_identity_verified": file_targeted,
                                "requested_node_id": original_node, "provided_version": source.input.version,
                                "file_scope": "requested_file" if file_targeted else "active_desktop_document",
                                "image_status": "page_overview_use_inspect_node" if page_overview else ("captured" if image else "unavailable"),
                                "node_id": target, "node_ids": list(dict.fromkeys(re.findall(r'id="(\d+:\d+)"', text))),
                                "visible_text_ids": [node["node_id"] for node in visible_texts[:250]],
                                "hidden_text_ids": [node["node_id"] for node in hidden_texts[:80]],
                                "inspection_targets": inspection_targets,
                                "arrow_annotations": arrow_annotations,
                                "screenshot_width": screenshot_width,
                                "screenshot_height": screenshot_height,
                                "detail_limited": bool(
                                    screenshot_width is not None and screenshot_width < 700
                                    and screenshot_height and screenshot_height / screenshot_width > 2
                                ),
                                "text_nodes_omitted": omitted_texts,
                                "visual_targets_omitted": omitted_targets,
                            },
                            state_id=hashlib.sha256(text.encode() + (image or b"")).hexdigest()[:24],
                            image=image,
                            partial=bool((target and image is None) or omitted_texts or omitted_targets),
                            raw_content=text,
                        )
                        return self._remember_capture(session_id, source, capture)
        except EngineError:
            raise
        except ImportError as exc:
            raise EngineError("figma_mcp_dependency_missing", "请安装 requirements-session.txt 的 MCP 客户端依赖。", status_code=503) from exc
        except Exception as exc:
            raise EngineError("figma_mcp_connection_failed", "MCP 连接/授权失败或超时，未读取该文件。", status_code=503) from exc

    @staticmethod
    def _text(result: Any) -> str:
        text = "\n".join(block.text for block in result.content if getattr(block, "type", None) == "text")
        if not text and getattr(result, "structured_content", None):
            return json.dumps(result.structured_content, ensure_ascii=False)
        return text

    @staticmethod
    async def _image(result: Any) -> bytes | None:
        for block in result.content:
            if getattr(block, "type", None) == "image":
                return base64.b64decode(block.data, validate=True)
            if getattr(block, "type", None) == "text":
                try:
                    data = json.loads(block.text)
                except ValueError:
                    continue
                url = data.get("image_url") if isinstance(data, dict) else None
                if url:
                    parsed = urlparse(url)
                    if parsed.scheme != "https" or parsed.hostname not in {"www.figma.com", "figma.com"}:
                        raise EngineError("figma_asset_url_rejected", "截图地址不在允许的 Figma 来源中。", status_code=502)
                    if not parsed.path.startswith("/api/mcp/asset/"):
                        raise EngineError("figma_asset_url_rejected", "截图地址不是 MCP 资产。", status_code=502)
                    import httpx
                    async with httpx.AsyncClient(follow_redirects=False, timeout=20) as client:
                        async with client.stream("GET", url) as response:
                            response.raise_for_status()
                            chunks: list[bytes] = []
                            size = 0
                            async for chunk in response.aiter_bytes():
                                size += len(chunk)
                                if size > 15 * 1024 * 1024:
                                    raise EngineError("figma_asset_too_large", "截图超过读取限制。", status_code=502)
                                chunks.append(chunk)
                            return b"".join(chunks)
        return None

    async def act(self, session_id: str, source: SourceRecord, action: Action, **_: Any) -> Capture:
        if action.kind not in {"inspect_node", "observe"}:
            raise EngineError("figma_read_only", "画板接入仅支持读取，不修改设计。", status_code=403)
        if action.kind == "inspect_node" and not re.fullmatch(r"\d+:\d+", action.node_id):
            raise EngineError("figma_node_invalid", "节点 ID 无效。", status_code=422)
        prior = self._states.get((session_id, source.source_id))
        if action.kind == "inspect_node" and (
            not prior or not self._same_source(prior, source)
            or action.node_id not in self._known_nodes.get((session_id, source.source_id), set())
        ):
            raise EngineError("figma_node_not_observed", "节点不在已读取材料中，不能猜测节点 ID。", status_code=422)
        return await self.read(session_id, source, action.node_id or None)


class AdapterHub:
    def __init__(self, *, browser: BrowserAdapter | None = None, figma: FigmaMCPAdapter | None = None) -> None:
        config = load_reviewer_config(required=False)
        browser_config = config.get("tools", {}).get("browser", {})
        figma_config = config.get("tools", {}).get("figma_mcp", {})
        self.browser = browser or BrowserAdapter(
            allow_local=os.getenv("REVIEW_SESSION_ALLOW_LOCAL", "") == "1"
            or bool(browser_config.get("allow_local_network", False)),
        )
        snapshot_root = (
            os.getenv("REVIEW_FIGMA_SNAPSHOT_ROOT", "")
            or str(figma_config.get("snapshot_root", ""))
            or str(Path(__file__).resolve().parent.parent / "out" / "figma-snapshots")
        )
        self.figma = figma or FigmaMCPAdapter(
            os.getenv("REVIEW_FIGMA_MCP_URL", "")
            or (str(figma_config.get("url", "")) if figma_config.get("enabled") else ""),
            os.getenv("REVIEW_FIGMA_MCP_TOKEN", "") or str(figma_config.get("bearer_token", "")),
            snapshot_root=snapshot_root,
        )
        from .session_materials import DocumentReader
        self.documents = DocumentReader(allow_local=getattr(self.browser, "allow_local", False))
        self._read_verified: set[str] = set()
        self._operation_verified: set[str] = set()

    def capabilities(self) -> dict[str, Any]:
        return {
            "website": {"installed": importlib.util.find_spec("playwright") is not None,
                        "read_verified": "website" in self._read_verified, "operation_verified": "website" in self._operation_verified},
            "figma_prototype": {"installed": importlib.util.find_spec("playwright") is not None,
                               "read_verified": "figma_prototype" in self._read_verified, "operation_verified": "figma_prototype" in self._operation_verified},
            "figma_board": {
                "installed": importlib.util.find_spec("mcp") is not None,
                "configured": bool(self.figma.endpoint), "verified": "figma_board" in self._read_verified,
                "snapshot_root_configured": bool(self.figma.snapshot_root),
                "authorization": "bearer" if self.figma.token else (
                    "local_desktop" if urlparse(self.figma.endpoint).hostname in {"localhost", "127.0.0.1", "::1"}
                    else "backend_oauth"
                ),
                "read_verified": "figma_board" in self._read_verified,
            },
            "document": {"configured": True},
            "image": {"configured": True},
        }

    async def read(self, session_id: str, source: SourceRecord) -> Capture:
        if source.input.kind in {"website", "figma_prototype"}:
            capture = await self.browser.read(session_id, source)
        elif source.input.kind == "figma_board":
            capture = await self.figma.read(session_id, source)
        elif source.input.kind == "image":
            try:
                raw = base64.b64decode(source.input.image_base64, validate=True)
                prepared = prepare_image(raw, filename="input.png")
            except (ValueError, EngineError) as exc:
                raise EngineError("session_image_invalid", "图片输入无效。", status_code=422) from exc
            capture = Capture(
                content="用户提供的静态界面，不证明点击后行为。",
                locator={"sha256": prepared.sha256, "width": prepared.width, "height": prepared.height},
                state_id=prepared.sha256[:24], image=base64.b64decode(prepared.data_url.split(",", 1)[1]),
                image_mime_type=prepared.mime_type,
            )
        else:
            capture = await self.documents.read(session_id, source)
        if not capture.partial:
            self._read_verified.add(source.input.kind)
        return capture

    @staticmethod
    def _document(source: SourceRecord, index: int) -> Capture:
        chunks: list[str] = []
        current = ""
        for line in source.input.content.splitlines(keepends=True):
            while len(line) > 12000:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(line[:12000])
                line = line[12000:]
            if len(current) + len(line) > 12000:
                chunks.append(current)
                current = ""
            current += line
        if current:
            chunks.append(current)
        if index >= len(chunks):
            raise EngineError("document_chunk_invalid", "文档分块索引不存在。", status_code=422)
        return Capture(
            content=chunks[index],
            locator={"reference": source.input.reference, "title": source.input.title,
                     "chunk_index": index, "chunk_count": len(chunks),
                     "start_character": sum(len(chunk) for chunk in chunks[:index]),
                     "end_character": sum(len(chunk) for chunk in chunks[:index + 1])},
            state_id=hashlib.sha256((str(index) + chunks[index]).encode()).hexdigest()[:24],
            partial=len(chunks) > 1,
        )

    async def needs_authorization(self, session_id: str, source: SourceRecord, action: Action) -> bool:
        if source.input.kind == "image" and action.kind == "observe":
            return False
        if source.input.kind == "figma_board":
            return False
        if source.input.kind == "document" and action.kind == "inspect_document":
            return False
        if source.input.kind in {"website", "figma_prototype"}:
            return await self.browser.action_needs_authorization(session_id, source, action)
        return True

    async def act(self, session_id: str, source: SourceRecord, action: Action, *, authorized: bool) -> Capture:
        if source.input.kind == "image" and action.kind == "observe":
            # 静态图可重复读取，证据保留相同图像指纹，不生成交互结果。
            capture = await self.read(session_id, source)
        elif source.input.kind in {"website", "figma_prototype"}:
            capture = await self.browser.act(session_id, source, action, authorized=authorized)
            if (
                not capture.partial
                and action.kind != "observe"
                and capture.state_id != action.expected_state_id
                and (
                    source.input.kind != "figma_prototype"
                    or capture.locator.get("operation_verified", False)
                )
            ):
                self._operation_verified.add(source.input.kind)
        elif source.input.kind == "figma_board":
            capture = await self.figma.act(session_id, source, action)
        elif source.input.kind == "document" and action.kind == "inspect_document":
            capture = await self.documents.read(session_id, source, action.chunk_index)
        else:
            raise EngineError("source_not_interactive", "该材料不能执行交互动作。", status_code=422)
        if not capture.partial:
            self._read_verified.add(source.input.kind)
        return capture

    async def close(self) -> None:
        await self.browser.close()
