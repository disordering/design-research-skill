"""归档已结束阶段的调用原件；保留摘要和文档链接，完整原目录移入本地备份。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
from urllib.parse import unquote, urlsplit
import zipfile

import d_final_evidence_audit as auditor

REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO.parent.resolve()
WORK = WORKSPACE / "work"
ROOT = REPO / "docs/D-最终验收证据"
TEST_ROOT = WORK / "d_final_pack_calls_test"
CALL_PATHS = (Path("调用"), Path("主任务链/调用"), Path("逐屏链/调用"))
MANIFEST = "归档成员SHA256.json"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def checked_path(path, allowed):
    """移动前检查最终绝对路径，并拒绝符号链接和 Windows junction。"""
    path = Path(path).absolute()
    allowed = Path(allowed).resolve()
    resolved = path.resolve()
    if resolved == allowed or not resolved.is_relative_to(allowed):
        raise ValueError(f"路径超出指定范围：{path}")
    for component in (path, *path.parents):
        if os.path.lexists(component):
            info = component.lstat()
            if component.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError(f"拒绝链接或重解析目录：{component}")
        if component == allowed:
            break
    return resolved


def tree_files(directory):
    result, pending = [], [directory]
    while pending:
        current = pending.pop()
        for child in sorted(current.iterdir()):
            checked_path(child, WORKSPACE)
            if child.is_dir():
                pending.append(child)
            elif child.is_file():
                result.append(child)
            else:
                raise ValueError(f"调用目录含非普通文件：{child}")
    return sorted(result)


def fingerprint(directory):
    return {path.relative_to(directory).as_posix(): {"字节": path.stat().st_size, "SHA256": digest(path.read_bytes())}
            for path in tree_files(directory)}


def safe_move(source, target, source_root, target_root):
    source = checked_path(source, source_root)
    target = checked_path(target, target_root)
    if os.path.lexists(target):
        raise FileExistsError(f"目标已存在，不覆盖：{target}")
    if source.drive.lower() != target.drive.lower():
        raise ValueError("本工具只在同一工作区磁盘内重命名，避免跨盘半完成移动。")
    target.parent.mkdir(parents=True, exist_ok=True)
    checked_path(target, target_root)
    source.rename(target)


def terminal_stage(stage):
    result_path, snapshot_path = stage / "运行结果.json", stage / "会话快照.json"
    if not result_path.is_file() or not snapshot_path.is_file():
        raise ValueError(f"阶段尚无完整终态输出：{stage.name}")
    result, snapshot = read_json(result_path), read_json(snapshot_path)
    if not result.get("结束") or snapshot.get("status") not in {"completed", "cancelled", "awaiting_input"}:
        raise ValueError(f"阶段仍在运行：{stage.name}")
    return {p.name: digest(p.read_bytes()) for p in (result_path, snapshot_path)}


def terminal_calls(directory):
    records = list(directory.rglob("调用记录.json"))
    if not records:
        raise ValueError(f"调用目录没有摘要：{directory}")
    for path in records:
        data = read_json(path)
        if not data.get("结束") or data.get("状态") in {None, "", "开始", "运行中", "进行中"}:
            raise ValueError(f"拒绝归档在途调用：{path}")
        if not (data.get("操作") or data.get("操作标签")):
            raise ValueError(f"调用摘要缺少操作标识：{path}")
    return records


def markdown_targets(paths):
    """收集当前 Markdown 的显式本地链接；链接目标仍保留在原路径。"""
    targets = {}
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig")
        raw_links = re.findall(r"\]\(\s*(<[^>]+>|[^)\r\n]+)\)", text)
        raw_links += re.findall(r"^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)", text, flags=re.MULTILINE)
        raw_links += re.findall(r"href=[\"']([^\"']+)[\"']", text)
        for raw in raw_links:
            value = raw[1:raw.index(">")] if raw.startswith("<") else re.sub(r"\s+[\"'][^\"']*[\"']\s*$", "", raw).strip()
            parsed = urlsplit(value)
            if parsed.scheme and not re.match(r"^[A-Za-z]:[/\\]", value):
                continue
            target_text = unquote(value.split("#", 1)[0].split("?", 1)[0])
            if not target_text:
                continue
            target = Path(target_text)
            if not target.is_absolute():
                target = path.parent / target
            targets.setdefault(target.resolve(), []).append(str(path))
    return targets


def call_signature(result):
    rows = []
    for call in result["真实调用"]:
        logical = []
        for location in call["保存位置"]:
            if "!" in location:
                container, member = location.split("!", 1)
                location = str(PurePosixPath(container).parent / member)
            logical.append(location)
        rows.append({"线程": call.get("Codex会话"), "逻辑路径": sorted(set(logical)),
                     "操作": call["操作"], "状态": call["状态"], "模型": call.get("模型"),
                     "输入指纹": sorted({x["stdin_LF_SHA256"] for x in call["输入指纹核对"]}),
                     "输入全部匹配": all(x["输入指纹匹配"] for x in call["输入指纹核对"]),
                     "图片核对数": call["图片核对数"], "用量": call.get("用量"), "耗时毫秒": call.get("耗时毫秒")})
    return sorted(rows, key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True))


def require_audit(scope):
    result = auditor.audit(scope, require_complete=True)
    if result["问题数"] or result["在途调用数"]:
        raise ValueError(f"原审计器未通过：{scope.name}，问题 {result['问题数']}，在途 {result['在途调用数']}")
    return result


def formal_batch_finished():
    config = read_json(ROOT / "新样本/正式配置冻结.json")
    scope_path = ROOT / "新样本/用户缩减范围记录.json"
    planned = set(config["正式轮次"])
    started = planned
    if scope_path.is_file():
        scope = read_json(scope_path)
        if scope.get("用户新要求") != "15分钟内完成测试，不必严格九轮":
            raise ValueError("执行范围调整缺少本次用户决定。")
        done = scope["正式已自然归档"]
        finishing = scope["正式已启动待收尾"]
        cancelled = scope["取消未启动"]
        labels = done + finishing + cancelled
        if len(labels) != len(set(labels)) or set(labels) != planned:
            raise ValueError("缩减范围必须完整且无重复地列明原计划轮次。")
        started = set(done + finishing)
        for label in cancelled:
            sample, round_no = label.rsplit("-", 1)
            path = ROOT / "新样本/原生评审" / f"{config['正式批次']}-{sample}-第{round_no}轮"
            if path.exists() and (list(path.rglob("调用记录.json")) or (path / "运行结果.json").exists()):
                raise ValueError(f"标为未启动取消的轮次已有执行证据：{label}")
    for label in sorted(started):
        sample, round_no = label.rsplit("-", 1)
        terminal_stage(ROOT / "新样本/原生评审" / f"{config['正式批次']}-{sample}-第{round_no}轮")
    # 诊断试点及其他已启动阶段同样须终态；取消未启动不算失败。
    for path in (ROOT / "新样本/原生评审").iterdir():
        if path.is_dir() and list(path.rglob("调用记录.json")):
            terminal_stage(path)
    require_audit(ROOT)


def verify_archive(path, originals):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        names = [item.filename for item in archive.infolist() if not item.is_dir()]
        expected_names = {"调用/" + name for name in originals} | {MANIFEST}
        assert len(names) == len(set(names)) and set(names) == expected_names
        rows = json.loads(archive.read(MANIFEST))["文件"]
        assert len(rows) == len(originals)
        for row in rows:
            name = row["路径"]
            assert auditor.safe_name(name) and name.startswith("调用/")
            raw = archive.read(name)
            assert len(raw) == row["字节"] and digest(raw) == row["SHA256"]
            assert originals[name[len("调用/"):]] == {"字节": row["字节"], "SHA256": row["SHA256"]}


def pack_stage(stage, backup_root, markdown_files, *, apply=False, offline_fixture=False):
    allowed = TEST_ROOT if offline_fixture else ROOT
    stage = checked_path(stage, allowed)
    backup_root = checked_path(backup_root, WORK)
    if backup_root.is_relative_to(stage) or stage.is_relative_to(backup_root):
        raise ValueError("源阶段和备份目录必须分离。")
    if os.path.lexists(backup_root):
        raise FileExistsError("备份目录已经存在，请使用新的名称。")
    terminal = terminal_stage(stage)
    if not offline_fixture:
        formal_batch_finished()
    before_audit = require_audit(stage)
    links = markdown_targets(markdown_files)
    plans = []
    for relative in CALL_PATHS:
        directory = stage / relative
        if not directory.exists():
            continue
        checked_path(directory, stage)
        originals = fingerprint(directory)
        records = terminal_calls(directory)
        retained = {p.relative_to(directory).as_posix() for p in records}
        linked = {p.relative_to(directory).as_posix(): sources for p, sources in links.items()
                  if p.is_relative_to(directory) and p.is_file()}
        retained.update(linked)
        archive = directory.with_name("调用原件.zip")
        if os.path.lexists(archive):
            raise FileExistsError(f"ZIP 已存在，不覆盖：{archive}")
        plans.append({"directory": directory, "relative": relative, "originals": originals,
                      "retained": retained, "linked": linked, "archive": archive})
    if not plans:
        raise ValueError("指定阶段没有约定位置的调用目录。")
    public_plan = {"阶段": str(stage), "备份根目录": str(backup_root), "离线小样本": offline_fixture,
                   "目录": [{"调用目录": p["relative"].as_posix(), "原文件数": len(p["originals"]),
                             "保留原路径": sorted(p["retained"]), "Markdown链接": p["linked"],
                             "ZIP": p["archive"].name} for p in plans]}
    if not apply:
        return {"状态": "仅预览，未移动文件", **public_plan}
    backup_root.mkdir(parents=True, exist_ok=False)
    save(backup_root / "执行计划.json", public_plan)
    save(backup_root / "归档前审计.json", before_audit)
    moved = []
    try:
        for index, plan in enumerate(plans):
            prepared = backup_root / "预备保留件" / str(index)
            prepared.mkdir(parents=True)
            for name in sorted(plan["retained"]):
                target = prepared / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(plan["directory"] / name, target)
            assert fingerprint(prepared) == {name: plan["originals"][name] for name in plan["retained"]}
            temporary_zip = backup_root / f"预备调用原件-{index}.zip"
            rows = [{"路径": "调用/" + name, **value} for name, value in sorted(plan["originals"].items())]
            with zipfile.ZipFile(temporary_zip, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
                for row in rows:
                    archive.write(plan["directory"] / row["路径"][len("调用/"):], row["路径"])
                archive.writestr(MANIFEST, json.dumps({"文件": rows}, ensure_ascii=False, indent=2) + "\n")
            verify_archive(temporary_zip, plan["originals"])
            plan.update(prepared=prepared, temporary_zip=temporary_zip,
                        backup=backup_root / "完整原目录" / plan["relative"])
        # 所有 ZIP 和保留件准备成功后，最后再次确认终态和源字节，再开始移动。
        assert terminal_stage(stage) == terminal
        for plan in plans:
            terminal_calls(plan["directory"])
            assert fingerprint(plan["directory"]) == plan["originals"]
        for plan in plans:
            safe_move(plan["directory"], plan["backup"], stage, WORK)
            moved.append(plan)
            safe_move(plan["prepared"], plan["directory"], WORK, stage)
            safe_move(plan["temporary_zip"], plan["archive"], WORK, stage)
            plan["archive_promoted"] = True
            assert fingerprint(plan["backup"]) == plan["originals"]
            assert fingerprint(plan["directory"]) == {name: plan["originals"][name] for name in plan["retained"]}
        after_audit = require_audit(stage)
        assert call_signature(before_audit) == call_signature(after_audit), "原审计器的线程、返回、输入或图片配对发生变化。"
        assert terminal_stage(stage) == terminal
        for plan in plans:
            verify_archive(plan["archive"], plan["originals"])
        save(backup_root / "归档后审计.json", after_audit)
        result = {"状态": "归档完成", **public_plan, "原审计器核对通过": True,
                  "真实CLI记录数": after_audit["真实CLI记录数"], "调用状态": after_audit["调用状态"],
                  "线程输入图片签名保持": True,
                  "归档": [{"ZIP": str(p["archive"]), "ZIP_SHA256": digest(p["archive"].read_bytes()),
                            "完整原目录备份": str(p["backup"]), "原文件数": len(p["originals"]),
                            "CRC及全部成员SHA通过": True, "备份和保留件原字节保持": True} for p in plans]}
        save(backup_root / "打包结果.json", result)
        return result
    except Exception as error:
        # 失败时先保留新产生的目录/ZIP，再恢复完整原目录；不递归删除任何文件。
        restored = []
        for index, plan in reversed(list(enumerate(moved))):
            if plan["directory"].exists():
                safe_move(plan["directory"], backup_root / "失败保留件" / str(index), stage, WORK)
            if plan.get("archive_promoted") and plan["archive"].exists():
                safe_move(plan["archive"], backup_root / f"失败归档-{index}.zip", stage, WORK)
            safe_move(plan["backup"], plan["directory"], WORK, stage)
            assert fingerprint(plan["directory"]) == plan["originals"]
            restored.append(plan["relative"].as_posix())
        save(backup_root / "执行异常.json", {"错误": str(error), "已恢复完整原目录": restored})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, help="一个已结束的阶段目录")
    parser.add_argument("--backup-root", required=True, help="work 内尚不存在的独立备份目录")
    parser.add_argument("--markdown", action="append", help="额外核对的 Markdown 文件，可重复")
    parser.add_argument("--offline-fixture", action="store_true", help="仅允许 work/d_final_pack_calls_test 内的小样本")
    parser.add_argument("--apply", action="store_true", help="执行归档；默认仅预览")
    args = parser.parse_args()
    markdown = [REPO / "README.md", *(REPO / "docs").rglob("*.md"), *map(Path, args.markdown or [])]
    output = pack_stage(Path(args.stage), Path(args.backup_root), markdown,
                        apply=args.apply, offline_fixture=args.offline_fixture)
    print(json.dumps(output, ensure_ascii=False, indent=2))
