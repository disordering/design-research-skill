"""在当前 Python 环境运行产品回归，并把实际退出码和逐项结果留给 D。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/D-三项修复证据/程序回归'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite', choices=['backend', 'frontend'])
    parser.add_argument('--extra-site', action='append', default=[], help='本地已安装的附加依赖目录')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PYTHONIOENCODING':'utf-8', 'PYTHONDONTWRITEBYTECODE':'1', 'NO_COLOR':'1'}
    if args.suite == 'backend':
        xml = OUT / '后端逐项.xml'
        # 使用本轮的新 XML；没有生成报告时不能把之前一次的文件当作结果。
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / 'pytest.xml'
            cmd = [sys.executable, '-c', 'import json,site,sys; [site.addsitedir(p) for p in json.loads(sys.argv.pop(1))]; import pytest; raise SystemExit(pytest.main(sys.argv[1:]))',
                   json.dumps([str(Path(p).resolve()) for p in args.extra_site]), '-q', 'tests', '--junitxml', str(result_path)]
            run = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True)
            (OUT/'后端运行.txt').write_bytes(run.stdout + run.stderr)
            if not result_path.is_file():
                raise SystemExit(run.returncode or 1)
            shutil.copyfile(result_path, xml)
        suite = ElementTree.parse(xml).find('testsuite')
        counts = {key:int(suite.attrib[key]) for key in ('tests','errors','failures','skipped')}
        counts['passed'] = counts['tests'] - counts['errors'] - counts['failures'] - counts['skipped']
        name, artifact = '后端', xml
    else:
        node = shutil.which('node')
        if not node:
            raise SystemExit('未找到 Node.js')
        files = sorted((ROOT/'frontend/tests').glob('*.test.mjs'))
        run = subprocess.run([node, '--test', '--test-reporter=tap', '--test-isolation=none', *map(str,files)],
                             cwd=ROOT/'frontend', env=env, capture_output=True)
        name, artifact = '前端', OUT/'前端逐项.txt'
        artifact.write_bytes(run.stdout + run.stderr)
        counts = {k:int(v) for k,v in re.findall(r'^# (tests|pass|fail|skipped|cancelled|todo) (\d+)\s*$', run.stdout.decode('utf-8'), re.M)}
        if 'pass' not in counts:
            raise SystemExit(run.returncode or 1)
    report = {'套件':name,'退出码':run.returncode,'计数':counts,'逐项文件':artifact.name,
              '逐项文件SHA256':hashlib.sha256(artifact.read_bytes()).hexdigest()}
    (OUT/(name+'汇总.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(report)
    raise SystemExit(run.returncode)


if __name__ == '__main__':
    main()
