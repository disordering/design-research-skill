// Frontend provisional contract. Replace this adapter after agreement with B.
const wait=()=>new Promise(r=>setTimeout(r,450));
export const mockProvider={
 async createReview(input){await wait();return {id:crypto.randomUUID(),mode:'mock',version:1,context:input.context,image:input.image,createdAt:new Date().toISOString(),issues:[
 {id:'issue-01',ruleId:'R19',heuristic:'H08',title:'示例：主要操作的视觉层级不足',severity:'medium',decision:'candidate_issue',principle:'主要任务操作应易于定位',detection:'预设示例：主操作与次要操作的视觉权重接近。',description:`可能增加“${input.context.goal}”的定位成本；此判断没有检查上传图片。`,suggestion:'突出主要操作，降低次要操作的视觉权重，并与任务内容就近放置。',position:{x:.72,y:.75},reviewStatus:'pending',note:''},
 {id:'issue-02',ruleId:'R07',heuristic:'H02',title:'示例：输入项缺少清楚的字段名称',severity:'high',decision:'candidate_issue',principle:'输入项名称应说明所需信息',detection:'预设示例：关键字段只有占位文案。',description:'输入后可能难以回看字段用途；需对照实际截图核验。',suggestion:'增加持续可见的字段名称，必要时提供示例。',position:{x:.35,y:.42},reviewStatus:'pending',note:''},
 {id:'issue-03',ruleId:'R03',heuristic:'H01',title:'示例：等待反馈需要额外证据',severity:'low',decision:'insufficient_evidence',principle:'等待状态应说明系统正在做什么',detection:'单张静态图不能证明点击后是否有反馈。',description:'需要补充加载状态截图或实际操作记录。',suggestion:'先补充证据，再决定是否构成问题。',position:null,reviewStatus:'verify',note:''}
 ],logs:[{at:new Date().toISOString(),text:'创建模拟评审；结果为预设示例'}]};},
 async reviseReview(review,feedback){await wait();const next=structuredClone(review);next.version++;next.issues=next.issues.map(i=>({...i,engineDisposition:i.reviewStatus==='rejected'?'模拟重评：已按人工反馈排除':i.reviewStatus==='confirmed'?'模拟重评：保留为已确认发现':'模拟重评：等待更多证据'}));next.logs.push({at:new Date().toISOString(),text:`模拟反馈重评 v${next.version}：${feedback||'提交当前审核状态'}`,feedback:structuredClone(next.issues.map(({id,reviewStatus,severity,note})=>({id,reviewStatus,severity,note}))),context:structuredClone(next.context)});return next;},
 async recheckReview(review,image){await wait();const next=structuredClone(review);next.version++;next.previousImage=review.image;next.image=image;next.issues=next.issues.map((i,n)=>({...i,recheckStatus:i.reviewStatus==='rejected'?'不纳入复审':['示例：已解决','示例：部分解决','示例：无法判断'][n%3]}));next.logs.push({at:new Date().toISOString(),text:`模拟复审 v${next.version}：使用预设状态，未分析新图片`});return next;}
};
export function createReviewService(provider=mockProvider){for(const key of ['createReview','reviseReview','recheckReview'])if(typeof provider[key]!=='function')throw new Error(`Provider missing ${key}`);return provider;}
export const reviewService=createReviewService();
