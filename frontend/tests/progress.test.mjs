import {test} from 'node:test';import assert from 'node:assert/strict';import {progressData} from '../dist/session-progress.js';
test('coverage excludes stale and other runs, never equates completed with passed',()=>{const p=progressData({status:'completed',report_completeness:'partial',run_id:'new',checks:[{run_id:'old',execution_status:'executed'},{run_id:'new',stale:true,execution_status:'executed'},{run_id:'new',execution_status:'executed'},{run_id:'new',execution_status:'not_executed'}]});assert.equal(p.total,2);assert.equal(p.percent,50);assert.match(p.title,/未完成/);});
test('error overrides backend completed and historical warnings do not mark recovered run failed',()=>{assert.match(progressData({status:'completed',run_limitations:['会话执行失败（AttributeError）']}).title,/异常/);const p=progressData({status:'checking',run_id:'new',messages:[{type:'run_started',run_id:'new',warning_count:1}],warnings:['会话执行失败（AttributeError）'],checks:[]});assert.equal(p.errors.length,0);assert.equal(p.percent,null);});

test('provider connectivity failure is visibly abnormal even when backend completed',()=>{assert.match(progressData({status:'completed',run_limitations:['The model provider could not be reached.']}).title,/异常/);});

import {isRunning,phaseWaitSeconds} from '../dist/session-progress.js';
test('running guard and wait indicator do not invent percent; timeout is error',()=>{assert.equal(isRunning({status:'planning'}),true);assert.equal(isRunning({status:'completed'}),false);assert.equal(phaseWaitSeconds({updated_at:'2026-11-03T00:00:00Z'},Date.parse('2026-11-03T00:01:00Z')),60);assert.match(progressData({status:'completed',run_limitations:['本轮达到时间限制，保留已完成记录。']}).title,/异常/);});

test('invalid evidence quotes stay visibly failed after model returns',()=>{const p=progressData({status:'completed',warnings:['understand 校验失败：正式目标/要求必须保留每个来源的原文摘录。','understand 输出结构无效，未补造结果。'],checks:[]});assert.equal(p.errors.length,2);assert.match(p.title,/异常/);});
