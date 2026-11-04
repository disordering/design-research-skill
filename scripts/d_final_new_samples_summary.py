"""只汇总已导出的新样本原生记录；不生成参考答案或替代判断。"""
from pathlib import Path
import json,hashlib
from collections import Counter
from d_final_new_samples_audit import raw_bytes
ROOT=Path(__file__).resolve().parents[1]/'docs/D-最终验收证据/新样本'
records=[]
for stage in sorted((ROOT/'原生评审').iterdir()):
    snapshot=stage/'会话快照.json'
    if not snapshot.exists():continue
    s=json.loads(snapshot.read_text(encoding='utf-8'))
    result=json.loads((stage/'运行结果.json').read_text(encoding='utf-8'))
    env=json.loads((stage/'运行环境.json').read_text(encoding='utf-8'))
    checks=[c for c in s['checks'] if c['run_id']==s['run_id'] and not c['stale'] and c['scope_status']=='included']
    model_calls=s.get('model_calls',[])
    usage=Counter(); usage_calls=0
    for call_record in stage.rglob('调用记录.json'):
        event_file=call_record.parent/'CLI原始事件.jsonl'
        for line in raw_bytes(event_file).decode('utf-8',errors='replace').splitlines():
            try:event=json.loads(line)
            except ValueError:continue
            if event.get('type')=='turn.completed':
                usage_calls+=1
                for key,value in event.get('usage',{}).items():
                    if isinstance(value,(int,float)):usage[key]+=value
    records.append({
        '目录':stage.name,'样本':env['样本'],'轮次':env['轮次'],'原版能力试点':env.get('原版能力试点',False),
        '统计组':'原版能力诊断' if env.get('原版能力试点',False) else ('修复回归' if env['样本']=='N01' else '新任务独立验收'),
        '来源':'AI真实模型原生链','模型':env['模型'],'会话ID':s['session_id'],
        '源码冻结清单SHA256':env['源码冻结清单SHA256'],'材料冻结清单SHA256':env['材料冻结清单SHA256'],
        '状态':s['status'],'完整度':s['report_completeness'],'墙钟秒':result['墙钟秒'],
        '用户缩减范围收尾':(stage/'用户缩减范围收尾事件.json').exists(),
        '主任务CLI调用':result['主任务CLI调用'],'逐屏CLI调用':result['逐屏CLI调用'],
        'CLI原始用量':dict(usage),'含用量的已完成CLI数':usage_calls,
        '用量口径':'逐项累加 CLI turn.completed 的 usage；输入、缓存输入、输出分别保留，不估算费用。未返回用量的调用不按零用量解释。',
        '生产调用状态':dict(Counter(c.get('status') for c in model_calls)),
        '生产调用阶段':dict(Counter(c.get('operation') for c in model_calls)),
        '范围内检查数':len(checks),'执行状态':dict(Counter(c['execution_status'] for c in checks)),
        '固定要求检查':[{k:c.get(k) for k in ['check_id','coverage_id','ref','task_id','object_refs','execution_status','decision','reason','evidence_ids','object_ids']} for c in checks if c['ref'].startswith('REQ-')],
        '动作':s['actions'],'问题':s['questions'],'最终发现':s['findings'],
        '逐屏结果':s['screen_reviews'],'警告':s['warnings'],'运行说明':s['run_limitations'],
        '原快照SHA256':hashlib.sha256(snapshot.read_bytes()).hexdigest()})
path=ROOT/'各轮事实汇总.json'
path.write_text(json.dumps({'来源':'已完成会话原始记录的程序汇总，不作答案评分','轮次':records},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps([{'目录':x['目录'],'状态':x['状态'],'主调用':x['主任务CLI调用'],'逐屏调用':x['逐屏CLI调用'],'发现数':len(x['最终发现'])} for x in records],ensure_ascii=False))

