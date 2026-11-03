// C-owned transitional module. Replace via this boundary when B provides native recheck results.
export const resolutionLabels={resolved:'已解决',partially_resolved:'部分解决',unresolved:'仍存在',unable_to_determine:'无法判断',not_applicable:'不再适用',excluded_by_human:'人工排除'};
export function buildRecheckResults(previous,current){
 const items=previous.issues.map(old=>{
  const rules=old.rule_ids||[old.ruleId];
  const candidates=current.issues.filter(n=>(n.rule_ids||[n.ruleId]).some(r=>rules.includes(r))).map(n=>n.id);
  return {previous_finding_id:old.id,title:old.title,previous_description:old.description,previous_note:old.note||'',previous_review_status:old.reviewStatus,previous_severity:old.severity,candidate_current_finding_ids:candidates,current_finding_ids:[],resolution:'unable_to_determine',reason:candidates.length?'新版有相同判据的候选发现，需要人工核对是否为同一问题。':'新版未报出对应问题，但不能据此认定已解决，请对照新版截图确认。',current_evidence_description:'',human_confirmation:'pending',origin:'c_rules',updated_at:null};
 });
 return {schema_version:'c-recheck-1.0',previous_review_id:previous.id,current_review_id:current.id,evaluation_mode:'c_assisted_manual',is_stub:previous.mode!=='engine'||current.mode!=='engine',items,warnings:['C 过渡补充层：判据交集仅用于候选关联，最终状态由人工核验。B 后续提供原生复审结果后替换此模块。']};
}
export function confirmRecheckItem(item,{resolution,reason,evidence,currentIds=[]},current){
 if(!Object.hasOwn(resolutionLabels,resolution))throw Error('请选择有效复审状态');
 if(!reason?.trim())throw Error('请填写逐问题复审理由');
 if(['resolved','partially_resolved','unresolved'].includes(resolution)&&!evidence?.trim())throw Error('请填写新版截图中的证据位置或观察现象');
 if(currentIds.some(id=>!current.issues.some(n=>n.id===id)))throw Error('关联发现不属于本轮评审');
 return {...item,resolution,reason:reason.trim(),current_evidence_description:evidence?.trim()||'',current_finding_ids:[...new Set(currentIds)],human_confirmation:'confirmed',origin:'human',updated_at:new Date().toISOString()};
}
export function recheckMarkdown(result){if(!result)return [];return ['## 逐问题复审结果（C 补充层）',`来源：${result.evaluation_mode}；${result.is_stub?'含模拟数据，不能作为真实修复证明':'人工核验结论，非 B 自动判断'}`,...result.items.flatMap(i=>[`### ${i.title}`,`- 原问题 ID：${i.previous_finding_id}`,`- 结果：${resolutionLabels[i.resolution]}`,`- 人工确认：${i.human_confirmation==='confirmed'?'已确认':'待确认'}`,`- 理由：${i.reason}`,`- 新版证据：${i.current_evidence_description||'未填写'}`,`- 关联新版问题：${i.current_finding_ids.join('、')||'未关联'}`,''])];}
