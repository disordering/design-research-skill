export const phases=[['T01','登记任务'],['T02','读取材料'],['T03','理解目标'],['T04','制定计划'],['T05','取证与操作'],['T06','逐项检查'],['T07','核验证据'],['T08','交流与变更'],['T09','生成报告'],['T10','新版复审']];
export function progressData(s){const checks=(s.checks||[]).filter(c=>!c.stale&&c.run_id===s.run_id);const count=x=>checks.filter(c=>c.execution_status===x).length;const total=checks.length,done=count('executed');const start=[...(s.messages||[])].reverse().find(m=>m.type==='run_started'&&m.run_id===s.run_id);const warnings=(s.warnings||[]).slice(start?.warning_count||0);const errors=[...new Set([...(s.run_limitations||[]),...warnings].filter(x=>/执行失败|校验失败|输出结构无效|AttributeError|Traceback|could not be reached|provider rejected|HTTP (?:4|5)\d\d|model_network_error|时间限制|超时|timeout/i.test(x)))];const finished=['completed','cancelled'].includes(s.status);return {total,done,percent:total?Math.floor(done/total*100):null,running:count('running'),blocked:count('blocked'),failed:count('failed'),pending:count('planned')+count('not_executed'),errors,title:errors.length?'运行异常，未完成审查':s.status==='completed'?(s.report_completeness==='complete'?'本轮结束，检查处置完整':'本轮结束，仍有未完成检查'):s.status==='cancelled'?'运行已取消':s.status==='created'?'已创建，尚未开始运行':s.status==='awaiting_input'?'等待补充或恢复环境':'正在执行',finished};}

export function isRunning(s){return !!s&&['reading','planning','checking','rechecking'].includes(s.status);}
export function phaseWaitSeconds(s,now=Date.now()){const at=Date.parse(s.updated_at||'');return Number.isFinite(at)?Math.max(0,Math.floor((now-at)/1000)):null;}

// 状态提示随会话状态变化，创建和等待补充时保留各自说明。
export function progressNotice(s,now=Date.now()){
  if(isRunning(s))return `本阶段最近更新距今 ${phaseWaitSeconds(s,now)??0} 秒。正在等待后端处理或模型响应；无需再次点击开始。`;
  if(s.status==='created')return '会话已创建，点击开始运行后生成评审结果。';
  if(s.status==='awaiting_input')return '本轮等待补充材料、回答或授权，提交后可继续。';
  if(s.status==='cancelled')return '本轮已取消；下方时间是最后保存时间。';
  if(s.status==='completed')return '本轮已结束；下方时间是最后保存时间。';
  return '下方显示会话最后保存时间。';
}
