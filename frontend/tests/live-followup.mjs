// Explicit live test: requires local stub backend. Does not call a paid model.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {engineProvider} from '../dist/engine-adapter.js';
const nativeFetch=globalThis.fetch;
globalThis.fetch=(url,options)=>nativeFetch(typeof url==='string'&&url.startsWith('/engine')?'http://127.0.0.1:4173'+url:url,options);
const health=await (await nativeFetch('http://127.0.0.1:8000/healthz')).json();
assert.equal(health.stub_allowed,true);
const png=await readFile(new URL('../../../work/integration-screen.png',import.meta.url));
const image='data:image/png;base64,'+png.toString('base64');
const first=await engineProvider.createReview({image,context:{goal:'保存设置',audience:'新用户',type:'web',intent:'减少误触'}});
assert.equal(first.mode,'stub','This test must only run against stub');
first.issues[0].reviewStatus='rejected';first.issues[0].note='该按钮为禁用状态，请核查';
const second=await engineProvider.reviseReview(first,'核查人工驳回');
assert.match(second.rawReport.context.scenario,/禁用状态/);assert.equal(second.version,2);assert.equal(second.comparison.issues[0].reviewStatus,'rejected');assert.equal(second.issues[0].reviewStatus,'pending');
const third=await engineProvider.recheckReview(second,image,'新版已调整入口');
assert.match(third.rawReport.context.scenario,/新版已调整入口/);assert.equal(third.version,3);assert.equal(third.mode,'stub');
console.log('PASS: same endpoint receives feedback and revision context; versions 1/2/3; stub remains explicit.');
