# 明鉴：本地交互评审原型

需要 Node.js。无需安装依赖。在此目录执行 `node server.mjs`（有 npm 也可执行 `npm start`），打开 http://127.0.0.1:4173 。停止服务按 Ctrl+C。

## 已实现
上传与图片解码检查（PNG/JPEG/WebP，3 MB）、内置示例、目标确认、四段式发现、证据不足、人工审核、严重度及理由、模拟反馈重评、模拟修改稿复审、Markdown 报告、本机浏览器存储（最多 8 条）及清除入口。图片不上传外部服务。存储失败会提示，仍可导出。

## 模拟边界
没有 AI 图片分析。固定的三个示例发现、两个示例坐标及复审状态不随图片内容变化。当前报告明确标注模拟。反馈重评保留用户状态并按预设逻辑更新展示，绝非真实重算。判据引用仅 R19、R07、R03 的演示内容，不是完整判据库。存储为当前浏览器 localStorage；大图较多可能超过额度，不适合作正式档案。

## 后续接入 B
`dist/review-service.js` 是唯一服务调用入口，`createReviewService(provider)` 可替换 provider。前端临时契约：

- `createReview({image, context})`：image 为 data URL 或内置素材路径；context 包含 name/type/audience/goal/intent。
- `reviseReview(review, feedback)`：含当前目标、逐问题 id/reviewStatus/severity/note，返回新版本完整记录。
- `recheckReview(review, image)`：传原记录及新截图，返回新版本及逐问题 recheckStatus。

真实适配器应转换图片为后端要求的文件或上传引用，再通过后端调用模型；绝不可在前端放 API Key。待与 B 确认 URL、鉴权、大小限制、错误结构、版本、稳定问题 ID、异步任务与超时、证据坐标格式。当前未配置真实 API。引擎应返回四段式意见、判据出处、检测结论、严重度、可选相对位置。必须校验返回数据再渲染，并明确显示真实模式；请求失败不得悄悄退回 mock。

检测结论与人工状态分开：decision = candidate_issue/no_visible_issue/insufficient_evidence/not_applicable；reviewStatus = pending/confirmed/rejected/verify。实际 mock 只覆盖前者中的候选问题和证据不足。位置 x/y 为 0–1 图片相对坐标。

运行服务层检查：`npm test`。
