import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createReviewerFinding, reviewerMarkdown} from '../dist/reviewer-finding.js';
import {engineProvider} from '../dist/engine-adapter.js';
import {buildRecheckResults, recheckMarkdown} from '../dist/recheck-supplement.js';

const fields={
  title:'下午回执显示上午地点',steps:'选下午、核对、提交',evidence:'周五14:00二层 → 回执09:00一层',
  severity:'high',authorType:'ai_simulation'
};

test('问题补记要求明确来源、步骤、证据与等级；同题人工和 AI 的来源分别保留',()=>{
  for (const field of Object.keys(fields)) {
    assert.throws(()=>createReviewerFinding({...fields,[field]:'  '},{version:3}));
  }
  const issue=createReviewerFinding(fields,{version:3});
  assert.match(reviewerMarkdown(issue).join('\n'),/AI 模拟补记/);
  const human=createReviewerFinding({...fields,authorType:'human'},{version:3});
  assert.match(reviewerMarkdown(human).join('\n'),/人工补记/);
  assert.notEqual(human.id,issue.id);
  assert.notEqual(issue.id,createReviewerFinding(fields,{version:3}).id);
  assert.equal(issue.observedVersion,3);
  assert.equal(issue.reviewStatus,'pending');
  assert.equal(issue.originalSeverity,'high');
});

test('真实引擎适配器保留同图补记；换图时仅在原版及待核对结果中引用旧证据',async t=>{
  let calls=0;
  t.mock.method(globalThis,'fetch',async path=>{
    if(String(path).startsWith('data:')) return new Response(new Blob(['页面截图'],{type:'image/png'}));
    assert.equal(path,'/engine/api/review-audit');
    calls++;
    return Response.json({schema_version:'1.0',review_id:'review-'+calls,status:'completed',
      model:{is_stub:false,provider:'fixture',model:'fixture'},summary:{candidate_issues:0},findings:[],rule_results:[]});
  });
  const r=await engineProvider.createReview({image:'data:old',context:{goal:'预约',intent:''}});
  const issue=createReviewerFinding(fields,r);
  r.issues.push(issue);
  const next=await engineProvider.reviseReview(r,'仅补充流程说明');
  assert.deepEqual(next.issues,[issue]);
  assert.deepEqual(next.rawReport.findings,[]);
  assert.doesNotMatch(next.followup.scenario,/下午回执显示上午地点/);
  next.issues[0].note='v2 审核';
  assert.equal(r.issues[0].note,'');
  assert.equal(next.comparison.issues[0].note,'');
  // 两次选择相同的图片文件也表示发起了新的修改稿复审。
  const changed=await engineProvider.recheckReview(next,'data:old','核对当前版本');
  assert.equal(changed.issues.length,0);
  assert.equal(changed.comparison.issues[0].note,'v2 审核');
  const recheck=buildRecheckResults(next,changed);
  assert.equal(recheck.items[0].resolution,'unable_to_determine');
  assert.match(recheckMarkdown(recheck).join('\n'),/原版本证据：周五14:00二层/);
  assert.equal(calls,3);
});
