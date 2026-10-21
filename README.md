# 《智能设计系统与管理策略》课程项目仓库

**核心命题**：交互方案评审skill

## 当前可提交成果

- **D 测试与文档交付**：[阶段性报告](docs/D-阶段性报告.md) · [本轮开发测试总览](docs/D-本轮开发测试总览.md) · [完整材料下载](docs/D-发布索引.md) · [真人执行清单](docs/D-真人材料执行清单.md)
- **单案例引用口径**：[D 复核勘误](docs/D-单案例复核勘误.md)。原始归档保留；引用下方报告时须同时采用勘误中的计数、覆盖范围、耗时与证据限制。
- **最新单样本审查报告**：
  [商业手游角色试用页综合报告](deliverables/2026-10-21-character-trial/report-showcase.md)
- **案例交接页**：
  [2026-10-21-character-trial](deliverables/2026-10-21-character-trial/README.md)
- **机器可读结果**：
  [report.json](deliverables/2026-10-21-character-trial/report.json)
- **过程与耗时**：
  [manifest.json](deliverables/2026-10-21-character-trial/manifest.json)

该报告包含成果截图、原型参考、过程叠加图、各阶段输入输出、指标解释、判据相关性、目标检查和源数据文件索引。此单样本结果用于 MVP 效果展示，不代表统计意义上的召回率或误报率。

## 快速交接

### 1. 环境

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

开发与测试：

```powershell
python -m pip install -r requirements-dev.txt
```

可选本地模型路径需要 64 位 Python 3.11+ 和至少 16 GB 显存，依赖见
[`requirements-perception.txt`](requirements-perception.txt)。

### 2. 千问 AI 平台 API Key

我用的是千问 AI 平台 API Key，如果有更好的平台可以换源，需要有以下能力的模型
- 视觉理解：`qwen3.8-flash`
- 综合推理：`qwen3.8-max-0902`
- 判据相关性：文本向量、文本重排、多模态向量和多模态重排
- GUI 操作辅助：`gui-plus-2026-02-26`

平台入口：

- [千问 AI 平台](https://www.qianwenai.com/)
- [模型列表](https://www.qianwenai.com/models)
- [API Key 文档](https://platform.qianwenai.com/docs/developer-guides/administration/api-keys)

获取 Key 后创建本地配置：

```powershell
Copy-Item .\config\reviewer.example.toml .\config\reviewer.toml
```

在 `config/reviewer.toml` 的 `providers.qwen.api_key` 中填写 Key。配置文件包含密钥，请勿提交。完整说明见
[`docs/config-setup.md`](docs/config-setup.md)。

### 3. 启动前检查

```powershell
python -m engine validate-config
python -m engine validate-criteria
python -m pytest -q
```

### 4. 分阶段运行

```powershell
python -m engine stage-init .\screen.png `
  --reference .\prototype.png `
  --goal-file .\design-goal.txt `
  --platform game

python -m engine stage <run_dir> ocr
python -m engine stage <run_dir> ui
python -m engine stage <run_dir> reference_ui
python -m engine stage <run_dir> goal
python -m engine stage <run_dir> metrics
python -m engine stage <run_dir> relevance
python -m engine stage <run_dir> audit
python -m engine stage <run_dir> report
python -m engine stage <run_dir> narrative
```

每一步的状态、耗时、模型、token 使用量、原始响应和解析结果都会写入运行目录。完整说明见
[`docs/staged-workflow.md`](docs/staged-workflow.md)。

### 5. 归档验收成果

- `deliverables/<日期>-<case-slug>/`：验收后计划提交的完整成果。
- 已验收运行不得原地覆盖；重跑必须建立新的 `run-id`。
- 命名和归档规则见 [`deliverables/README.md`](deliverables/README.md)。

## B 引擎（交互评审 API）

核心分析链和 C 的接入契约见 [`docs/b-engine.md`](docs/b-engine.md)。
升级后的感知、判据相关性、可计算参数和评估方案见
[`docs/b-engine-v2-plan.md`](docs/b-engine-v2-plan.md)，模型 Key 填写方式见
[`docs/config-setup.md`](docs/config-setup.md)。
分阶段运行、缓存和本地验收方式见
[`docs/staged-workflow.md`](docs/staged-workflow.md)。

```powershell
python -m pip install -r requirements.txt
python -m engine validate-config
python -m engine validate-criteria
python -m engine serve --port 8000
```

主要接口为 `POST /api/review-audit`，健康检查为 `GET /healthz`，接口文档位于 `http://127.0.0.1:8000/docs`。



## 仓库结构

```
.
├── README.md
├── config/                # 模型配置模板与字段说明
├── deliverables/          # 验收后计划提交的审查成果
│   └── 2026-10-21-character-trial/
├── docs/                  # 架构、配置、分阶段运行与 API 文档
├── engine/                # B 引擎代码
├── materials/             # 课程资料
├── reference/
│   └── skills/            # 4 个同类开源 skill
├── tests/                 # 单元与接口测试
├── 判据库_v1.json         # A 方法专家交付的 24 条判据
├── requirements.txt
├── requirements-dev.txt
└── requirements-perception.txt
```

## 当前进度

2026 年 10 月 21 日，D 已完成 10 张开发图的评审，形成 24 项具体发现；P01 新口径评审另有 2 项目标建议。累计保存 14 次 Codex 视觉评审，新增 9 次运行的 167/167 项结构检查全部通过。

25 条作者候选已完成逐项对照：22 条完整对应、1 条范围收敛、1 条部分对应、1 条判定依据不同；S08 另发现 1 项持续提示问题。前期程序修复的最新回归为 64/64，S03 与 S07 修复回放各通过 14/14 项检查。

C 已交付 `frontend/` 与课程报告初稿。D 完成 9/9 项前端测试、8/8 项 S07 保存结果适配核对，以及 11/11 项模拟操作与字段保存核对，四轮导出和刷新恢复记录均已归档。

[D 阶段性报告](docs/D-阶段性报告.md)与[本轮开发测试总览](docs/D-本轮开发测试总览.md)汇总结果；[发布索引](docs/D-发布索引.md)提供完整材料和逐文件定位。两位评审者标注、P01 五秒识别、工具计时和问卷材料已经备齐，接续按[真人执行清单](docs/D-真人材料执行清单.md)回收记录并统稿。

## 中期汇报 · 四人分工

**v1 范围**：界面截图 + 第①层通用交互原则 + 四段式意见（原则 → 检测 → 描述 → 建议）。
规范溯源、场景专项不做，留给 v2/v3。

### A · 方法专家

**判据库 v1**（大）
把启发式评审的判据整理成引擎能直接调用的条目：判据内容、出处、适用界面类型。先做第①层通用交互原则 20–30 条。
→ 交给 B 接引擎。**完成标志**：B 能直接用它给一张截图产出带出处的意见。

**方法五要素拆解**（中）
输入 / 过程（7 步）/ 输出 / 决策点（评估性·方向性·解释性·边界性）/ 痛点（时间·认知·一致性·遗漏），并挑出关键决策点与最痛痛点。

**五维评估方案**（中）
准确性、一致性、可解释性、效率、体验，每维定一个可执行指标；信度用与资深设计师对照的召回率 / 误报率。
→ 交给 D 落成测试。

**报告**：I.2 项目定义 · II.1 五要素 · II.2 AI 能力映射 · III.3 评估框架

### B · Vibe Coder（引擎）

**核心分析链**（大）
截图 → 多模态视觉理解 → 判据库匹配 → 逐条检测 → 四段式意见。这是 Skill 的"心脏"。
**完成标志**：一张图进，一份带证据锚点和判据出处的问题清单出。

**输入输出契约**（中）
各环节的入参、返回字段和取值范围定死，并处理模型输出不稳定的情况。
→ 交给 C 做界面、D 做统计。

**报告**：III.1 架构选择（含双维度评分）· III.4 设计文档概述 · IV.1 MVP 边界 · IV.2 前两轮

### C · Vibe Coder（交互集成）

**界面与评审流程**（大）
上传截图 → 问题清单 → 人工干预 → 导出评审报告。
**完成标志**：不碰代码的人也能自己跑完一整遍。

**四个 HITL 节点**（中）
确认设计目标 / 确认·驳回发现 / 严重度校准 / 复审闭环。用户的修改要能回流触发重算，而不只是改显示。

**报告**：III.2 人机协同设计 · IV.2 第三轮 · IV.3 MVP 现状与已知问题

### D · 测试与文档

**测试方案与数据**（中）
10 条界面样本 + 20–30 条专家参考标注；与 2 位资深设计师人工评审对照，定好召回率 / 误报率的算法。
→ 依赖 A 的评估方案。

**测试执行与汇总**（大）
效率计时、6–8 人的瞬时识别小实验、主观体验问卷，汇总成一张结果表。
→ 交给 A 写 III.3。

**归档与统稿**（大）
收拢四人的对话日志与关键提示词。各节初稿由主责人写，D 只统稿不代写。

**报告**：I.1 小组信息 · III.3 量化结果 · IV.3 运行日志 · V Vibe Coding 总结 · 附录

### 依赖与并行

- **判据库是唯一的硬前置**：B 和 C 在它交付前用 mock 数据推进，不要等。
- 三条线可并行：A（方法）· B+C（技术）· D（测试准备）。
- 收口只在两处：10/20 测试执行、10/22 统稿。

### 顺序

| 时间 | 交什么 |
| --- | --- |
| 10/16 五 | 判据库骨架（A）· 最小闭环：1 张图→1 条意见（B）· 界面骨架 mock（C）· 日志模板 + 模拟数据（D） |
| 10/17 六 | 判据库 20–30 条（A）· 引擎接真实判据库（B）· 界面接真实后端（C）· 测试方案（D） |
| 10/18 日 | 五要素拆解定稿（A）· 四段式打磨（B）· 四个 HITL 节点（C）· 样本 + 参考标注（D） |
| 10/19 一 | 报告 II / III 初稿（A 主笔，D 汇总） |
| 10/20 二 | 测试执行（D 牵头，A 当资深设计师） |
| 10/21 三 | 报告 IV / V 初稿 + 录屏 |
| 10/22 四 | 统稿提交（20:00 前） |

## 相关链接

**同类开源 Skill**（本地副本见 `reference/skills/`）

- [refactoring-ui-plugin](https://github.com/gnurio/refactoring-ui-plugin) — 把《Refactoring UI》拆成 10 个原子技能 + 1 个 meta 技能
- [material-design-3-ui-skill](https://github.com/skydashnet/material-design-3-ui-skill) — 以 M3 官方规范为 source of truth，要求先核对官方指南再断言
- [design_skill](https://github.com/grapeot/design_skill) — "确定性工具给事实，模型给判断"
- [ai-friendly-web-design-skill](https://github.com/ianho7/ai-friendly-web-design-skill) — 输出带严重度分级
- [knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins) — Anthropic 官方 Design Plugin，可作参照

**同类产品**

- [UX Audit AI](https://uxaudit.tech)
- [Heustrics](https://heustrics.com)
- [Attention Insight](https://attentioninsight.com)
