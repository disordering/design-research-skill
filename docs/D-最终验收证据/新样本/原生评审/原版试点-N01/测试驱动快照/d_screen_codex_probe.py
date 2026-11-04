"""以真实 Codex CLI 验证原生产逐屏 OCR、元素解析、指标和审查链。"""
from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import site
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import zipfile


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
for name in ("d_nov_review_deps", "d_nov_mcp"):
    directory = REPO.parent / "work" / name
    if directory.exists():
        site.addsitedir(str(directory))

from engine.contracts import ReviewContext
from engine.errors import EngineError
from engine.methods import MethodRegistry
from engine.model import ModelCallResult
from engine.session_contracts import Evidence
from engine.session_screen_review import QwenScreenTechnicalReviewer, ScreenReviewModels


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class CodexScreenTransport:
    """操作名仅用于日志，不向生产消息插入标签、答案或预设发现。"""
    is_stub = False
    supports_images = True

    def __init__(self, root, model, budget):
        self.root, self.model, self.budget, self.calls = root, model, budget, 0
        self.cli = shutil.which("codex.exe") or shutil.which("codex")
        if not self.cli:
            raise RuntimeError("未找到已登录的 Codex CLI。")

    async def complete(self, messages, *, operation, **kwargs):
        if self.calls >= self.budget:
            raise EngineError("screen_probe_budget", "本批次逐屏调用已达到上限。", status_code=429)
        self.calls += 1
        # 生产修复消息的用户内容是字符串；这里只标记留档名，不改消息内容。
        tag = operation + ("_repair" if isinstance(messages[1]["content"], str) else "")
        return await asyncio.to_thread(self._complete, self.calls, messages, tag, kwargs)

    def _complete(self, number, messages, operation, kwargs):
        started = time.monotonic()
        call_dir = self.root / "调用" / f"{number:02d}-{operation}"
        call_dir.mkdir(parents=True, exist_ok=False)
        save(call_dir / "生产消息.json", messages)
        save(call_dir / "调用参数.json", kwargs)
        # CLI 用图片附件承接原消息中的 data URL；原字节另存并核对摘要。
        prompt_parts, images = [], []
        with tempfile.TemporaryDirectory(prefix="d-screen-codex-") as temporary:
            command = [self.cli, "exec", "--ignore-user-config", "--ephemeral",
                       "--skip-git-repo-check", "--sandbox", "read-only", "--cd", temporary,
                       "--model", self.model, "-c", "model_reasoning_effort=low", "--json"]
            for message in messages:
                prompt_parts.append("[" + message["role"] + "]")
                content = message["content"]
                if isinstance(content, str):
                    prompt_parts.append(content)
                    continue
                for part in content:
                    if part["type"] == "text":
                        prompt_parts.append(part["text"])
                    elif part["type"] == "image_url":
                        header, encoded = part["image_url"]["url"].split(",", 1)
                        raw = base64.b64decode(encoded, validate=True)
                        suffix = ".png" if "png" in header else ".jpg"
                        image = self.root / "输入图片" / (sha(raw) + suffix)
                        image.parent.mkdir(parents=True, exist_ok=True)
                        if not image.exists():
                            image.write_bytes(raw)
                        images.append({"序号": len(images) + 1, "SHA256": sha(raw),
                                       "文件": image.relative_to(self.root).as_posix()})
                        prompt_parts.append(f"[原消息图片 {len(images)}，见随附图片]")
                        command += ["--image", str(image)]
                    else:
                        raise RuntimeError("逐屏消息含未支持的内容类型：" + part["type"])
            prompt = "\n".join(prompt_parts)
            (call_dir / "原始输入.txt").write_text(prompt, encoding="utf-8")
            marker = {"执行来源": "真实 Codex CLI / AI 模型调用", "开始": utc(),
                      "操作标签": operation, "模型": self.model, "推理设置": "low",
                      "输入SHA256": sha(prompt.encode("utf-8")), "图片": images,
                      "固定响应": False}
            save(call_dir / "调用记录.json", marker)
            print(f"{utc()} {number:02d} {operation} 开始，{len(prompt)} 字/{len(images)} 图", flush=True)
            try:
                result = subprocess.run(command + ["-"], cwd=temporary, input=prompt.encode("utf-8"),
                                        capture_output=True, timeout=180,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except subprocess.TimeoutExpired as error:
                (call_dir / "CLI原始事件.jsonl").write_bytes(error.stdout or b"")
                (call_dir / "CLI诊断.txt").write_bytes(error.stderr or b"")
                marker.update(结束=utc(), 状态="超时")
                save(call_dir / "调用记录.json", marker)
                raise EngineError("codex_cli_timeout", "单次逐屏调用超过 180 秒。", status_code=504)
        (call_dir / "CLI原始事件.jsonl").write_bytes(result.stdout)
        (call_dir / "CLI诊断.txt").write_bytes(result.stderr)
        events = []
        for line in result.stdout.decode("utf-8", errors="replace").splitlines():
            if line.startswith("{"):
                with contextlib.suppress(json.JSONDecodeError):
                    events.append(json.loads(line))
        items = [e["item"] for e in events if e.get("type") == "item.completed"]
        answer = next((x.get("text") for x in reversed(items) if x.get("type") == "agent_message"), None)
        done = next((e for e in events if e.get("type") == "turn.completed"), None)
        thread = next((e["thread_id"] for e in events if e.get("type") == "thread.started"), None)
        marker.update(结束=utc(), 退出码=result.returncode, Codex会话=thread,
                      耗时毫秒=round((time.monotonic() - started) * 1000))
        if answer:
            (call_dir / "模型原答.txt").write_text(answer, encoding="utf-8")
        if result.returncode or not answer or not done:
            marker["状态"] = "调用失败"
            save(call_dir / "调用记录.json", marker)
            raise EngineError("codex_cli_failed", "逐屏调用未返回完整响应，已保留原始事件。", status_code=502)
        if any(x["type"] not in ("reasoning", "agent_message") for x in items):
            marker["状态"] = "出现额外工具调用"
            save(call_dir / "调用记录.json", marker)
            raise EngineError("unexpected_tool", "逐屏模型进行了额外工具调用，保留记录并停止本次结果。", status_code=502)
        marker.update(状态="已返回", 用量=done.get("usage", {}))
        save(call_dir / "调用记录.json", marker)
        print(f"{utc()} {number:02d} {operation} 返回，{marker['耗时毫秒']} ms", flush=True)
        return ModelCallResult(text=answer, provider="codex_cli", model=self.model,
                               usage=done.get("usage", {}), request_id=thread,
                               latency_ms=marker["耗时毫秒"], json_mode_used=False)


class ScreenClient:
    is_stub = False

    def __init__(self, transport, operation):
        self.transport, self.operation = transport, operation
        self.settings = SimpleNamespace(provider="codex_cli", model=transport.model)

    async def complete(self, messages, **kwargs):
        return await self.transport.complete(messages, operation=self.operation, **kwargs)


class CodexScreenReviewer(QwenScreenTechnicalReviewer):
    """只替换测试实例的客户端装配，完整继承原生产 review 方法。"""

    def __init__(self, criteria, transport):
        self.criteria = criteria
        self.engine = ScreenReviewModels(
            ocr=ScreenClient(transport, "screen_ocr"),
            gui=ScreenClient(transport, "screen_ui"),
            reasoning=ScreenClient(transport, "screen_reasoning"),
        )


async def run(args):
    root = REPO / "docs/D-本轮续测证据/逐屏Codex" / args.name
    if root.exists():
        raise SystemExit("批次已存在，请换名保留既有证据。")
    root.mkdir(parents=True)
    image_path = REPO / "fixtures/d-v02-static/T02.png"
    task_path = REPO / "fixtures/d-v02-batch/tasks.json"
    task = next(x for x in json.loads(task_path.read_text(encoding="utf-8"))["tasks"] if x["id"] == "T02")
    raw = image_path.read_bytes()
    purpose = task["purpose"]
    context = ReviewContext(design_goal=purpose, scenario=purpose, platform="unknown")
    evidence = Evidence(source_id="T02-original", kind="design", source_version=sha(raw),
                        context_version=1, locator={"sha256": sha(raw)}, content="T02 通知设置原始界面截图")
    registry = MethodRegistry(REPO / "方法专家开发交付-v0.2")
    transport = CodexScreenTransport(root, args.model, args.max_calls)
    reviewer = CodexScreenReviewer(registry.criteria, transport)
    manifest = {
        "来源": "AI 使用真实 Codex CLI 调用原生产逐屏审查链", "开始": utc(),
        "原图": image_path.relative_to(REPO).as_posix(), "原图SHA256": sha(raw),
        "任务卡": task_path.relative_to(REPO).as_posix(), "任务": task,
        "输入上下文": context.model_dump(mode="json"), "模型": args.model,
        "最大模型调用": args.max_calls, "判据版本": registry.criteria.version,
        "产品源码SHA256": {str(p.relative_to(REPO)): sha(p.read_bytes()) for p in [
            REPO / "engine/session_screen_review.py", REPO / "engine/advanced.py",
            REPO / "engine/cv_metrics.py", REPO / "engine/session_service.py",
        ]},
        "测试脚本SHA256": sha(Path(__file__).read_bytes()),
        "接入方式": "测试子类仅装配三个客户端，继承 QwenScreenTechnicalReviewer.review；未写配置或密钥",
    }
    save(root / "输入登记.json", manifest)
    try:
        output = await reviewer.review(evidence=evidence, image_bytes=raw, context=context, max_calls=args.max_calls)
        save(root / "逐屏结果.json", output.review.model_dump(mode="json"))
        save(root / "模型调用校验.json", [asdict(c) for c in output.calls])
        for name, (content, mime) in output.artifacts.items():
            target = root / "产物" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        result = {
            "结束": utc(), "执行来源": "AI 真实模型调用", "状态": output.review.status,
            "实际CLI调用": transport.calls, "生产链调用记录数": len(output.calls),
            "调用阶段": [{"阶段": c.operation, "状态": c.status, "线程": c.request_id,
                         "结构错误": c.validation_error} for c in output.calls],
            "摘要": output.review.summary, "候选数": len(output.review.issues),
            "判据结果数": len(output.review.rule_results), "警告": output.review.warnings,
            "产物数": len(output.artifacts),
        }
        save(root / "运行结果.json", result)
        with zipfile.ZipFile(root / "逐屏产物.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted((root / "产物").rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root))
            for name in ("输入登记.json", "逐屏结果.json", "模型调用校验.json", "运行结果.json"):
                archive.write(root / name, name)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return output.review.status == "completed"
    except Exception as error:
        save(root / "运行结果.json", {"结束": utc(), "执行来源": "AI 真实模型调用",
                                    "状态": "异常", "实际CLI调用": transport.calls,
                                    "错误类型": type(error).__name__, "错误": str(error)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="唯一证据批次名")
    parser.add_argument("--model", default="gpt-6-astra")
    parser.add_argument("--max-calls", type=int, choices=range(1, 13), default=4)
    args = parser.parse_args()
    raise SystemExit(0 if asyncio.run(run(args)) else 1)


if __name__ == "__main__":
    main()
