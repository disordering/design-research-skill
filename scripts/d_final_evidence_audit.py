"""核验原始调用、图片、JSON 与 ZIP；按真实线程去重，在途调用留待终态。"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Callable
import zipfile

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "docs/D-最终验收证据"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stdin_bytes(raw):
    """CLI stdin 使用 LF；Windows 留档的 CRLF 字节另计文件 SHA。"""
    return raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def excluded(name):
    path = PurePosixPath(name)
    return path.name == "归档校验.json" or "__pycache__" in path.parts or path.suffix == ".pyc"


def safe_name(name):
    path = PurePosixPath(str(name).replace("\\", "/"))
    return bool(path.parts) and not path.is_absolute() and ".." not in path.parts and ":" not in path.parts[0]


@dataclass
class Entry:
    container: str
    name: str
    location: str
    reader: Callable[[], bytes]

    def read(self):
        return self.reader()


def audit(scope=ROOT, *, require_complete=False):
    scope = Path(scope).resolve()
    errors, files, records, packages, pending_reads = [], [], [], [], []
    entries, counts = {}, Counter()

    def error(location, problem):
        errors.append({"文件": location, "问题": problem})

    def parse_json(entry):
        try:
            data = json.loads(entry.read().decode("utf-8-sig"))
        except (ValueError, UnicodeError, OSError, RuntimeError) as exc:
            error(entry.location, f"JSON 无法读取：{exc}")
            return None
        counts["归档JSON" if entry.container else "文件JSON"] += 1
        if PurePosixPath(entry.name).name == "调用记录.json" and isinstance(data, dict) and ("操作" in data or "操作标签" in data):
            records.append((entry, data))
        return data

    with ExitStack() as stack:
        for path in sorted(scope.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(scope).as_posix()
            if excluded(relative):
                continue
            try:
                raw = path.read_bytes()
            except OSError as exc:
                error(relative, f"文件无法读取：{exc}")
                continue
            files.append({"文件": relative, "字节": len(raw), "SHA256": digest(raw)})
            entry = Entry("", relative, relative, path.read_bytes)
            entries[("", relative)] = entry
            if path.suffix == ".json":
                parse_json(entry)
            if path.suffix != ".zip":
                continue
            package = {"文件": relative, "成员数": 0, "CRC通过": False,
                       "SHA清单数": 0, "逐成员SHA已核对": 0, "逐成员SHA失败": 0}
            packages.append(package)
            try:
                archive = stack.enter_context(zipfile.ZipFile(path))
                infos = archive.infolist()
                names = [i.filename for i in infos if not i.is_dir()]
                package["成员数"] = len(infos)
                if len(names) != len(set(names)):
                    error(relative, "ZIP 包含重名成员")
                bad = archive.testzip()
                package["CRC通过"] = bad is None
                if bad:
                    error(relative, f"ZIP CRC 校验失败：{bad}")
                manifests = []
                for name in names:
                    if not safe_name(name):
                        error(relative, f"ZIP 成员路径无效：{name}")
                        continue
                    if excluded(name):
                        continue
                    item = Entry(relative, name, relative + "!" + name, partial(archive.read, name))
                    entries[(relative, name)] = item
                    if PurePosixPath(name).suffix == ".json":
                        data = parse_json(item)
                        if PurePosixPath(name).name == "归档成员SHA256.json" and data is not None:
                            manifests.append((item, data))
                for manifest, data in manifests:
                    package["SHA清单数"] += 1
                    rows = data if isinstance(data, list) else data.get("文件", []) if isinstance(data, dict) else None
                    if not isinstance(rows, list) or not rows:
                        error(manifest.location, "成员 SHA 清单没有有效条目")
                        continue
                    covered = set()
                    for row in rows:
                        if not isinstance(row, dict) or not row.get("路径") or not row.get("SHA256"):
                            error(manifest.location, "成员 SHA 条目缺少路径或指纹")
                            continue
                        name = str(row["路径"]).replace("\\", "/")
                        if not safe_name(name):
                            error(manifest.location, "成员 SHA 条目路径无效")
                            continue
                        if name not in names:
                            name = str(PurePosixPath(manifest.name).parent / name)
                        if name not in names:
                            error(manifest.location, f"清单成员缺失：{row['路径']}")
                            continue
                        if name in covered:
                            error(manifest.location, f"SHA 清单重复成员：{name}")
                            continue
                        covered.add(name)
                        if excluded(name):
                            continue
                        content = archive.read(name)
                        package["逐成员SHA已核对"] += 1
                        if digest(content) != row["SHA256"] or ("字节" in row and len(content) != row["字节"]):
                            package["逐成员SHA失败"] += 1
                            error(manifest.location, f"成员 SHA 或字节数不匹配：{name}")
                    prefix = str(PurePosixPath(manifest.name).parent)
                    expected = {n for n in names if not excluded(n) and n != manifest.name
                                and (prefix == "." or n.startswith(prefix + "/"))}
                    if expected - covered:
                        error(manifest.location, f"SHA 清单未覆盖 {len(expected - covered)} 个成员")
            except (zipfile.BadZipFile, OSError, RuntimeError, KeyError) as exc:
                error(relative, f"ZIP 无法校验：{exc}")

        # 失败桥接可能尚未来得及把线程号写进摘要，先从已收到的原始事件恢复。
        # 原始摘要保持不变；这里只补核对器的内存索引。
        resolved_records, logical_threads = [], defaultdict(set)
        for entry, data in records:
            logical = str(PurePosixPath(entry.container).parent / entry.name) if entry.container else entry.name
            resolved = dict(data)
            thread = data.get("Codex会话")
            event_name = str(PurePosixPath(entry.name).parent / "CLI原始事件.jsonl")
            event_entry = entries.get((entry.container, event_name))
            event_threads = set()
            if event_entry:
                try:
                    for line in event_entry.read().decode("utf-8-sig", errors="replace").splitlines():
                        try:
                            row = json.loads(line)
                        except ValueError:
                            # 超时可留下截断的末行，已经完整记录的启动事件仍有效。
                            continue
                        if isinstance(row, dict) and row.get("type") == "thread.started" and row.get("thread_id"):
                            event_threads.add(row["thread_id"])
                except (OSError, RuntimeError) as exc:
                    error(event_entry.location, f"CLI 线程事件无法读取：{exc}")
            if len(event_threads) > 1:
                error(event_entry.location, "单次 CLI 原始事件含多个线程编号")
            if thread:
                resolved["会话编号来源"] = "调用记录"
                if event_threads and thread not in event_threads:
                    error(event_entry.location, "CLI 事件的线程编号与调用记录不一致")
            elif len(event_threads) == 1:
                thread = next(iter(event_threads))
                resolved["Codex会话"] = thread
                resolved["会话编号来源"] = "CLI 原始事件 thread.started"
            if thread:
                logical_threads[logical].add(thread)
            resolved_records.append((entry, resolved, logical))

        # 仅保留摘要的展开文件可沿同逻辑路径取得 ZIP 原件的线程，再跨路径去重。
        groups = defaultdict(list)
        for entry, data, logical in resolved_records:
            known = logical_threads[logical]
            if not data.get("Codex会话") and len(known) == 1:
                data["Codex会话"] = next(iter(known))
                data["会话编号来源"] = "同逻辑调用的其他归档副本"
            if len(known) > 1:
                error(entry.location, "同逻辑调用的归档副本线程编号不一致")
            key = ("thread", data["Codex会话"]) if data.get("Codex会话") else ("location", logical)
            groups[key].append((entry, data))
        calls = []
        for key, copies in groups.items():
            chosen = next((pair for pair in copies if pair[1].get("状态") == "已返回"),
                          next((pair for pair in copies if pair[1].get("结束")), copies[0]))
            origin, data = chosen
            status = data.get("状态") or "进行中"
            in_progress = not data.get("结束") and status in {"进行中", "开始", "运行中"}
            call = {"目录": str(PurePosixPath(origin.location).parent),
                    **{field: data.get(field) for field in ["模型", "Codex会话", "会话编号来源", "耗时毫秒", "用量"]},
                    "操作": data.get("操作") or data.get("操作标签"), "状态": status,
                    "保存位置": [entry.location for entry, _ in copies], "副本数": len(copies),
                    "输入指纹核对": [], "图片核对数": 0}
            calls.append(call)
            for field in ["模型", "输入SHA256"]:
                if len({d[field] for _, d in copies if d.get(field)}) > 1:
                    error(origin.location, f"同一线程的 {field} 不一致")
            if len({d.get("操作") or d.get("操作标签") for _, d in copies}) > 1:
                error(origin.location, "同一线程的操作标签不一致")

            def companions(filename, *, image=False):
                result, seen = [], set()
                for entry, _ in copies:
                    parent = PurePosixPath(entry.name).parent
                    if image:
                        parent = parent.parent.parent
                    name = str(parent / filename.replace("\\", "/"))
                    item = entries.get((entry.container, name))
                    if item and item.location not in seen:
                        seen.add(item.location)
                        result.append(item)
                return result

            def missing(problem):
                if in_progress and not require_complete:
                    pending_reads.append({"文件": origin.location, "问题": problem})
                else:
                    error(origin.location, problem)

            prompts = companions("原始输入.txt")
            if data.get("输入SHA256") and not prompts:
                missing("缺少调用输入，展开目录和同线程归档均未找到")
            for prompt in prompts:
                try:
                    content = prompt.read()
                    logical_sha, file_sha = digest(stdin_bytes(content)), digest(content)
                    valid = not data.get("输入SHA256") or logical_sha == data["输入SHA256"]
                    call["输入指纹核对"].append({"位置": prompt.location, "stdin_LF_SHA256": logical_sha,
                        "归档文件SHA256": file_sha, "输入指纹匹配": valid})
                    if not valid:
                        error(prompt.location, "CLI stdin 的 LF 输入指纹不匹配")
                    if data.get("归档文件SHA256") and file_sha != data["归档文件SHA256"]:
                        error(prompt.location, "Windows 留档文件 SHA256 不匹配")
                except (UnicodeError, OSError) as exc:
                    error(prompt.location, f"调用输入无法读取：{exc}")

            for image in data.get("图片", []):
                if not isinstance(image, dict) or not image.get("文件") or not image.get("SHA256") or not safe_name(image["文件"]):
                    error(origin.location, "输入图片记录无有效相对路径或 SHA256")
                    continue
                images = companions(image["文件"], image=True)
                if not images:
                    missing("缺少输入图片：" + image["文件"])
                for item in images:
                    call["图片核对数"] += 1
                    if digest(item.read()) != image["SHA256"]:
                        error(item.location, "输入图片指纹不匹配")

            if in_progress:
                if require_complete:
                    error(origin.location, "调用仍在进行中，不能出具终态核对")
                continue
            if status != "已返回":
                # 失败或超时是有效终态记录，不要求它伪造 turn.completed。
                continue
            if not data.get("Codex会话"):
                error(origin.location, "缺少真实会话编号")
            answers, event_files = companions("模型原答.txt"), companions("CLI原始事件.jsonl")
            if not answers:
                error(origin.location, "缺少已返回的模型原答")
            for answer in answers:
                if not answer.read().decode("utf-8-sig").strip():
                    error(answer.location, "模型原答为空")
            if not event_files:
                error(origin.location, "缺少 CLI 原始事件")
            for event_file in event_files:
                try:
                    rows = [json.loads(line) for line in event_file.read().decode("utf-8-sig").splitlines()
                            if line.strip().startswith("{")]
                except (UnicodeError, ValueError) as exc:
                    error(event_file.location, f"CLI 原始事件无法读取：{exc}")
                    continue
                if not any(row.get("type") == "turn.completed" for row in rows):
                    error(event_file.location, "CLI 未记录正常返回 turn.completed")
                threads = {row.get("thread_id") for row in rows if row.get("type") == "thread.started"}
                if data.get("Codex会话") not in threads:
                    error(event_file.location, "CLI 事件的线程编号与调用记录不一致")

    result = {"检查UTC": datetime.now(timezone.utc).isoformat(),
        "范围": ("D-最终验收证据" if scope == ROOT.resolve() else str(scope.relative_to(ROOT.resolve())) if scope.is_relative_to(ROOT.resolve()) else scope.name),
        "核对内容": "原始调用与报告文件完整性；不替代逐项产品验收结论。",
        "要求全部终态": require_complete, "文件数": len(files), "可解析JSON": sum(counts.values()),
        "展开JSON": counts["文件JSON"], "ZIP内JSON": counts["归档JSON"],
        "真实CLI记录数": len(calls), "调用记录副本数": len(records), "重复留档副本数": len(records) - len(calls),
        "调用状态": dict(Counter(c["状态"] for c in calls)), "调用操作": dict(Counter(c["操作"] for c in calls)),
        "在途调用数": sum(c["状态"] in {"进行中", "开始", "运行中"} for c in calls),
        "在途待核对": pending_reads, "产品包数": len(packages), "问题数": len(errors), "问题": errors,
        "真实调用": calls, "产品包": packages, "文件清单": files}
    result["结论"] = "存在完整性问题" if errors else "在途材料待终态后补验" if result["在途调用数"] else "本次范围内完整性通过"
    return result


def run(scope=ROOT, output=None, *, require_complete=False):
    result = audit(scope, require_complete=require_complete)
    target = Path(output) if output else ROOT / "归档校验.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in {"真实调用", "产品包", "文件清单"}}, ensure_ascii=False, indent=2))
    return bool(result["问题数"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", default="", help="只核对最终验收证据下的指定子目录")
    parser.add_argument("--output", help="核对结果另存路径；子目录核对必须指定，避免覆盖总归档结论")
    parser.add_argument("--require-complete", action="store_true", help="最终核对时要求所有模型调用已到终态")
    args = parser.parse_args()
    selected = (ROOT / args.scope).resolve()
    if not selected.is_relative_to(ROOT.resolve()):
        parser.error("--scope 必须在 D-最终验收证据目录内")
    if args.scope and not args.output:
        parser.error("子目录核对必须使用 --output 指定独立结果")
    raise SystemExit(run(selected, args.output, require_complete=args.require_complete))
