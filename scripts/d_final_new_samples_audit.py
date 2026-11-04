"""核对已归档正式轮次的冻结配置、原始输入和证据指纹，不读取参考答案。"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "docs/D-最终验收证据/新样本"
ZIP_CACHE = {}


def raw_bytes(path):
    """原件可在原路径，也可在同层归档包内，按原相对路径读取。"""
    if path.exists():
        return path.read_bytes()
    for parent in path.parents:
        if parent == ROOT.parent:
            break
        member = path.relative_to(parent).as_posix()
        for archive in parent.glob("*.zip"):
            if archive not in ZIP_CACHE:
                ZIP_CACHE[archive] = zipfile.ZipFile(archive)
            opened = ZIP_CACHE[archive]
            if member in opened.namelist():
                return opened.read(member)
    raise FileNotFoundError(path)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(raw_bytes(path)).hexdigest()


def main():
    config = read(ROOT / "正式配置冻结.json")
    scope_file = ROOT / "用户缩减范围记录.json"
    canceled = read(scope_file).get("取消未启动", []) if scope_file.exists() else []
    failures = []
    frozen_counts = {}
    for folder, manifest, fingerprint in [
        ("冻结材料", "冻结清单.json", "材料冻结清单SHA256"),
        ("冻结运行源码-修后v1", "源码冻结清单.json", "源码冻结清单SHA256"),
    ]:
        directory = ROOT / folder
        if digest(directory / manifest) != config[fingerprint]:
            failures.append(f"冻结清单指纹变化：{folder}")
        files = read(directory / manifest)["文件"]
        frozen_counts[folder] = len(files)
        for item in files:
            if digest(directory / item["路径"]) != item["SHA256"]:
                failures.append(f"冻结文件指纹变化：{folder}/{item['路径']}")

    records, pending, sessions, threads = [], [], [], []
    common = None
    forbidden = ["独立AI参考_冻结.json", "d_final_acceptance_reference", config["参考SHA256"]]
    for sample_round in config["正式轮次"]:
        sample, round_number = sample_round.split("-")
        stage = ROOT / "原生评审" / f"修后v1-{sample}-第{round_number}轮"
        if not (stage / "运行结果.json").exists():
            if sample_round not in canceled:
                pending.append(sample_round)
            continue
        env, request = read(stage / "运行环境.json"), read(stage / "创建请求.json")
        snapshot = read(stage / "会话快照.json")
        sessions.append(snapshot["session_id"])
        for key in ["材料冻结清单SHA256", "源码冻结清单SHA256"]:
            if env[key] != config[key]:
                failures.append(f"{stage.name}：{key}不符")
        if env["模型"] != config["正式模型"] or request["actor_type"] != "ai":
            failures.append(f"{stage.name}：模型或执行者来源不符")
        comparable = {key: env[key] for key in ["运行脚本SHA256", "主任务桥接SHA256", "逐屏桥接SHA256", "限额"]}
        if common is None:
            common = comparable
        elif comparable != common:
            failures.append(f"{stage.name}：驱动或预算与其他正式轮次不同")
        for file, key in [
            ("d_final_new_samples.py", "运行脚本SHA256"),
            ("d_native_recheck.py", "主任务桥接SHA256"),
            ("d_screen_codex_probe.py", "逐屏桥接SHA256"),
        ]:
            if digest(stage / "测试驱动快照" / file) != env[key]:
                failures.append(f"{stage.name}：驱动快照指纹不符 {file}")
            if digest(ROOT / "冻结测试驱动" / file) != env[key]:
                failures.append(f"{stage.name}：公共冻结驱动与本轮执行版本不符 {file}")
        card = next((ROOT / "冻结材料").glob(f"{sample}-*/任务卡.txt")).read_text(encoding="utf-8").strip()
        if request["sources"][1]["content"] != card:
            failures.append(f"{stage.name}：模型输入任务卡与冻结材料不同")

        calls, image_count, usage, usage_calls = 0, 0, Counter(), 0
        for chain in ["主任务链", "逐屏链"]:
            chain_dir = stage / chain
            for record_file in sorted((chain_dir / "调用").glob("*/调用记录.json")):
                calls += 1
                record = read(record_file)
                if record["模型"] != config["正式模型"] or record["推理设置"] != config["推理设置"]:
                    failures.append(f"{stage.name}/{chain}/{record_file.parent.name}：模型配置不符")
                # 桥接记录的是传入 CLI 的逻辑 UTF-8 文本；读取时统一平台换行。
                prompt = raw_bytes(record_file.parent / "原始输入.txt").decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
                if hashlib.sha256(prompt.encode("utf-8")).hexdigest() != record["输入SHA256"]:
                    failures.append(f"{stage.name}/{chain}/{record_file.parent.name}：输入文本指纹不符")
                if any(marker in prompt for marker in forbidden):
                    failures.append(f"{stage.name}/{chain}/{record_file.parent.name}：输入出现参考文件标识")
                for item in record.get("图片", []):
                    image_count += 1
                    if digest(chain_dir / item["文件"]) != item["SHA256"]:
                        failures.append(f"{stage.name}/{chain}/{record_file.parent.name}：输入图片指纹不符")
                event_file = record_file.parent / "CLI原始事件.jsonl"
                try:
                    event_text = raw_bytes(event_file).decode("utf-8")
                except FileNotFoundError:
                    failures.append(f"{stage.name}/{chain}/{record_file.parent.name}：缺少 CLI 原始事件")
                    continue
                for line in event_text.splitlines():
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if event.get("type") == "thread.started":
                        threads.append(event["thread_id"])
                    if event.get("type") == "turn.completed":
                        usage_calls += 1
                        usage.update({k: v for k, v in event.get("usage", {}).items() if isinstance(v, (int, float))})
        records.append({"轮次": sample_round, "统计组": "修复回归" if sample == "N01" else "新任务独立验收",
                        "会话ID": snapshot["session_id"], "实际CLI调用": calls, "输入图片引用": image_count,
                        "已返回用量的CLI数": usage_calls, "CLI原始用量": dict(usage),
                        "状态": snapshot["status"], "完整度": snapshot["report_completeness"]})
    if len(sessions) != len(set(sessions)):
        failures.append("正式轮次复用了产品会话 ID")
    if len(threads) != len(set(threads)):
        failures.append("不同 CLI 调用复用了模型线程 ID")
    output = {"核查UTC": datetime.now(timezone.utc).isoformat(), "来源": "AI 程序核对原始归档，无新增模型调用",
              "冻结文件数": frozen_counts, "已完成轮数": len(records), "待完成轮次": pending,
              "用户取消未启动轮次": canceled,
              "正式配置一致": not failures, "问题": failures, "轮次": records,
              "隔离核对范围": "核对冻结任务卡、驱动指纹和生产输入未出现参考文件标识；独立参考内容未读取。结合驱动交叉核查记录解释输入隔离。",
              "用量口径": "输入、缓存输入与输出按 CLI 原始 usage 分别汇总，不估算费用；无返回用量的调用不记作零消耗。"}
    (ROOT / "正式轮次归档核查.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"已完成": len(records), "待完成": pending, "问题": failures}, ensure_ascii=False))


if __name__ == "__main__":
    main()
