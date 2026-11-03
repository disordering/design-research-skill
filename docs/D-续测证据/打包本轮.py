"""生成本轮只读交接件，保留仓库相对目录，校验 ZIP 字节。"""
import json,re,sys
from hashlib import sha256
from pathlib import Path
from urllib.parse import unquote
from zipfile import ZipFile, ZIP_DEFLATED
from 校验归档 import main as verify

base=Path(__file__).resolve().parent;repo=base.parents[1]
def package(target):
    old=sys.argv;sys.argv=[old[0]]
    try:verify()
    finally:sys.argv=old
    files=set()
    def add(p):
        p=p.resolve()
        if p.is_file() and p.is_relative_to(repo) and '__pycache__' not in p.parts:files.add(p)
    for p in base.rglob('*'):add(p)
    for folder in ['fixtures/d-v02-sites','fixtures/d-v02-batch','fixtures/d-v02-static','docs/D-护法复核证据','docs/D-复核证据',
                   'docs/D-新版真人执行/03-匿名原始任务','docs/D-新版真人执行/04-次批匿名任务']:
        for p in (repo/folder).rglob('*'):add(p)
    for n in ['D-内部测试收尾.md','D-案例复核表.md','D-护法其余五项复核.md','D-吴山石案例复核.md','D-Flex退出复核.md',
              'D-新版真人执行/01-评审者/独立评审记录.html','D-新版真人执行/02-体验者/两轮任务体验记录.html']:
        add(repo/'docs'/n)
    for ls in json.loads((base/'批次/材料索引.json').read_bytes())['任务'].values():
        for src in ls:
            p=repo/src['文件'];assert sha256(p.read_bytes()).hexdigest()==src['SHA256'];add(p)
    # 纳入核心报告的直接依据；源码复跑按相同版本仓库恢复。
    for md in list(files):
        if md.suffix!='.md': continue
        for raw in re.findall(r'\[[^\]]*\]\(([^)]+)\)',md.read_text('utf-8-sig')):
            t=unquote(raw.split('#',1)[0].strip('<>'))
            if t and not re.match(r'^\w+:|^/',t):add(md.parent/t)
    readme='''本轮 D 内部测试交接件

从 docs/D-内部测试收尾.md 开始。原始运行、截图、AI 判读及产品报告包放在 docs/D-续测证据 下。
48 张 Codex 批次输入图均已逐一核验。包内使用原有仓库相对目录，可和组内代码对照。
这是本轮材料和结果的离线副本。运行程序时，请使用原项目工作区、相同环境及本地测试脚本。
'''
    with ZipFile(target,'x',compression=ZIP_DEFLATED) as z:
        z.writestr('先读我.txt',readme.encode('utf-8-sig'))
        for p in sorted(files):z.write(p,p.relative_to(repo).as_posix())
    with ZipFile(target) as z:
        assert z.testzip() is None
        for p in files:assert sha256(z.read(p.relative_to(repo).as_posix())).digest()==sha256(p.read_bytes()).digest()
    print(f'{len(files)+1} files, {target.stat().st_size} bytes')
if __name__=='__main__':package(Path(sys.argv[1]))
