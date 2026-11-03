"""核对归档里的编号、原答、比较结论和本地引用，不重新调用模型。"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from hashlib import sha256
from pathlib import Path
from urllib.parse import unquote
from zipfile import ZipFile

base=Path(__file__).resolve().parent
repo=base.parents[1]
def read(rel):return json.loads((base/rel).read_bytes())
def sha(p):return sha256(p.read_bytes()).hexdigest()
def main():
    batch=base/'批次/模型原答'
    log=read('批次/覆盖校验.json')
    coding={r['位置']:r for r in read('批次/结果比较/逐条映射.json')}
    pos={f'{k}-{c}-{i:02}' for k in [f'T{x:02}' for x in range(1,11)]
         for c in ('ABC' if k in ('T03','T04','T05','T06') else 'A') for i in range(1,4)}
    assert set(coding)==pos=={f.stem for f in batch.glob('*.json')}==set(log['逐项文件指纹'])
    sessions=set(); states=Counter();count=0
    for sid in pos:
        f=batch/(sid+'.json');r=json.loads(f.read_bytes())
        assert sha(f)==coding[sid]['原件_SHA256']==log['逐项文件指纹'][sid]
        assert r['位置']==sid and r['工具动作']==[] and r['结束事件']==['turn.completed']
        sessions.add(r['会话']);counts=r['原答']['候选'];states.update([r['原答']['任务状态']]);count+=len(counts)
        assert [x['问题'] for x in counts]==[x['原问题'] for x in coding[sid]['原问题映射']]
    assert len(sessions)==54 and dict(states)==log['任务状态汇总'] and count==log['原答候选条目含跨轮重复']
    groups=read('批次/结果比较/18组统计.json'); assert len(groups)==18 and sum(len(set(v['状态']))==1 for v in groups.values())==18
    assert sum(v['三轮均提出']==v['至少一轮提出'] for v in groups.values())==8
    table=lambda role:{(t['task'],c['id']):c['status'] for t in read(f'模拟评审/双AI原件/{role}/逐题意见.json')['assessments'] for c in t['checks']}
    assert len(table('AI甲'))==18 and table('AI甲')==table('AI乙')
    rounds=read('模拟评审/实测/12轮汇总.json')['原始记录']
    cells=Counter((r['任务'],r['方式']) for r in rounds);assert len(cells)==6 and set(cells.values())=={2}
    qq=read('方法验收/两轮判读/逐题原答.json'); assert len(qq)==42 and all(len(v)==2 for v in qq.values())
    assert len(read('方法验收/四项追测/原答.json')['原答'])==4
    score=read('方法验收/评分器实际输出.json'); assert len(score)==7 and sum(not x['符合本项期望'] for x in score)==4
    web=read('网站边界/实测/实际记录.json')['记录'];assert len(web)==15 and sum(x['符合'] for x in web)==13
    test=ET.parse(base/'方法验收/后端回归.xml').find('.//testsuite').attrib
    assert test['tests']=='226' and all(test[k]=='0' for k in ('skipped','failures','errors'))
    assert 'pass 10' in (base/'方法验收/前端回归.txt').read_text('utf-8-sig')
    gates=read('批次/产品引擎首轮.json')['首轮'];assert len({r['位置'] for r in gates})==len(gates)==18 and sum(r['千问调用'] for r in gates)==0
    prod=[]
    for name,expected in [('引擎接Codex',8),('引擎接Codex原预算',9)]:
        p=read('批次/'+name+'/联调结果.json')
        assert len(p['引擎模型回合'])==expected and p['问题数']==0 and p['完整度']=='partial'
        assert all(c['provider']=='codex_cli' and c['is_stub'] is False and c['status']=='validated' for c in p['引擎模型回合'])
        prod.append(p['会话'])
    assert len(set(prod))==2
    follow=read('批次/引擎接Codex原预算/授权与澄清/同会话续测.json')
    assert follow['会话']==prod[-1] and follow['末版']==2 and follow['原版本续测前指纹']==follow['原版本续测后指纹'] and follow['原版本可回读']
    docs=[base.parent/'D-内部测试收尾.md',base.parent/'D-新版测试报告.md',*base.rglob('*.md')]
    missing=[]
    for doc in docs:
        for raw in re.findall(r'\[[^\]]*\]\(([^)]+)\)',doc.read_text('utf-8-sig')):
            local=unquote(raw.split('#',1)[0].strip('<>'))
            if local and not re.match(r'^\w+:|^/',local) and not (doc.parent/local).exists():
                missing.append((doc.relative_to(repo).as_posix(),local))
    if missing:raise AssertionError(missing)
    for z in base.rglob('*.zip'):
        with ZipFile(z) as pack:assert pack.testzip() is None,z
    checked={'独立模型回合':len(sessions),'候选原条数':count,'状态':dict(states),'三轮任务状态完全相同的组':18,
             '三轮候选集合完全相同的组':8,'原始文件与逐条编码':54,'模拟双评相同判断':18,'交叉操作轮数':len(rounds),
             '方法场景':len(qq),'额外问法追测':4,'评分程序反例':len(score),'浏览器边界检查':len(web),
             '千问配置的实际首轮会话':len(gates),'千问模型调用':0,'独立的产品内Codex单案会话数':len(prod),'两次产品内Codex首版调用':[8,9],
             '后端通过':226,'前端通过':10,'文档链接逐一检查的文件数':len(docs),'失效相对链接数':0}
    print(json.dumps(checked,ensure_ascii=False,indent=2))
    if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(checked,ensure_ascii=False,indent=2), encoding='utf-8')

if __name__=='__main__':main()
