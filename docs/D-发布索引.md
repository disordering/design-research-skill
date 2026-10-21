# D 报告与测试材料发布索引

## 10 月 22 日最新归档：六人识别与数据收尾

[当前数据收尾结果](D-数据收尾结果.md) · [D 阶段性报告](D-阶段性报告.md) · [下载新版完整材料](../deliverables/2026-10-22-d-data-closeout.zip)

本轮完成 6 人 P01 五秒识别、18 条原话与 Codex 辅助判分：Q1 2/6、Q2 0/6、Q3 4/6。真实工具体验 1 条、三项各 4 分；3 个 AI 操作角色及 AI 模拟共识按来源分别汇总。新版包内从 `D数据收尾材料/报告/六人识别与数据收尾.md` 开始，逐题判分位于 `输入/判分/识别判分.json`，计算结果位于 `结果/当前结果.txt`，八份识别原件位于 `材料/识别原稿/`。

本轮数据整理已完成，下一步整合课程总稿和演示。以下归档按原版本保留，文件路径和校验值继续对应各自材料包。

## 前一轮归档：体验数据、模拟测试与修复

[本轮结果说明](D-体验数据与模拟测试.md) · [D 阶段性报告](D-阶段性报告.md)

| 下载 | 内容 | 文件数 |
| --- | --- | ---: |
| [体验数据与模拟测试完整包](../deliverables/2026-10-22-d-experience-and-simulation.zip) | 1 条真人体验、3 角色 AI 模拟操作、模拟共识、报告与汇总程序、回归证据 | 110 |
| [明鉴本地试用版](../deliverables/2026-10-22-mingjian-local-trial.zip) | 目标同步修复后的前端、测试与启动器 | 21 |
| [被试填写工具](../deliverables/2026-10-22-participant-tool.zip) | 五秒识别、任务计时和三项体验评分 | 7 |

本轮真人评分 4/4/4，使用后补填的 1 秒按键时间单列；AI 模拟角色与 AI 共识分别标记来源。前端 10/10、导出核对 12/12、汇总程序 86/86、导入核查 8/8 通过。[修复源码](../frontend/dist/review-service.js)与[新增回归](../frontend/tests/service.test.mjs)直接进入仓库。

完整包内从 `D更新材料/先看这里.txt` 开始。阶段性报告的新材料定位见[本轮材料索引](D-体验数据与模拟测试.md#阶段性报告的材料定位)。以下保留此前归档与 F001—F542 定位条目。

## 此前发布记录

更新：2026 年 10 月 22 日。本次新增双评审记录与复核讨论包，入口见下方。10 月 21 日的完整归档包含 10 张开发图的 24 项发现、P01 的 2 项目标建议、C 前端验收、真人执行材料，以及此前完整测试记录。累计 14 次 Codex 视觉评审；本次提交整理既有结果。

[D 阶段性报告](D-阶段性报告.md) · [本轮开发测试总览](D-本轮开发测试总览.md) · [交付进度](D-交付进度.md) · [真人执行清单](D-真人材料执行清单.md)

## 10 月 22 日：双评审记录与复核讨论

[双评审阶段补充](D-双评审阶段补充.md) · [下载复核讨论包](../deliverables/2026-10-22-d-human-review-followup.zip)

本次收到两位各 270 项的独立选择记录，整理 33 项分歧、11 个候选条目及合并后的 42 行讨论表。包内包含原稿、继续填写 JSON、Codex 复核建议、2 项修改草案、参考图集和 D 报告补充，共 38 个文件。解压后从 `双评审复核讨论包/00_先看这里.txt` 开始。

本包单独归档，供独立选择之后的补充和讨论使用。下方 10 月 21 日的 542 文件归档保留原版本。

## 下载完整材料

两个普通 ZIP 使用相同根目录 `D-开发测试与真人执行包/`。将两份都解压到同一位置，即得到完整的 542 个文件。两包分工互补，没有重复文件；无需分卷工具。解压后从 `README.md` 或 `docs/D-阶段性报告.md` 开始阅读。

| 归档 | 内容 | 文件数 | 大小 |
|---|---|---:|---:|
| [本轮材料](../deliverables/2026-10-21-d-expansion-current.zip) | 最新报告、9 次新增评审、作者候选对照、C 验收、真人工具与最新源码快照 | 280 | 10.86 MB |
| [前期支撑](../deliverables/2026-10-21-d-expansion-history.zip) | 此前 5 次视觉评审、S03/S07 原始与修复回放、历史报告、开发样本与原版本代码 | 262 | 19.12 MB |

单独分发：[两位评审者独立标注材料](../deliverables/2026-10-21-d-independent-reviewers.zip) · [P01 五秒识别主持人材料](../deliverables/2026-10-21-d-p01-recognition-host.zip)。P01 主持人材料与完整归档一致；独立标注材料在归档中的 17 个原始文件基础上，新增 `00_评审说明.txt`，共 18 个文件。发给评审者时下载此独立包，先读说明再填写模板。[在线阅读评审者说明](D-评审者说明.md)。

## GitHub 直接阅读

- [25 条作者候选逐项对照](D-作者候选开发对照.md)
- [C 前端交付验收](D-C前端交付验收.md)与[四轮浏览器操作验收](D-C浏览器操作验收.md)
- [真人材料执行清单](D-真人材料执行清单.md)与[P01 主持人执行卡](D-P01主持人执行卡.md)
- [完整验证证据 JSON](D-验证证据.json)：其中相对文件路径以解压后的归档根目录为基准。

网页阅读版把归档内的文件链接转换为本索引中的定位条目。每条列出下载包、包内路径与 SHA-256；完整归档内保留原始文件和可直接打开的相对链接。原始 JSON 的旧执行路径另有 `evidence/codex-expansion-20261021/原路径与包内路径映射.json`。

## 归档校验

- `2026-10-21-d-expansion-current.zip`：`24aaf54b037c15b153652858bb3a82f2d2a87ef8b4196d86eec8035986e7f456`。
- `2026-10-21-d-expansion-history.zip`：`37b49a1a1ba7a330ea56df27747a6eed36e39c1358448094c61b6de57c470143`。

## 逐文件定位

### D078

- 包内目录：`reproduction/source/tests/`。

- [reproduction/source/tests/test_api.py](#f476)
- [reproduction/source/tests/test_config.py](#f477)
- [reproduction/source/tests/test_d_regressions.py](#f478)
- [reproduction/source/tests/test_engine.py](#f479)
- [reproduction/source/tests/test_finding_deduplication.py](#f480)
- [reproduction/source/tests/test_input_limits.py](#f481)
- [reproduction/source/tests/test_model.py](#f482)
- [reproduction/source/tests/test_normalization_conflicts.py](#f483)
- [reproduction/source/tests/test_parsing.py](#f484)
- [reproduction/source/tests/test_review_recovery.py](#f485)

### F001

- 包内路径：`deliverables/2026-10-21-character-trial/audit.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`054d654202559d9d0f526341527afceb4f4dbad71bc15feb5479b967d52d65c9`。

### F002

- 包内路径：`deliverables/2026-10-21-character-trial/criteria-relevance.csv`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f9fad349a7f288597e90038471d6adab85cdec003cb4a72c8a06f83096c3c125`。

### F003

- 包内路径：`deliverables/2026-10-21-character-trial/criteria-relevance.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`46247e93c57fb086ad11e4ac2945e6871420df3f42f3a9d129477bbc90a6ad83`。

### F004

- 包内路径：`deliverables/2026-10-21-character-trial/design-goal.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`cad77c132b8f403bbcad298ce0e80ac81a50299613cf15c77d0d13b77f13e151`。

### F005

- 包内路径：`deliverables/2026-10-21-character-trial/goal-constraints.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`efa1e76dab702e97ddd414214cdf6156bea371f1f47aa7b54461b96bfdc93818`。

### F006

- 包内路径：`deliverables/2026-10-21-character-trial/manifest.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8f03e74c20d72f7fbf73846527f841f02dabaed7870037d57865bccb0677027a`。

### F007

- 包内路径：`deliverables/2026-10-21-character-trial/metrics.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`4990bdc930a84044defb9360143aad89394e9cc3bf0588372e3534e607f09c04`。

### F008

- 包内路径：`deliverables/2026-10-21-character-trial/narrative.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`993b05217f1c7f3bc57fef05f994637fe0a40db6b1056c643ec4e514508757dd`。

### F009

- 包内路径：`deliverables/2026-10-21-character-trial/ocr.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`b63430e86229a58be3a2d597b427e6147c7c16ee5d058ad7fd1d6558d1071696`。

### F010

- 包内路径：`deliverables/2026-10-21-character-trial/prototype-elements.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`7a6d8a11f93126b449f2e9080e88275ba1f3eabf5c2e7a5e6f1a5e66e56828a9`。

### F011

- 包内路径：`deliverables/2026-10-21-character-trial/prototype.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`9123e383f258a1d4d23597ac216b8440ac9d70ee1f41835ab464bcad93a7a832`。

### F012

- 包内路径：`deliverables/2026-10-21-character-trial/raw/audit.raw.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`a5f23535776ef397c1a49581a4cc896117ee7c04939e1c62960f142087c7121f`。

### F013

- 包内路径：`deliverables/2026-10-21-character-trial/raw/criteria-relevance.raw.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`39e7568fa6470246981c2feb5e91d5b43c509211f4b7d63a4f677105b39bb928`。

### F014

- 包内路径：`deliverables/2026-10-21-character-trial/raw/goal-constraints.raw.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`efa1e76dab702e97ddd414214cdf6156bea371f1f47aa7b54461b96bfdc93818`。

### F015

- 包内路径：`deliverables/2026-10-21-character-trial/raw/narrative.raw.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`993b05217f1c7f3bc57fef05f994637fe0a40db6b1056c643ec4e514508757dd`。

### F016

- 包内路径：`deliverables/2026-10-21-character-trial/raw/ocr.raw.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`c1b5d48b2da9dc2bd6d56541587d11dd640affb99517daa22950791f404ac138`。

### F017

- 包内路径：`deliverables/2026-10-21-character-trial/raw/prototype-elements.raw.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`7e42f6cc1aea0e5d3e1c85d49a4151b0084927f109ab4ba48701b8b65e15564f`。

### F018

- 包内路径：`deliverables/2026-10-21-character-trial/raw/ui-elements.raw.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`891b77521c6f305a71b3ed18848d410cd982eb7df698d3def0caca21efe3aae6`。

### F019

- 包内路径：`deliverables/2026-10-21-character-trial/README.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`15bfdc58bca46087624596ce63798e9c3919818dfd83cfefdfe50ad576b241f7`。

### F020

- 包内路径：`deliverables/2026-10-21-character-trial/report-showcase.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`e11f3027f9685ed09df10c49339d0d9f8c2a48367e3f7638b2dae33f064cc78e`。

### F021

- 包内路径：`deliverables/2026-10-21-character-trial/report-summary.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`152efc91ad4ce9572957256c4621cb894d2d17119211905529689f4cda6adc03`。

### F022

- 包内路径：`deliverables/2026-10-21-character-trial/report.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`bdee10698a3f490efca027d6373e2736b92c2f6a5d1c1a69b516290390eecde8`。

### F023

- 包内路径：`deliverables/2026-10-21-character-trial/review-metadata.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`3b8c89fcdeaec374e6f72fc1061613255a7a675b26b33ad712e54ca215f6bad6`。

### F024

- 包内路径：`deliverables/2026-10-21-character-trial/screenshot.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f1201f54c66f3210ed14bd8785f0a3c532ee0e89cd6d3992cfaeb9970b7db1ed`。

### F025

- 包内路径：`deliverables/2026-10-21-character-trial/SHA256SUMS.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`147f98a49f7018bccb3907215a60b4ae46d3afd9ac5b0681540006ddf5dc8e73`。

### F026

- 包内路径：`deliverables/2026-10-21-character-trial/ui-elements.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`c76597f0e11bc189854f8c7e92399e370dc4c9e18b2881833fbf0d48c50cf3fa`。

### F027

- 包内路径：`deliverables/2026-10-21-character-trial/visual-focus-proxy.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`6f4c24298f2649817316a83116529b0652a82110c9db5c693649039be0c91512`。

### F028

- 包内路径：`deliverables/2026-10-21-character-trial/visual-ui-elements.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`a5c534a91c6f47ba3b41c00c59634f3ab7054baa7b61d40508dc43443a17848c`。

### F029

- 包内路径：`docs/2026-10-21-S07去重修复.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`5be59127aa81ce5db950e1465c6c61d0eda296c0fdb4a9cd5ffc9d39bab1e91b`。

### F030

- 包内路径：`docs/2026-10-21-修复说明.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`6b41a56680ebd4c50c184df0b9b585d45760d043319ed91f8a089cd7748f43a4`。

### F031

- 包内路径：`docs/b-engine-v2-plan.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`43ea17cd22d86e8081ccdb86390501262e15a7cfa00befbca5199f8f1496652f`。

### F032

- 包内路径：`docs/b-engine.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`000ee814da9f25844c6d79853a17cd459b5ea52b8cf1371982417e06b6256c2a`。

### F033

- 包内路径：`docs/config-setup.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`ab3770c6567de88073043df7b22619cdcbeffb77982031fccc8696256d88ac74`。

### F034

- 包内路径：`docs/D-Codex三轮一致性对照.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`dbee2fa588e8124a21d40a42901ec2f6fd3a54cb160dc1b7f9b40323881988bc`。

### F035

- 包内路径：`docs/D-Codex证据索引.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`304cec5e640e262fa365392562244a55505c05d94bbbabb2f8996944341db626`。

### F036

- 包内路径：`docs/D-S03与S07评审汇总.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`a56d39c0dd7746f09b6a070f93ff8a791f6523a80d5a7c3cfa98ffcf42988565`。

### F037

- 包内路径：`docs/D-S03修复后回放结果.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`6c900f22bb839c83cb239177b94d7a7e17f6644b485caec2470f1138b8c81ff6`。

### F038

- 包内路径：`docs/D-S07修复后回放结果.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`969ffeb18ea8f86a002c2e51de80f6a71e617ce645bae8ff0ac6cba67c3e29c7`。

### F039

- 包内路径：`docs/D-交付进度.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`be360f34a58c86b7469c57bf846e6fbe8511dfbc83988b312c6f599c800b7536`。

### F040

- 包内路径：`docs/D-单案例复核勘误.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`337777b1c058b6369f29c25d34054ac7250a5c2c8cec29beff762ac2a20121cc`。

### F041

- 包内路径：`docs/D-本轮开发测试总览.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f0c29a215a9e5f6ff847f9a7270f23a1ef555110aa785ab8cfd17be406773509`。

### F042

- 包内路径：`docs/D-测试判定说明-v1.1.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`378799d1ae883cf33beafd392a402dcdf292b73011f132f562d07dd3a78fe6d7`。

### F043

- 包内路径：`docs/D-现有材料与下一轮测试.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`588792bfeb856f6ed48059e875a606bd728eeb843317f6fdd336c47326507ba0`。

### F044

- 包内路径：`docs/D-真人测试记录模板.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`5b8967435ea056b8c712902367b2cef8c9f2feb78bf707a8ac605ddbd968cdd1`。

### F045

- 包内路径：`docs/D-阶段性报告.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`027897ad1a5ea13ee6afb4a4e17ad6cad01c412648ad09f13b08146385de2e40`。

### F046

- 包内路径：`docs/D-验证证据.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`6ab7c6f7e2723c12eebf7297e3b187bceb3075a14997a6bd0e689b9c7ec3cb98`。

### F047

- 包内路径：`docs/history/d-report-20261021/S07去重修复前/D-阶段性报告.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`7154bf0878336234e1214d62dd0b4d34facd495274bb2c84ddc1b78c75ed1252`。

### F048

- 包内路径：`docs/history/d-report-20261021/S07去重修复前/D-验证证据.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`02a1c0fb6e17c77072ee22dc005de6f138551683280f1f7b05d23910519b84a7`。

### F049

- 包内路径：`docs/history/d-report-20261021/S07去重修复前/报告更新校验.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`a509e22d739c41015dea31554cc163de48b0fddb1a31f4fa75d482868adb3200`。

### F050

- 包内路径：`docs/history/d-report-20261021/v1.1开发评测前/D-阶段性报告.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`e49b2b9153067d82e0a94b5b7a0f650a81ecd9655b89085ba16f07be94e308fc`。

### F051

- 包内路径：`docs/history/d-report-20261021/v1.1开发评测前/D-验证证据.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`4641a07218ae547527f50ed5ed9349b0bb3e57ca55e676d13e5713498b999b39`。

### F052

- 包内路径：`docs/history/d-report-20261021/v1.1开发评测前/报告更新校验.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`1ba188f655bc7f79707e30bf9b95672c9963adb39abfd1c0acee61ee74eba822`。

### F053

- 包内路径：`docs/history/d-report-20261021/三轮版_口径整理前/D-阶段性报告.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`118fd4601adcf3bf3498b010aa93b8be5b8c264b6b5ed495105a471b7f422546`。

### F054

- 包内路径：`docs/history/d-report-20261021/三轮版_口径整理前/D-验证证据.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`be492d067fd4c53d7a4fe38452586251b256cdec394b2cc95130bb2d106b89ea`。

### F055

- 包内路径：`docs/history/d-report-20261021/三轮版_口径整理前/报告更新校验.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`39b20c2f25425b9197940a7b47f6d876611bf6601c5d3ff8126c1a8a5d82d48e`。

### F056

- 包内路径：`docs/history/d-report-20261021/单轮版/D-阶段性报告.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`7527492b97726bbc71e5eb3732c21dfa9e04e25eb27e3686ba4af7368a9a168d`。

### F057

- 包内路径：`docs/history/d-report-20261021/单轮版/D-验证证据.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`fb19c223b161697bf3c4a1b3d6b3d6003553c70920d029a85b2614477e80f5af`。

### F058

- 包内路径：`docs/history/d-report-20261021/单轮版/报告更新校验.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`d00708a44e5d6f4e8c68a2764631a61d57c4079950986ce63fafcbba679871f6`。

### F059

- 包内路径：`docs/history/d-report-20261021/原程序验证版/D-阶段性报告.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`31e2f39d4f48284d40c0071f563f8379b2fa146b0f2c2344cce5f42772f8055e`。

### F060

- 包内路径：`docs/history/d-report-20261021/原程序验证版/D-验证证据.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`096d89e6ff725a96680805220c6c70088c2f1dadd91050198c4918007550c461`。

### F061

- 包内路径：`docs/history/s07-published-20261021/D-交付进度.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`b6aad520c710cdd0a59e1880518d17e087bef9b63929d11d0de7c964dcaa1f09`。

### F062

- 包内路径：`docs/history/s07-published-20261021/D-阶段性报告.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`08c46a21405d437edfe29acbf444c8c729944bc851ad8411700dc6f3713ae468`。

### F063

- 包内路径：`docs/history/s07-published-20261021/D-验证证据.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`49fb778d8ace8f423c91fac511e17e74a4955bc8dfcb047f74aa071c5e38f4f5`。

### F064

- 包内路径：`docs/history/s07-published-20261021/publication-manifest.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`91c1ad3cbf5d26d339ff6ce5748f07c5ae6a772197e4744c057ef359bf059e85`。

### F065

- 包内路径：`docs/history/s07-published-20261021/README.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`70baabd4d6fecfd6c4471edc025371b05c890b9be117aef97717f40579a356e3`。

### F066

- 包内路径：`docs/history/s07-published-20261021/路径说明.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`6fcae85a4edf1a21b4ac43b5ad3ef1c0d8165ef9a8bbcf90335e71aaaed20205`。

### F067

- 包内路径：`docs/staged-workflow.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`df0ec757897198b340ae61ae9f853f06fa3a54ae09f8a95f039db0692c625e11`。

### F068

- 包内路径：`evidence/codex-expansion-20261021/GitHub最新核对.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`3621d3c530b1b69bc0118c60b266ee3c6a2edea29a82f2a34e7221b5f5d3f939`。

### F069

- 包内路径：`evidence/codex-expansion-20261021/qa/实验工具逻辑校验.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`d78b9eb286d511231b6436708df2a5581e3da79936d4447b640fc5cb8b7fe14a`。

### F070

- 包内路径：`evidence/codex-expansion-20261021/qa/实验页设备验收状态.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`00a82733eedd2178b4ce72f96e6c66c77d00da543c6c8181c2ff30b2e9f5ce8a`。

### F071

- 包内路径：`evidence/codex-expansion-20261021/qa/批次整理日志.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`a9a8c320587b8cbe5f5fbffbfde8713fdf703fd9ff60a8c74e1cf0e366864d79`。

### F072

- 包内路径：`evidence/codex-expansion-20261021/qa/独立复核.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`84bf70755318ada06889f1ed3dfd4f90390647515d09d59a67d270aedf46cfa9`。

### F073

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`ed2295780c7430570eacca1c847923087458cc5e69be0703ac6e5f6664c3f4c7`。

### F074

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/criteria.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F075

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/D-测试判定说明.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`7be8af456d1d8e0f3fbbc027cca66af3cb9a6a31e251f32586871a7bd1e82b1c`。

### F076

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/design-goal.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`cad77c132b8f403bbcad298ce0e80ac81a50299613cf15c77d0d13b77f13e151`。

### F077

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/goal-review.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`d2f1b2878cc70de40b4ae31f194c7af5a7f23501a97815ca5fbe33e6241607b9`。

### F078

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/prompt.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`6d0b5b11fcaf4cf84d36c59084dc1f76c9e2dce94dc86fe64379c103135863ad`。

### F079

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/protocol-trace.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`6b435ebc477883a7fe37bb2ea8ba00b42acdeb421345c57e54f42726e0fd2743`。

### F080

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/prototype.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`9123e383f258a1d4d23597ac216b8440ac9d70ee1f41835ab464bcad93a7a832`。

### F081

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/raw-audit.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`e3c9c6b67a79ded06d7d932d1153d54c3b879dc56443c0a5931c0c5ec933bcb1`。

### F082

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/raw-audit.schema.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`940621be588458ecbd133fbedf2b7c9a379881ec70d0eaa9237b9ce408210bb6`。

### F083

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/report.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`649feee341158dbdac83a78e82e85d2c64a37d4fd6f3bf70ffc6f57b0bfebc3a`。

### F084

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/review-timing.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`a69296a95ad5b5d6cf60b780e3fa6893e7cc14ab4ff17493cefadf37f193907e`。

### F085

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/run-manifest.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`d91e832198e97f6d9b6d53a5f7506388d9152bc2bef5828bdc62b5e2b2915dd5`。

### F086

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/sample-context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`63a000efe455ab2a4e5d832b11f786da8159e5dd78946671691a84bcf1ab7271`。

### F087

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/screenshot.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f1201f54c66f3210ed14bd8785f0a3c532ee0e89cd6d3992cfaeb9970b7db1ed`。

### F088

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/文件校验.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`9d2ee4ceee6e3d892f155cd0eb024572ffe7d06789810622c26d2527c527e338`。

### F089

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/评审结果.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`4d5c2b809778ec6b7f1b805618fb287cca92c3392d7ced00639f1b7060c98bc0`。

### F090

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-p01/验证结果.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`2c4b124f51715f596c54102564cf710e9dc751dfa59faf8cb4ccfa7f40664833`。

### F091

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f68eb2f6b0c12c15c927ceb16890a3db303347da6dcfac1c69647a26fbfa2148`。

### F092

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/criteria.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F093

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/D-测试判定说明.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`7be8af456d1d8e0f3fbbc027cca66af3cb9a6a31e251f32586871a7bd1e82b1c`。

### F094

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/prompt.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f3bfe9eb506420726f448a5983f22f9751bc7d1d498a7744699a264a2ee05a4a`。

### F095

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/protocol-trace.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`20ab69cecf46baa7c9a2a42e0b975fa26b4ca27ecdff48aac7428690c9e975c1`。

### F096

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/raw-audit.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`165e4ac5e8f71689644f7495c3683b1acce323ac4c407bdc5f6f3d0aa91071c1`。

### F097

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/raw-audit.schema.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`940621be588458ecbd133fbedf2b7c9a379881ec70d0eaa9237b9ce408210bb6`。

### F098

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/report.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`622c8bdc057854ee66898ce3dfe80fea643c164e0d771fe8693068f997fbb35f`。

### F099

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/review-timing.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`69bb1cd63951cf48edddcd83a7f86a5c58bd5bb00fc5e32d99e3c9fde61c48b6`。

### F100

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/run-manifest.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`2ea983bc0315dd64ada559901962c960636278fb4c46585fb9eb827a27d4200c`。

### F101

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/sample-context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`a214621d802826224030ed6d4b48e0a24be97279ca36d0d5e55726193f8f45ee`。

### F102

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/screenshot.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`4a0859d3eba534c34695a917fbacba8b50362be7c5b027d22a0926bc02c79920`。

### F103

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/文件校验.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`dfb13601db154d871486da298b11d25ea780772dd1b56787cbe7a51515992f90`。

### F104

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/评审结果.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`610665bbb9e7209cfa41e7ea0fc86384b43a24b8d3747d5b7c349f7fc37db03b`。

### F105

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s01/验证结果.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`24632644ae8bcaf84b1dc1fa772f44d08afd71454eb8ca556b46b74493022fcf`。

### F106

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`c9a5f11d44574b2a19f933b6dfff42307f529d7be7260019607284a26722cc66`。

### F107

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/criteria.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F108

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/D-测试判定说明.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`7be8af456d1d8e0f3fbbc027cca66af3cb9a6a31e251f32586871a7bd1e82b1c`。

### F109

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/prompt.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f3bfe9eb506420726f448a5983f22f9751bc7d1d498a7744699a264a2ee05a4a`。

### F110

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/protocol-trace.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`cb69b9449c7b5a672a332644189681c74e0be7b1fefc5360ff64ffe8dfdee7f2`。

### F111

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/raw-audit.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`d643654d209f9021c5e1398e0af67e6458fec4ecea5e0c3ab3887424d06cbacc`。

### F112

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/raw-audit.schema.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`940621be588458ecbd133fbedf2b7c9a379881ec70d0eaa9237b9ce408210bb6`。

### F113

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/report.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`21f5e128493dd15acb347a976e678c0cdfe0a9b6bdf94bab81cf15ee4fba9819`。

### F114

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/review-timing.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`efdba8c39bd75fb554f6803bd5a501de966d3321756b74db5089d49737f07de0`。

### F115

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/run-manifest.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`d43aa73419e99eed4843a9c1e2046749989f6a8293f70e2d9ef8166dcd6c0bdc`。

### F116

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/sample-context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`9f7e436112dae09382d8479d1bb17a19404cb923f3e41ba2b0cc5a68a1c36664`。

### F117

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/screenshot.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`e4775cb3ce705aa467dcc7acf86ade8ad0d01d0256c8ba9502fbabdcc6be60c1`。

### F118

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/文件校验.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`ec5e8301e51f062064533bb0d87720268970271a0ad4242198567ee9f9adf1f5`。

### F119

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/评审结果.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8258d26fe50a3a17da3a811a5d973e6de45ab9d1cf3e93ae42264ccfa086c531`。

### F120

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s02/验证结果.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`082a2ff55ced31ea9d18a7918968beb3d4eb0c3d0cb194453e9dfe8ddb13803b`。

### F121

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`70f12e99837024c1ceeb73ba924fc37b5ce0b30430c7bdd05591739cda545730`。

### F122

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/criteria.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F123

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/D-测试判定说明.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`7be8af456d1d8e0f3fbbc027cca66af3cb9a6a31e251f32586871a7bd1e82b1c`。

### F124

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/prompt.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f3bfe9eb506420726f448a5983f22f9751bc7d1d498a7744699a264a2ee05a4a`。

### F125

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/protocol-trace.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`ded2daf6ae2d8a81733cf954c45f1681816165ce43f37d8f45c9b3770f81d7f0`。

### F126

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/raw-audit.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`0d066ae6f94dd89f49a682cd74fcfb04bd4a1a17ace10c981831651e80956660`。

### F127

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/raw-audit.schema.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`940621be588458ecbd133fbedf2b7c9a379881ec70d0eaa9237b9ce408210bb6`。

### F128

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/report.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`82456d79d0bea58045d1549ab64d56ee641c1152d1f0e46ed4b83790cd6e9b35`。

### F129

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/review-timing.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`95a5eb3e12036735fea95d2a10aaca27c568b5eae8042f99f00061d3d0e697ed`。

### F130

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/run-manifest.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`81386e87bec1402bf211c632e4928e0109e28c5ae97613d503529559de768e5c`。

### F131

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/sample-context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`39495d42aff17472402dc63844da3d8b0ce5b0493933ef83cf18ba4b91993acf`。

### F132

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/screenshot.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`b0e713bc2416d64497e84c304ffb10fff344f2211e98fc420679f241c81af753`。

### F133

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/文件校验.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`4cff2175cf62c43d58f2a8ba730e8a7a635772ef87f6a438237071fd4374ec29`。

### F134

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/评审结果.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`a5ee87fbfb03e546754c658b235d92fc015b41774339e9b20f2ddf292ba5e684`。

### F135

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s04/验证结果.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`5bec0528128f6f738f27673c25fe1b90f2f34b6a143d70cdee6cc6cdde698e31`。

### F136

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f34f2fe29a4525beffbc6fd66c0662e28a411e1c24009e2d0e57f8dc1250dc70`。

### F137

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/criteria.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F138

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/D-测试判定说明.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`7be8af456d1d8e0f3fbbc027cca66af3cb9a6a31e251f32586871a7bd1e82b1c`。

### F139

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/prompt.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f3bfe9eb506420726f448a5983f22f9751bc7d1d498a7744699a264a2ee05a4a`。

### F140

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/protocol-trace.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`1aa155827b16298d3de98e68b0b04c32453d4dabf466e3d2914ac20ebc134112`。

### F141

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/raw-audit.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`63e3a0728b32855ea3000c78a9cd55b0880dcbb006f83771850bd0a1a2b4167f`。

### F142

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/raw-audit.schema.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`940621be588458ecbd133fbedf2b7c9a379881ec70d0eaa9237b9ce408210bb6`。

### F143

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/report.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`2b7b18922f9d14fc08110b55e009b5a41ef9f0dbce0b7be19165a8b28f792139`。

### F144

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/review-timing.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`6c4f09bdd1af0adb5f79d8e5f829c2d09a9e5c503d82c488bcb2dfe490a792f8`。

### F145

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/run-manifest.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`9be493aa2c1f6fe027abbe0482a738acb73788b51c7a62ea517468f8c4f845ca`。

### F146

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/sample-context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`7e231409db6c7102959e9071acaf6abb8fe5673fcf5fcaf82386b641329a1d49`。

### F147

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/screenshot.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`3defd879aeabf83dfdd97d127a395eb414aba55eb577422c03965d4cb6bde65b`。

### F148

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/文件校验.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`a58362b721a9252f118656626d1be5d1d516a5ef0861611e6364e23deb4629ca`。

### F149

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/评审结果.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`9e44490dd137c86d88f34256d5baeda321b110c916c4bdf75fadf0e967392a29`。

### F150

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s05/验证结果.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`1556a5f1409832907fd02c50a12752f53b7b3b3ca2ad6486f6c4c2334f8287f7`。

### F151

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`fc7e894aa29cb7b0c047b184650bea36b010e80517b6f93686885f9dd314f127`。

### F152

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/criteria.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F153

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/D-测试判定说明.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`7be8af456d1d8e0f3fbbc027cca66af3cb9a6a31e251f32586871a7bd1e82b1c`。

### F154

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/prompt.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f3bfe9eb506420726f448a5983f22f9751bc7d1d498a7744699a264a2ee05a4a`。

### F155

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/protocol-trace.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`6581bc177f30b3ef793448cec51fafb7f9f1410baae8a8ae75fe805eb3e6ccd0`。

### F156

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/raw-audit.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`48aa353578e2809e17ee1d62095fdc1ace3aa2d51d32cc6133c76d5bbc363a95`。

### F157

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/raw-audit.schema.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`940621be588458ecbd133fbedf2b7c9a379881ec70d0eaa9237b9ce408210bb6`。

### F158

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/report.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`e49d88f4bb9fb2c9b0a99a4d22e456e2118a2ff7259acd6371ee9911fe839fa6`。

### F159

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/review-timing.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`c6bfa9037757a6444c44f1b497df9a35b357a13789c14c9dd4846baacbe8103e`。

### F160

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/run-manifest.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`a8aac31f46e5a7030a20270f525e825258879174fbe94f2a0fdbd83a66fa6c02`。

### F161

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/sample-context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`72738f0f2b551db9e3212ee719fbff8dcf8a1bdd22a73f0cd00bf520db2b83f6`。

### F162

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/screenshot.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8dc2c05d309b08c48469ddac08bb7b2bfca95a3c2fbdea497300bfa492e065ab`。

### F163

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/文件校验.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`53c359f6f1fcc0e4edb35ce395d63f38e6171fb362f63c069f0e71c6e4360e0b`。

### F164

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/评审结果.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f6c299947c81b1dc93def63b690cc4989916a305badb69472d0353ca96310190`。

### F165

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s06/验证结果.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`71d86112c5bc2f27df3dfbf60fa92b19e223f6655b336cdb7916d7605e200cb1`。

### F166

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`a09b7841aa5a389c3a28c40247bf06d0576e1cf8e6e1177af92df815ef1c47c7`。

### F167

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/criteria.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F168

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/D-测试判定说明.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`7be8af456d1d8e0f3fbbc027cca66af3cb9a6a31e251f32586871a7bd1e82b1c`。

### F169

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/prompt.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f3bfe9eb506420726f448a5983f22f9751bc7d1d498a7744699a264a2ee05a4a`。

### F170

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/protocol-trace.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`521aba73027f8bd6118d8c591549419c1cd5468291497652661c5e7e965a20e5`。

### F171

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/raw-audit.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`64a9029369e64c94808ac8e0f389b5c810ba1e70dcd1baade7709638cee2056a`。

### F172

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/raw-audit.schema.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`940621be588458ecbd133fbedf2b7c9a379881ec70d0eaa9237b9ce408210bb6`。

### F173

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/report.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`c9ae73c86058f40faaf1d6361549fe4a4d6b92dc3bfbf455748def063c52062a`。

### F174

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/review-timing.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`cbad57a73d285566fce176f6d89b05d80096392552ab16f358c347565ef36656`。

### F175

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/run-manifest.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`cc80384c29831f87ff832185d15a08051a29d42b56e056935c5c7ba76cc18223`。

### F176

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/sample-context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`9e50c78d517e70292bc23081aedaff41324649c0ee7a5e905ec4a4d9b024070d`。

### F177

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/screenshot.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`47ee014f811d950d32cc0ab418677a199a432d99a931430498fe580514b38aeb`。

### F178

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/文件校验.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`aa52ee41bd7ca75805a6464844a150a8830f9d8640af8b5338f163d262d307d2`。

### F179

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/评审结果.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`61f60f91d9fae8ce57083dd4a588e71895d62942f58b88c2fa6e2e1c5b363e07`。

### F180

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s08/验证结果.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`999c6685dee089a5cd7e5b1c6e9e13969dc274874b77187db7c86373bd42ac1a`。

### F181

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`3b220629e79c0deb28337b171984f55f36420a65948186c53800e8907babd806`。

### F182

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/criteria.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F183

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/D-测试判定说明.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`7be8af456d1d8e0f3fbbc027cca66af3cb9a6a31e251f32586871a7bd1e82b1c`。

### F184

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/prompt.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f3bfe9eb506420726f448a5983f22f9751bc7d1d498a7744699a264a2ee05a4a`。

### F185

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/protocol-trace.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`4bb22327861e834d464baf25676ba2a589ae47ddd05e2e23a3a34769a931a488`。

### F186

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/raw-audit.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f8549d94faa8d00280fc061695b66d3edd5698b787272463ae70ea3b67a5e43c`。

### F187

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/raw-audit.schema.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`940621be588458ecbd133fbedf2b7c9a379881ec70d0eaa9237b9ce408210bb6`。

### F188

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/report.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`b7976b553b0a0e29025f7345af1409d020c09db1cc1580bb6e6b5a08d2e78f0e`。

### F189

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/review-timing.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`7741ca2b1c77b6b10f40dbe0ba55c61d03ee9e978b3a1bc4720a5c2a0ad073d0`。

### F190

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/run-manifest.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`b23f5af7978254f375a09ba645cfd4a78ed124c8c4351b523edb3761e4ff9e84`。

### F191

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/sample-context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8098327d4dfd04aad1932aeaaf60b011f51b0972467eb454db65392e0a3f7b67`。

### F192

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/screenshot.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`2e57845dcbba1ded443fb35475a85d303a815321869e550236cc475a0a970a85`。

### F193

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/文件校验.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`0ce49c470dc4138f6667e2f5b56450224fe4836b54b6804d0ff6bbe5df8ff7f7`。

### F194

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/评审结果.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`b9b79eac4a97558f9840965f3a633b3e947828354b69f626c699dd9328063392`。

### F195

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s09/验证结果.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`760d97e6c28ebb1d4bb1cd08e9b770e877f87d61d40868f8e718c18787b2de01`。

### F196

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`b9551c5d5822ac83a3a39e4718974776dafe20b1b313e372ff9a01deb455beb7`。

### F197

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/criteria.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F198

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/D-测试判定说明.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`7be8af456d1d8e0f3fbbc027cca66af3cb9a6a31e251f32586871a7bd1e82b1c`。

### F199

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/prompt.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f3bfe9eb506420726f448a5983f22f9751bc7d1d498a7744699a264a2ee05a4a`。

### F200

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/protocol-trace.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`4b9bbdd6090178bb55615e9b28d8d110cb747617efac8c52ba7bf815b329f410`。

### F201

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/raw-audit.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`7bd60b6784ff641b4b6cdd3b3dd3c443762418dd39404856480830746cfaad36`。

### F202

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/raw-audit.schema.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`940621be588458ecbd133fbedf2b7c9a379881ec70d0eaa9237b9ce408210bb6`。

### F203

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/report.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`5254f60b6b9bd70b79a89ef47039ce036cb4ad1c902df632de5d40270baa64cf`。

### F204

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/review-timing.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`1d82dc7c7c9a4c0b512e6dd29dac5700475e38e1255fc02436a74cfaef227d59`。

### F205

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/run-manifest.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`19adcc586a4dca7e2ae8b8a281d42ec3094b7196a9ce53feaebd760bb5001ef4`。

### F206

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/sample-context.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`a80bb5c8ec6b2e23cf59b1c8a70814a29d79abd185f54321e144849c70e9002a`。

### F207

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/screenshot.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`630fffc802a477cc581ed483bf4460a562333e1bd61ea101d9387ae5d2511600`。

### F208

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/文件校验.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8ce46d1638083e0e7657aceaed6025f28613819e7e97630bc9ff07fc0e56b288`。

### F209

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/评审结果.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`d046cc62c2629abaaee62a64b68a268ec4326b1818a33b8383b3a3632831b05e`。

### F210

- 包内路径：`evidence/codex-expansion-20261021/runs/20261021-204528-s10/验证结果.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`cfee00ba2c292edac95728a2ee8de48e92c7a0acc346057f1bbe4f454b6df305`。

### F211

- 包内路径：`evidence/codex-expansion-20261021/作者候选开发对照.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`b4c24fc2fba2b170348b376e0af81942b80b7e60a43a8d8bfd8ce755ee37f9bc`。

### F212

- 包内路径：`evidence/codex-expansion-20261021/作者候选开发对照.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`6f9b6760e254f3928015226dab6996a1d7455df849c7b758b18b5c041d675474`。

### F213

- 包内路径：`evidence/codex-expansion-20261021/作者候选开发对照.original.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`6dc2704dabeb30be66775a16c16fc02f64ba9b5daa0e7583ceecf88cd2a1e80c`。

### F214

- 包内路径：`evidence/codex-expansion-20261021/便携对应关系校验.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`11749c98f48506b711cf25388717df83c62cb4f36ffc1503c5474b28f7b50fcc`。

### F215

- 包内路径：`evidence/codex-expansion-20261021/原路径与包内路径映射.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`5882d819be80417465c0993b3b1968fc980da3a6145181847e6c2e2c9613e3eb`。

### F216

- 包内路径：`evidence/codex-expansion-20261021/执行计划.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`73657c32644ded75b5701892c095e032c8b7fe2eca25867ea213b2eff294a70c`。

### F217

- 包内路径：`evidence/codex-expansion-20261021/批次校验状态.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`a9a8c320587b8cbe5f5fbffbfde8713fdf703fd9ff60a8c74e1cf0e366864d79`。

### F218

- 包内路径：`evidence/codex-expansion-20261021/本轮统计汇总.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`ed1d881baed4138bec85223cd9e698f2ae5910032f7c8b47d02dc2dc56b6c474`。

### F219

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/context.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`a3d5b7198873f917b42dbd4eeaa662499fb36a01261ef6804692e261b034b2c1`。

### F220

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/criteria.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F221

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/D-测试判定说明.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`7be8af456d1d8e0f3fbbc027cca66af3cb9a6a31e251f32586871a7bd1e82b1c`。

### F222

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/prompt.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`708cd3a65db126da61b4137be03eb938106881eec0c66362eca8e5491c8b57f9`。

### F223

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/protocol-trace.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`d691addf4f9f21541689e421148173bd3fc839204b545ac66bf9b49fa40753f5`。

### F224

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/raw-audit.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`43889cc3e7afa46f74010375177a558bea96a87aa46bb4580c6d1ee3da5e0654`。

### F225

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/raw-audit.schema.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`18fef6ca4907a0c7d144479420062003124712c0186b3da0fc14cd730c8d16d6`。

### F226

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/report.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8263583d5ef1430dc5e9d7dff073faebf5c60001206acc5510debd1ff27f3b8a`。

### F227

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/review-timing.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`25117e9747e17b4072bd17a18995e9af7bb0a7806265eaca55b76e6af590bdcc`。

### F228

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/run-manifest.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`5e967454053cc3ec6b6e5ad80c4076c02a5c404924571bad1b64d33ca3e4aa22`。

### F229

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/sample-context.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`427e2400b1bfadf404cd4a7a5d949dfd775fd8dceb73bf02b949cbce662b8325`。

### F230

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/screenshot.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`c75a0e99460aec2b89d2ca0ace94726800774fc93f9533389303c187769ed428`。

### F231

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/完整问题与建议.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`54850eb05fa4d63a82bbd3aa5d079e0f2a793519a021c966fc7411aaf7cf9708`。

### F232

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/完整问题与建议.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`b45548ec0291ff906bb7dae245b892619d7b3890879c1ac6e75bf4fa57b191dc`。

### F233

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/文件校验.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`3b791fe33dbc440517421b9d52c8c19163b2eed8c63905439496d1a82a4ccd56`。

### F234

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/评审结果.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`eecabbd5194e78a7b1b2bc08a1da5dd91d29308f783d7626fd0b7ba2685caa9e`。

### F235

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/输出对应记录.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`cea24f1ce24ddfc1e4f058afc6348806579c1cc0e72162852a704ba49b91035f`。

### F236

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s03/验证结果.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`521bcdbe9a123080e8675b37db81739a0544e51f081eba4a101a34f7c5b21f05`。

### F237

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/context.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`6adb733aa2fbee101cac0d26b5915e7eaa041349f9b13bd7408adf7389b961f6`。

### F238

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/criteria.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F239

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/D-测试判定说明.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`7be8af456d1d8e0f3fbbc027cca66af3cb9a6a31e251f32586871a7bd1e82b1c`。

### F240

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/prompt.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`708cd3a65db126da61b4137be03eb938106881eec0c66362eca8e5491c8b57f9`。

### F241

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/protocol-trace.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`36910c080ab85879ba72f40e19b1688741f97408649318ad0fcc48e65a38452c`。

### F242

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/raw-audit.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`3c61fde79c789a67d06651652cead475dc8723bc91e495a6d45a65352f2a6671`。

### F243

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/raw-audit.schema.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`18fef6ca4907a0c7d144479420062003124712c0186b3da0fc14cd730c8d16d6`。

### F244

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/report.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`0e65d773ae4890ce2b06fc1bab7fe8e836071d3e10d5e3132a3284116a2c731a`。

### F245

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/review-timing.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`d85333afdeacefadb75a45c35cf3235eedf1d85dd1e505fee01e985d16570da9`。

### F246

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/run-manifest.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`e6e09cf1b925cc838f83f9e41a8febe93a433633e24089262335854e2d961284`。

### F247

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/sample-context.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`276ce9bc5e0eaa847898f343c0a82b3a4593ea3d408a831cbac5e97cfd56ab7e`。

### F248

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/screenshot.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`490a35029c5a2cd09ff5863502d82a2f9c10a169039442ac97ea1654586d71a7`。

### F249

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/完整问题与建议.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8a0b770a932a88d2a68881c82cebebbb0940f8369d589f2b3e6db77035ea6c65`。

### F250

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/完整问题与建议.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`b73f1a9fa2696afeb19d6d68f98a5cd8fb56d1c72762bfb528abd62ccce9ecba`。

### F251

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/文件校验.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`784d8e7d3e6403f469fad029057d0626b1c2259b7158e4fafa28e0528dfe183c`。

### F252

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/评审结果.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`aa656769c8ce36b02f238c1026931886e1e3bd85829140e36b2c78f5add30b87`。

### F253

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/输出对应记录.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`66f969fa20f081b8bdcc89f08c41b94ba85a4b2a7b1108c02847571fefb22391`。

### F254

- 包内路径：`evidence/codex-pilot-v11-20261021/20261021-192850-s07/验证结果.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`ebf9401cd575de73169f6b8f1d6bae3854ac05731ccb35b8e08ce9e5fca334be`。

### F255

- 包内路径：`evidence/codex-pilot-v11-20261021/S03与S07评审汇总.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`e7de7265af905ae51f645239bb8d7fb60a78df5d0e65875a3deb4b3436164b46`。

### F256

- 包内路径：`evidence/codex-pilot-v11-20261021/作者候选开发对照.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`6d86675cfb586bbdeae8e9155637fcf583b0420b99aecbe10e2d3412d7728946`。

### F257

- 包内路径：`evidence/codex-pilot-v11-20261021/开发评测进度.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`556083ce4ed0be48219c575e0d3357b725f05b005d694fb03ff3efa88ca32349`。

### F258

- 包内路径：`evidence/codex-pilot-v11-20261021/执行计划.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`764587b52214b9911ade78830d049158b257c6c48562ae6ae8128810329bab93`。

### F259

- 包内路径：`evidence/codex-pilot-v11-20261021/运行结果汇总.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`9492e69762c3783b73c69449129efe03bf9124288b92831799def1246e7ac8c8`。

### F260

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r02/context.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`08b10ee1a4db770699741b51ce33d6f189c73ce84ccb6bf8cfe017eae53e6c49`。

### F261

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r02/criteria.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F262

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r02/design-goal.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`cad77c132b8f403bbcad298ce0e80ac81a50299613cf15c77d0d13b77f13e151`。

### F263

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r02/goal-review.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8517a1f72c45f1e050b8440f18216f37ef3359d7a143ef54e887ad2afae54f88`。

### F264

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r02/prompt.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`56c7bbe40ec348bbe31ea57d3cae64524dfab3b9e6fd7d9fb9380fdedb10dd84`。

### F265

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r02/prototype.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`9123e383f258a1d4d23597ac216b8440ac9d70ee1f41835ab464bcad93a7a832`。

### F266

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r02/raw-audit.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`40d3ad25bc90185ef6e1ce7c29384945fa1e910397f4df272bb472ed97a130d0`。

### F267

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r02/raw-audit.schema.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`18fef6ca4907a0c7d144479420062003124712c0186b3da0fc14cd730c8d16d6`。

### F268

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r02/report.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`c67fe1422b37de570b0d3235668a5c899853b9641157ff4038d7eee4b3a90ab6`。

### F269

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r02/review-timing.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`a45579f4beaffa2a300f3f135e2e3c33f9dcbff9b52772cfd54576e6d58d4fe7`。

### F270

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r02/run-manifest.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`c5c708a5594b407f1b0d2b4a02d886b8706d319653cb0428409aff16b9e49cc9`。

### F271

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r02/screenshot.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f1201f54c66f3210ed14bd8785f0a3c532ee0e89cd6d3992cfaeb9970b7db1ed`。

### F272

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r02/文件校验.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`4597f7d154b9d1a4c24ef5871d48cea34a1fdf5cb247c9680b6f1027bc9fd6b4`。

### F273

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r02/验证结果.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f40429d7acabfa5a369da893715f2fe8a92b40620535a4d8c74c49802a288048`。

### F274

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r03/context.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`08b10ee1a4db770699741b51ce33d6f189c73ce84ccb6bf8cfe017eae53e6c49`。

### F275

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r03/criteria.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F276

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r03/design-goal.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`cad77c132b8f403bbcad298ce0e80ac81a50299613cf15c77d0d13b77f13e151`。

### F277

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r03/goal-review.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`d0e716293309eb09edbf4bb93af56088b09dbdf0f3a409b43609c096eb4e72ec`。

### F278

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r03/prompt.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`56c7bbe40ec348bbe31ea57d3cae64524dfab3b9e6fd7d9fb9380fdedb10dd84`。

### F279

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r03/prototype.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`9123e383f258a1d4d23597ac216b8440ac9d70ee1f41835ab464bcad93a7a832`。

### F280

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r03/raw-audit.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`d7078d8a23248733acff82d8c8ce9b838c8f4c56ba0cc5ddbb101e8aca30709b`。

### F281

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r03/raw-audit.schema.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`18fef6ca4907a0c7d144479420062003124712c0186b3da0fc14cd730c8d16d6`。

### F282

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r03/report.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`d2207582ca8555a5577c837614f219f529a5ddfaca84b9fd137ad87001ac6af3`。

### F283

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r03/review-timing.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`1bfb3af7030309e9fd7962b424575a760317756cbe5999ee13422fc8781d9671`。

### F284

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r03/run-manifest.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`526f290ad22a023c4504d0a8c50b2d6205a4f355858b54c68e4e92b83184e72c`。

### F285

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r03/screenshot.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f1201f54c66f3210ed14bd8785f0a3c532ee0e89cd6d3992cfaeb9970b7db1ed`。

### F286

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r03/文件校验.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`a63048bc313257cfd64cc8575ccaa25d956308bb4d3c79f8e8e5618ea8a58881`。

### F287

- 包内路径：`evidence/codex-repeat-20261021/20261021-190558-r03/验证结果.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`dff1f795b8a1ac0f6899cd436e6f17849de13718b4d64508751242a7f53490b1`。

### F288

- 包内路径：`evidence/codex-repeat-20261021/三轮一致性对照.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`fed88d5dc27d045df3a1aa885ab18ff06c3431dccdecf6017495cc060441faf3`。

### F289

- 包内路径：`evidence/codex-repeat-20261021/三轮一致性结果.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`a5a8fcc31cb8a73e4ea70749fa83d8573d178a5d0777350b21b61285fcfbe76b`。

### F290

- 包内路径：`evidence/codex-repeat-20261021/对照方案.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`385f8a8c72c459f2440a939ba1a902053a51eed75b4fe50bc161e4036b3f2231`。

### F291

- 包内路径：`evidence/codex-repeat-20261021/对照结论.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`6da104c78046a9402a22d433c024e6b2c9590d4a7a8e88e45bb086e2219045e4`。

### F292

- 包内路径：`evidence/codex-repeat-20261021/汇总文件校验.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`bcb428489e6f996c43e80c17ff5d3ea1cf4c188e9ef1c9fa740782c5c765deed`。

### F293

- 包内路径：`evidence/codex-run-20261021/20261021-185001/assemble_codex_run.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`483f4457765cf091f373b0e0099f03581ac86afe02f88a8cc894fa973c6b3bc8`。

### F294

- 包内路径：`evidence/codex-run-20261021/20261021-185001/context.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`08b10ee1a4db770699741b51ce33d6f189c73ce84ccb6bf8cfe017eae53e6c49`。

### F295

- 包内路径：`evidence/codex-run-20261021/20261021-185001/criteria.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F296

- 包内路径：`evidence/codex-run-20261021/20261021-185001/design-goal.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`cad77c132b8f403bbcad298ce0e80ac81a50299613cf15c77d0d13b77f13e151`。

### F297

- 包内路径：`evidence/codex-run-20261021/20261021-185001/goal-review.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8597ecdbced8f54c1684b40b9e75000d58d35bd9bcf71b0959e831d63ff7e121`。

### F298

- 包内路径：`evidence/codex-run-20261021/20261021-185001/prompt.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`56c7bbe40ec348bbe31ea57d3cae64524dfab3b9e6fd7d9fb9380fdedb10dd84`。

### F299

- 包内路径：`evidence/codex-run-20261021/20261021-185001/prototype.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`9123e383f258a1d4d23597ac216b8440ac9d70ee1f41835ab464bcad93a7a832`。

### F300

- 包内路径：`evidence/codex-run-20261021/20261021-185001/raw-audit.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`d8aca745a8f97c6e54ee30cd9303fb68c68415cae3c3d5dd993f550506b293d1`。

### F301

- 包内路径：`evidence/codex-run-20261021/20261021-185001/raw-audit.schema.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`18fef6ca4907a0c7d144479420062003124712c0186b3da0fc14cd730c8d16d6`。

### F302

- 包内路径：`evidence/codex-run-20261021/20261021-185001/report.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`04eee8b9eb6759752b1e89ef9e5ac36a3f31aca6ff81ed036b9490f045929db5`。

### F303

- 包内路径：`evidence/codex-run-20261021/20261021-185001/review-timing.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`e11d13e9281f6a4841ed1fe248a1f99cd8dac045cf777280e14c5d6bc7f3f533`。

### F304

- 包内路径：`evidence/codex-run-20261021/20261021-185001/run-manifest.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`7581c127b807dfd3dead11b34ad43186e0028b2b54db4b05b0a24c5d94044f5f`。

### F305

- 包内路径：`evidence/codex-run-20261021/20261021-185001/screenshot.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f1201f54c66f3210ed14bd8785f0a3c532ee0e89cd6d3992cfaeb9970b7db1ed`。

### F306

- 包内路径：`evidence/codex-run-20261021/20261021-185001/文件校验.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`28a958c276b3285eed9ece34d4167cefcea950a55808a693223f0b2753182005`。

### F307

- 包内路径：`evidence/codex-run-20261021/20261021-185001/评审报告.html`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`cc74966270bc56401fb8382b621abe7aa8898f3fc3386d0d125fb9f719e894ee`。

### F308

- 包内路径：`evidence/codex-run-20261021/20261021-185001/评审报告.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`ef872164c1574956bff27102712df1750ead5ad34cf803a0f2e8c9b4bd53a3e4`。

### F309

- 包内路径：`evidence/codex-run-20261021/20261021-185001/验证结果.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f663be89a804f77d424700bb2a04b6d21122826f2e94a8845b020cb1203e7718`。

### F310

- 包内路径：`evidence/d-protocol-20261021/D-测试判定说明.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`7be8af456d1d8e0f3fbbc027cca66af3cb9a6a31e251f32586871a7bd1e82b1c`。

### F311

- 包内路径：`evidence/d-protocol-20261021/GitHub材料核对.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f27dad94fb835d1f7187225b39190006c0b3dbd5bf673371a54987ca4e12036d`。

### F312

- 包内路径：`evidence/d-protocol-20261021/下一轮样本清单.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`745c631e68d328cee0668f7b4c98fb3bb7dd812b3adb555efdad30a702eb9fe6`。

### F313

- 包内路径：`evidence/d-protocol-20261021/交付校验.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`bdf98fb613d4086e3f0fef3c46e03f899dfbe12f91bb7bffe3411ec5908cc49c`。

### F314

- 包内路径：`evidence/d-protocol-20261021/判定版本记录.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`5ff359980221d031f79bcc9048be8f7e430a507a45214edd513f38ca0a1a8ee6`。

### F315

- 包内路径：`evidence/d-protocol-20261021/本地材料盘点.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`72b2a406efc8be5ca0249e0064d0435164acf8543b9b923566549deac2e26ccc`。

### F316

- 包内路径：`evidence/d-protocol-20261021/现有材料与下一轮测试.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`5a965326e18aacf1e0e371d0dabb615d1e24751774d93c0d65e76b36b8adb184`。

### F317

- 包内路径：`evidence/development-samples-20261019/03_D测试记录工作簿.xlsx`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`e2378b61c532d7f9be7228679661ea8945a91c7e35b80576e48e23472db47072`。

### F318

- 包内路径：`evidence/development-samples-20261019/samples/manifest.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`984341fbc2f3d7291352fbf3eaee62d6a23cc24d41ef349b8d51c2b388dca7b3`。

### F319

- 包内路径：`evidence/development-samples-20261019/samples/S01.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`4a0859d3eba534c34695a917fbacba8b50362be7c5b027d22a0926bc02c79920`。

### F320

- 包内路径：`evidence/development-samples-20261019/samples/S02.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`e4775cb3ce705aa467dcc7acf86ade8ad0d01d0256c8ba9502fbabdcc6be60c1`。

### F321

- 包内路径：`evidence/development-samples-20261019/samples/S03.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`c75a0e99460aec2b89d2ca0ace94726800774fc93f9533389303c187769ed428`。

### F322

- 包内路径：`evidence/development-samples-20261019/samples/S04.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`b0e713bc2416d64497e84c304ffb10fff344f2211e98fc420679f241c81af753`。

### F323

- 包内路径：`evidence/development-samples-20261019/samples/S05.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`3defd879aeabf83dfdd97d127a395eb414aba55eb577422c03965d4cb6bde65b`。

### F324

- 包内路径：`evidence/development-samples-20261019/samples/S06.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8dc2c05d309b08c48469ddac08bb7b2bfca95a3c2fbdea497300bfa492e065ab`。

### F325

- 包内路径：`evidence/development-samples-20261019/samples/S07.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`490a35029c5a2cd09ff5863502d82a2f9c10a169039442ac97ea1654586d71a7`。

### F326

- 包内路径：`evidence/development-samples-20261019/samples/S08.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`47ee014f811d950d32cc0ab418677a199a432d99a931430498fe580514b38aeb`。

### F327

- 包内路径：`evidence/development-samples-20261019/samples/S09.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`2e57845dcbba1ded443fb35475a85d303a815321869e550236cc475a0a970a85`。

### F328

- 包内路径：`evidence/development-samples-20261019/samples/S10.png`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`630fffc802a477cc581ed483bf4460a562333e1bd61ea101d9387ae5d2511600`。

### F329

- 包内路径：`evidence/development-samples-20261019/主持人参考/素材清单_含预设覆盖规则.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`984341fbc2f3d7291352fbf3eaee62d6a23cc24d41ef349b8d51c2b388dca7b3`。

### F330

- 包内路径：`evidence/development-samples-20261019/主持人参考/预设候选_非专家标注.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`4bd9b72fac4ec788a4321b0ecc4f2ff95d0864facb584847d7e065d11d77c627`。

### F331

- 包内路径：`evidence/first-run/evidence/archive_audit.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`21bf7c45382ce7dc7081940282b6cf548686c4f95861974838856323f6af3be6`。

### F332

- 包内路径：`evidence/first-run/evidence/d_runtime_edges_findings.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f3f3d1b1ed162d0a1d5128eb3168bb9d6580e16d1fdeea92fea0b9fd9b2af9ae`。

### F333

- 包内路径：`evidence/first-run/evidence/d_runtime_edges_harness_initial.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`7c9e199f4a57ddf463171a7ae3a424a8c4f8ec9384d3e60b80d89d62a59d4c7f`。

### F334

- 包内路径：`evidence/first-run/evidence/d_runtime_edges_harness_initial.log`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`eac441f531cc6c2b1f319d8ff49abad0ed741003fc7715a0e1d2dafacd11ac8b`。

### F335

- 包内路径：`evidence/first-run/evidence/d_runtime_edges_result.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`12c3555b450c7ebc96754a292c4775af64a6aa964a2e0b79e9f155dcec9162f7`。

### F336

- 包内路径：`evidence/first-run/evidence/d_runtime_edges_result.log`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`fb84cc66dd3c21cf5678ffcbd86064fc59e57443dc55baa20d281e8976385d94`。

### F337

- 包内路径：`evidence/first-run/evidence/visual_audit.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`222eaf239e180f8f25f030cd6b9cf4f3aa32ac756d8f1f865eb8714a295d8378`。

### F338

- 包内路径：`evidence/first-run/execution_results.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`03a827227ad7c72a17af61f4083c7624e989b2591d5115eef609791d00073f4a`。

### F339

- 包内路径：`evidence/first-run/logs/health_empty_key.log`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`0e33862735c751a200d1a808ec6929d32fb97f8d89c48b44c437653db3ec5f28`。

### F340

- 包内路径：`evidence/first-run/logs/metrics_replay_1.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f23a2a036da6d1130006d69097ac98070c032d45fc4374c92f747aa29f53ae7a`。

### F341

- 包内路径：`evidence/first-run/logs/metrics_replay_2.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f23a2a036da6d1130006d69097ac98070c032d45fc4374c92f747aa29f53ae7a`。

### F342

- 包内路径：`evidence/first-run/logs/metrics_replay_3.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f23a2a036da6d1130006d69097ac98070c032d45fc4374c92f747aa29f53ae7a`。

### F343

- 包内路径：`evidence/first-run/logs/pip_freeze.log`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f3202123f62e022dcda50d1aa31fa22c05ad014c7a81dd9a30c9db87293e4799`。

### F344

- 包内路径：`evidence/first-run/logs/pytest_existing.xml`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`4096f162fed875315dd8fd3337a8cc785cf30a8c74645dd0c5b7f7b9f8a7f5d0`。

### F345

- 包内路径：`evidence/first-run/logs/pytest_fresh_archive.log`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`39b8e7c0d2286da3aeabd5259ea6ff282811881ff107b5f08c07edec1cd26890`。

### F346

- 包内路径：`evidence/first-run/logs/pytest_with_example_config.log`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`ebce929b21748089dad8a2242c3def473b2e76351309625d86b76e66a57b5e3e`。

### F347

- 包内路径：`evidence/first-run/logs/sample_uploads.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`1302a1b39aa673bdcec419065fd5a90d6b0c5be9ff8c66f113ff75d18902b8d1`。

### F348

- 包内路径：`evidence/first-run/logs/validate_config_empty_key.log`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`5e723f3ea7620db16a28a88fc3990b16bbce99aaac799d4d91ee91f9e5f1a1a3`。

### F349

- 包内路径：`evidence/first-run/logs/validate_criteria.log`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`18d8eea2d81f6ecbbff40d34f2db320fe989d0da53f0fa5755bd6466be4d446b`。

### F350

- 包内路径：`evidence/first-run/reproduce/original_local_run_d_checks.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`31a3c118c2d0a122a837731fd43ee8be125374d8f3113e3955dde2a1804f3f69`。

### F351

- 包内路径：`evidence/first-run/reproduce/test_d_runtime_edges.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`23d8f9bd4d88e9ce47e9ae57cd2b52a3a4b01efc47f6cf5fab7257e38feed2c8`。

### F352

- 包内路径：`evidence/first-run/reproduce/复现说明.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`bb4265b63806d04752ba9f05a71f1769c13fdb0c639aebab95068c0d129c707b`。

### F353

- 包内路径：`evidence/fixes/logs/all_tests.log`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`edf82f5bbfa8936ebbd6ac3d1666c4720fb9b7e189f20031f6d86ba1aaad4517`。

### F354

- 包内路径：`evidence/fixes/logs/all_tests.xml`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`de183906421984245b03d093e83925c22822985bb1cc2d8e88976e24787b6d55`。

### F355

- 包内路径：`evidence/fixes/logs/dependencies.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f3202123f62e022dcda50d1aa31fa22c05ad014c7a81dd9a30c9db87293e4799`。

### F356

- 包内路径：`evidence/fixes/logs/patch_check.log`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`d1810735143d66f0a86dcbdf2ad0ae26d69626ea544d4fae4f56cd351406e2b9`。

### F357

- 包内路径：`evidence/fixes/review_result.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8ac841dbc2aed69f63b4910c10b3bb1e0ae22fffb722dac2180adb43d9c09c5d`。

### F358

- 包内路径：`evidence/fixes/verification_results.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`99c1671269f2df70935fe764d2789a2972778b8579875c6bc1e0f42685f708a3`。

### F359

- 包内路径：`evidence/original-report-20261021/D-阶段性报告.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8cc2e5cc895484157cf6cd427d9c720ae90a6f93221f18ad1df1033a2167b746`。

### F360

- 包内路径：`evidence/original-report-20261021/D-验证证据.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`fc9d83efe31ede39a416bd6cb4b91a4fafbf1645eb58a941d4ff8db14c8f95dd`。

### F361

- 包内路径：`evidence/original-report-20261021/报告更新校验.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`bdee64c68b72419508cbf0128cadfcef5cbe8a064e26b95e96a02e3195019fa3`。

### F362

- 包内路径：`evidence/repository-docs-20261021/2026-10-21-修复说明.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`3dfe394f4811d777ab10ab52f46c5325f7e1ce7d4c2f119df89e97247e24cf66`。

### F363

- 包内路径：`evidence/repository-docs-20261021/b-engine-v2-plan.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`7754bdf59679e49976a270edc212b32c8480b9b528975a2f61253ec0e196ea43`。

### F364

- 包内路径：`evidence/repository-docs-20261021/config-setup.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`79a3947ffcaca005fa21c33916ddbc98d4296f4d585e45f644fb10311520b07e`。

### F365

- 包内路径：`evidence/repository-docs-20261021/D-交付进度.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`c8701f70eb23dfaf938afd33d5540adb24d2e3824a54abdd235b7efe8b440dbc`。

### F366

- 包内路径：`evidence/repository-docs-20261021/D-单案例复核勘误.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`89217e2d931d9014c24e0c94cc8a2d3ad06a17f0451537013e72c7baa0c3616d`。

### F367

- 包内路径：`evidence/repository-docs-20261021/D-真人测试记录模板.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`2b6af5f75dceca1e5b3d033a1758f75f05feb25144b8b27135b4e44660c20b3f`。

### F368

- 包内路径：`evidence/repository-docs-20261021/staged-workflow.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`2bb3255742a0b08bbe7bf529a004487d439cf92894aefe71061ccbf18b3cdad9`。

### F369

- 包内路径：`evidence/s07-fix-20261021/logs/full-regression.log`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`389b76bb7d4c6155643d79a104c923c542ead682e6dc02b324621291cedfbdf1`。

### F370

- 包内路径：`evidence/s07-fix-20261021/logs/full-regression.xml`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`73ff61b2362f721b0faeb7fbd69f1a3b1362eaddb82e86e4ffa7e41233347a08`。

### F371

- 包内路径：`evidence/s07-fix-20261021/replay-after/S03/report.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`e8aedaa2c3bcf2c23ab4859e65f3cee08d5d01e2ebcedb5cf9b713a4f885a37b`。

### F372

- 包内路径：`evidence/s07-fix-20261021/replay-after/S03/评审结果.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`b5736b776dec0613fcd7213c369f27c85d821d3f2e9345d66472a5f29e6543c4`。

### F373

- 包内路径：`evidence/s07-fix-20261021/replay-after/S03/验证结果.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`0625cc83e33c8cb268746212421b94608f5bf709f09d3ab81a1bed701c23c159`。

### F374

- 包内路径：`evidence/s07-fix-20261021/replay-after/S07/report.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`22dc6bb9a6ddc80af5a69d57c63a40e2276a5e22f4229b57c35b48a48858b652`。

### F375

- 包内路径：`evidence/s07-fix-20261021/replay-after/S07/评审结果.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`00f0ee97c85a0503ded18b64fd278f86e84448024096d08f8b5f58d2dfac099a`。

### F376

- 包内路径：`evidence/s07-fix-20261021/replay-after/S07/验证结果.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`ce70bf23ea1838c4aac06d3304790099ba1ae1fad94824b220d0996cbb6af2cb`。

### F377

- 包内路径：`evidence/s07-fix-20261021/replay-before/S03/report.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`d9e70b3c548f0899c88668009564997e0e5a1fdb13f4c648ece90d11df04a12c`。

### F378

- 包内路径：`evidence/s07-fix-20261021/replay-before/S03/验证结果.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`0748d0ce451660ac2ea436100af84467fb7821fea1c7bc6207320583d44ec87e`。

### F379

- 包内路径：`evidence/s07-fix-20261021/replay-before/S07/report.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`bbee3f9c533e0022d220ff8b1efd79bcd2f02b78910ebe9a064d999b5e0c2cc1`。

### F380

- 包内路径：`evidence/s07-fix-20261021/replay-before/S07/验证结果.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`48972fbcf8e5770bba12baf0259009e084dbda63301ea55228d10567c7efb59a`。

### F381

- 包内路径：`evidence/s07-fix-20261021/S07去重修复与复测.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`2bd2e562cc50885ea3b5bea9936b144b12606d8fe3d9f1ac8d1986d2e14aa150`。

### F382

- 包内路径：`evidence/s07-fix-20261021/交付校验.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`2f83010504de35cd537f603fc2c5fe6e9815403fcc34973ac8580efe4852d3cc`。

### F383

- 包内路径：`evidence/s07-fix-20261021/修复与复测汇总.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`32125d6bd408aeffcca63d6b3a72cfd1118a9a91ea6816f88aeef23416ac442e`。

### F384

- 包内路径：`evidence/s07-fix-20261021/修复基线.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`d159dad8e96ec1eb6529d0291e7c9f6f13f9ecd91f64c5c3abd38a70a74a9b35`。

### F385

- 包内路径：`evidence/s07-fix-20261021/修改文件清单.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`6949f6a0605726fab59eaea64d4bd80a01804f9e5ddcbd04e17792d835ee15ec`。

### F386

- 包内路径：`evidence/s07-fix-20261021/回归测试结果.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`6311b5f606d8fe1ae5216d1854a5ca831263c1ca22c06645958a65f05ad96316`。

### F387

- 包内路径：`evidence/s07-fix-20261021/回放结果_after.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8d3b86cd6ac5cc0331ec2316632499ae166175d126562bbff49bc7af0549bb54`。

### F388

- 包内路径：`evidence/s07-fix-20261021/回放结果_before.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`590cdf21409a5a76a4f4390342929ee5ca4c836a82a9cca05458a9f11dd5c13d`。

### F389

- 包内路径：`evidence/s07-fix-20261021/本地修改.diff`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`1fd295a30978ec4e7853e41001c44f2a0e02ead64af5a520c06290a5a35f7fbe`。

### F390

- 包内路径：`frontend-qa/C前端交付验收.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`63bc876c9fb666fdf81356f0ce43d95d8d802f211a0b56a3beb450b17b56d9ea`。

### F391

- 包内路径：`frontend-qa/C前端交付验收.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`9155c551063bffefe7c053acdfb6744c83e316dc22098b4a16fdae31cd99f9fe`。

### F392

- 包内路径：`frontend-qa/C前端操作验收.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`aa5b35e609622da4b8d0d234b69ecb0c69d12c1f001f6ea0021813fcfb7e8058`。

### F393

- 包内路径：`frontend-qa/frontend-node-test-exit-code.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`13bf7b3039c63bf5a50491fa3cfd8eb4e699d1ba1436315aef9cbe5711530354`。

### F394

- 包内路径：`frontend-qa/frontend-node-test-stdout.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`594c972fa12200cbb5bd30d57f1c897ffce6c5d6aba13d74c91966f49a7bf754`。

### F395

- 包内路径：`frontend-qa/frontend-syntax-checks.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8bcc23a2340ce6c81c7b5a05ea8be28d3add3ecfebe19e46f5acddc0c204785c`。

### F396

- 包内路径：`frontend-qa/node-version.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`0696fc75ebdd632c8c328370653d4dddc37504bf96b32317a50d7189cc1a775f`。

### F397

- 包内路径：`frontend-qa/S07前端适配核对-stdout.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`907a326c723b828b0684fe14aeddfb74ff196062da8bbcaa7109dcbfae80e842`。

### F398

- 包内路径：`frontend-qa/S07前端适配核对.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`aaac29e6846951a1cd7ade82fa8d4fea93e9041d285a30cd9bf2faf08ee9243f`。

### F399

- 包内路径：`frontend-qa/刷新后页面状态.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`837a6246017b3e2381cead78f1b9556fa0700d0135f6210e90a8490fbe38494c`。

### F400

- 包内路径：`frontend-qa/浏览器操作验收.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`c69b54ba9b1c00440115b40c10db7a270abe5bbdcb63bfb1bf12bb41576b9a28`。

### F401

- 包内路径：`frontend-qa/浏览器操作验收.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`0a1b5a487346b6c51f1805f1d281bc4c1c3ec95af4f0b1740dbac161d107be8b`。

### F402

- 包内路径：`frontend-qa/评审报告-v1.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`c2fec8a53e11c51eec0dd32f1da1fa42f3589bd2941ed28d93dc8984e2bb98eb`。

### F403

- 包内路径：`frontend-qa/评审报告-v2.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`0c42e770f902923307155467deade0be679139bce8e67fd2267c1f2c8956b989`。

### F404

- 包内路径：`frontend-qa/评审报告-v3.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`96c830e6359d0ba5d6ed955775ac28568d2c4ab3faa2cd42b9d469f9981b87c1`。

### F405

- 包内路径：`frontend-qa/评审报告-v4.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f92d297ce7e77e26473ca6c770855849cca3eab45f2eafef52d6d6195850c5dd`。

### F406

- 包内路径：`human-study/00_执行清单.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`fe9bb1e39ad5c18734c98931c5d44665bb9d30a15cba39d5ce97e8dea92198bf`。

### F407

- 包内路径：`human-study/blind-review/criteria.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F408

- 包内路径：`human-study/blind-review/D-v1.1判定口径.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`e1996f5e073c6c9d2e839bca83e08b4d29921e7e2b2a79f6ca43aabc2cef5bb2`。

### F409

- 包内路径：`human-study/blind-review/gallery.html`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`0aab6852a2400af834ee8604f18f209731874a290fe5cd4cd0c2ed16e7317bb7`。

### F410

- 包内路径：`human-study/blind-review/images/P01-prototype.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`9123e383f258a1d4d23597ac216b8440ac9d70ee1f41835ab464bcad93a7a832`。

### F411

- 包内路径：`human-study/blind-review/images/P01.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f1201f54c66f3210ed14bd8785f0a3c532ee0e89cd6d3992cfaeb9970b7db1ed`。

### F412

- 包内路径：`human-study/blind-review/images/S01.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`4a0859d3eba534c34695a917fbacba8b50362be7c5b027d22a0926bc02c79920`。

### F413

- 包内路径：`human-study/blind-review/images/S02.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`e4775cb3ce705aa467dcc7acf86ade8ad0d01d0256c8ba9502fbabdcc6be60c1`。

### F414

- 包内路径：`human-study/blind-review/images/S03.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`c75a0e99460aec2b89d2ca0ace94726800774fc93f9533389303c187769ed428`。

### F415

- 包内路径：`human-study/blind-review/images/S04.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`b0e713bc2416d64497e84c304ffb10fff344f2211e98fc420679f241c81af753`。

### F416

- 包内路径：`human-study/blind-review/images/S05.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`3defd879aeabf83dfdd97d127a395eb414aba55eb577422c03965d4cb6bde65b`。

### F417

- 包内路径：`human-study/blind-review/images/S06.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8dc2c05d309b08c48469ddac08bb7b2bfca95a3c2fbdea497300bfa492e065ab`。

### F418

- 包内路径：`human-study/blind-review/images/S07.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`490a35029c5a2cd09ff5863502d82a2f9c10a169039442ac97ea1654586d71a7`。

### F419

- 包内路径：`human-study/blind-review/images/S08.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`47ee014f811d950d32cc0ab418677a199a432d99a931430498fe580514b38aeb`。

### F420

- 包内路径：`human-study/blind-review/images/S09.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`2e57845dcbba1ded443fb35475a85d303a815321869e550236cc475a0a970a85`。

### F421

- 包内路径：`human-study/blind-review/images/S10.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`630fffc802a477cc581ed483bf4460a562333e1bd61ea101d9387ae5d2511600`。

### F422

- 包内路径：`human-study/blind-review/共识参考_空白.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`d6f18b16ed3c01d19f8cb25c4e7e4639419cdb71e15765cc68627093286e3a30`。

### F423

- 包内路径：`human-study/blind-review/独立标注模板.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`1aaf89d5402f24b17ef58c291abbfcb1c3fcd4e82de880eec6dce92ec8e03fc4`。

### F424

- 包内路径：`human-study/recognition/assets/P01.png`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f1201f54c66f3210ed14bd8785f0a3c532ee0e89cd6d3992cfaeb9970b7db1ed`。

### F425

- 包内路径：`human-study/recognition/index.html`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`99a376f90c8989f88c8784773b1dab70cf962cd825c69fb03f69b35c77d11c51`。

### F426

- 包内路径：`human-study/recognition/主持人判分表.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`17d7abafe39d35ca5827c27465b6cbbec628580f502f1a0d5352b42acc9052dc`。

### F427

- 包内路径：`human-study/recognition/主持人执行卡.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8a75af7043c3a40262c9e158f79b1cd9b82227dd423613693f39706aedb7d179`。

### F428

- 包内路径：`human-study/recognition/执行方案.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`a259868a35986c26320dab4a6e2120e55581fe5cb21dd615ce2872be091423bb`。

### F429

- 包内路径：`human-study/工具体验与界面验收.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`e6fa54fc44aef325385601822ba74d6f817202630406f95a17808486ab92e5b9`。

### F430

- 包内路径：`publication-manifest.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`64abffbc30674144b7e625fce5fc8fc8fcc4742744a1c3f461a786069a27af2d`。

### F431

- 包内路径：`README.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`d4143eb78310d3430d740c68622f995136dc0563a8bcac8d68f1fa50e6bf6e08`。

### F432

- 包内路径：`reference/c-delivery-9780c03/交互界面README要求核对.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`a9cd561b5f6f45b369630b81ff773b0511c9d16ce9942392d989bb8bc9f8ffe4`。

### F433

- 包内路径：`reference/c-delivery-9780c03/交互界面复审补充功能已实现与B替换说明.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`c330f3df68b872f220dad6f3de2e824bd5a0537ed03b6f521169d484f5cecbc1`。

### F434

- 包内路径：`reference/c-delivery-9780c03/交互界面课程报告初稿.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`051c8060708bb0cdd84a68d62156a7ca1529658b33abcb77bcb330879f12227a`。

### F435

- 包内路径：`reference/c-delivery-9780c03/本地联调测试结果.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`1f7fa0b6b13166ce033d89df9ae6313982b33b792dd2a8158fa3f43578a06dea`。

### F436

- 包内路径：`reference/repository-README.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`c8dc445854290f1bc98bf53494563c1512e4b7d7be8a4faf19e2382beec536b2`。

### F437

- 包内路径：`reproduction/expansion-scripts/assemble_local_package.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`08ec9705d41ef46d8d5e1dac8968e301acd715d4b917b936e854c8934210a3f3`。

### F438

- 包内路径：`reproduction/expansion-scripts/build_human_kit.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`1345e41e278e0d4dc3ff5b890459129365b265dbf4345fee4f2cf3e874761342`。

### F439

- 包内路径：`reproduction/expansion-scripts/check-s07-frontend.mjs`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`6b80443ffe79cbcdacc317bef6cf03798835bc3fa8c27444bb261916ca81e6a5`。

### F440

- 包内路径：`reproduction/expansion-scripts/finalize.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f7035d520834b3c8a5129af9804e20cd361bcc31e515cbe3b993887bd3cafac7`。

### F441

- 包内路径：`reproduction/expansion-scripts/finalize_package.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`81319b0c4da7b3e8ab84a174832795a80b0103b3ec4be1512352f51df0b60263`。

### F442

- 包内路径：`reproduction/expansion-scripts/prepare.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`685c51f43f99e2a3adabbc3a540342a3cf5a95084c542b172a4bb365ee0062b3`。

### F443

- 包内路径：`reproduction/expansion-scripts/test_recognition.cjs`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8f574f418221af924ad92899927f71559c3f519d9047cdfeebe14f57982e8a37`。

### F444

- 包内路径：`reproduction/original-scripts/replay_saved_audits.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`e2867c83e313cbcdaab7d2c6ec07ed3becd7c3aaa0880543e7c72a4237252328`。

### F445

- 包内路径：`reproduction/original-scripts/run_regression.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`750c18a6b21a72869c7062306dac2a25679fbafcbbe77acfefdbf3f39aff31c7`。

### F446

- 包内路径：`reproduction/original-scripts/update_d_report.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`e7dfead5f6d5e05cc54d7ade9e533fb8637c58ed47672f8d00a458596c4993df`。

### F447

- 包内路径：`reproduction/source/.env.example`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f4268241f10109e18ea76319658b9d66f2c3f161ed5e275f6706322e260f5019`。

### F448

- 包内路径：`reproduction/source/config/reviewer.example.toml`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`93a30dc31ea0749b5e07beb76391e203aa796c9472a6a1460b786a6d852024ad`。

### F449

- 包内路径：`reproduction/source/docs/2026-10-21-S07去重修复.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`eb2fdfe8c4829ce9c406561975cc3886e9ee5a23e3928228f595477c0e28dd51`。

### F450

- 包内路径：`reproduction/source/docs/b-engine.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`6fe9cc22ce4f2071d39fc31c1af2902c394d761007c309a01077c907062fd713`。

### F451

- 包内路径：`reproduction/source/engine/__init__.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`da2285a034bd7863a5e8a66732818fb2bee6dec216db131441ed96ff2f9380cc`。

### F452

- 包内路径：`reproduction/source/engine/__main__.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`6d8b7d7846a845059d7a3107143f11131f63c5511d669b44085b15ec5e3d2279`。

### F453

- 包内路径：`reproduction/source/engine/advanced.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`cf1c7349ebadcce288f3b81a17ba245f7b7414014280ae89c646e2bf5a922e08`。

### F454

- 包内路径：`reproduction/source/engine/advanced_contracts.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8a07229d309cd6560336dfc9a31e01ea843239416e193a1fb552acd3d58bb810`。

### F455

- 包内路径：`reproduction/source/engine/api.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`cac473d1f7219bd4477e9eeb1fd4259080bd6b886d4718f203e2ca692c055f98`。

### F456

- 包内路径：`reproduction/source/engine/cli.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`06c2a17a476f8370224b09f286f25ad0efe304c7aa43572cb0fa7f6abc442d92`。

### F457

- 包内路径：`reproduction/source/engine/config.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f44b0af6726d67ce6ded5c9207e0d15cf436a017fc2864a590e4c512438ea68d`。

### F458

- 包内路径：`reproduction/source/engine/contracts.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`d54c190392d698aa5015d570446e7a8dd184c3c4f5eabfc5e4b8c5a20d1b478f`。

### F459

- 包内路径：`reproduction/source/engine/criteria.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`b9e7da89e005d84fb7021fd5649a694cd43364ad0868b325b0592584b7941851`。

### F460

- 包内路径：`reproduction/source/engine/cv_metrics.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`5a0d7e8f72c11b6a0c502b19698108f54d401042b8771acb985a891dd773fb32`。

### F461

- 包内路径：`reproduction/source/engine/errors.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`f1a4e952e3095cfc3937b3c691d713337af4d4aeee4a56700478e13a54bed85c`。

### F462

- 包内路径：`reproduction/source/engine/imaging.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`7a3b957545f5e1c1742ba854d5a5923648112910d5035b2ccfc65358c0e2ebd1`。

### F463

- 包内路径：`reproduction/source/engine/local_model.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`047b6b2e501e1d61b1f3a3953bf5f832a0d7a6668ac7cea7a2f5d1dee7ab4d31`。

### F464

- 包内路径：`reproduction/source/engine/model.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`133fbb60c55aa215d26eb39e9c718a538a6b45b0950e74b1b973d96d5e1ba541`。

### F465

- 包内路径：`reproduction/source/engine/parsing.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`14f0d0150ca23398aeac83507e914795c9318678fa34662ad460c2e7791a0019`。

### F466

- 包内路径：`reproduction/source/engine/prompting.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`079f5e186bc63e9c5e3c23e69c6da0819e38e84c1987149fcfd77d22f254fd3d`。

### F467

- 包内路径：`reproduction/source/engine/runtime.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`222654e538f3d455db992591bad8786e787f21790d3e2c50d7058d2f81deace3`。

### F468

- 包内路径：`reproduction/source/engine/service.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`daada6a3bd0d5a158c2e59878abff77b76901f66781c4062936f683fcb2e53a7`。

### F469

- 包内路径：`reproduction/source/engine/staged.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`84b851f5dbe2668442743993325c95808a182673936d2d535901b7b64a1e4f04`。

### F470

- 包内路径：`reproduction/source/engine/stub.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`4cb3ab8928fef96ab0c57b4e1e06ec54d0ae67cae7d437cdf754c62a0009ae84`。

### F471

- 包内路径：`reproduction/source/fixtures/s07_raw_audit.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`3c61fde79c789a67d06651652cead475dc8723bc91e495a6d45a65352f2a6671`。

### F472

- 包内路径：`reproduction/source/README.md`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`c8dc445854290f1bc98bf53494563c1512e4b7d7be8a4faf19e2382beec536b2`。

### F473

- 包内路径：`reproduction/source/requirements-dev.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8636f9ab1a075be9f3039e2a6471837259c4f36b625bcaf7a3d9a1edd2419c6d`。

### F474

- 包内路径：`reproduction/source/requirements-perception.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`de93546979e43c0e231eee38bcfd4f5b72216c7d24c9021d480fb3e4b1e3184a`。

### F475

- 包内路径：`reproduction/source/requirements.txt`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`26e2d0ad0ec36406e8830b587cc0a3b9d0a69c9686264abc809fd62e97196f63`。

### F476

- 包内路径：`reproduction/source/tests/test_api.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`51838839a8ba451e256d8f1f92d919c513d3bdf4124c1cd60d4b8911fb75f6d6`。

### F477

- 包内路径：`reproduction/source/tests/test_config.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`c652c07b6a3a81d368c15a3adbafa7f0d3d4e1f28df22cdeccd872a2e8bdb7ed`。

### F478

- 包内路径：`reproduction/source/tests/test_d_regressions.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`ac7eaa2db703c6a7aaa5ce2f28a6d0ca05c0d880617aa162cea956a04072c251`。

### F479

- 包内路径：`reproduction/source/tests/test_engine.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`1b9796e2a3c2935453ba56185fb942838b1520cc0b1d2819382f62c3610e4328`。

### F480

- 包内路径：`reproduction/source/tests/test_finding_deduplication.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`a5dd6ab9c7e74a24e5065e5a29b4b42d22b3a13590e674d32378ea2c20b1a531`。

### F481

- 包内路径：`reproduction/source/tests/test_input_limits.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`4459064adec3284a2f1f1aa72198ce5eb4b6ae76bb959a32cc4cc8b8c013e9c6`。

### F482

- 包内路径：`reproduction/source/tests/test_model.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`eac22d21ce016fb1ede8b56d3deeb6a39680a38449e0d690246393cc2cf3741b`。

### F483

- 包内路径：`reproduction/source/tests/test_normalization_conflicts.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`d89edd60b61c4ebfb962bdc6c18cc2ea5b51ef1144bb8deec922dc7367597c2d`。

### F484

- 包内路径：`reproduction/source/tests/test_parsing.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`09d74cac7e6a58cfaa1b6577d62f1ffa8b9bf68b991cf305e354a50772c0101f`。

### F485

- 包内路径：`reproduction/source/tests/test_review_recovery.py`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`39f17ac3bd16b3cb3ef9835963e6d417231317cc59bbab2534ba01fbd0459c16`。

### F486

- 包内路径：`reproduction/source/判据库_v1.json`。
- 下载：[前期支撑](../deliverables/2026-10-21-d-expansion-history.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F487

- 包内路径：`reproduction/source-9780c03/.env.example`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f4268241f10109e18ea76319658b9d66f2c3f161ed5e275f6706322e260f5019`。

### F488

- 包内路径：`reproduction/source-9780c03/config/reviewer.example.toml`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`93a30dc31ea0749b5e07beb76391e203aa796c9472a6a1460b786a6d852024ad`。

### F489

- 包内路径：`reproduction/source-9780c03/engine/__init__.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`da2285a034bd7863a5e8a66732818fb2bee6dec216db131441ed96ff2f9380cc`。

### F490

- 包内路径：`reproduction/source-9780c03/engine/__main__.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`6d8b7d7846a845059d7a3107143f11131f63c5511d669b44085b15ec5e3d2279`。

### F491

- 包内路径：`reproduction/source-9780c03/engine/advanced.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`cf1c7349ebadcce288f3b81a17ba245f7b7414014280ae89c646e2bf5a922e08`。

### F492

- 包内路径：`reproduction/source-9780c03/engine/advanced_contracts.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8a07229d309cd6560336dfc9a31e01ea843239416e193a1fb552acd3d58bb810`。

### F493

- 包内路径：`reproduction/source-9780c03/engine/api.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`cac473d1f7219bd4477e9eeb1fd4259080bd6b886d4718f203e2ca692c055f98`。

### F494

- 包内路径：`reproduction/source-9780c03/engine/cli.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`06c2a17a476f8370224b09f286f25ad0efe304c7aa43572cb0fa7f6abc442d92`。

### F495

- 包内路径：`reproduction/source-9780c03/engine/config.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f44b0af6726d67ce6ded5c9207e0d15cf436a017fc2864a590e4c512438ea68d`。

### F496

- 包内路径：`reproduction/source-9780c03/engine/contracts.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`d54c190392d698aa5015d570446e7a8dd184c3c4f5eabfc5e4b8c5a20d1b478f`。

### F497

- 包内路径：`reproduction/source-9780c03/engine/criteria.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`b9e7da89e005d84fb7021fd5649a694cd43364ad0868b325b0592584b7941851`。

### F498

- 包内路径：`reproduction/source-9780c03/engine/cv_metrics.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`5a0d7e8f72c11b6a0c502b19698108f54d401042b8771acb985a891dd773fb32`。

### F499

- 包内路径：`reproduction/source-9780c03/engine/errors.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f1a4e952e3095cfc3937b3c691d713337af4d4aeee4a56700478e13a54bed85c`。

### F500

- 包内路径：`reproduction/source-9780c03/engine/imaging.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`7a3b957545f5e1c1742ba854d5a5923648112910d5035b2ccfc65358c0e2ebd1`。

### F501

- 包内路径：`reproduction/source-9780c03/engine/local_model.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`047b6b2e501e1d61b1f3a3953bf5f832a0d7a6668ac7cea7a2f5d1dee7ab4d31`。

### F502

- 包内路径：`reproduction/source-9780c03/engine/model.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`133fbb60c55aa215d26eb39e9c718a538a6b45b0950e74b1b973d96d5e1ba541`。

### F503

- 包内路径：`reproduction/source-9780c03/engine/parsing.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`14f0d0150ca23398aeac83507e914795c9318678fa34662ad460c2e7791a0019`。

### F504

- 包内路径：`reproduction/source-9780c03/engine/prompting.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`079f5e186bc63e9c5e3c23e69c6da0819e38e84c1987149fcfd77d22f254fd3d`。

### F505

- 包内路径：`reproduction/source-9780c03/engine/runtime.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`222654e538f3d455db992591bad8786e787f21790d3e2c50d7058d2f81deace3`。

### F506

- 包内路径：`reproduction/source-9780c03/engine/service.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`daada6a3bd0d5a158c2e59878abff77b76901f66781c4062936f683fcb2e53a7`。

### F507

- 包内路径：`reproduction/source-9780c03/engine/staged.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`84b851f5dbe2668442743993325c95808a182673936d2d535901b7b64a1e4f04`。

### F508

- 包内路径：`reproduction/source-9780c03/engine/stub.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`4cb3ab8928fef96ab0c57b4e1e06ec54d0ae67cae7d437cdf754c62a0009ae84`。

### F509

- 包内路径：`reproduction/source-9780c03/fixtures/s07_raw_audit.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`5b197d8ac0b47de1c408e01fab508ac79e628140d3787d63b661585a88af0f73`。

### F510

- 包内路径：`reproduction/source-9780c03/frontend/CHANGELOG.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`0adf05d834575ee2e68e92c1e6374519826dc3876f736c04a7cea291db1259d3`。

### F511

- 包内路径：`reproduction/source-9780c03/frontend/dist/app.js`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`80d133753c02aa77c2be2ed40a9fba1048b607b793e10f6291399c1fc5aa033f`。

### F512

- 包内路径：`reproduction/source-9780c03/frontend/dist/demo.svg`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`a70e0dd313eee8d56f2add5d63035e36cf88f5127ada5b8b699caac853afa4b9`。

### F513

- 包内路径：`reproduction/source-9780c03/frontend/dist/engine-adapter.js`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`81161ddd195539fe84ff34fe9ba9825a6d07132b283f5fe7c524809994361240`。

### F514

- 包内路径：`reproduction/source-9780c03/frontend/dist/index.html`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f5d1880dda9079cf39c9b8101dce6047bc354f37c5c27d703e559f16ac82e9bb`。

### F515

- 包内路径：`reproduction/source-9780c03/frontend/dist/recheck-supplement.js`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`fdf9665720b4e7c04b59b672fe053d85ef7a3e00071a894527922b8fe7a966bc`。

### F516

- 包内路径：`reproduction/source-9780c03/frontend/dist/review-service.js`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`4b065247347661cb9f984817880b650f923359d3711a5ad81161b83ad59a5cc7`。

### F517

- 包内路径：`reproduction/source-9780c03/frontend/dist/storage.js`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`7c133f1fb22ed1aa67aa8ae60aaf642faa6a8a06bee76b820183a39e85dbed5e`。

### F518

- 包内路径：`reproduction/source-9780c03/frontend/dist/style.css`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`74531f373bd3608d7523ab6e9c81de4798018a0ad74cde05d2e83ccc11692959`。

### F519

- 包内路径：`reproduction/source-9780c03/frontend/package.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`1a64f3c568d1b0e6f0dc91ebf8130dc1120851d37cabe6ff5fe8cc45fa4ccb94`。

### F520

- 包内路径：`reproduction/source-9780c03/frontend/README.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`cae8b1275de6afaa687cb232c4750fe4c9bf90116a1ccd326d849bc222853edb`。

### F521

- 包内路径：`reproduction/source-9780c03/frontend/server.mjs`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`eafc3f90b29f27166c7c6abd25fbddf9fefc8e2f1b2dcedc8791e587004a3905`。

### F522

- 包内路径：`reproduction/source-9780c03/frontend/tests/adapter.test.mjs`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`0532de0163fe11c10423e798110b5d8958ce1f914f8c1b6c5c3bec1a89bed68b`。

### F523

- 包内路径：`reproduction/source-9780c03/frontend/tests/live-followup.mjs`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`4301ed3372a348a72b672269362d07b54e40ff3cdb61117796bfe7ccf042e140`。

### F524

- 包内路径：`reproduction/source-9780c03/frontend/tests/recheck.test.mjs`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`0ef0f476def76215697ccf51c161b3315da14104149ff705175e8d9937c87492`。

### F525

- 包内路径：`reproduction/source-9780c03/frontend/tests/service.test.mjs`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`eb7b6984db923ff38c29818e99949472c20423d36f5e7203588519e97ebc7547`。

### F526

- 包内路径：`reproduction/source-9780c03/README.md`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`5038d822a465d4972613ba167f7580c01778c48bf1c3b0c87a5f84d733033ba0`。

### F527

- 包内路径：`reproduction/source-9780c03/requirements-dev.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8636f9ab1a075be9f3039e2a6471837259c4f36b625bcaf7a3d9a1edd2419c6d`。

### F528

- 包内路径：`reproduction/source-9780c03/requirements-perception.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`de93546979e43c0e231eee38bcfd4f5b72216c7d24c9021d480fb3e4b1e3184a`。

### F529

- 包内路径：`reproduction/source-9780c03/requirements.txt`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`26e2d0ad0ec36406e8830b587cc0a3b9d0a69c9686264abc809fd62e97196f63`。

### F530

- 包内路径：`reproduction/source-9780c03/tests/test_api.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`51838839a8ba451e256d8f1f92d919c513d3bdf4124c1cd60d4b8911fb75f6d6`。

### F531

- 包内路径：`reproduction/source-9780c03/tests/test_config.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`c652c07b6a3a81d368c15a3adbafa7f0d3d4e1f28df22cdeccd872a2e8bdb7ed`。

### F532

- 包内路径：`reproduction/source-9780c03/tests/test_d_regressions.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`ac7eaa2db703c6a7aaa5ce2f28a6d0ca05c0d880617aa162cea956a04072c251`。

### F533

- 包内路径：`reproduction/source-9780c03/tests/test_engine.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`1b9796e2a3c2935453ba56185fb942838b1520cc0b1d2819382f62c3610e4328`。

### F534

- 包内路径：`reproduction/source-9780c03/tests/test_finding_deduplication.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`a5dd6ab9c7e74a24e5065e5a29b4b42d22b3a13590e674d32378ea2c20b1a531`。

### F535

- 包内路径：`reproduction/source-9780c03/tests/test_input_limits.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`4459064adec3284a2f1f1aa72198ce5eb4b6ae76bb959a32cc4cc8b8c013e9c6`。

### F536

- 包内路径：`reproduction/source-9780c03/tests/test_model.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`eac22d21ce016fb1ede8b56d3deeb6a39680a38449e0d690246393cc2cf3741b`。

### F537

- 包内路径：`reproduction/source-9780c03/tests/test_normalization_conflicts.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`d89edd60b61c4ebfb962bdc6c18cc2ea5b51ef1144bb8deec922dc7367597c2d`。

### F538

- 包内路径：`reproduction/source-9780c03/tests/test_parsing.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`09d74cac7e6a58cfaa1b6577d62f1ffa8b9bf68b991cf305e354a50772c0101f`。

### F539

- 包内路径：`reproduction/source-9780c03/tests/test_review_recovery.py`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`39f17ac3bd16b3cb3ef9835963e6d417231317cc59bbab2534ba01fbd0459c16`。

### F540

- 包内路径：`reproduction/source-9780c03/判据库_v1.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`8be40cfe628bf5d914f970ef5b4d5367810eada5e77be432e81bec9937ce3688`。

### F541

- 包内路径：`全包文件校验.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`f51b6fa58a5291acdce5e2745bf08afb4206ed830d71b980f0c1a7d7aaeb8843`。

### F542

- 包内路径：`最终归档核查.json`。
- 下载：[本轮材料](../deliverables/2026-10-21-d-expansion-current.zip)。
- SHA-256：`381f281b34b5164a271b0a107dbf9e76538adf483a29e8a5fb508163a2a26fa3`。
