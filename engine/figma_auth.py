"""Independent backend OAuth using the MCP SDK, with protected local tokens."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from uuid import uuid4
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .errors import EngineError

TOKEN_PATH = Path(__file__).resolve().parent.parent / "out" / "credentials" / "figma-oauth.dat"


def _registration_failed(error: BaseException) -> bool:
    from mcp.client.auth.exceptions import OAuthRegistrationError
    if isinstance(error, OAuthRegistrationError):
        return True
    return any(_registration_failed(child) for child in getattr(error, "exceptions", ()))


class OAuthStorage:
    def __init__(self, endpoint: str, path: Path = TOKEN_PATH) -> None:
        self.endpoint = endpoint
        self.path = path

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            raw = self.path.read_bytes()
            if os.name == "nt":
                import win32crypt
                raw = win32crypt.CryptUnprotectData(raw, None, None, None, 0)[1]
            data = json.loads(raw)
            return data if data.get("endpoint") == self.endpoint else {}
        except Exception as exc:
            raise EngineError("figma_oauth_cache_invalid", "本地 OAuth 缓存不可读，请重新授权。", status_code=503) from exc

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data["endpoint"] = self.endpoint
        raw = json.dumps(data).encode("utf-8")
        if os.name == "nt":
            import win32crypt
            raw = win32crypt.CryptProtectData(raw, "Design review Figma OAuth", None, None, None, 0)
        temporary = self.path.with_name(self.path.name + f".{uuid4().hex}.pending")
        temporary.write_bytes(raw)
        if os.name != "nt":
            temporary.chmod(0o600)
        temporary.replace(self.path)

    async def get_tokens(self):
        from mcp.shared.auth import OAuthToken
        stored = self._load()
        data = stored.get("tokens")
        if data and data.get("expires_in") is not None and stored.get("token_issued_at"):
            data["expires_in"] = max(0, int(data["expires_in"] - (time.time() - stored["token_issued_at"])))
        return OAuthToken.model_validate(data) if data else None

    async def set_tokens(self, tokens) -> None:
        data = self._load()
        data["tokens"] = tokens.model_dump(mode="json")
        data["token_issued_at"] = time.time()
        self._save(data)

    async def get_client_info(self):
        from mcp.shared.auth import OAuthClientInformationFull
        data = self._load().get("client")
        return OAuthClientInformationFull.model_validate(data) if data else None

    async def set_client_info(self, client_info) -> None:
        data = self._load()
        data["client"] = client_info.model_dump(mode="json")
        self._save(data)


def oauth_provider(endpoint: str, storage: OAuthStorage, *, redirect_handler=None, callback_handler=None, callback_url="http://127.0.0.1:8766/callback"):
    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import OAuthClientMetadata

    async def needs_login(_url: str):
        raise EngineError(
            "figma_mcp_authorization_required",
            "后端需要独立 Figma 授权，请执行 python -m engine figma-login。", status_code=503,
        )
    return OAuthClientProvider(
        server_url=endpoint,
        client_metadata=OAuthClientMetadata(
            client_name="Design Review Engine", redirect_uris=[callback_url],
            token_endpoint_auth_method="client_secret_post",
            grant_types=["authorization_code", "refresh_token"],
        ),
        storage=storage, redirect_handler=redirect_handler or needs_login,
        callback_handler=callback_handler,
    )


async def interactive_login(endpoint: str, *, timeout: int = 300) -> dict:
    from mcp import ClientSession
    from mcp.shared.auth import AuthorizationCodeResult
    from .session_adapters import mcp_transport

    storage = OAuthStorage(endpoint)
    loop = asyncio.get_running_loop()
    result = loop.create_future()

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != "/callback":
                self.send_error(404)
                return
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            error = params.get("error", [None])[0]
            self.send_response(200 if code else 400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(("授权回复已接收，可以回到工具。" if code else "授权未完成。").encode("utf-8"))

            def deliver():
                if result.done():
                    return
                if error or not code:
                    result.set_exception(EngineError("figma_oauth_denied", "授权被拒绝或未返回有效代码。", status_code=403))
                else:
                    result.set_result(AuthorizationCodeResult(code=code, state=state, iss=params.get("iss", [None])[0]))
            loop.call_soon_threadsafe(deliver)

        def log_message(self, *_):
            pass  # Callback URLs contain authorization codes.

    try:
        server = ThreadingHTTPServer(("127.0.0.1", 8766), Callback)
    except OSError as exc:
        raise EngineError("figma_oauth_port_busy", "OAuth 回调端口 8766 已被占用，请先释放该端口。", status_code=503) from exc
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    callback_url = f"http://127.0.0.1:{server.server_port}/callback"

    async def redirect(url: str):
        print("请在浏览器打开以下 Figma 官方授权链接并确认账户：", flush=True)
        print(url, flush=True)

    async def callback():
        return await asyncio.wait_for(result, timeout)

    provider = oauth_provider(
        endpoint, storage, redirect_handler=redirect, callback_handler=callback,
        callback_url=callback_url,
    )
    try:
        async with asyncio.timeout(timeout):
            async with mcp_transport(endpoint, {}, auth=provider) as transport:
                async with ClientSession(transport[0], transport[1]) as client:
                    await client.initialize()
                    tools = (await client.list_tools()).tools
                    return {"authorized": True, "tools": [t.name for t in tools], "token_storage": "Windows DPAPI" if os.name == "nt" else "owner-only file"}
    except Exception as exc:
        if _registration_failed(exc):
            raise EngineError(
                "figma_oauth_registration_denied",
                "Figma 拒绝注册后端 MCP 客户端。远程服务目前限制客户端接入；"
                "请使用官方桌面 MCP（127.0.0.1:3845/mcp）或获准的远程客户端。"
                "未取得授权，重复输入账号密码不能解决此问题。",
                status_code=403,
            ) from None
        raise
    finally:
        await asyncio.to_thread(server.shutdown)
        server.server_close()
