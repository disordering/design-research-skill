"""对冻结的两组 H05 图片各执行三次独立 Codex 证据读图，不调用评审产品。"""
import hashlib
import json
import os
import sys
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
SOURCE = REPO.parent / 'work/d_1104_latest_audit/H05复审对照'
MODEL = 'gpt-6-astra'
DISABLED = ['shell_tool','unified_exec','view_image','browser_use','browser_use_external',
            'computer_use','apps','plugins','multi_agent','code_mode_host','hooks','skill_search']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2)+'\n')


def schema():
    def obj(properties):
        return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
    return obj({'三条要求':{'type':'array','minItems':3,'maxItems':3,'items':obj({
        '要求编号':{'type':'integer','enum':[1,2,3]},
        '状态':{'type':'string','enum':['达成','受阻','证据不足']},
        '问题':{'type':'string'},
        '严重度':{'type':'string','enum':['高','中','低','无','待定']},
        '图号与可见值':{'type':'string'},
        '依据':{'type':'string'}
    })}})


def prepare():
    trace = SOURCE/'实测/四组走查.json'
    data = json.loads(trace.read_text(encoding='utf-8'))
    card = SOURCE/'A/任务卡.txt'
    assert card.read_bytes()==(SOURCE/'B/任务卡.txt').read_bytes()
    source_card = OUT/'输入/任务卡原文.txt'
    source_card.parent.mkdir(parents=True, exist_ok=True)
    assert not source_card.exists(), '此目录已记录输入，请新建目录执行，保留原有证据'
    shutil.copyfile(card, source_card)
    prompt = '''你正在做图片证据判断。只使用本条给到的两张附件、任务卡原文和记录路径，不调用任何工具，不读取其他文件，不打开网页，也不自行执行操作。
图1是路径中最后一次核对信息时的画面，图2是提交后的完成画面。
记录路径：选择下午二层服务台 → 核对信息 → 返回选择 → 核对信息 → 提交登记。
请用中文回答任务卡中三条要求各自的状态、问题、严重度、引用图号与可见值、判断依据。每条要求恰好一项。状态只用“达成”“受阻”“证据不足”。无问题可写“无”，严重度用“高”“中”“低”“无”或“待定”。材料未展示的内容请自行标识证据不足。

任务卡原文如下
'''+source_card.read_text(encoding='utf-8-sig')
    (OUT/'输入/完整提示词.txt').write_text(prompt, encoding='utf-8')
    save(OUT/'输入/输出结构.json',schema())
    inputs = []
    expectations = []
    for group, version in [('图组01','A'),('图组02','B')]:
        row = next(r for r in data['路径'] if r['版本']==version and r['时段']=='下午')
        images = []
        for number, name in enumerate([f'{version}-下午-01核对.png',f'{version}-下午-02回执.png'],1):
            original = SOURCE/'实测'/name
            assert sha(original)==row['截图'][name]
            masked = OUT/'输入'/group/f'frame-{number:02d}.png'
            masked.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original,masked)
            images.append({'图号':number,'输入文件':masked.relative_to(OUT).as_posix(),
                           '原图':str(original),'原图SHA256':sha(original),'输入图SHA256':sha(masked)})
        inputs.append({'图组':group,'图':images})
        expectations.append({'图组':group,'本机样本':version,'要求3回执目标错配':not row['回执与预期一致'],
            '浏览器提交前':row['提交前'],'浏览器实际回执':row['实际回执'],'浏览器返回保留选择':row['返回已保留选择']})
    save(OUT/'输入索引.json',{'模型':MODEL,'推理设置':'low','任务卡原文件SHA256':sha(card),
        '任务卡输入SHA256':sha(source_card),'完整提示词SHA256':sha(OUT/'输入/完整提示词.txt'),
        '图组':inputs,'提供给模型的材料':'仅附件两图、完整提示词与输出结构；未提供图组映射、预期、代码或说明'})
    save(OUT/'冻结评分口径.json',{'冻结时间UTC':datetime.now(timezone.utc).isoformat(),
        '浏览器记录':str(trace),'浏览器记录SHA256':sha(trace),'预期':expectations,
        '目标':'逐次核对要求3是否识别提交前后时段与服务台错配。每组3次，分别报告稳定性。',
        '附加核对':'检查引用可见值及图号；选择页未提供，不把未见的选择控件、双选项布局写成图中事实。',
        '诊断层次':'对冻结的操作后图像判断，不是浏览器自动探索、原生引擎端到端测评或真人测试。'})
    return prompt, inputs


def run_one(job):
    group, repeat, images, prompt = job
    slot = f'{group}-第{repeat}次'
    target = OUT/'原始会话'/slot
    target.mkdir(parents=True, exist_ok=False)
    result = {'会话位置':slot,'图组':group,'重复':repeat,'模型':MODEL,'推理设置':'low',
        '开始UTC':datetime.now(timezone.utc).isoformat(),'输入文本SHA256':hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
        '输入图片':[{'图号':x['图号'],'SHA256':x['输入图SHA256']} for x in images]}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='h05-read-') as temp:
        root = Path(temp)
        structure = root/'schema.json'
        structure.write_text(json.dumps(schema(),ensure_ascii=False),encoding='utf-8')
        cmd = [os.environ['CODEX_APP_RUNTIME_CLI_PATH'],'exec','--ignore-user-config','--ephemeral',
               '--skip-git-repo-check','--sandbox','read-only','--cd',temp,'--model',MODEL,
               '-c','model_reasoning_effort=low','-c','web_search="disabled"','--output-schema',str(structure),'--json']
        for feature in DISABLED:
            cmd += ['--disable',feature]
        for number, data in enumerate(images,1):
            original = OUT/data['输入文件']
            assert sha(original)==data['输入图SHA256']
            image = root/f'frame-{number:02d}.png'
            shutil.copyfile(original,image)
            cmd += ['--image',str(image)]
        result['禁用功能'] = DISABLED
        try:
            proc = subprocess.run(cmd+['-'],input=prompt.encode('utf-8'),capture_output=True,timeout=240,cwd=temp)
            (target/'CLI原始事件.jsonl').write_bytes(proc.stdout)
            (target/'CLI标准错误.txt').write_bytes(proc.stderr)
            events = [json.loads(line) for line in proc.stdout.decode('utf-8').splitlines() if line.strip().startswith('{')]
            completed = [e.get('item',{}) for e in events if e.get('type')=='item.completed']
            # 同时检查开始与结束事件，避免只检查完成项而遗漏未完成工具调用。
            tool_items = [e.get('item',{}) for e in events if e.get('type','').startswith('item.')
                          and e.get('item',{}).get('type') not in (None,'reasoning','agent_message','error')]
            result['线程ID'] = next((e.get('thread_id') for e in events if e.get('type')=='thread.started'),None)
            result['工具项'] = tool_items
            result['退出码'] = proc.returncode
            result['结束事件'] = [e['type'] for e in events if e.get('type') in ['turn.completed','turn.failed','error']]
            raw = next((i.get('text') for i in reversed(completed) if i.get('type')=='agent_message'),None)
            assert proc.returncode==0 and raw and result['线程ID'] and result['结束事件']==['turn.completed'], '会话未正常完成'
            assert not tool_items, '会话使用了额外工具，排除'
            (target/'模型原答.txt').write_text(raw,encoding='utf-8')
            answer = json.loads(raw)
            assert sorted(x['要求编号'] for x in answer['三条要求'])==[1,2,3]
            save(target/'模型原答.json',answer)
            result['状态']='已返回'
        except Exception as exc:
            result.update(状态='失败',原因=str(exc))
            if isinstance(exc,subprocess.TimeoutExpired):
                (target/'CLI原始事件.jsonl').write_bytes(exc.stdout or b'')
                (target/'CLI标准错误.txt').write_bytes(exc.stderr or b'')
    result['耗时秒']=round(time.monotonic()-started,2)
    save(target/'调用记录.json',result)
    print(slot,result['状态'],result['耗时秒'],flush=True)
    return result


def main():
    prompt, groups=prepare()
    jobs=[(g['图组'],repeat,g['图'],prompt) for repeat in range(1,4) for g in groups]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(run_one,jobs))
    save(OUT/'调用汇总.json',{'完成UTC':datetime.now(timezone.utc).isoformat(),'并发上限':6,'调用':results})
    assert all(r['状态']=='已返回' for r in results)
    assert len({r['线程ID'] for r in results})==6


def reparse():
    # error 项是工具禁用后的启动通知，不是调用；保留初次采集状态，另存复核结果。
    results=[]
    for target in sorted((OUT/'原始会话').iterdir()):
        initial=json.loads((target/'调用记录.json').read_text(encoding='utf-8'))
        events=[json.loads(line) for line in (target/'CLI原始事件.jsonl').read_text(encoding='utf-8').splitlines() if line.strip().startswith('{')]
        tool_items=[e.get('item',{}) for e in events if e.get('type','').startswith('item.')
                    and e.get('item',{}).get('type') not in (None,'reasoning','agent_message','error')]
        notices=[e['item'] for e in events if e.get('item',{}).get('type')=='error']
        messages=[e['item']['text'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
        assert initial['退出码']==0 and initial['结束事件']==['turn.completed'] and not tool_items and messages
        raw=messages[-1]
        with (target/'模型原答.txt').open('x',encoding='utf-8') as stream:
            stream.write(raw)
        answer=json.loads(raw)
        assert sorted(row['要求编号'] for row in answer['三条要求'])==[1,2,3]
        save(target/'模型原答.json',answer)
        revised={**initial,'状态':'已返回','工具项':tool_items,'启动通知':notices,
                 '解析复核':'初次解析把工具禁用启动通知误计为工具调用。本记录按原始事件复核，不重新调用模型。'}
        revised.pop('原因',None)
        save(target/'解析复核.json',revised)
        results.append(revised)
    assert len(results)==len({r['线程ID'] for r in results})==6
    save(OUT/'有效调用汇总.json',{'复核UTC':datetime.now(timezone.utc).isoformat(),'实际模型调用数':6,'独立线程数':6,'额外工具调用数':0,'调用':results})
    print('6 个原始独立会话均完成，0 次额外工具调用；解析复核另存。')


if __name__=='__main__':
    reparse() if '--reparse' in sys.argv else main()
