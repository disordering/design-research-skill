# 分阶段审查与本地验收

每次审查创建一个独立运行目录：

```text
out/stages/<run_id>/
  image.png
  reference.png
  manifest.json
  ocr.json
  ui.json
  reference_ui.json
  goal.json
  metrics.json
  relevance.json
  criteria_relevance.csv
  audit.json
  report.json
  overlay_elements.png
  overlay_focus.png
  raw/
    ocr.raw.txt
    ui.raw.txt
    reference_ui.raw.txt
    goal.raw.txt
    relevance.raw.txt
    audit.raw.txt
```

## 1. 创建运行

```powershell
python -m engine stage-init .\screen.png `
  --reference .\prototype.png `
  --goal-file .\design_goal.txt `
  --platform game `
  --scenario "商业手游角色试用页" `
  --target-user "中轻度手游玩家"
```

命令返回的 `run_dir` 用于后续所有阶段。

## 2. 逐阶段运行

```powershell
python -m engine stage <run_dir> ocr
python -m engine stage <run_dir> ui
python -m engine stage <run_dir> reference_ui
python -m engine stage <run_dir> goal
python -m engine stage <run_dir> metrics
python -m engine stage <run_dir> relevance
python -m engine stage <run_dir> audit
python -m engine stage <run_dir> report
```

每个命令只执行一个阶段。完成后检查对应 JSON 和 `raw/*.raw.txt`，确认结构、定位和语义后再继续。

## 3. 查看状态和耗时

```powershell
python -m engine stage-status <run_dir>
```

`manifest.json` 会记录每个阶段的状态、耗时、模型、token 使用量、原始输出和产物路径。

## 4. 缓存规则

- 已完成的阶段不会影响后续阶段复现。
- 单阶段失败时，前面的成功结果保留。
- `metrics` 和 `report` 不调用模型，可在模型结果不变时快速重算。
- `audit` 或 `report` 算法调整后，只需重跑受影响阶段。

## 5. 模型调整说明

实测中 `GUI-Plus` 更偏向输出 GUI 操作指令，不擅长遵循静态元素 JSON 契约，因此：

- 结构化 OCR 与 UI 解析使用 `qwen3.8-flash`。
- 目标拆解、判据相关性、最终综合审查使用 `qwen3.8-max-0902`。
- `GUI-Plus` 保留为点击性、下一步动作和 affordance 的后续辅助模型。
