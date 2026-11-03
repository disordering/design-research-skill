"""按本批原答逐条编码，沿用上轮主题；新出现的具体问题另列。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import shutil

here = Path(__file__).resolve().parent
old = here.parents[1]/'D-续测证据/批次'
spec = importlib.util.spec_from_file_location('d_topic_compare',old/'对照三轮.py')
coding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coding)
files = sorted((here/'模型原答').glob('*.json'))
fingerprint = hashlib.sha256(b''.join(p.read_bytes() for p in files)).hexdigest()
assert len(files)==54 and fingerprint=='ac84f9f3b1a2ddd237386b53cc1759b01ebce866f3c9ceb52f033cb333ff35a8', '原答已变，请重新核对编码'
coding.here = here
coding.definitions['T04'][1].append('填写前看不到页数和份数的允许范围')
coding.definitions['T07'][1].extend(['织羽强化没有说明各材料本次消耗','已达到天赋等级但灰态难解释'])
coding.definitions['T08'][1].append('不同选择范围显示相同分解所得')
coding.definitions['T09'][1].append('初始位置的取消按钮受底部手势区遮挡')
# 一格对应一条原答；+ 表示同一条明说了多个现象，/ 分开三个会话。
coding.manual = {
    'T01-A':'- / 1 / 1','T02-A':'1 2+3 4 / 1 2+3 4 / 2+3 1 4',
    'T03-A':'1 2 / 1 2 / 1 2','T03-B':'1 2 / 1 2 / 1 2','T03-C':'3 4 1 / 3+4 1 2 / 3 4 1',
    'T04-A':'1+2 / 2 / 2','T04-B':'2 / 1 / 1+2','T04-C':'1 5 / 3 2 / 3 1',
    'T05-A':'1 / 1 / 1','T05-B':'1 / 1 / 1','T05-C':'2 3 4 / 2 3 4+5 / 2 3 1+4',
    'T06-A':'1 2 / 1 2 / 1','T06-B':'1 / 1 / 1','T06-C':'1 3 2 / 1 3 / 1 3',
    'T07-A':'1 2 5 / 2 1 6 / 1 2 7','T08-A':'1 2 3 / 1 2 3+4 / 1 2 3',
    'T09-A':'1+2 3 / 1 2 / 1+2 3','T10-A':'1 2 / 1 2 / 2',
}

if __name__ == '__main__':
    target = here/'候选对照'
    target.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        stage = Path(work)/'编码'
        coding.main(stage)
        for p in stage.iterdir():
            shutil.copyfile(p,target/p.name)
    def load(root):
        return json.loads((root/'18组统计.json').read_bytes())
    before, after = load(old/'结果比较'), load(target)
    def stable(batch):
        return sum(r['三轮均提出']==r['至少一轮提出'] for r in batch.values())
    common = {k: sorted(set(before[k]['三轮均提出']) & set(after[k]['三轮均提出'])) for k in after}
    (target/'跨两批比较.json').write_text(json.dumps({'旧批三轮候选集合一致组数':stable(before),
        '新批三轮候选集合一致组数':stable(after),'编码方法':'按对象与现象归并；仅计候选，不计建议和待验证栏。',
        '六次均提到的主题':common},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
