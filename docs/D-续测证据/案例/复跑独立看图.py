"""用六个独立的 Codex 会话盲读两张画面，记录实际输入、输出与文件指纹。"""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
DOCS = ROOT.parent.parent
HF = DOCS / "D-护法复核证据" / "EV06-升星选择和执行.jpg"
WS = DOCS / "D-复核证据" / "吴山石" / "EV03-包裹入口.jpg"
HF_TASK = (
    "只根据附图，不读取文件、不使用工具。假设你正在这个游戏画面，"
    "任务是把当前护法提升一颗星。你第一下会点哪里？只回答控件原文字、方位、"
    "相对全图的中心坐标 x/y（0 到 1），并用一句话说明你对点击结果的预期。若无法判断可如实写。"
)
WS_TASK = (
    "只根据这张完整的包裹截图，不读取文件、不使用工具。请抄出已选物品详情面板的"
    "主标题和下一行副标题，并说明该物品的等级。请只按文字作答，读不清的字标“？”；"
    "请写明等级读自哪个区域。"
)


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def measure(index, source, width, task, output, executable):
    with tempfile.TemporaryDirectory(prefix="dcase-") as name:
        isolated = Path(name)
        if width:
            raw = isolated / "画面.png"
            with Image.open(source) as src:
                height = round(src.height * width / src.width)
                src.resize((width, height), Image.Resampling.LANCZOS).save(raw)
        else:
            raw = isolated / "画面.jpg"
            shutil.copyfile(source, raw)
        with Image.open(raw) as img:
            size = list(img.size)
        answer = isolated / "回答.txt"
        command = [
            executable, "exec", "--ephemeral", "--skip-git-repo-check", "--ignore-user-config",
            "--color", "never", "--sandbox", "read-only", "--json", "-C", name, "-i",
            str(raw), "-o", str(answer), task,
        ]
        run = subprocess.run(command, capture_output=True, timeout=160)
        events = []
        for line in run.stdout.decode("utf-8", "replace").splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
        items = [e.get("item", {}).get("type") for e in events if e.get("item")]
        raw_answer = answer.read_text(encoding="utf-8").strip() if answer.exists() else ""
        if run.returncode or not raw_answer or not events:
            raise RuntimeError(f"{index} 未取得独立会话回答，退出码 {run.returncode}")
        evidence = {
            "试次": index, "来源": "独立 Codex 临时会话，同一模型服务",
            "任务原文": task, "输入画面尺寸": size, "输入画面SHA256": digest(raw),
            "原图SHA256": digest(source), "CLI版本": subprocess.check_output(
                [executable, "--version"], text=True
            ).strip(), "会话": next((e.get("thread_id") for e in events if e.get("thread_id")), None),
            "输出事件": items, "回答原文": raw_answer,
        }
        (output / f"{index}.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True, help="本次新建的空目录")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        parser.error("请选择空目录，以保留旧实测记录。")
    cli = shutil.which("codex.exe") or shutil.which("codex")
    if not cli:
        parser.error("找不到 Codex CLI")
    jobs = [(f"升星-{i}", HF, None, HF_TASK) for i in (1, 2, 3)]
    jobs += [(f"等级-{width}", WS, width, WS_TASK) for width in (1194, 844, 667)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(measure, *j, args.output, cli) for j in jobs]
        for future in futures:
            future.result()
