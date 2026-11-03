"""读取公开规格中的场景，与验收答案隔离；每批开一个新的只读 Codex 会话。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import subprocess
import tempfile
import time

here = Path(__file__).resolve().parent
repo = here.parents[2]
spec = repo / '方法专家开发交付-v0.2'
def dump(p, x):
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def tasks():
    c = [(m[1], m[2].strip()) for line in (spec/'01-04-场景输入流程与技术路径.md').read_text('utf-8').splitlines()
         if (m := re.match(r'^\| (C\d\d) [^|]+\| ([^|]+)\|', line))]
    q = [(i['test_id'], i['condition']) for i in json.loads((spec/'09-开发验收用例.json').read_text('utf-8'))['cases']]
    # 补足孤立条件的问法；不发送规格中的期望、关键验收点或结论。
    context = {
        'QA01':'要判断普通玩家能否理解页面上的专用术语。',
        'QA02':'要做“相关输入和选项的分组”这一项检查。',
        'QA03':'要做“相关输入和选项的分组”这一项检查。',
        'QA27':'请说明召回统计如何记账。','QA28':'请说明如何出报告和计算发现数。',
        'QA30':'请说明三轮判断一致率和覆盖率。','QA31':'请说明如何纳入体验和效率统计。',
    }
    return [(k,t+'。'+context.get(k,'')) for k,t in c+q]

def main(out):
    out.mkdir(parents=True, exist_ok=False)
    raw = tasks()
    assert len(raw) == len(dict(raw)) == 42
    cli = shutil.which('codex.exe') or shutil.which('codex')
    if not cli: raise SystemExit('未找到本机 Codex。')
    args_base=[cli,'exec','--ephemeral','--skip-git-repo-check','--ignore-user-config','-s','read-only',
               '-m','gpt-6-astra','-c','model_reasoning_effort="low"','--json']
    head = ('你是一名设计产品测试员。以下是独立的假设情境，不是实际产品运行。逐项回答：在给定事实下应怎么判断、系统怎样处理或怎样计入统计？'
            '用一至两句中文，说清实际状态与理由；涉及多种状态请分别说明。各题只用题面事实，不假设未给的材料，不调用任何工具。'
            '只返回 JSON 对象，键是编号，值是中文回答，不要代码块。\n')
    runs=[]
    for turn in (1,2):
        rng=random.Random(4000+turn)
        cases=raw[:];rng.shuffle(cases)
        for part in range(3):
            sl=cases[part*14:(part+1)*14]
            ids={f'K{i+1:02}':k for i,(k,_) in enumerate(sl)}
            prompt=head+json.dumps({u:t for u,(_,t) in zip(ids,sl)},ensure_ascii=False)
            runs.append((f'轮{turn}-组{part+1}',ids,prompt))
    def run(job):
        name,ids,prompt=job
        path=out/name;path.mkdir()
        (path/'输入.txt').write_text(prompt,encoding='utf-8')
        start=time.time()
        with tempfile.TemporaryDirectory() as wd:
            r=subprocess.run(args_base+['-C',wd,'-'],input=prompt.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=240)
        events=[]
        for line in r.stdout.decode('utf-8','replace').splitlines():
            try: events.append(json.loads(line))
            except ValueError: continue
        types=[e.get('item',{}).get('type') for e in events if e.get('type')=='item.completed']
        messages=[e['item']['text'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
        logs={'exit':r.returncode,'seconds':round(time.time()-start,2),'completed_item_types':types,
              'thread_id':next((e.get('thread_id') for e in events if e.get('type')=='thread.started'),None),
              'usage':[e.get('usage') for e in events if e.get('type')=='turn.completed'],
              'input_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'mapping':ids}
        dump(path/'运行.json',logs)
        if not messages: raise RuntimeError(f'{name}: 无模型返回，退出码 {r.returncode}')
        (path/'原答.txt').write_text(messages[-1],encoding='utf-8')
        msg=messages[-1].strip().removeprefix('```json').removesuffix('```').strip()
        replies=json.loads(msg)
        assert r.returncode==0 and all(t in ('reasoning','agent_message') for t in types) and set(replies)==set(ids), (name,types)
        return name,{ids[u]:v for u,v in replies.items()}
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows=dict(pool.map(run,runs))
    result={k:[next(values[k] for n,values in rows.items() if n.startswith(f'轮{roundno}') and k in values) for roundno in (1,2)] for k,_ in raw}
    dump(out/'逐题原答.json',result)
    print('42 个条件，各两次，已读回全部答案。')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('out',type=Path);main(p.parse_args().out.resolve())
