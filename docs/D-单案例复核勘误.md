# D：角色试用单案例复核勘误

复核日期：2026-10-21。对应运行：`20261021-030524-84e90f`。

本文是对既有归档的 **AI 辅助核查与报告引用口径修订**，没有重新运行模型，没有修改原始数据，也不构成真人专家评审。原始报告和原始输出均保留；汇报时请采用本文限定后的结论，不再直接引用原报告中的夸大表述。

## 可以引用的结果

> 仓库保存了一个角色试用页的非模拟模型运行案例。9 项目标检查中，7 项被模型判为达标、1 项发现候选违规、1 项证据不足；24 条通用判据完成相关性筛选，其中 8 条进入深度审查，另外 16 条没有深审。系统形成 1 个尚未人工裁决的候选问题。记录的阶段执行时间合计为 273.372 秒，归档时间戳跨度为 644 秒。本案例说明流程有运行留档，尚不能证明准确率、召回率、真人效率提升或商业上线合格。

这里的“达标”是归档中的模型状态，不能改写为已经人工验证达标。

本次直接读取结构化文件重新计数、累加阶段时间、计算带时区时间戳差，并检查清单引用与文件哈希；没有把旧摘要中的数字当作统计依据。以下字段路径用于复核原值，中文表述用于课件和报告；如两者冲突，应回到原字段检查，不以生成的叙述覆盖原记录。

## 数字与证据口径

| 项目 | 复核结果及可定位字段 |
|---|---|
| 目标检查 | [audit.json](../deliverables/2026-10-21-character-trial/audit.json#L118) 的 `$.goal_checks[*].status` 共 9 项：`met=7`、`observed_violation=1`、`insufficient_evidence=1`。原叙述 [narrative.json](../deliverables/2026-10-21-character-trial/narrative.json#L33) 的 `$.stages[5].conclusion` 写成“8+1+1”，应按结构化数据改为 **7+1+1**。 |
| 实际覆盖 | [criteria-relevance.json](../deliverables/2026-10-21-character-trial/criteria-relevance.json) 的 `$[*].selected` 为 24 条中 8 条真；[audit.json](../deliverables/2026-10-21-character-trial/audit.json#L67) 的 `$.rule_statuses` 只有 8 条。其余 16 条在 [report.json](../deliverables/2026-10-21-character-trial/report.json#L170) 的 `$.rule_results[*]` 被记作 `insufficient_evidence`，但 `reason` 均为“未进入相关性 Top-K，未执行深度检查”。因此必须另写 **未执行深审**，不能视为已审后材料不足、规则不适用或已经通过。 |
| 耗时 | [manifest.json](../deliverables/2026-10-21-character-trial/manifest.json) 的 `$.stages.*.elapsed_ms` 合计 `273372` 毫秒；`$.created_at` 为 `03:05:24+08:00`，`$.stages.narrative.updated_at` 为 `03:16:08+08:00`，相差 644 秒。二者差额 370.628 秒的原因没有记录，不能擅自归为等待或人工操作。两个值均不能直接替代真实用户任务计时。 |

深审的八条规则均记录为 `no_visible_issue`，意思是本次可见材料中未发现问题，不等于完整产品没有问题。目标检查与通用规则审查是两套维度，不能把九项目标和二十四条规则简单相加作为“审查总通过率”。后续实验应分别保留筛选范围、实际执行范围和判断结果；不能用未深审的规则条数直接计算漏检数或通过率。若冻结参考集中的明确问题未被检出，仍计为漏检（FN），不能因为其判据未进入深审而排除。

## 模型运行与人工复核的边界

[report.json](../deliverables/2026-10-21-character-trial/report.json#L5) 的 `$.model.is_stub=false`，模型为 `qwen3.8-max-0902`；[manifest.json](../deliverables/2026-10-21-character-trial/manifest.json) 中 `ocr`、`ui`、`reference_ui`、`goal`、`relevance`、`audit`、`narrative` 七个阶段均有模型名、非零 `usage`、`latency_ms` 及留存的原始输出。[校验清单](../deliverables/2026-10-21-character-trial/SHA256SUMS.txt) 中 27 个文件的哈希均匹配。这支持“存在非模拟运行的归档证据”；本次没有独立重跑或核验供应商调用记录，哈希一致也不证明判断正确。

[F001](../deliverables/2026-10-21-character-trial/report.json#L137) 的 `$.findings[0].decision=candidate_issue`，`review_status=unreviewed`，来源是 G08 目标检查，不是新增的第 25 条通用判据。AI 对[截图](../deliverables/2026-10-21-character-trial/screenshot.png)的目视核查支持两处字形分别为“锋芒崭露”和“锋芒斩露”；但两处分别是活动标题与角色名称，[原型](../deliverables/2026-10-21-character-trial/prototype.png)的左下仅为“角色名字”占位。尚无正式文案表证明必须同名，故不能指定哪个字一定错误，也不能将 F001 记为已确认真阳性。

原叙述 `$.stages[1].conclusion`、`$.metrics[5].interpretation`、`$.limitations[1]` 中的“人工复核”没有对应的复核者、时间与裁决记录。本次 AI 核查不能补足真人证据；若同学另有记录，应另行附上。

## 视觉指标应怎样解释

[metrics.json](../deliverables/2026-10-21-character-trial/metrics.json) 中，`$.global.negative_space_proxy=0.7748` 是留白代理；`$.readability.low_contrast_count=0` 仅表示未触发本次检测阈值，同一结果仍有 `small_text_candidate_count=10`。这些数值不能证明所有文字可读、阅读负荷合格或点击意愿增强。

`$.prototype_alignment.mean_iou=0.1724`，两张原图画布宽度也不同。目视只能支持“主要功能分区大体保留”，不足以支持“完全吻合”或量化对齐率超过 90%。归档没有证明低 IoU 一定由坐标偏移造成。G09 本身仍为交互反馈证据不足，因此原报告“符合商业手游上线标准”的总评不再作为结论引用。

## 原始输出路径勘误

[manifest.json](../deliverables/2026-10-21-character-trial/manifest.json) 有 **6 处引用、实际涉及 3 个文件** 缺少 `raw/` 前缀；文件没有丢失。下表供查阅或复现时定位，原清单保持不动。

| 原字段 | 应定位的文件 |
|---|---|
| `$.stages.ocr.outputs[1]`、`$.stages.ocr.raw_output` | [raw/ocr.raw.txt](../deliverables/2026-10-21-character-trial/raw/ocr.raw.txt) |
| `$.stages.audit.outputs[1]`、`$.stages.audit.raw_output` | [raw/audit.raw.txt](../deliverables/2026-10-21-character-trial/raw/audit.raw.txt) |
| `$.stages.narrative.outputs[2]`、`$.stages.narrative.raw_output` | [raw/narrative.raw.txt](../deliverables/2026-10-21-character-trial/raw/narrative.raw.txt) |

D 的后续实测仍需两位真实评审的独立标注与共识、固定版本的重复运行，以及真实参与者的任务与计时记录；本案例和本勘误不能替代这些材料。
