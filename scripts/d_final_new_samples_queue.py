"""以固定双路队列接续新样本剩余六轮，保持同一正式配置。"""
import asyncio,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
ROOT=REPO/'docs/D-最终验收证据/新样本'
WORK=REPO.parent/'work/d_final_new_samples_queue'
def utc():return datetime.now(timezone.utc).isoformat()
def save():
    (WORK/'队列状态.json').write_text(json.dumps(STATE,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def label(sample,round):return f'修后v1-{sample}-第{round}轮'
def result_path(name):return ROOT/'原生评审'/name/'运行结果.json'
def blocker(name):
    stage=ROOT/'原生评审'/name
    for path in stage.rglob('CLI原始事件.jsonl'):
        for line in path.read_text(encoding='utf-8',errors='replace').splitlines():
            try:event=json.loads(line)
            except ValueError:continue
            if event.get('type') not in {'error','turn.failed'}:continue
            text=json.dumps(event,ensure_ascii=False).lower()
            if any(x in text for x in ['usage_limit','usage limit','rate_limit','rate limit','insufficient_quota','not authenticated','authentication','unauthorized']):
                return {'文件':str(path.relative_to(ROOT)),'原因':'真实CLI返回额度或鉴权阻塞，停止新增轮次'}
    return None
STATE={'开始':utc(),'来源':'AI 固定双路执行队列','正式模型':'gpt-6.1-sol','推理设置':'low','源码':'冻结运行源码-修后v1','最大本批并发':2,'计划':[
    {'路':'A','等待':'修后v1-N02-第1轮','后续':[label('N01',2),label('N03',2),label('N02',3)]},
    {'路':'B','等待':'修后v1-N03-第1轮','后续':[label('N02',2),label('N01',3),label('N03',3)]}],
    '条目':[],'阻塞':None}
async def worker(route,predecessor,jobs,stop):
    print(route,'等待',predecessor,flush=True)
    while not result_path(predecessor).exists():
        if stop.is_set():return
        await asyncio.sleep(10)
    prior_blocker=blocker(predecessor)
    if prior_blocker:
        STATE['阻塞']=prior_blocker;stop.set();save();return
    for sample,round in jobs:
        if stop.is_set():return
        name=label(sample,round);row={'路':route,'批次':name,'开始':utc(),'状态':'运行中'}
        STATE['条目'].append(row);save();print(route,'启动',name,flush=True)
        args=[sys.executable,str(REPO/'scripts/d_final_new_samples.py'),'--sample',sample,'--round',str(round),'--engine-snapshot','冻结运行源码-修后v1','--batch','修后v1','--model','gpt-6.1-sol']
        environment=os.environ.copy();environment['PYTHONIOENCODING']='utf-8';environment['PYTHONDONTWRITEBYTECODE']='1'
        with (WORK/(name+'.log')).open('wb') as log:
            process=await asyncio.create_subprocess_exec(*args,cwd=REPO,env=environment,stdout=log,stderr=asyncio.subprocess.STDOUT)
            row['PID']=process.pid;save();code=await process.wait()
        row['结束']=utc();row['退出码']=code
        if code or not result_path(name).exists():
            row['状态']='脚本异常';STATE['阻塞']={'批次':name,'原因':'脚本异常或未导出最终记录'};stop.set();save();return
        result=json.loads(result_path(name).read_text(encoding='utf-8'))
        row.update({'状态':'已归档','产品状态':result['状态'],'完整度':result['完整度'],'CLI调用':result['全部CLI调用'],'墙钟秒':result['墙钟秒']})
        print(route,'完成',name,row['完整度'],row['CLI调用'],'调用',flush=True)
        block=blocker(name)
        if block:STATE['阻塞']=block;stop.set()
        save()
async def main():
    WORK.mkdir(parents=True,exist_ok=False);save();stop=asyncio.Event()
    await asyncio.gather(
        worker('A',label('N02',1),[('N01',2),('N03',2),('N02',3)],stop),
        worker('B',label('N03',1),[('N02',2),('N01',3),('N03',3)],stop))
    STATE['结束']=utc();STATE['状态']='阻塞后停止新增轮次' if stop.is_set() else '剩余六轮均已归档';save()
    print(STATE['状态'],flush=True)
asyncio.run(main())

