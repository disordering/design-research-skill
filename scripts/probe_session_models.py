"""Tiny, bounded visual/JSON capability probes; never a quality ranking."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image
from engine.model import ModelSettings, OpenAICompatibleModel
from engine.parsing import parse_json_object
from engine.errors import EngineError


async def main():
    buffer = io.BytesIO()
    Image.new("RGB", (640, 360), (220, 20, 30)).save(buffer, "PNG")
    image = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    result = []
    for provider, name in [("qwen", "qwen3.8-flash"), ("deepseek", "deepseek-v4-pro")]:
        settings = replace(ModelSettings.from_env(provider, name), max_tokens=512, max_retries=1, timeout_seconds=45)
        client = OpenAICompatibleModel(settings)
        try:
            call = await client.complete([
                {"role": "system", "content": 'Identify the dominant image color. Return only JSON {"color":"..."}.'},
                {"role": "user", "content": [{"type": "text", "text": "What is the dominant color?"},
                                             {"type": "image_url", "image_url": {"url": image}}]},
            ], extra_body={"enable_thinking": False} if provider == "qwen" else None)
            parsed = parse_json_object(call.text)
            result.append({"provider": provider, "model": name, "received_json": parsed,
                           "latency_ms": call.latency_ms, "usage": call.usage,
                           "assessment": "Visual/JSON capability only, not review quality."})
        except (EngineError, ValueError) as exc:
            result.append({"provider": provider, "model": name,
                           "error": exc.code if isinstance(exc, EngineError) else "json_invalid",
                           "assessment": "Capability not confirmed; do not assume vision support."})
    output = ROOT / "out" / "session-probes" / "model-capabilities.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
