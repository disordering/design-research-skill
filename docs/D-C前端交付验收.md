# C 前端交付验收

验收版本：`9780c03`。日期：2026-10-21。

前端现有 **9 项离线测试全部通过**，6 个 JavaScript 文件语法检查全部通过。将 S07 修复后报告送入当前前端适配器，**8/8 项核对通过**：5 项具体问题、24 条判据及两处 R17 问题完整保留。

本次直接读取交付源码及四份根目录 C 说明，运行固定数据测试与保存结果的格式转换。执行范围不含浏览器操作或模型调用；浏览器验收另行留存。

## 测试结果

| 检查 | 数量 | 通过 | 原始证据 |
|---|---:|---:|---|
| 报告适配、字段校验、反馈上下文 | 4 | 4 | [frontend/tests/adapter.test.mjs:3](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/tests/adapter.test.mjs#L3) |
| mock 服务反馈与修改稿逻辑 | 2 | 2 | [frontend/tests/service.test.mjs:2](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/tests/service.test.mjs#L2) |
| 逐问题复审、证据要求、关联校验、导出文本 | 3 | 3 | [frontend/tests/recheck.test.mjs:4](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/tests/recheck.test.mjs#L4) |
| 源码语法 | 6 个文件 | 6 | [语法检查记录](D-发布索引.md#f395) |
| S07 保存结果的前端适配 | 8 项核对 | 8 | [S07 适配记录](D-发布索引.md#f398) |

9 项单元测试与 8 项 S07 数据核对分别统计。测试退出码为 0，失败、取消和跳过均为 0；Node 版本为 v24.15.0。[完整 stdout](D-发布索引.md#f394) · [机器可读验收记录](D-发布索引.md#f390)。

复现命令，在仓库 `frontend/` 目录执行：

```powershell
node --test --test-isolation=none tests/adapter.test.mjs tests/service.test.mjs tests/recheck.test.mjs
```

## 启动与数据入口

前端入口是 `frontend/server.mjs`，执行 `node server.mjs` 后访问 `http://127.0.0.1:4173`。前端使用 Node 内置模块。引擎模式通过本地 `/engine/` 代理调用 `127.0.0.1:8000`；后端入口为 `python -m engine serve --port 8000`。依据：[frontend/server.mjs:1](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/server.mjs#L1)、[README.md:111](https://github.com/disordering/design-research-skill/blob/9780c03/README.md#L111)。

| 模式 | 当前行为 | 代码依据 |
|---|---|---|
| 模拟演示 | 使用三个固定示例，反馈和复审采用预设逻辑 | [frontend/dist/review-service.js:3](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/review-service.js#L3) |
| 本地引擎 | 上传图片和目标字段至 B 的 `/api/review-audit`，完整保留原始报告 | [frontend/dist/engine-adapter.js:15](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/engine-adapter.js#L15) |
| stub / 引擎来源标识 | 按 B 返回的 `model.is_stub` 显示来源 | [frontend/dist/engine-adapter.js:6](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/engine-adapter.js#L6)、[frontend/dist/app.js:38](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/app.js#L38) |

前端源码已具备真实 B 接口适配。模型来源取自返回报告。本次 S07 使用已有 `codex-session` 结果做离线适配，新增模型调用为 0。

## 四个人工介入节点

| 节点 | 实际实现 | 代码与测试证据 |
|---|---|---|
| 目标确认 | 输入目标用户、任务、平台和场景；修改目标后调用评审并生成新轮次 | [frontend/dist/index.html:9](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/index.html#L9)、[frontend/dist/app.js:22](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/app.js#L22)、[frontend/dist/app.js:30](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/app.js#L30) |
| 发现审核 | 确认、驳回、待验证、撤销审核；审核理由输入时保存 | [frontend/dist/app.js:24](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/app.js#L24)、[frontend/dist/app.js:25](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/app.js#L25) |
| 严重度校准 | 严重、高、中、低四级可调，原始等级保存在 `originalSeverity`，反馈包含原值和修改值 | [frontend/dist/app.js:26](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/app.js#L26)、[frontend/dist/engine-adapter.js:10](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/engine-adapter.js#L10)、[frontend/tests/adapter.test.mjs:6](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/tests/adapter.test.mjs#L6) |
| 复审闭环 | 新截图再次进入 B；每条旧问题生成候选关联，由人选择结论、填写理由与新版证据，保存并导出 | [frontend/dist/app.js:32](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/app.js#L32)、[frontend/dist/app.js:43](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/app.js#L43)、[frontend/dist/recheck-supplement.js:11](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/recheck-supplement.js#L11)、[frontend/tests/recheck.test.mjs:4](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/tests/recheck.test.mjs#L4) |

复审记录采用 `c-recheck-1.0`，包含前后报告 ID、旧问题 ID、候选与确认关联、解决状态、理由、新版证据、人工确认状态和时间。当前是 C 辅助人工复审流程。对应字段见 [frontend/dist/recheck-supplement.js:3](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/recheck-supplement.js#L3)。

## 反馈、保存与导出

引擎模式的“提交反馈”确实再次执行 `POST /api/review-audit`。`scenario` 汇入旧问题摘要、人工审核状态、原/新严重度、理由和本轮意见；超过 2000 字时在发出请求前提示调整。离线测试核对了反馈字段与超限行为。依据：[frontend/dist/app.js:29](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/app.js#L29)、[frontend/dist/engine-adapter.js:8](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/engine-adapter.js#L8)、[frontend/tests/adapter.test.mjs:6](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/tests/adapter.test.mjs#L6)。

数据保存到 IndexedDB 的 `mingjian/records`，旧 localStorage 记录自动迁移。Markdown 包含模型来源、版本、四段式意见、人工审核、判据、反馈上下文、逐问题复审结论及日志。逐问题导出文本通过现有测试。依据：[frontend/dist/storage.js:1](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/storage.js#L1)、[frontend/dist/app.js:11](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/app.js#L11)、[frontend/dist/app.js:36](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/app.js#L36)、[frontend/dist/recheck-supplement.js:18](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/recheck-supplement.js#L18)。

版本记录按 ID 保存。引擎每轮的新 `review_id` 可形成独立历史；mock 重评沿用同一 ID、递增版本并更新该记录。D 的历史版本验收应分别记录两种模式。依据：[frontend/dist/review-service.js:9](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/review-service.js#L9)、[frontend/dist/app.js:13](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/app.js#L13)、[frontend/dist/engine-adapter.js:6](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/engine-adapter.js#L6)。

## S07 前端适配结果

| 记录 | 判据 | 证据坐标（x, y, width, height） |
|---|---|---|
| F001：作业到期的开启状态无法辨认 | R17 | 0.681, 0.539, 0.141, 0.052 |
| F003：当前界面主题没有可见选中标记 | R17 | 0.576, 0.447, 0.245, 0.061 |

五项问题均保留独立记录，证据坐标与引擎输出逐项相同，24 条判据检查完整保留。新发现统一进入待人工审核状态。S07 原始报告 SHA-256：`22dc6bb9a6ddc80af5a69d57c63a40e2276a5e22f4229b57c35b48a48858b652`。[适配原始输出](D-发布索引.md#f397)。

## 统稿对齐清单

以下按“历史记录保留、当前说明更新”处理：

| 现有材料 | 统稿采用的当前口径 | 对照依据 |
|---|---|---|
| `frontend/README.md` 的 3 MB、localStorage、仅 mock 描述 | 15 MB、IndexedDB、mock/引擎双模式 | [frontend/README.md:6](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/README.md#L6) 对照 [frontend/dist/app.js:15](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/app.js#L15)、[frontend/dist/storage.js:1](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/storage.js#L1) |
| `frontend/CHANGELOG.md` 的 5 MB 代理与无逐问题控件 | 代理 16 MB；逐问题人工关联和复审表单已实现 | [frontend/CHANGELOG.md:3](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/CHANGELOG.md#L3) 对照 [frontend/server.mjs:8](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/server.mjs#L8)、[frontend/dist/app.js:43](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/app.js#L43) |
| 旧联调记录的“反馈仅保存” | 当前引擎模式将反馈加入 scenario 后再次请求 B | [本地联调测试结果.md:12](https://github.com/disordering/design-research-skill/blob/9780c03/本地联调测试结果.md#L12) 对照 [frontend/dist/engine-adapter.js:15](https://github.com/disordering/design-research-skill/blob/9780c03/frontend/dist/engine-adapter.js#L15) |
| 旧联调记录的 6 项前端测试 | 当前为 9/9，增加了复审补充层测试 | [本地联调测试结果.md:20](https://github.com/disordering/design-research-skill/blob/9780c03/本地联调测试结果.md#L20) 对照本次 stdout |
| C 初稿的 B 测试 45 通过、3 失败 | 当前引用 D 发布的 64 项通过，旧结果保留为早期环境记录 | [交互界面课程报告初稿.md:77](https://github.com/disordering/design-research-skill/blob/9780c03/交互界面课程报告初稿.md#L77) 对照 [README.md:142](https://github.com/disordering/design-research-skill/blob/9780c03/README.md#L142) |
| C 初稿的 `outputs/frontend` 和“未提交” | 代码当前位于仓库 `frontend/`，随 `9780c03` 交付 | [交互界面课程报告初稿.md:99](https://github.com/disordering/design-research-skill/blob/9780c03/交互界面课程报告初稿.md#L99) |
| 文中提及的示例下载与录屏材料 | 将 D 实际验收产生的下载、截图和录屏按文件路径收录 | [本地联调测试结果.md:26](https://github.com/disordering/design-research-skill/blob/9780c03/本地联调测试结果.md#L26)、[交互界面README要求核对.md:17](https://github.com/disordering/design-research-skill/blob/9780c03/交互界面README要求核对.md#L17) |

## D 可直接用于统稿的 C 材料

《交互界面课程报告初稿》已经提供 III.2、IV.2 第三轮和 IV.3 三个章节正文。D 可直接整理这些既有初稿，统一章节编号、测试版本和附件链接。

| 统稿位置 | 已有正文 | D 的整合动作 |
|---|---|---|
| III.2 人机协同设计 | 四个节点、反馈回流、复审补充层 | 保留 C 的设计说明，补入本次验收证据 |
| IV.2 第三轮 | mock、接口适配、持久化修复、逐问题复审 | 整理为实现—发现—调整—验证的过程 |
| IV.3 当前实现与运行日志 | 前端链路、审核、历史、导出 | 采用当前 64 项后端、9 项前端和 S07 适配结果，按测试类型分别陈述 |
| 附录 | C 文件职责与 B 替换边界 | 统一为 `frontend/` 路径，附本次日志和复审结构说明 |

原始 C 文档及源码保持原样。本文与 JSON 记录构成 D 的独立验收附件。
