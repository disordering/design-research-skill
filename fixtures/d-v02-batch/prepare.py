"""为开发回归生成独立的引擎请求，只读取事先登记的无答案材料。"""
import argparse
import base64
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WEB = HERE.parent / 'd-v02-sites'
STATIC = HERE.parent / 'd-v02-static'
GROUP_BOARD = 'https://www.figma.com/design/j9Z5Y839AREXf0OPysbbJ7/?node-id='
SHARED = ['public/index.html', 'public/common.js', 'public/style.css']
sys.path.insert(0, str(REPO))
from engine.session_contracts import SessionCreate


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def json_bytes(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def source(title, kind, **values):
    return {'title': title, 'kind': kind, **values}


def make_sources(task, condition, web_tasks):
    kind = task['kind']
    if kind == 'image':
        pixels = (STATIC / task['file']).read_bytes()
        return task['purpose'], [source(task['title'], 'image', role='design',
                version=sha(pixels), image_base64=base64.b64encode(pixels).decode('ascii'))]
    if kind == 'figma_board':
        return task['purpose'], [source(f"{task['title']} · 原稿 {i}", kind, role='design',
                reference=GROUP_BOARD + node) for i, node in enumerate(task['nodes'], start=1)]
    if kind == 'figma_prototype':
        return task['purpose'], [source(task['title'], kind, role='design', reference=task['url'])]

    site_id = task['seed']
    seed = web_tasks[site_id]
    case = site_id.lower()
    if seed['url_path'] != f'/{case}/':
        raise ValueError('网站入口与任务编号不匹配')
    sources = [source(site_id + ' 校园服务', 'website', version='D-WEB-1.0',
                      reference='http://127.0.0.1:4311' + seed['url_path'])]
    if condition in ('B', 'C'):
        path = f'requirements/{case}.md'
        if seed['requirements'] != path:
            raise ValueError('需求来源与任务编号不匹配')
        sources.append(source('服务要求 1.0', 'document', role='product_spec',
                              evidence_kind='requirement', version='D-WEB-1.0',
                              content=(WEB / path).read_text(encoding='utf-8')))
    if condition == 'C':
        path = f'public/{case}/app.js'
        if seed['entry_script'] != path:
            raise ValueError('工程入口与任务编号不匹配')
        for filename in [path, *SHARED]:
            sources.append(source(filename, 'document', role='implementation',
                                  evidence_kind='implementation', version='D-WEB-1.0',
                                  content=(WEB / filename).read_text(encoding='utf-8')))
    return seed['purpose'], sources


def assemble(profile):
    spec = json.loads((HERE / 'tasks.json').read_text(encoding='utf-8'))
    web = json.loads((WEB / 'cases.json').read_text(encoding='utf-8'))
    assert web['common_files_for_C'] == SHARED
    seeds = {row['id']: row for row in web['cases']}
    assert list(seeds) == ['W01', 'W02', 'W03', 'W04']
    assert [row['id'] for row in spec['tasks']] == [f'T{i:02d}' for i in range(1, 11)]
    matrix = {}
    ledger = []
    for task in spec['tasks']:
        previous = []
        for condition in ('ABC' if task['kind'] == 'website' else 'A'):
            purpose, sources = make_sources(task, condition, seeds)
            if previous:
                assert sources[:len(previous)] == previous
            previous = sources
            assert len(sources) == ({'A': 1, 'B': 2, 'C': 6}[condition]
                                     if task['kind'] == 'website' else len(task.get('nodes', [1])))
            body = {'purpose': purpose, 'sources': sources, **profile, 'limits': spec['limits'],
                    'allow_interaction': task['kind'] in ('website', 'figma_prototype'),
                    'auto_run': False, 'require_structured_claims': True}
            SessionCreate.model_validate(body)
            digest = sha(json_bytes(body))
            for repeat in (1, 2, 3):
                slot = f"{task['id']}-{condition}-{repeat:02d}"
                matrix[slot] = body
                ledger.append({'slot':slot, 'task':task['id'], 'kind':task['kind'],
                               'condition':condition, 'repeat':repeat, 'status':'待运行',
                               'primary':repeat==1, 'session_id':None, 'request_sha256':digest})
    assert len(matrix) == len(ledger) == 54
    assert Counter(r['condition'] for r in ledger) == {'A':30, 'B':12, 'C':12}
    assert sum(row['primary'] for row in ledger) == 18
    for slot, body in matrix.items():
        reparsed = SessionCreate.model_validate_json(json_bytes(body))
        assert reparsed.auto_run is False, slot
    return spec, matrix, ledger


def inputs():
    paths = [HERE/'tasks.json', WEB/'cases.json', *(STATIC/f'T0{i}.png' for i in (1, 2))]
    paths.extend(WEB / filename for filename in SHARED)
    for i in range(1, 5):
        paths.extend([WEB/f'requirements/w0{i}.md', WEB/f'public/w0{i}/app.js'])
    return {file.relative_to(REPO).as_posix():
            sha(file.read_bytes() if file.suffix=='.png' else file.read_text(encoding='utf-8').encode())
            for file in paths}


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=['qwen', 'deepseek', 'generic', 'local'], required=True)
    parser.add_argument('--model', required=True, help='同一批次固定的实际模型名')
    parser.add_argument('--output', type=Path, help='新的或空的独立目录，省略则只校验')
    args = parser.parse_args()
    model = args.model.strip()
    if not model:
        parser.error('模型名不能为空')
    profile = {'provider': args.provider, 'model_name': model}
    spec, matrix, ledger = assemble(profile)
    fingerprints = inputs()
    expected = json.loads((HERE/'frozen-inputs.json').read_text(encoding='utf-8'))
    if fingerprints != expected:
        raise ValueError('输入版本已改变。创建新版批次并重新冻结材料。')
    if args.output:
        output = args.output.resolve()
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise ValueError('输出目录已有文件，请选择空目录，保留已有批次记录。')
        requests = output / 'requests'
        requests.mkdir(parents=True)
        for slot, body in matrix.items():
            write_json(requests/f'{slot}.json', body)
        write_json(output/'slots.json', ledger)
        write_json(output/'batch.json', {'version':spec['version'], 'profile':profile,
                   'limits':spec['limits'], 'inputs':fingerprints, 'model_calls':0, 'sessions_created':0})
    print('54 个请求通过 SessionCreate 校验。A 30，B 12，C 12。正式会话 0。')


if __name__ == '__main__':
    main()
