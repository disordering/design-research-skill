# 角色试用页审查

## 成果入口

- [综合评审报告](./report-showcase.md)
- [机器可读报告](./report.json)
- [运行清单与耗时](./manifest.json)
- [输入设计目标](./design-goal.txt)

## 运行信息

| 字段 | 内容 |
| --- | --- |
| 案例 | 商业手游角色试用页 |
| 运行编号 | `20261021-030524-84e90f` |
| 审查日期 | 2026-10-21 |
| 总耗时 | 约 273.38 秒 |
| 成果截图 | Figma frame `60:16` |
| 设计目标与原型 | Figma frame `60:15` |
| 审查模型 | `qwen/qwen3.8-max-0902` |
| 通用判据 | `判据库_v1.json`，24 条 |

## 结论

程序最终审查模型报告：

- 0 条 critical
- 0 条 high
- 1 条 medium
- 0 条 low
- G01–G07 达成
- G08 观察到角色名用字不一致
- G09 因静态截图无法验证交互反馈，标记为证据不足

`G08` 表示本轮评审中的名称与上线质量目标，`F001` 表示该目标下发现的问题。G/F 编号只在当前运行内有效。

## 文件说明

| 文件或目录 | 用途 |
| --- | --- |
| `report-showcase.md` | 综合评审报告 |
| `report.json` | 完整结构化审查结果 |
| `manifest.json` | 各阶段状态、耗时、模型与 token 使用量 |
| `screenshot.png` | 被审查成果截图 |
| `prototype.png` | 原型参考图 |
| `design-goal.txt` | 本轮设计目标原文 |
| `ocr.json` / `raw/ocr.raw.txt` | OCR 解析与模型原始输出 |
| `ui-elements.json` / `raw/ui-elements.raw.txt` | 成果截图 UI 元素解析与原始输出 |
| `prototype-elements.json` / `raw/prototype-elements.raw.txt` | 原型元素解析与原始输出 |
| `goal-constraints.json` / `raw/goal-constraints.raw.txt` | 目标约束拆解与原始输出 |
| `metrics.json` | 确定性视觉、密度、可读性、原型对齐指标 |
| `criteria-relevance.json` / `criteria-relevance.csv` | 24 条判据的相关性分项与排序 |
| `audit.json` / `raw/audit.raw.txt` | 最终审查、规则状态、目标检查与原始输出 |
| `narrative.json` / `raw/narrative.raw.txt` | 综合报告结构化内容与原始输出 |
| `visual-ui-elements.png` | UI 元素框叠加图 |
| `visual-focus-proxy.png` | 视觉焦点代理叠加图 |
| `report-summary.md` | 程序生成的精简版报告 |
| `SHA256SUMS.txt` | 审查包完整性校验值 |

## 复现

```powershell
python -m engine stage-init .\screenshot.png `
  --reference .\prototype.png `
  --goal-file .\design-goal.txt `
  --platform game `
  --scenario "商业手游角色试用页" `
  --target-user "中轻度手游玩家"

python -m engine stage <new-run-dir> ocr
python -m engine stage <new-run-dir> ui
python -m engine stage <new-run-dir> reference_ui
python -m engine stage <new-run-dir> goal
python -m engine stage <new-run-dir> metrics
python -m engine stage <new-run-dir> relevance
python -m engine stage <new-run-dir> audit
python -m engine stage <new-run-dir> report
python -m engine stage <new-run-dir> narrative
```

复现会产生新的 `run-id`，不要把新结果覆盖到已验收目录。
