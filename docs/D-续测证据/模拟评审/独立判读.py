"""将六题的原图及可见状态送给两个不共享历史的 Codex 会话。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
DOCS = HERE.parents[1]
SAMPLES = DOCS / "D-新版真人执行/04-次批匿名任务"
MODEL = "gpt-6-astra"


def dump(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def build_prompt(runs):
    neutral = []
    images = []
    for num in ("H01", "H02"):
        folder = next(SAMPLES.glob(num+"-*"))
        neutral.append({"题号": num, "卡": (folder/"任务卡.txt").read_text(encoding="utf-8-sig"),
                        "要求": (folder/"设计要求.txt").read_text(encoding="utf-8-sig")})
        images.append(folder/"原始设计.png")
    for task, num in zip("ABC", ["H03","H04","H05"], strict=True):
        records = [read(p) for p in sorted(runs.glob(f"*-{task}/网页走查.json"))]
        variants = {}
        for raw in records:
            if raw["附加路径"] not in variants:
                variants[raw["附加路径"]] = raw["各步"]
        neutral.append({"题号": num, "卡":records[0]["任务卡"], "观察序列": list(variants.values())})
    raw = read(DOCS / "D-AI操作证据/巡展资料/运行记录/逐步记录.json")
    folder = next(SAMPLES.glob("H06-*"))
    neutral.append({"题号":"H06", "卡": (folder/"任务卡.txt").read_text(encoding="utf-8-sig"),
                    "要求": (folder/"设计要求.txt").read_text(encoding="utf-8-sig"),
                    "观察序列": [{"序号":i,"界面":s["当前可访问性树"]}
                              for i,s in enumerate(raw["轮次"][0]["步骤"], start=1)]})
    prompt = """请独立评审六个设计任务。所附第1张图为H01，第2张为H02。其余为浏览器记录的可见状态。
仅依本次原图、任务要求及观察序列作答，无需打开文件、命令行、搜索或任何工具。将每项设计要求分别判定，界面证明的事实与后台事实分开。
严重度定义：低=轻微表述；中=有恢复办法但明显增加判断或操作成本；高=关键分支结果明确错误且没有合理可用替代；严重=观察到重大不可逆后果或全部关键路径无替代。
仅输出JSON对象，格式为 {"assessments":[{"task":"H01", "checks":[{"id":1, "status":"符合/不符合/证据不足（三选一）","evidence":"事实、位置或具体步骤"}], "issues":[{"phenomenon":"具体问题","severity":"低/中/高/严重/待验证（择一）","reason":"为何、影响和可恢复性"}]}]}。
每题3个checks，只有依据支持的缺陷才记入issues。如一项任务没有明确问题，issues使用空数组。
原始材料如下。""" + json.dumps(neutral, ensure_ascii=False, separators=(",",":"))
    return prompt, images


def execute(label, out, prompt, images):
    folder = out/label
    folder.mkdir()
    with TemporaryDirectory(prefix="d-isolated-review-") as tmp:
        attachments = []
        for index, img in enumerate(images, 1):
            target = Path(tmp) / f"sample{index}.png"
            shutil.copyfile(img, target)
            attachments += ["-i", str(target)]
        command = [os.environ.get("CODEX_APP_RUNTIME_CLI_PATH") or shutil.which("codex.cmd"), "exec", "--ignore-user-config", "--ephemeral",
                   "--skip-git-repo-check", "--sandbox", "read-only", "-m", MODEL, "-c", 'model_reasoning_effort="medium"',
                   "--json", *attachments, "-"]
        start = datetime.now(timezone.utc).isoformat()
        result = subprocess.run(command, cwd=tmp, input=prompt.encode("utf-8"), capture_output=True,
                                timeout=600, check=False)
        elapsed = datetime.now(timezone.utc).isoformat()
        events_file = folder/"独立会话.jsonl"
        events_file.write_bytes(result.stdout)
        events = []
        for line in result.stdout.decode("utf-8","replace").splitlines():
            if line.strip().startswith("{"):
                events.append(json.loads(line))
        items = [e.get("item",{}) for e in events if e.get("type") == "item.completed"]
        texts = [i["text"] for i in items if i.get("type") == "agent_message" and i.get("text")]
        meta = {"标签":label, "来源":"独立 Codex 上下文", "模型":MODEL, "开始UTC":start, "结束UTC":elapsed,
                "进程退出码":result.returncode, "调用工具": [i.get("type") for i in items
                                               if i.get("type") not in ("agent_message","reasoning")],
                "中性提示SHA256":hashlib.sha256(prompt.encode("utf-8")).hexdigest()}
        if not texts:
            meta["错误"] = result.stderr.decode("utf-8","replace")[-900:]
            dump(folder/"会话核验.json", meta)
            raise RuntimeError(f"{label} 未返回评审意见，见原始会话")
        text = texts[-1].strip()
        (folder/"回复原文.txt").write_text(text, encoding="utf-8")
        if text.startswith("```"):
            text = text.split("\n",1)[1].rsplit("```",1)[0]
        parsed = json.loads(text)
        assert len(parsed["assessments"]) == 6
        assert {t["task"] for t in parsed["assessments"]} == {f"H{i:02}" for i in range(1,7)}
        assert not meta["调用工具"] and all({c["id"] for c in t["checks"]} == {1,2,3} for t in parsed["assessments"])
        dump(folder/"逐题意见.json", parsed)
        dump(folder/"会话核验.json", meta)
        print(label,"完成")


def main(runs, out):
    out.mkdir(parents=True, exist_ok=False)
    prompt, images = build_prompt(runs)
    (out/"两次同一提示.txt").write_text(prompt,encoding="utf-8")
    dump(out/"附件核验.json", [{"顺序":i,"材料":str(p.relative_to(DOCS)).replace("\\","/"),
                            "SHA256":hashlib.sha256(p.read_bytes()).hexdigest()} for i,p in enumerate(images,1)])
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(execute, label, out, prompt, images) for label in ("AI甲", "AI乙")]
        for item in pending:
            item.result()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args = parser.parse_args()
    main(args.runs, args.out)

