"""D 逐条编码后复算：比较同一任务、同一材料三轮实际提出的问题。"""
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
import sys

here=Path(__file__).resolve().parent
# 每行三个运行，/ 分轮，空格分原答条目，+ 表示一条意见明说了多个不同问题。
definitions={
'T01':('角色试用',['ERROR 装饰可能被误认作异常']),
'T02':('通知设置',['作业到期开关无可见选中态','主题无可见选中态','字号无可见选中态','工具图标缺名称']),
'T03':('讨论室预约',['人数改回合法值却保留报错','时段冲突后仍突出确认按钮','库存结果按时段固定','回执号固定／没有独立预约记录']),
'T04':('打印报价',['配送楼栋未提前标明必填','错误提示远离楼栋输入框','打印单号固定','出错后焦点回到页面而非楼栋']),
'T05':('设备报修',['房间和描述未提前标明必填','固定工单号与状态','首次按次数触发断网','只漏一项也笼统提示补两项','校验后焦点未定位缺项']),
'T06':('活动报名',['满员后仍突出报名按钮','取消后缺明确反馈','跨时段也拦截已有报名']),
'T07':('护法养成',['升阶页缺护法姓名，难以区分同头像','节点升级按钮写升星','天赋条件含占位文字','经验数值相贴','升级预览与天赋解锁关系不明确']),
'T08':('吴山石',['选中 15 级、详情为 12 级','分组与组内勾选状态不对应','全选后待分解数量仍为零']),
'T09':('Flex',['取消无效','左上返回无效']),
'T10':('CHOPS',['弹窗标题未说明选择对象','弹窗下半部留白、遮挡列表','商品卡供应商名字颜色浅'])
}
manual={
'T01-A':'1 / - / 1','T02-A':'1 2+3 4 / 2+3 1 4 / 1 2+3 4',
'T03-A':'1 2 / 1 2 / 1 2','T03-B':'1 2 / 1 2 / 1 2','T03-C':'3+4 2 1 / 3 4 1 / 3+4 1 2',
'T04-A':'1+2 / 2 / 1+2','T04-B':'1+2 / 2 / 2','T04-C':'3 2+4 / 3 1 / 3 2+4',
'T05-A':'1 / 1 / 1','T05-B':'1 / 1 / 1','T05-C':'2 3 1+4 / 3 2 1+4 / 2 3 1+5',
'T06-A':'1 / 1 2 / 1','T06-B':'1 / 1 / 1','T06-C':'1 3 / 1 3 / 1 3',
'T07-A':'1 2 3 / 2 1 4 / 2 1 5','T08-A':'1 2 / 1 2 3 / 1 2 3',
'T09-A':'1+2 / 1+2 / 1 2','T10-A':'1 2 / 2 3 / 1 2'
}

def main(out):
    out.mkdir(parents=True,exist_ok=False)
    groups={}; totals=Counter(); records=[];identities=set()
    for group,assignment in manual.items():
        task=group[:3];title,topics=definitions[task]; shapes=[];states=[];counts=[];levels={}
        for i,token in enumerate(assignment.split('/'),1):
            pos=f'{group}-{i:02}';f=here/'模型原答'/f'{pos}.json';r=json.loads(f.read_bytes());a=r['原答']
            assert r['位置']==pos and r['状态']=='已返回' and r['会话'] not in identities
            identities.add(r['会话']); codes=[s.split('+') for s in token.split() if s!='-']
            assert len(codes)==len(a['候选']),(pos,codes,len(a['候选']))
            captured=set();mapped=[]
            for cand,ids in zip(a['候选'],codes):
                names=[topics[int(k)-1] for k in ids];captured.update(names)
                for n in names: levels.setdefault(n,[]).append(cand['严重度'])
                mapped.append({'原问题':cand['问题'],'原严重度':cand['严重度'],'对应问题':names})
            shapes.append(captured);states.append(a['任务状态']);counts.append(len(codes));totals.update([states[-1]])
            records.append({'位置':pos,'原件_SHA256':sha256(f.read_bytes()).hexdigest(),'状态':states[-1],'原问题映射':mapped})
        union=set.union(*shapes);inter=set.intersection(*shapes)
        groups[group]={'任务':title,'状态':states,'候选条数':counts,'三轮均提出':sorted(inter),'至少一轮提出':sorted(union),'各主题出现轮数':{k:sum(k in s for s in shapes) for k in sorted(union)},'原候选等级':levels}
    assert len(records)==len(identities)==54
    def write(name,v): (out/name).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
    write('逐条映射.json',records);write('18组统计.json',groups)
    stable=sum(v['三轮均提出']==v['至少一轮提出'] for v in groups.values())
    status_equal=sum(len(set(v['状态']))==1 for v in groups.values())
    md=['# 同一材料三次重跑：任务结果与问题清单','',
        f'54 份返回来自 54 个不同的 Codex 会话。18 个“任务 × 材料”组合中，**{status_equal} 组的任务状态三轮相同，{stable} 组的候选问题集合三轮相同**。每条原答最多列三个候选。即使任务结果相同，也可能换掉其中一个问题。','',
        '按问题对象和现象对齐；一条意见明说了两个问题就分别记，换词、条目顺序和拆条不影响比较。下表分子为三次都提到的不同问题数，分母为三次合起来至少提到一次的不同问题数。该比例描述候选重复出现的程度，不评价正确率，也不等于逐判据的共同执行率。','',
        '| 任务 / 材料 | 三轮任务状态 | 原候选条数（第 1 / 2 / 3 轮） | 三轮均提 / 合并后共见 | 三轮均提的内容 |',
        '| --- | --- | --- | --- | --- |']
    for key,v in groups.items():
        s=v['状态']; label=s[0]+' × 3' if len(set(s))==1 else ' / '.join(s)
        md.append(f"| {key} {v['任务']} | {label} | {' / '.join(map(str,v['候选条数']))} | {len(v['三轮均提出'])} / {len(v['至少一轮提出'])} | {'；'.join(v['三轮均提出']) or '无'} |")
    md+=['','A：任务与画面；B：A 加需求；C：B 再加源码。网站三种条件共用相同的操作图。结果状态指给定证据能否支持该任务；采集时实际点击过的步骤和模型看图的次数分别记录。','',
         '[每组意见及严重度](18组统计.json) · [逐条编码与原件指纹](逐条映射.json) · [54 份模型原答](../模型原答)']
    (out/'三轮对照.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    print(len(records),len(groups),status_equal,stable)
if __name__=='__main__':main(Path(sys.argv[1]))
