# B引擎临时副本与修改记录

日期：2026-11-04。此副本由用户明确授权，用于本地临时运行，不修改原版B源码。

## 位置与当前运行方式

- 原版：仓库根目录 engine/。
- 副本：仓库 out/b-engine-copy/engine/。
- 副本独立配置：out/b-engine-copy/config/reviewer.toml、out/b-engine-copy/.env。
- 运行选择：out/backend-selection.json，enabled=true时C启动器加载副本。
- Python环境仍使用仓库自己的.venv；服务端口仍8000，前端仍4173。
- 会话存储显式指向原仓库out/sessions，因此历史记录和新会话都可继续读取，不复制或覆盖旧报告。
- 副本、配置、Key和项目证据均位于Git忽略的out中，不应上传。可分享本说明与不含密钥的修改补丁。

## 修改了什么

1. 副本engine/session_context.py新增quarantine_unverifiable_claims：无法逐字验证、缺少完整来源引用的目标/要求/意见移至unknowns待核实，不作为正式审查依据；依赖这些声明的子要求及冲突同步排除。支持引用的声明保留。
2. 副本engine/session_service.py在原有引用修复之后、严格校验之前调用隔离函数；写入warnings和run_limitations，保证存在隔离声明时报告仍为partial。
3. 原有quote_matches、validate_quotes、validate_understanding保持严格校验，不接受模型自造OCR，不把未知行为当作已验证行为。
4. 副本中一项旧测试原来预期坏引用导致整个材料理解失败，现改为验证坏要求被隔离、有效目标仍保留；新增两项测试检查坏引用仍被严格拒绝、父声明失效时子声明不残留。
5. C启动器增加受限路径选择，只允许选择仓库out内的副本。副本配置将会话存储指回原仓库；模型仍generic/qwen3.8-flash，显式关闭thinking，8192输出tokens，90秒单请求、600秒整轮。

## 验证

- 最终副本全量pytest：225 passed，59.90秒。
- 原版engine全部Python文件与建立副本前的SHA-256清单一致。
- 清单：out/b-engine-copy/source-manifest.json。
- 补丁：frontend/B引擎临时副本修改.patch，包含两个引擎文件与副本测试变更，无配置Key。
- 真实工作台复测会话：session-15f4c69cc37e42ed82f235ec4ba666e1。复用上一轮材料和输入；已通过understand校验并进入T04制定计划。最终运行结果另见下方追加记录。

## 切回原版或重新启用副本

在仓库中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\frontend\切换引擎.ps1 -Mode original
```

重新启用副本改为-Mode copy。脚本只修改下一次启动的选择，不中断当前任务；结束当前任务并重启后端后才生效。按frontend/启动新版后端.ps1启动。若已有后台8000服务，需先停止旧的后端进程，避免端口冲突。

切回原版后仍保留副本、新报告和原历史，不删除目录。原版自身尚未包含本补丁，会恢复原版校验行为。以后更新B仓库不会自动更新此副本，须重新比对。只改原仓库.env或reviewer.toml也不会自动同步副本配置。

## 临时方案的限制

隔离有问题的声明可使其他检查继续，但不会恢复图片里缺少的可靠OCR文本，被隔离的业务要求仍待核实；不能将这种部分报告称为完整业务审查。建议B后续补充图片文本提取、证据映射与精确结构修复。未经人工核对的视觉文字不能自动升级为正式产品要求。

## 本轮最终结果

真实运行已结束：14次模型返回，材料理解及检查计划校验通过，已越过原来的引用校验阻塞。但后续plan两次、judge两次的原始返回均为JSON数组`[]`（仅2个字符），不是所要求的schema对象，因此仍然没有执行检查，报告为partial，0项完成；不属于再次连接失败，也不是完整审查通过。

未将空数组伪造为规划或评审结论。后续需继续核对模型/代理对复杂schema的遵循能力，以及plan/judge提示和协议。当前副本仅解决“坏引用拖垮整段材料理解”的问题，未解决上述独立阻塞。

本轮原生人审报告、审计报告、结构化报告与retest-result.json均保存在out/b-engine-copy中。没有修改原版引擎，也未提交或推送GitHub。

## 2026-11-04 全流程复测追加修正

真实初审已进入judge并完成2项检查，但E08在证据不足时被降级成insufficient_evidence，违反冲突类字段契约，触发ValidationError。仅在副本session_service.py的最终CheckItem验证前再按kind归一化decision，使冲突类降级为needs_clarification。新回归直接执行_judge验证此路径；副本全量现为226 passed（60.77秒）。原版engine仍未修改。

详细输入和真实结果位于工作区outputs/前端全流程真实复测-20261104/测试报告.md。修正后的补丁已更新。
