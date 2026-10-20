# B 引擎 v2 技术规划

## 1. 结论先行

B 引擎不再采用“把截图和整本判据一次性塞给一个通用大模型”的单提示词路径。计划采用混合架构：

```text
截图/原型
  -> 确定性的图像规范化、OCR 与布局测量
  -> 专用 GUI 感知模型
  -> 目标/原型约束分解
  -> 判据相关性检索与重排
  -> 只针对高相关判据执行视觉检查
  -> 证据框、数值指标和四段式建议
  -> 多模型复核与人工校准
```

技术栈：

- 后端：Python 3.11+ 64 位、FastAPI、Pydantic、HTTPX、TOML。
- 本地计算：Pillow、NumPy、OpenCV、scikit-image、SciPy、scikit-learn。
- 云端主模型：千问 AI 平台。
- 开源对照：Hugging Face 上的 Holo1.5、UI-TARS、OmniParser。
- 配置：`config/reviewer.toml`，不会进入 Git。

## 2. 为什么不用单个通用 VLM

单个 VLM 可以描述“这张图看起来怎么样”，但不足以稳定支撑交互评审：

- 不能保证所有坐标和证据框准确。
- 容易把未展示的点击行为当作事实。
- 24 条判据同时塞入上下文时，容易出现漏项、重复和严重度漂移。
- 只能输出文本，不能解释“为什么判据与当前界面相关”。
- 不能区分审美判断、可测量视觉指标和用户注意力预测。

因此，新架构将模型判断和确定性测量分开：

- 专用模型负责识别 UI 元素、文字、控件和作用。
- 传统视觉算法负责计算可复验的尺寸、对比度、边缘密度、色彩和布局参数。
- 检索模型负责判据相关性。
- 旗舰 VLM 负责综合解释、严重度和建议。
- 每个数值都记录计算方法、输入区域和版本。

## 3. 模型选型

### 3.1 主运行时

| 角色 | 选定模型/方法 | 选择理由 |
| --- | --- | --- |
| UI 元素与控件感知 | `qwen3.8-flash` | 实测能按结构化 JSON 返回 18 个元素和归一化框；GUI-Plus 的提示协议偏向操作指令，不适合直接做静态结构解析 |
| 操作/可点击性辅助 | `gui-plus-2026-02-26` | 千问官方专用 GUI 模型，保留用于主操作、可点击区域和下一步动作的辅助判断 |
| 综合视觉推理 | `qwen3.8-max-0902` | 千问当前最高能力档多模态模型，支持 1M 上下文、16M 像素图片、结构化输出；适合层级、密度、风格和目标一致性分析 |
| OCR 与文字定位 | `qwen3.8-flash`（主）/ `qwen3.5-ocr`（辅助） | Flash 实测可按约定输出 OCR 框；专用 OCR 模型返回原生数组，接入时需单独适配 |
| 判据文本检索 | `qwen3.7-text-embedding` + `qwen3.7-text-rerank` | 最新文本向量与交叉注意力重排，适合从判据目标和应用条件中找出候选规则 |
| 多模态相关性 | `qwen3-vl-embedding` + `qwen3-vl-rerank` | 直接连接截图、视觉区域和判据文本，产生可解释的相关性排序，避免只靠关键词 |
| 确定性参数 | OpenCV / scikit-image / NumPy | 对比度、边缘密度、饱和度、OCR 框和布局对齐必须可复算 |

### 3.2 Hugging Face 模型对照

| 候选 | 优势 | 当前判断 |
| --- | --- | --- |
| `Hcompany/Holo1.5-7B` | 开源 UI localization；模型卡报告 ScreenSpot-v2 93.31、ScreenSpot-Pro 57.94，平均 UI 定位 77.32 | 作为开源感知 A/B 基准优先候选 |
| `ByteDance-Seed/UI-TARS-1.5-7B` | 游戏和 GUI agent 表现强，支持 grounding prompt | 作为第二对照，重点测试游戏界面 |
| `microsoft/OmniParser-v2.0` | 截图转结构化元素，ScreenSpot-Pro 约 39.6；V2 推理约 0.6–0.8 秒/帧 | 适合元素解析基线，但定位精度低于 Holo/UI-TARS |

本地部署安排：

- 当前机器是 32 位 Python，无法安装 PyTorch。
- GPU 为 RTX 3060 Laptop，6 GB 显存，不足以直接运行 7B BF16 模型。
- 默认运行时使用云端 GUI-Plus，不让本机硬件成为产品瓶颈。
- 另一台 RTX 5070 Ti（16 GB）已纳入目标配置，可使用 64 位 Python 3.12、NF4 4-bit 和本地 Holo1.5-7B。
- 已支持 `local_holo` 与 `local_ui_tars` 两个惰性加载后端；当前电脑不需要安装 PyTorch。
- 推荐分工是“本地 UI 感知 + 云端 Qwen 综合推理”，既保留本地 A/B 能力，也避免只依赖一台机器的显存。

### 3.3 DeepSeek 的位置

DeepSeek 作为文本综合、规则解释和 Qwen 不可用时的备用通道。它不应替代 UI grounding 和 OCR，也不能在没有视觉证据时生成坐标。

## 4. 感知链

### 4.1 截图规范化

保留原始图和分析图两套尺寸：

- 原始图用于最终证据框和像素级测量。
- 分析图允许放大到模型最佳输入分辨率，但必须记录变换矩阵。
- 去除 EXIF，统一色彩空间为 sRGB。
- 计算原始宽高、有效像素、缩放比例、SHA-256。

### 4.2 UI 元素解析

输出统一的元素集合：

```json
{
  "element_id": "E01",
  "bbox": [0.03, 0.08, 0.18, 0.18],
  "role": "button",
  "label": "开始试用",
  "visual_priority": 0.91,
  "interactable": true,
  "state": "default",
  "source": "gui_plus|holo|omniparser|ocr",
  "confidence": 0.88
}
```

同一元素允许来自多个模型，按 bbox IoU 和标签相似度合并；冲突不静默覆盖，保留在 debug 记录中。

### 4.3 OCR

OCR 输出：

- 文字内容
- 行/词 bbox
- 字体高度估计
- OCR 置信度
- 与控件元素的归属关系
- 小字、遮挡、截断、低对比风险

OCR 不单独判断“文案好坏”，只提供可测量事实。

### 4.4 视觉焦点候选

Attention Insight 类产品使用预测注意力的模型。为避免概念混淆，本项目分层：

- **视觉显著性代理**：OpenCV spectral residual / fine-grained saliency，仅供参考。
- **元素显著性**：结合尺寸、对比度、边缘密度、位置、色彩和模型给出的视觉优先级。
- **预测注意力**：只有在使用专门眼动/注意力模型并完成校准后，才可标记为 attention。

当前 MVP 输出会明确写 `metric_type = "visual_focus_proxy"`，不会把普通 saliency 宣称为真实用户注意力。

### 4.5 原型对照

如果上传原型参考图：

- 对导航、角色区、奖励区、主按钮等功能区域做匹配。
- 用匈牙利算法给参考元素与成果元素配对。
- 计算区域 IoU、中心点偏移、面积比例和阅读顺序变化。
- 不使用整图 SSIM 代替布局一致性，因为风格变化会严重干扰 SSIM。

## 5. 判据相关性分析

### 5.1 判据索引

每条判据拆成多个检索字段：

- 判据标题
- 启发式原则
- `applies_if`
- `check`
- `mark_issue_if`
- `abstain_if`
- 建议
- 平台标签
- 视觉证据类型，例如文字、按钮、导航、弹窗、表单
- 需要的上下文，例如设计目标、目标用户、操作风险

### 5.2 查询构成

相关性查询不是单纯使用设计目标，而是组合：

- 设计目标原文
- 原型约束
- UI 元素角色与文字
- OCR 可见文案
- 页面状态
- 当前平台
- 已知用户任务

### 5.3 混合打分

初版采用可解释的加权分数：

```text
R(rule) =
  0.45 * visual_rerank
  + 0.25 * text_rerank
  + 0.20 * attribute_match
  + 0.10 * context_prior
```

其中：

- `visual_rerank`：截图整体/局部与判据视觉语义的相关性。
- `text_rerank`：检索模型对目标、元素文字和判据文本的交叉打分。
- `attribute_match`：平台、控件、状态和 `applies_if` 的确定性匹配。
- `context_prior`：设计目标明确提到的约束优先级。

结果不会只返回一个 `score`，而是返回分项：

```json
{
  "rule_id": "R19",
  "relevance": {
    "final": 0.91,
    "visual": 0.94,
    "text": 0.83,
    "attribute": 1.0,
    "prior": 0.8
  },
  "reasons": [
    "页面存在明确主操作按钮",
    "设计目标要求核心操作按钮成为第一视觉焦点"
  ],
  "gate": "passed"
}
```

高分判据进入深度检查；低分判据仍保留 `not_applicable` 或 `insufficient_evidence` 原因，不能直接从报告中消失。

### 5.4 相关性评估

用专家标注检验：

- `Precision@5`、`Recall@8`
- `NDCG@8`
- 判据适用/不适用二分类 F1
- 同一截图的排名稳定性

若检索没有优于“全量 24 条判据”基线，就不能声称相关性分析有效，应回到全量检查并保留检索作为辅助。

## 6. 新 Figma 设计目标的结构化拆解

Figma frame `60:15` 的目标可拆成以下约束：

| 约束 | 可测对象 | 计划指标 |
| --- | --- | --- |
| 遵循原型布局与功能分区 | 导航、角色展示、奖励、主按钮 | 功能区域 IoU、中心偏移、面积比例变化 |
| 角色是第一视觉焦点 | 角色主体框、装备/文字/按钮 | 角色与主按钮的视觉优先级分数、显著性质量占比 |
| 核心操作按钮也是第一焦点 | “开始试用”按钮 | CTA 面积比、对比度、边缘强度、与角色区距离 |
| 控制信息密度并合理留白 | 文本、面板、装饰元素 | 文本覆盖率、元素数量/千像素、负空间占比、拥挤区域数 |
| 数值与文字清晰易读 | OCR 文本框 | 估计字高、局部对比度、遮挡率、截断数 |
| 多巴胺风格但底板克制 | 控件和背景 | 控件/背景饱和度差、明度分布、色彩数量、高饱和面积比 |
| 交互反馈明确 | 按钮、选中态、视觉层级 | 控件状态可见性、主次按钮样式差异 |
| 禁止无意义纹理、过曝、重描边 | 背景、描边、装饰 | 高频边缘密度、亮白像素占比、边框像素比例、纹理重复度 |
| 商业手游上线清晰度 | 整体图 | 文本可读率、元素遮挡率、关键区裁切检查 |

README 的 24 条通用判据仍保留；上述目标是额外的“目标一致性层”，不能取代通用判据。

## 7. 需要显示的开发参数

每次评审除了问题清单，还要输出 `diagnostics`：

### 7.1 截图与解析

- 原图/分析图尺寸、缩放比例
- 元素数量、可交互元素数量
- OCR 块数、低置信度块数
- 模型版本、耗时、token 使用量
- 模型间冲突元素数

### 7.2 视觉层级

- 前 5 个视觉焦点及各自 bbox
- 角色区视觉质量占比
- CTA 视觉质量占比
- CTA 与次操作的显著性比
- 视觉层级差距是否足够

### 7.3 可读性

- 文本高度分位数
- 局部对比度分位数
- 低于最小字高的文本块数
- 低对比文本块数
- 被装饰/人物遮挡的文本块数

### 7.4 密度与装饰

- 文本像素覆盖率
- 可交互控件覆盖率
- 负空间比例
- 背景高频边缘密度
- 高饱和度面积比例
- 过亮像素比例
- 重描边候选数量

### 7.5 一致性与原型

- 同类控件颜色/形状/尺寸离散度
- 主次按钮层级差
- 功能区域 IoU
- 元素中心偏移
- 阅读顺序变化

### 7.6 判据与证据

- 每条判据的视觉/文本/属性/先验相关分
- 进入检查的 Top-K
- 每条判据的判定和弃权原因
- 每个问题的证据框
- 证据质量分，例如目标中心是否落在框内
- 多模型一致率

### 7.7 调试产物

计划生成：

```text
out/debug/<review_id>/
  report.json
  elements.json
  ocr.json
  criteria_relevance.csv
  goal_constraints.csv
  metrics.json
  overlay_elements.png
  overlay_text.png
  overlay_focus.png
  overlay_prototype_match.png
  model_trace.json
```

这些文件在开发阶段默认保留，正式演示时可按配置关闭。

## 8. 判定与建议层

每个问题必须由以下证据共同支持：

1. 元素或 OCR 证据。
2. 至少一个可复算指标或明确的视觉检测结果。
3. 与该问题相关的判据。
4. 目标一致性约束，若设计目标中有要求。

四段式继续保留：

- 原则
- 检测
- 描述
- 建议

额外增加：

- `goal_links`：关联的设计目标约束
- `metrics_snapshot`：支持判断的数值
- `model_agreement`：多模型一致率
- `evidence_quality`：证据框质量
- `calibration_note`：置信度解释

严重度不能仅由 VLM 自由决定。计划先使用规则基础分，再结合目标权重、可见后果和模型意见，输出可解释的严重度分解。

## 9. 稳定性与复核

- 对同一截图重复运行 2 次，计算问题集合 Jaccard 和严重度一致率。
- 屏蔽原始随机性：temperature 低、固定模型快照、记录 seed（供应商支持时）。
- OCR、元素框、相关性分数和最终问题分别缓存。
- 模型输出不合格只修复结构，不允许补造视觉证据。
- 关键结论采用第二模型或第二提示策略复核；不一致进入人工节点，不强行合并。

## 10. 效果评估

### 10.1 现有 Figma 样本

首批真实样本：

- [设计目标：`60:15`](https://www.figma.com/design/dAWQ1dG8pOh5RBHa3CFZ7t/skill?node-id=60-15)
- [成果截图：`60:16`](https://www.figma.com/design/dAWQ1dG8pOh5RBHa3CFZ7t/skill?node-id=60-16)
- 原型参考：`60:15` 中的原型图

用途：

- 验证角色/CTA 第一焦点约束。
- 验证信息密度和装饰抑制。
- 验证工具是否能发现事实问题，而不是重复目标原文。

### 10.2 指标

| 维度 | 指标 |
| --- | --- |
| 发现能力 | Recall、Precision、F1、严重度加权召回率 |
| 证据质量 | bbox IoU、中心点命中率、OCR 原文命中率 |
| 判据相关性 | Precision@K、NDCG@K、适用性 F1 |
| 一致性 | 重复运行 Jaccard、模型间一致率、Krippendorff α |
| 校准 | Brier score、ECE、置信度分层准确率 |
| 效率 | 各阶段耗时、总耗时、token 使用量 |
| 可解释性 | 带判据出处比例、带计算参数比例、无证据断言率 |

### 10.3 消融实验

必须比较：

1. 单通用 VLM + 全量判据。
2. 通用 VLM + 相关性筛选。
3. 专用 UI 感知 + 相关判据。
4. 专用 UI 感知 + 确定性指标 + 相关判据。
5. 上述方案 + 多模型复核。

只有第 4/5 项在专家标注上优于第 1 项，才说明新方法确实更有效。

## 11. API 契约变化

主接口仍为 `POST /api/review-audit`，但响应扩展：

```json
{
  "report": {
    "findings": [],
    "rule_results": []
  },
  "perception": {
    "elements": [],
    "ocr": [],
    "model_conflicts": []
  },
  "goal_constraints": [],
  "criteria_relevance": [],
  "diagnostics": {
    "focus": {},
    "readability": {},
    "density": {},
    "consistency": {},
    "prototype_alignment": {},
    "timings": {},
    "usage": {}
  },
  "artifacts": {
    "overlay_focus": null,
    "overlay_elements": null,
    "criteria_relevance_csv": null
  }
}
```

开发默认返回完整诊断；正式产品可通过 `diagnostics_level` 控制精简程度。

## 12. 实施阶段

### 阶段 1：感知与参数

- OCR、UI 元素解析、焦点候选、基础视觉指标。
- 在 Figma `60:16` 与原型图上生成叠加图。
- 验收标准：关键区域和文字框位置肉眼可核验，数值方法可复算。

### 阶段 2：目标约束与判据相关性

- 结构化设计目标。
- 判据索引、混合检索、重排和相关性分项输出。
- 验收标准：相关性排序优于全量判据基线，并有人工可读理由。

### 阶段 3：审查与四段式输出

- Top-K 判据深检、证据框、结构化输出和契约修复。
- 验收标准：真实截图端到端产出，无证据断言率可统计。

### 阶段 4：评估与调优

- 10 张样本、专家标注、消融实验、重复运行一致性。
- 验收标准：召回率、误报率、证据命中率和耗时均形成结果表。

## 13. 本次确认点

建议按以下决定继续：

1. 主运行时采用千问云端混合模型，不以单 VLM 为主。
2. Hugging Face 的 Holo1.5-7B 作为开源定位 A/B 基准，不阻塞主服务。
3. 所有视觉参数同时输出原始值、归一化值、方法和证据区域。
4. 相关性分析必须做基线和消融，不默认宣称有效。
5. 设计目标和原型图作为独立目标一致性层，不混入 24 条通用判据。
6. 配置放在 `config/reviewer.toml`，密钥永不进入 Git。

## 14. 官方依据

- [千问视觉模型选型](https://platform.qianwenai.com/docs/developer-guides/getting-started/vision-models)
- [GUI-Plus 界面交互](https://platform.qianwenai.com/docs/developer-guides/text-generation/gui-interaction)
- [Qwen OCR](https://platform.qianwenai.com/docs/developer-guides/multimodal/ocr)
- [向量与重排模型](https://platform.qianwenai.com/docs/developer-guides/getting-started/embedding-models)
- [千问重排序](https://platform.qianwenai.com/docs/developer-guides/embeddings/reranking)
- [Holo1.5-7B 模型卡](https://huggingface.co/Hcompany/Holo1.5-7B)
- [UI-TARS-1.5-7B 模型卡](https://huggingface.co/ByteDance-Seed/UI-TARS-1.5-7B)
- [OmniParser-v2.0 模型卡](https://huggingface.co/microsoft/OmniParser-v2.0)
