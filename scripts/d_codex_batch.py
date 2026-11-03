"""D 开发批次：准备固定视觉证据，启动新的 Codex 会话，逐个保存输出。"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'docs/D-续测证据/批次'
WEB = REPO / 'fixtures/d-v02-sites'
SPEC = REPO / 'fixtures/d-v02-batch'
sys.path[:0] = [str(WEB), str(SPEC), str(REPO)]
from prepare import assemble, inputs

MODEL = 'gpt-6-astra'
PROMPT = """请独立评审下列界面与任务。只使用本条给到的材料，不调用工具，不读取其他文件。
附件按下列画面顺序给出。看图可以判断视觉线索，连续实际操作画面可以判断这次路径的结果。需求说明期望，源码说明实现。请用中文简短回答，至多报三个值得改的具体候选，允许没有问题。每条指出哪张画面或哪份材料能定位。仅推测或没展示的操作写在待验证项，勿用其支撑高严重度。设计画板中的编号、红框和原图旁的注释应按设计说明理解。任务状态仅用“达成”“受阻”“待验证”。静态图无法证明已成功完成操作。行动建议应针对直接证据。"""


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def relative(path):
    return path.relative_to(REPO).as_posix()


def record(path, caption):
    return {'文件': relative(path), 'SHA256': sha(path), '画面内容或先前动作': caption}


def web_evidence():
    import smoke
    from playwright.sync_api import sync_playwright
    from serve import make_server
    traces = {}
    with make_server(quiet=True) as server, sync_playwright() as pw:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        browser = pw.chromium.launch()
        try:
            for i, flow in enumerate((smoke.room, smoke.print_shop, smoke.repair, smoke.workshop), 1):
                task = f'T{i+2:02d}'
                context = browser.new_context(locale='zh-CN', viewport={'width': 1280, 'height': 800})
                try:
                    page = context.new_page()
                    page.goto(f'http://127.0.0.1:{server.server_port}/w{i:02d}/')
                    frames = []
                    def capture():
                        path = OUT / '网站过程' / task / f'{len(frames)+1:02d}.jpg'
                        path.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(path), type='jpeg', quality=85)
                        frames.append(record(path, page.locator('body').inner_text()))
                    def observe(browser_page, target, expected, steps):
                        smoke_expect = smoke.expect(target)
                        smoke_expect.to_contain_text(expected)
                        capture()
                    capture()
                    with patch.object(smoke, 'observation', observe):
                        flow(page, [])
                    traces[task] = frames
                finally:
                    context.close()
        finally:
            browser.close()
            server.shutdown()
            thread.join()
    return traces


def prepare_evidence():
    assert inputs() == read(SPEC / 'frozen-inputs.json'), '冻结输入发生变化'
    rows = {t: [record(REPO / f'fixtures/d-v02-static/{t}.png', '原图')] for t in ('T01', 'T02')}
    rows.update(web_evidence())
    hufa = REPO / 'docs/D-护法复核证据'
    source = REPO / 'docs/D-复核证据'
    hufa_paths = [next(hufa.glob('EV04-*')), next(hufa.glob('EV06-*')),
                  source / 'D-HF-001-节点升级原画面.jpg', hufa / 'EV09-织羽一键强化.jpg']
    rows['T07'] = [record(p, '画板视图 '+n) for p, n in zip(hufa_paths, read(SPEC/'tasks.json')['tasks'][6]['nodes'])]
    wushan = sorted((source/'吴山石').glob('*.jpg'))
    assert len(wushan) == 7
    rows['T08'] = [record(p, '画板视图 '+n) for p,n in zip(wushan, read(SPEC/'tasks.json')['tasks'][7]['nodes'])]
    labels = {
        'T09': ('Flex', [(1,'打开原型起点'), (2,'点 Wishlist'), (3,'点 Add Item'), (5,'下滚查看完整操作区'),
                          (6,'点底部 Cancel 中心'), (7,'点表单左上返回'), (9,'重新打开原型，进入 Wishlist'),
                          (10,'点清单左上返回')]),
        'T10': ('CHOPS', [(1,'打开原型起点'),(2,'点 Login'),(3,'点原型表单 Login'),(4,'点 Shop Now'),(5,'点弹窗右上关闭')])}
    for t,(name, sequence) in labels.items():
        rows[t]=[record(next((source/name).glob(f'{idx:02d}-*.jpg')), label) for idx,label in sequence]
    save(OUT/'材料索引.json', {'时间':utc(), '任务':rows})


def make_schema():
    text = {'type':'string'}
    def obj(fields):
        return {'type':'object', 'properties':fields, 'required':list(fields), 'additionalProperties':False}
    def array(item):
        return {'type':'array', 'items':item}
    return obj({'任务状态':{'type':'string','enum':['达成','受阻','待验证']}, '任务结果':text,
        '候选':array(obj({'问题':text,'证据位置':text,'严重度':{'type':'string','enum':['高','中','低']},'建议':text})),
        '待验证':array(text)})


def run_slot(job):
    slot, body, frames, cli, attempt = job
    start = utc()
    elapsed = time.monotonic()
    additions = [{'材料':x['title'], '角色':x['role'], '材料原文':x['content']}
                 for x in body['sources'] if x['kind']=='document']
    material = {'任务目的':body['purpose'], '画面次序':[f'第{i}张：'+r['画面内容或先前动作']
                  for i,r in enumerate(frames,1)], '补充材料':additions}
    prompt = PROMPT+'\n'+json.dumps(material,ensure_ascii=False)
    target = OUT/'模型原答'/f'{slot}.json'
    if target.is_file() and read(target).get('状态')=='已返回':
        return
    result={'位置':slot,'尝试':attempt,'开始':start,'模型':MODEL,'推理设置':'low',
            '提供图数':len(frames),'补充材料数':len(additions),'材料文本_SHA256':hashlib.sha256(prompt.encode()).hexdigest()}
    with tempfile.TemporaryDirectory(prefix='d-review-') as temp:
        tmp=Path(temp)
        schema=tmp/'schema.json'
        save(schema,make_schema())
        cmd=[cli,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only',
             '--cd',temp,'--model',MODEL,'-c','model_reasoning_effort=low','--output-schema',str(schema),'--json']
        for i, row in enumerate(frames,1):
            p=REPO/row['文件']
            assert sha(p)==row['SHA256']
            masked=tmp/f'frame-{i:02d}{p.suffix}'
            shutil.copyfile(p,masked)
            cmd+=['--image',str(masked)]
        try:
            proc=subprocess.run(cmd+['-'],input=prompt.encode(),capture_output=True,timeout=150,cwd=temp)
            events=[]
            for line in proc.stdout.decode('utf-8',errors='replace').splitlines():
                if line.strip().startswith('{'):
                    events.append(json.loads(line))
            items=[e.get('item',{}) for e in events if e.get('type')=='item.completed']
            result.update(会话=next((e.get('thread_id') for e in events if e.get('type')=='thread.started'),None),
                          工具动作=[i.get('type') for i in items if i.get('type') not in ('reasoning','agent_message')],
                          结束事件=[e['type'] for e in events if e.get('type') in ('turn.completed','turn.failed')])
            raw=next((i.get('text') for i in reversed(items) if i.get('type')=='agent_message'),None)
            if not raw or proc.returncode or 'turn.completed' not in result['结束事件']:
                err=next((str(e.get('error',e.get('message','')))[:400] for e in reversed(events) if e.get('type') in ('turn.failed','error')),'无完整回复')
                raise RuntimeError(f'退出 {proc.returncode}，{err}')
            result['原答']=json.loads(raw)
            result['状态']='已返回' if not result['工具动作'] else '使用额外工具，请排除'
        except Exception as exc:
            result.update(状态='失败',原因=str(exc)[:600] if not isinstance(exc,subprocess.TimeoutExpired) else '单次 150 秒超时')
    result['耗时秒']=round(time.monotonic()-elapsed,2)
    if target.exists():
        old=read(target)
        save(OUT/'未完成尝试'/f"{slot}-{old['尝试']}.json",old)
    save(target,result)
    print(slot,result['状态'],result['耗时秒'],flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('step',choices=['prepare','run','verify'])
    ap.add_argument('--parallel',type=int,default=4)
    ap.add_argument('--attempt',type=int,default=1)
    ap.add_argument('--prefix',default='')
    args=ap.parse_args()
    if args.step=='prepare':
        prepare_evidence()
        return
    assert inputs()==read(SPEC/'frozen-inputs.json')
    frames=read(OUT/'材料索引.json')['任务']
    _,matrix,ledger=assemble({'provider':'qwen','model_name':'qwen3.8-max-0902'})
    if args.step=='verify':
        rows=[read(OUT/'模型原答'/f"{r['slot']}.json") for r in ledger]
        assert [r['位置'] for r in rows]==[r['slot'] for r in ledger]
        assert len({r['会话'] for r in rows})==54
        assert all(r['模型']==MODEL and r['状态']=='已返回' and not r['工具动作']
                   and r['结束事件']==['turn.completed'] for r in rows)
        for t, fs in frames.items():
            for frame in fs:
                assert sha(REPO/frame['文件'])==frame['SHA256'], t
        for row in rows:
            slot=row['位置']
            assert row['提供图数']==len(frames[slot[:3]])
            assert row['补充材料数']==sum(s['kind']=='document' for s in matrix[slot]['sources'])
            ans=row['原答']
            assert ans['任务状态'] in ('达成','待验证','受阻') and ans['任务结果']
            assert len(ans['候选'])<=3
            assert all(set(i)=={'问题','证据位置','严重度','建议'} and all(i.values()) for i in ans['候选'])
        groups={r['位置'][:-3] for r in rows}
        assert len(groups)==18 and all(len({r['材料文本_SHA256'] for r in rows if r['位置'][:-3]==key})==1 for key in groups)
        save(OUT/'覆盖校验.json', {'时间':utc(),'独立会话数':len(rows),'组数':len(groups),
             '模型':MODEL,'推理设置':'low','不同图文件':sum(len(images) for images in frames.values()),
             '任务状态汇总':dict(Counter(r['原答']['任务状态'] for r in rows)),
             '原答候选条目含跨轮重复':sum(len(r['原答']['候选']) for r in rows),
             '首次成功':sum(r['尝试']==1 for r in rows),'模型额外工具动作':0,
             '逐项文件指纹':{r['位置']:sha(OUT/'模型原答'/f"{r['位置']}.json") for r in rows}})
        return
    cli=os.environ['CODEX_APP_RUNTIME_CLI_PATH']
    jobs=[(r['slot'],matrix[r['slot']],frames[r['task']],cli,args.attempt) for r in ledger if r['slot'].startswith(args.prefix)]
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        list(pool.map(run_slot,jobs))


if __name__=='__main__':
    main()
