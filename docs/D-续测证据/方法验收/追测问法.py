"""同一条件补齐检查对象后重问，只比较回答变化，不回填前两轮。"""
import json
from pathlib import Path
import tempfile
import shutil
import sys
import subprocess

out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
questions={
    '01':'只检查 E03「操作后是否有符合当前操作的状态反馈」：点标签后，目标页签内容已同步切到新页签，无加载动画。就这次切换，反馈检查结论是什么？',
    '02':'10 条计划检查在 3 轮中均未执行。分别报告 a) 共同执行覆盖，b) 仅比较三轮均实际执行的检查时的判断一致率，c) 全部计划检查的执行状态一致率。每项分别列分子和分母。',
    '03':'工具已尝试点击元素并抛出异常，应用未发生产品错误。分别填工具动作的执行状态、与该动作相关的产品缺陷结论。',
    '04':'正在运行时刷新并恢复，外部网页可能已变。请说明对已填审核、待答问题、下一次点击的页面和目标分别怎么处理。'
}
prompt='只按每项给出的事实独立作答，不查资料，不使用工具，每题 1 至 2 句中文。只返回 JSON 对象，键是两位编号。\n'+json.dumps(questions,ensure_ascii=False)
(out/'问题.txt').write_text(prompt,encoding='utf-8')
with tempfile.TemporaryDirectory() as wd:
    r=subprocess.run([shutil.which('codex.exe') or 'codex','exec','--ignore-user-config','--skip-git-repo-check','--ephemeral','-s','read-only','-m','gpt-6-astra','-c','model_reasoning_effort="low"','--json','-C',wd,'-'],input=prompt.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=150,check=True)
events=[json.loads(x) for x in r.stdout.decode().splitlines() if x.strip().startswith('{')]
items=[e['item'] for e in events if e.get('type')=='item.completed']
assert all(e['type'] in ('reasoning','agent_message') for e in items)
reply=next(e['text'] for e in reversed(items) if e['type']=='agent_message')
data=json.loads(reply.strip().removeprefix('```json').removesuffix('```').strip())
assert set(data)==set(questions)
(out/'原答.json').write_text(json.dumps({'会话':[e.get('thread_id') for e in events if e.get('type')=='thread.started'],'原答':data},ensure_ascii=False,indent=2),encoding='utf-8')
