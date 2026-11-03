"""在新目录复跑原来的 54 个评审位置，对比修前与修后两次模型批次。"""
import argparse
import os
import shutil
import sys
from collections import Counter
from pathlib import Path
import re

import d_codex_batch as batch

OLD = batch.OUT
NEW = batch.REPO / 'docs/D-三项修复证据/同批54次'


def check_materials():
    assert OLD != NEW and batch.inputs() == batch.read(batch.SPEC / 'frozen-inputs.json')
    source = OLD / '材料索引.json'
    NEW.mkdir(parents=True, exist_ok=True)
    if not (NEW / source.name).exists():
        shutil.copyfile(source, NEW / source.name)
    assert batch.sha(source) == batch.sha(NEW / source.name)
    for frames in batch.read(source)['任务'].values():
        for frame in frames:
            assert batch.sha(batch.REPO / frame['文件']) == frame['SHA256']


def compare():
    groups = {}
    sessions = set()
    old_stats, new_stats = (batch.read(path / '覆盖校验.json') for path in (OLD, NEW))
    fingerprints = old_stats['逐项文件指纹']
    assert fingerprints.keys() == new_stats['逐项文件指纹'].keys()
    for slot, fingerprint in fingerprints.items():
        old, new = [path / '模型原答' / f'{slot}.json' for path in (OLD, NEW)]
        assert batch.sha(old) == fingerprint and batch.sha(new) == new_stats['逐项文件指纹'][slot]
        a, b = map(batch.read, (old, new))
        assert all(a[k] == b[k] for k in ('位置','模型','推理设置','材料文本_SHA256','提供图数','补充材料数'))
        for row in (a, b):
            assert row['会话'] and row['会话'] not in sessions
            sessions.add(row['会话'])
        av, bv = a['原答'], b['原答']
        groups.setdefault(slot[:-3], []).append({'位置':slot,'修前状态':av['任务状态'],'修后状态':bv['任务状态'],
            '修前候选数':len(av['候选']),'修后候选数':len(bv['候选'])})
    assert len(sessions) == 108 and len(groups) == 18
    flat = sum(groups.values(), [])
    batch.save(NEW/'两批对照.json', {
        '性质':'同批材料的两次独立 AI 判读；程序修复成效另以同输入的程序返回验收。',
        '验证':'旧原答指纹匹配，输入索引逐字节相同，54 个位置各自的提示指纹、材料数、模型与推理设置相同。两批会话编号没有重复。',
        '视觉材料数':sum(len(frames) for frames in batch.read(OLD/'材料索引.json')['任务'].values()),
        '同位置任务状态相同数':sum(r['修前状态']==r['修后状态'] for r in flat),
        '两批':{label:{'状态数':dict(Counter(r[label+'状态'] for r in flat)),
            '候选总条数含重复':sum(r[label+'候选数'] for r in flat),
            '三次状态一致的组数':sum(len({r[label+'状态'] for r in group})==1 for group in groups.values())
            } for label in ('修前','修后')},
        '逐组':groups})


if __name__ == '__main__':
    selector = argparse.ArgumentParser(add_help=False)
    selector.add_argument('--new-name', help='另起一批的名称；同名批次可接续或核验')
    selected, remainder = selector.parse_known_args()
    sys.argv[1:] = remainder
    if selected.new_name:
        if not re.fullmatch(r'[\w-]{1,60}', selected.new_name) or Path(selected.new_name).is_reserved():
            raise SystemExit('批次名只使用文字、数字、下划线或短横线。')
        NEW = NEW.parent / '追加批次' / selected.new_name
    if sys.argv[1:2] not in (['run'], ['verify']):
        raise SystemExit('用法：python scripts/d_repair_batch.py run [--parallel 6] [--new-name 批次02]，完成后以同名执行 verify')
    check_materials()
    batch.OUT = NEW
    if sys.argv[1] == 'run':
        cli = os.environ.get('CODEX_APP_RUNTIME_CLI_PATH') or shutil.which('codex.exe') or shutil.which('codex')
        if not cli:
            raise SystemExit('未找到已登录的 Codex 命令')
        os.environ['CODEX_APP_RUNTIME_CLI_PATH'] = cli
    batch.main()
    if sys.argv[1] == 'verify':
        compare()
