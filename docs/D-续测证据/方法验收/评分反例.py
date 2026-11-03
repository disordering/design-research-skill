"""以受控报告输入项目自带评分器，核对统计口径；不调用模型。"""
import json
import sys
import tempfile
from pathlib import Path

here=Path(__file__).resolve().parent
repo=here.parents[2]
sys.path[:0]=[str(repo),str(repo/'tests')]
from test_session_service import create_service, request
from engine.session_contracts import Finding, FindingClaim
from engine.session_evaluation import EvaluationLabels,evaluate_session

def make(fid, title, kind='issue', stale=False):
    return Finding(finding_id=fid,kind=kind,title=title,check_ids=['R18'],evidence_ids=['e1'],
        principle='选择应保留',detection=title,description='当前选择与提交内容应一致',suggestion='从已选记录读取时段及地点',
        severity_reason='影响提交结果',object_id='回执',run_id=run_id,stale=stale,
        claims=[FindingClaim(claim_type='requirement_match',object_id='回执',expected='14:00 二层',
            observed=title,evidence_ids=['e1'],verification_status='supported')])

def label(name, word=None):
    return dict(label_id=name,object_id='回执',title_contains=[word] if word else [])

def call(name, fs, ls, expected, assertion):
    snapshot.findings=fs
    inp=EvaluationLabels(dataset='D-评分程序反例',findings=ls)
    result=evaluate_session(snapshot,inp)
    score=result['finding_metrics']
    return dict(场景=name,预测=[f.model_dump(mode='json',include={'finding_id','kind','title','stale','object_id','detection','claims'}) for f in fs],
                参考=ls,规范期望=expected,评分器实际=score,配对=result['matches'],符合本项期望=bool(assertion(score)))

with tempfile.TemporaryDirectory() as wd:
    service,_=create_service(Path(wd))
    snapshot=service.create(request());run_id=snapshot.run_id
    joined=make('F01','时段错误：14:00 被显示为 09:00；地点错误：二层被显示为一层')
    joined.claims[0].expected='14:00';joined.claims[0].observed='09:00'
    joined.claims.append(FindingClaim(claim_type='requirement_match',object_id='回执',expected='二层',observed='一层',evidence_ids=['e1'],verification_status='supported'))
    single=make('F02','时段错误：14:00 被显示为 09:00')
    labels=[label('回执的时段','时段错误'),label('回执的地点','地点错误')]
    fresh=make('F03','可加入分享按钮',kind='suggestion')
    rows=[
        call('两条原子问题已分别写入同一预测',[joined],labels,'两个参考均命中；只统计一条预测。',lambda d:d['matched']==2 and d['actual']==1),
        call('只有时段证据，不能顺带命中地点',[single],labels,'命中一处、漏掉一处。',lambda d:d['matched']==1 and d['missed']==1),
        call('检索漏掉判据，已有明确参考',[],labels[:1],'漏检 1 项；召回为 0/1。',lambda d:d['missed']==1 and d['recall']==0),
        call('没有参考也没有预测',[],[],'准确率与召回的分母均为 0，展示为不适用。',lambda d:d['precision'] is None and d['recall'] is None),
        call('单列设计建议',[single,fresh],labels[:1],'问题预测 1、命中 1；建议 1，另行评价。',lambda d:d['actual']==1 and d['extra']==0),
        call('旧版本不重复计数',[single,make('OLD','地点错误',stale=True)],labels,'只计本版时段，旧版本地点不计。',lambda d:d['actual']==1 and d['missed']==1),
        call('同一对象的不同问题：参考只给对象编号',[fresh.model_copy(update={'kind':'issue'})],[label('该页回执时段错误')],'只重合对象而现象不同，不应自动命中。',lambda d:d['matched']==0),
    ]
    p=Path(sys.argv[1])
    with p.open('x',encoding='utf-8') as f:json.dump(rows,f,ensure_ascii=False,indent=2)
    for r in rows: print(r['场景'],r['符合本项期望'])
