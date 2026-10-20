# B 引擎：截图交互评审

> 当前文档描述已跑通的 MVP 基线和接口契约。拟升级的感知、相关性分析和可计算参数架构见
> [`b-engine-v2-plan.md`](b-engine-v2-plan.md)。

## 当前范围

B 引擎完成一条可独立验证的分析链：

```text
截图预处理
  -> 多模态视觉理解
  -> 24 条判据逐项判定
  -> 同一现象合并
  -> 证据框与判据出处绑定
  -> 四段式问题清单
```

输入是单张 PNG、JPEG 或 WEBP 界面截图，可附带设计目标、场景、平台和目标用户。输出是可直接交给 C 的 JSON 评审对象。缺失上下文时，引擎必须保守弃权，不得猜测未展示的交互行为。

## 接口

启动服务：

```powershell
$env:REVIEW_PROVIDER = "qwen"
$env:DASHSCOPE_API_KEY = "<your-key>"
python -m engine serve --port 8000
```

主要接口：

- `GET /healthz`：服务、判据库和已配置模型供应商状态，不泄露密钥。
- `GET /api/criteria`：判据版本、来源和分布。
- `POST /api/review-audit`：`multipart/form-data` 上传 `image`。
- `POST /api/review-audit/base64`：JSON Base64 输入，适合自动化脚本。
- `GET /docs`：FastAPI 自动接口文档。

上传接口字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `image` | 是 | 单张截图，最大 15 MB，最短边至少 200 px |
| `design_goal` | 否 | 页面原本要解决的问题或用户任务 |
| `scenario` | 否 | 产品场景、前置流程或评审边界 |
| `platform` | 否 | `web`、`ios`、`android`、`desktop`、`game`、`unknown` |
| `target_user` | 否 | 目标用户；缺失时涉及用户专业程度的判据应弃权 |
| `provider` | 否 | `qwen`、`deepseek`、`generic`、`stub` |
| `model` | 否 | 覆盖服务端默认模型 |
| `analysis_mode` | 否 | 默认 `two_pass`；`single_pass` 减少一次模型调用 |

## 输出契约

核心字段：

```json
{
  "schema_version": "1.0",
  "review_id": "uuid",
  "status": "completed | partial",
  "model": {
    "provider": "qwen",
    "model": "qwen3.8-flash",
    "analysis_mode": "two_pass",
    "is_stub": false
  },
  "screen_analysis": {
    "page_type": "工作台",
    "visible_text": [],
    "regions": [],
    "controls": [],
    "observed_states": [],
    "task_clues": [],
    "uncertainties": []
  },
  "summary": {
    "rules_total": 24,
    "candidate_issues": 1,
    "no_visible_issue": 0,
    "insufficient_evidence": 23,
    "not_applicable": 0,
    "critical_count": 0,
    "high_count": 0,
    "medium_count": 1,
    "low_count": 0
  },
  "findings": [],
  "rule_results": [],
  "warnings": [],
  "timings_ms": {}
}
```

每条 `findings` 都包含：

- `rule_ids` 与 `sources`：判据编号、来源名称、URL 和“操作化而非原文摘录”的关系声明。
- `severity`：`critical`、`high`、`medium`、`low`。
- `confidence`：`0–1`。
- `principle`、`detection`、`description`、`suggestion`：四段式意见。
- `evidence`：归一化 `x/y/width/height`、区域说明和可见文字。
- `review_status`：初始固定为 `unreviewed`，供 C 的 HITL 驳回或确认。

`rule_results` 固定覆盖判据库中的全部规则，C 可以用它展示“为什么没报某条”。问题只进入 `findings`，弃权和无问题结论只进入 `rule_results`。

## 稳定输出策略

1. 模型先做纯视觉事实描述，再做判据审查；两者分开可减少把推测当作证据。
2. 输出必须包含全部 `rule_id`；漏项会在规范化阶段保守记为 `insufficient_evidence`，并写入 `warnings`。
3. 优先使用供应商的 JSON mode；不支持时自动降级并继续解析。
4. JSON 解析依次尝试直接解析、代码围栏、平衡括号提取和常见尾逗号修复。
5. Pydantic 契约校验失败时，只发起一次修复调用；修复后仍失败则返回可重试的 `model_contract_failed`，不编造结果。
6. 网络错误、限流和 5xx 使用指数退避重试，默认最多 3 次。
7. 未知判据、重复判据、无四段式证据的问题会被移除或降级，并在 `warnings` 中说明。
8. 证据框必须位于 `0–1` 归一化图像范围内。

## 模型配置

### 千问 AI 平台

```text
REVIEW_PROVIDER=qwen
REVIEW_MODEL=qwen3.8-flash
DASHSCOPE_API_KEY=<key>
```

默认使用千问 AI 的 OpenAI 兼容地址：

```text
https://maas.qianwenaiapi.com/compatible-mode/v1
```

### DeepSeek

```text
REVIEW_PROVIDER=deepseek
REVIEW_MODEL=deepseek-flash
DEEPSEEK_API_KEY=<key>
```

默认使用：

```text
https://api.deepseek.com
```

### 任意 OpenAI 兼容服务

```text
REVIEW_PROVIDER=generic
REVIEW_BASE_URL=<base-url>
REVIEW_API_KEY=<key>
REVIEW_MODEL=<vision-model-name>
```

不要在请求体或前端中传 API Key。服务端只从环境变量读取。

## 离线 Stub

`stub` 只用于 C 联调和契约测试。它不读取截图，输出会明确标为 `is_stub: true` 且带警告，不能被当作评审结果验收。

```powershell
$env:REVIEW_ALLOW_STUB = "1"
python -m engine review .\screen.png --provider stub
```

## 验收步骤

1. `python -m engine validate-criteria`：确认 24 条判据与来源字段有效。
2. `python -m pytest -q`：运行契约、解析、图片和 API 测试。
3. 配置视觉模型 Key，运行 `python -m engine review <真实截图> --goal <目标>`。
4. 人工检查：问题是否都有截图中可见的证据、证据框是否指向正确区域、判据出处是否完整、建议是否可执行。
5. 将同一截图交给 C 上传，确认接口、字段和 HITL 状态可被界面消费。

当前阶段的状态：代码和离线契约测试先完成；真实视觉模型端到端验证等待可用 API Key。
