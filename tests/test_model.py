import asyncio
import json

import httpx

from engine.model import ModelSettings, OpenAICompatibleModel


def test_qwen_preset_uses_openai_compatible_url(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.delenv("REVIEW_BASE_URL", raising=False)
    monkeypatch.delenv("REVIEW_MODEL", raising=False)
    settings = ModelSettings.from_env("qwen", None)
    assert settings.model == "qwen3.8-max-0902"
    assert settings.chat_completions_url == (
        "https://maas.qianwenaiapi.com/compatible-mode/v1/chat/completions"
    )


def test_compatible_client_sends_image_and_reads_content():
    received = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received["url"] = str(request.url)
        received["authorization"] = request.headers.get("authorization")
        received["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "req-test",
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"total_tokens": 12},
            },
        )

    settings = ModelSettings(
        provider="qwen",
        model="qwen3.8-flash",
        base_url="https://example.test/v1",
        api_key="secret-test-key",
    )
    model = OpenAICompatibleModel(
        settings,
        transport=httpx.MockTransport(handler),
        sleep=lambda _: asyncio.sleep(0),
    )
    result = asyncio.run(
        model.complete(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "inspect"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/jpeg;base64,AA=="},
                        },
                    ],
                }
            ]
        )
    )

    assert result.text == '{"ok": true}'
    assert received["url"] == "https://example.test/v1/chat/completions"
    assert received["authorization"] == "Bearer secret-test-key"
    assert received["payload"]["response_format"] == {"type": "json_object"}
    assert received["payload"]["messages"][0]["content"][1]["type"] == "image_url"
