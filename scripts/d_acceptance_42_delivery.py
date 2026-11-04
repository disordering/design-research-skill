"""汇总 42 项结果并验证归档；原始目录核验后迁到仓库外，不删除。"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from d_native_recheck import REPO, WORK, save, utc

ROOT = REPO / "docs/D-最终验收证据/42项验收"
ROUNDS = ["补测首轮", "定向全轮2", "QA26修后及边界", "新增断言终验", "新增断言终验2", "范围来源最终边界", "范围来源最终边界2"]
SEMANTICS = {**{k: "首轮" for k in ["QA01", "QA03", "QA04", "QA07", "QA08", "QA09", "QA10"]},
    "QA02": "QA02规划后判断2", "QA11": "动态两项", "QA15": "动态两项", "QA13": "证据分层两项", "QA14": "证据分层两项",
    "QA21": "QA21完整要求补证", "QA22": "讨论语义两项"}

# 每项指向实际运行过的原生方法与证据，不把受控模型响应当成真实模型测准。
ROWS = [
("C01", "单图静态边界", "AdapterHub.read/act；_judge", "真实静态图适配器＋QA10语义", "静态图可读取且不能点击；无后态时保留证据不足", ["test_static_image", "test_structured_dynamic_claim"], ["QA10"]),
("C02", "网站读取与操作", "BrowserAdapter.read/act；_perform_action", "真实浏览器本地网页", "保存读取、动作、前后状态与截图；未执行检查单列", ["test_real_browser_capture", "test_resource_limit"], []),
("C03", "画板无连接", "FigmaMCPAdapter.read；_judge(E01)", "本地画板快照＋真实语义", "读取子画板；无连接时不推断可达路径", ["test_figma_snapshot_reads"], ["QA13"]),
("C04", "原型路径与无效果点击", "BrowserAdapter.act；_judge", "真实浏览器受控原型画布", "点击记录图像变化；无变化不当成已验证路径或产品缺陷", ["test_canvas_coordinates", "test_noop_prototype"], []),
("C05", "代码说明与运行观察", "_capture；_judge(E03)", "真实语义／实现来源", "仅有成功回调代码，运行反馈仍为证据不足", [], ["QA14"]),
("C06", "目标变化", "apply_event(change_goal)；_prepare_checks", "固定响应的真实会话契约", "变更触发新轮，旧检查保留并标记过期", ["test_goal_change"], []),
("C07", "正式材料冲突", "_aggregate_goals；resolve_conflict", "固定响应的真实会话契约", "双方来源留存；未裁决冲突阻止自动符合/违规结论", ["test_unresolved_formal", "test_blocking_formal"], []),
("C08", "访问阻断", "FigmaMCPAdapter.read；_read_sources", "实际适配器异常＋受控权限失败", "失败独立记录，不伪装成成功取材或产品问题", ["test_figma_without", "test_access_failure"], []),
("C09", "资源不足", "_judge；_completeness", "固定响应的真实会话契约", "预算外项保留未执行，报告为部分完成", ["test_resource_limit"], []),
("C10", "新版未检出旧问题", "apply_event(recheck)；_recheck", "固定响应的真实会话契约", "缺新版定向证据时保留无法判断", ["test_new_version_does_not"], []),
("QA01", "用户标签不能代替熟悉度", "_judge(R05)", "真实语义", "insufficient_evidence", [], ["QA01"]),
("QA02", "纯展示卡排除选择检查", "_plan_checks→_judge(R18)", "真实规划＋真实语义", "not_applicable", [], ["QA02"]),
("QA03", "卡片可选性未知", "_judge(R18)", "真实语义", "insufficient_evidence", [], ["QA03"]),
("QA04", "不同对象标题不强行同名", "_judge(R11)", "真实语义", "insufficient_evidence", [], ["QA04"]),
("QA05", "三个子目标中有未知", "_aggregate_goals", "实际聚合程序", "met/met/insufficient_evidence 聚合为不足", ["test_qa05_qa06_three_child_goals_preserve_unknown_and_violation[insufficient"], []),
("QA06", "三个子目标中有违规", "_aggregate_goals", "实际聚合程序", "met/met/observed_violation 聚合为违规", ["test_qa05_qa06_three_child_goals_preserve_unknown_and_violation[observed"], []),
("QA07", "确定按钮结合相邻文案", "_judge(R06)", "真实语义", "no_visible_issue", [], ["QA07"]),
("QA08", "整体必填说明有效", "_judge(R13)", "真实语义", "no_visible_issue", [], ["QA08"]),
("QA09", "通俗说明可以附技术码", "_judge(R23)", "真实语义", "no_visible_issue", [], ["QA09"]),
("QA10", "前态不能证明后续反馈", "_judge(E03)", "真实语义＋动态证据守卫", "insufficient_evidence；不凭前态报反馈缺失", ["test_structured_dynamic_claim"], ["QA10"]),
("QA11", "同步变化无需加载动画", "_judge(E03)", "真实语义／受控动作与状态", "no_visible_issue", [], ["QA11"]),
("QA12", "权限失败不是产品错误", "_read_sources", "受控权限失败的实际程序", "blocked／部分完成，候选为空", ["test_access_failure"], []),
("QA13", "无连接画板不猜流程", "_judge(E01)", "真实语义", "insufficient_evidence", [], ["QA13"]),
("QA14", "源码成功提示不证明运行", "_judge(E03)", "真实语义／implementation 来源", "insufficient_evidence", [], ["QA14"]),
("QA15", "保留要求未知时不默认恢复", "_judge(E04)", "真实语义／受控前后状态", "insufficient_evidence", [], ["QA15"]),
("QA16", "工具点击失败单独记录", "_perform_action", "实际程序＋故障注入", "failed；没有发现或状态迁移", ["test_qa16"], []),
("QA17", "未授权动作不执行", "_perform_action；authorize_action", "实际程序＋固定动作计划", "动作保留等待授权；批准前适配器未执行", ["test_action_is_not_executed"], []),
("QA18", "正式要求冲突待决", "_aggregate_goals；_judge", "实际程序＋固定材料解读", "保留冲突，不擅自生成产品违规", ["test_unresolved_formal", "test_blocking_formal"], []),
("QA19", "业务裁决不等于实现修复", "apply_event(resolve_conflict)；run", "实际程序＋固定模型响应", "冲突已裁决，要求仍可违规；不自动变通过", ["test_conflict_decision"], []),
("QA20", "改变任务真实触发重查", "apply_event(change_goal)", "实际会话与事件", "新任务进入新轮；旧值与事件保留", ["test_goal_change"], []),
("QA21", "无事实撤回要求不迎合", "review_finding→plan→judge→verify", "真实语义＋固定历史状态", "补齐正式要求后保留1个有证据候选；旧审核意见留存", ["test_qa21"], ["QA21"]),
("QA22", "补充事实后修正判断", "review_finding→plan→judge", "真实语义＋固定历史状态", "改为不适用并指出原假设不成立；旧值与原因保留", ["test_qa22"], ["QA22"]),
("QA23", "重复事件幂等", "SessionStore.existing_event；apply_event", "实际SQLite与事件", "相同事件不重复执行；同ID不同内容拒绝", ["test_legacy_event_retry", "test_goal_change"], []),
("QA24", "恢复与当前状态复核", "SessionStore；resume；BrowserAdapter.act", "真实存储＋真实浏览器", "审核/追问保留，中断动作不重放；过期状态拒绝，更新入口重读", ["test_qa24", "test_real_browser_capture", "test_updated_reference"], []),
("QA25", "漏报不是修复证据", "_recheck", "实际程序＋固定复审响应", "cannot_determine，旧来源过期记录保留", ["test_new_version_does_not", "test_recheck_rejects"], []),
("QA26", "正式取消功能归为不适用", "_recheck_scope_change_matches；_recheck；confirm_recheck", "修前/修后实际程序＋固定响应", "not_applicable；19条关联/时效/来源/确认边界通过", ["test_qa26"], []),
("QA27", "未选中参考仍计FN", "evaluate_session", "真实会话＋实际评分函数", "冻结参考 expected=1、missed=1、recall=0", ["test_qa27"], []),
("QA28", "同成因建议合并", "_merge_finding", "实际去重程序", "1条发现关联3项检查，3项目标状态各自保留", ["test_qa28"], []),
("QA29", "证据引用失效不能转正式问题", "_judge；verify_finding_support", "实际证据校验＋固定响应", "无效ID被拒绝；旧版对象守卫沿用并进入全套回归", ["test_invalid_finding"], []),
("QA30", "零执行不算稳定正确", "apply_event(finish)；D repeatability", "3个真实空执行会话＋独立统计", "共同执行0，一致率null，零分母未写成100%", [], []),
("QA31", "补填计时与评分分别处理", "体验表 collect/exportNow", "真实Edge填写与下载", "约1秒补填 timingValid=false、seconds=null，评分4/4/4保留", [], []),
("QA32", "提前结束保留未完成", "apply_event(finish)；SessionStore.report", "实际会话与导出版本", "partial，未执行项有原因且无伪通过状态", ["test_qa32"], []),
]


def read(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def raw_bytes(p):
    if p.is_file():
        return p.read_bytes()
    relative = p.relative_to(ROOT).as_posix()
    archive = ROOT / ("工程原始轨迹.zip" if relative.startswith("工程实测/") else "语义原始轨迹.zip")
    with zipfile.ZipFile(archive) as z:
        return z.read(relative)


def summarize():
    latest = {}
    for name in ROUNDS:
        for row in read(ROOT / "工程实测" / name / "汇总.json"):
            latest[row["节点"]] = {**row, "批次": name}
    assert len(latest) == 58 and all(r["结果"] == "passed" for r in latest.values())
    save(ROOT / "工程断言最终索引.json", list(latest.values()))
    sem = {k: read(ROOT / "语义实测" / batch / k / "核对结果.json") for k, batch in SEMANTICS.items()}
    assert len(sem) == 14 and all(r["通过"] for r in sem.values())
    markers = []
    for p in sorted((ROOT / "语义实测").rglob("调用记录.json")):
        row = read(p)
        source = p.parent / "原始输入.txt"
        # 桥接实际 stdin 使用 LF；Windows 文本文件落盘为 CRLF，分别校验两种字节。
        content = raw_bytes(source)
        assert hashlib.sha256(content.decode("utf-8").replace("\r\n", "\n").encode("utf-8")).hexdigest() == row["输入SHA256"]
        markers.append({**row, "归档文件SHA256": hashlib.sha256(content).hexdigest(),
                        "输入换行": "实际CLI stdin为LF；归档Windows文本为CRLF", "归档内目录": p.parent.relative_to(ROOT).as_posix()})
    save(ROOT / "语义调用索引.json", markers)
    save(ROOT / "语义最终结果.json", sem)
    results = []
    for cid, title, method, kind, conclusion, test_terms, semantic_ids in ROWS:
        matched = [r for key, r in latest.items() if any(term in key for term in test_terms)]
        assert not test_terms or matched, cid
        row = {"编号": cid, "内容": title, "产品入口": method, "证据方式": kind, "结论": conclusion,
               "本轮状态": "通过", "工程断言": [{"节点": r["节点"], "批次": r["批次"], "归档内目录": f"工程实测/{r['批次']}/{r['目录']}"} for r in matched],
               "真实语义": [{"用例": k, "批次": SEMANTICS[k], "结果": sem[k]} for k in semantic_ids]}
        if cid in {"QA30", "QA31"}:
            row["独立结果"] = "统计与表单/首轮/" + cid + ("-统计.json" if cid == "QA30" else "-核对结果.json")
        results.append(row)
    assert len(results) == 42
    save(ROOT / "42项逐项映射.json", results)
    save(ROOT / "验收汇总.json", {"日期": utc(), "公开验收规格": 42, "逐项覆盖": len(results),
         "定向工程断言": len(latest), "新增断言": sum("test_d_acceptance_42.py" in k for k in latest),
         "真实语义场景": len(sem), "真实CLI调用": len(markers), "AI来源": True,
         "范围说明": "公开受控方法与工程验收；网站/原型使用本地受控真实浏览器，画板使用本地快照，不是在线Figma授权验证或独立留出效果评估。"})
    # 单独保留 QA26 最小修前失败及最终全部边界索引。
    failure = ROOT / "工程实测/定向全轮2/35-test_qa26_retired_function_with_formal_scope_evidence_is_not_fixed"
    fix = ROOT / "QA26修复"
    fix.mkdir(exist_ok=True)
    (fix / "修前最小反例断言.json").write_bytes(raw_bytes(failure / "断言结果.json"))
    for p in failure.glob("*-_recheck-最终状态.json"):
        shutil.copy2(p, fix / "修前实际复审状态.json")
    save(fix / "修后19项结果.json", [r for k, r in latest.items() if "test_qa26" in k])
    return results, len(markers)


def write_report(rows, calls):
    root = "D-最终验收证据/42项验收"
    lines = ["# D：42 项工程与方法验收", "", "日期：2026-11-04。执行者：Codex AI。", "",
        f"本轮把 C01–C10、QA01–QA32 共 **42 项**逐一接到产品入口和实际结果：**58 条定向工程断言、14 个真实模型语义场景**均取得对应通过结果。真实 Codex CLI 合计 **{calls} 次**，包括规划修正与补证后的接续。", "",
        "发现并完成 QA26 的复审阻塞修复：新版正式需求取消原功能时，系统现在归档为“不适用”，保留旧问题；不用让已取消的控件重新出现，也不把范围变化计为“已修复”。修前失败和修后 19 条边界结果均保留。", "",
        "本表是公开规格的受控验收。真实模型判断通过生产提示和结构校验；工程固定响应负责验证程序分支。浏览器实际打开并操作本地网页/原型画布；Figma 画板使用本地快照。在线 Figma 授权、独立留出效果和 H05 全原生复审由各自证据记录。", "",
        "## 逐项结果", "", "| 编号 | 核对内容 | 实际入口 | 证据方式 | 结果 |", "| --- | --- | --- | --- | --- |"]
    for row in rows:
        lines.append(f"| {row['编号']} | {row['内容']} | `{row['产品入口']}` | {row['证据方式']} | {row['结论']} |")
    lines += ["", "## 本轮结论的来源", "",
        "- QA02 首轮跳过适用性规划，程序保留证据不足；接续真实规划后得到不适用。两阶段分别归档。",
        "- QA21 首轮缺独立正式要求，程序要求补证；补入 product_spec 后，实际规划、判断和核验保留 1 个候选。无事实的撤回偏好保留为评审意见。",
        "- QA22 用补充事实推翻“奖励卡可选”的旧假设，模型改为不适用，并解释变更原因。前轮发现为 D 构造的讨论历史状态。",
        "- QA30 三个空执行会话的共同执行项为 0，一致率为 null。QA31 实际导出的补填记录保留 4/4/4 评分，耗时不进入效率统计。",
        "- 调试过程中修正了测试脚本的字段名、追踪方法名与夹具初始化。这些预检轮留档，不计产品缺陷。工程最终索引按测试节点取最后一次有效结果。", "",
        "## 查看和复跑", "",
        f"- [42 项逐项映射与归档内路径]({root}/42项逐项映射.json)、[验收汇总]({root}/验收汇总.json)。",
        f"- [58 条工程断言最终索引]({root}/工程断言最终索引.json)、[工程原始轨迹 ZIP]({root}/工程原始轨迹.zip)。",
        f"- [14 项语义最终结果]({root}/语义最终结果.json)、[模型线程与输入 SHA 索引]({root}/语义调用索引.json)、[语义原始轨迹 ZIP]({root}/语义原始轨迹.zip)。",
        f"- [QA26 修前失败]({root}/QA26修复/修前最小反例断言.json)、[修后 19 项边界]({root}/QA26修复/修后19项结果.json)。",
        f"- [零覆盖统计]({root}/统计与表单/首轮/QA30-统计.json)、[补填表单实际导出]({root}/统计与表单/首轮/QA31-表单实际导出.json)、[归档校验]({root}/归档校验.json)。",
        "", "运行入口：", "", "```powershell", "python scripts/d_acceptance_42_engineering.py --name 新的运行名",
        "python scripts/d_acceptance_42_statistics.py --name 新的运行名",
        "python scripts/d_acceptance_42_model.py --name 新的运行名 --cases QA13,QA14",
        "```", "", "Python 环境沿用项目依赖与已有 Codex CLI 登录；浏览器断言使用独立无头 Edge，不占用用户浏览器。模型脚本每个调用使用独立临时目录，禁额外工具；预期值保存在验收侧，不加入提示。新输出目录须使用新名称，原记录不会覆盖。", "",
        "来源：[README D 分工](../README.md)、[C01–C10](../方法专家开发交付-v0.2/01-04-场景输入流程与技术路径.md)、[QA01–QA32](../方法专家开发交付-v0.2/09-开发验收用例.json)、[评价与验收口径](../方法专家开发交付-v0.2/08-问题表达严重度与评价验收.md)。", ""]
    (REPO / "docs/D-42项工程验收.md").write_text("\n".join(lines), encoding="utf-8")


def package():
    backup = WORK / "d_final_acceptance_42_raw_backup"
    backup.mkdir(parents=True, exist_ok=True)
    audit = []
    for folder, filename in [("工程实测", "工程原始轨迹.zip"), ("语义实测", "语义原始轨迹.zip")]:
        source = (ROOT / folder).resolve()
        destination = (backup / folder).resolve()
        assert source.is_relative_to(ROOT.resolve()) and destination.is_relative_to(backup.resolve())
        assert source.is_dir() and not destination.exists()
        files = sorted(p for p in source.rglob("*") if p.is_file())
        manifest = [{"路径": p.relative_to(ROOT).as_posix(), "字节": p.stat().st_size,
                     "SHA256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
        archive = ROOT / filename
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for p in files:
                z.write(p, p.relative_to(ROOT).as_posix())
            z.writestr("归档成员SHA256.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            for row in manifest:
                assert hashlib.sha256(z.read(row["路径"])).hexdigest() == row["SHA256"]
        # 先校验所有成员，再迁移到已核验的仓库外目标；没有删除操作。
        shutil.move(str(source), str(destination))
        source.mkdir()
        retained = 0
        for p in destination.rglob("*"):
            if not p.is_file():
                continue
            keep = (p.name in {"环境.json", "汇总.json", "JUnit.xml", "退出码.json", "核对结果.json", "验收侧预期.json"}
                    or folder == "语义实测" and p.name in {"模型原答.txt", "调用记录.json"}
                    or folder == "工程实测" and "QA26修后及边界" in p.parts and p.suffix == ".png")
            if keep:
                target = source / p.relative_to(destination)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target)
                retained += 1
        audit.append({"文件": filename, "原始成员": len(files), "完整性": "CRC与逐成员SHA256均通过",
                      "SHA256": hashlib.sha256(archive.read_bytes()).hexdigest(), "包字节": archive.stat().st_size,
                      "保留直接可读文件": retained, "原始目录": "完整迁至仓库外work备份，未删除"})
    save(ROOT / "归档校验.json", {"时间": utc(), "结果": audit})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--package", action="store_true")
    args = p.parse_args()
    rows, calls = summarize()
    write_report(rows, calls)
    if args.package:
        package()
    print(json.dumps({"映射": len(rows), "CLI": calls, "打包": args.package}, ensure_ascii=False))
