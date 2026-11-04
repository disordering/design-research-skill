"""在指定引擎版本上重放 H05 首个模型动作，记录控件标签及实际选择。"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import site
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--extra-site', action='append', default=[])
    args = parser.parse_args()
    product = args.repo.resolve()
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(product), str(root/'tests')]
    for dep in args.extra_site:
        site.addsitedir(str(Path(dep).resolve()))
    from test_d_browser_labels import serve
    from engine.session_adapters import BrowserAdapter
    from engine.session_contracts import Action, SourceInput, SourceRecord
    from engine.errors import EngineError

    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit('请使用新的存档目录。')
    out.mkdir(parents=True)
    raw = (root/'docs/D-新版真人执行/03-匿名原始任务/C-H05/打开界面.html').read_bytes()
    async def run(url):
        browser = BrowserAdapter(allow_local=True)
        source = SourceRecord(input=SourceInput(kind='website', reference=url))
        try:
            initial = await browser.read('h05-label', source)
            (out/'操作前.png').write_bytes(initial.image)
            control = next(c for c in initial.controls if c['selector'] == '[data-review-control="1"]')
            action = Action(source_id=source.source_id, kind='click', selector=control['selector'],
                            target_label='周五14:00–14:30 二层服务台', expected_state_id=initial.state_id,
                            reason='重放实际模型第一次选择下午的动作', requires_explicit_authorization=False)
            error = ''
            try:
                after = await browser.act('h05-label', source, action, authorized=False)
            except EngineError as exc:
                error = exc.code + ': ' + exc.message
                after = await browser.capture('h05-label', source)
            (out/'操作后.png').write_bytes(after.image)
            selected = next(c for c in after.controls if c['type'] == 'radio' and c['checked'])
            result = {'输入页面SHA256': hashlib.sha256(raw).hexdigest(),
                      '适配器SHA256': hashlib.sha256((product/'engine/session_adapters.py').read_bytes()).hexdigest(),
                      '操作方式': 'AI程序重放已归档的实际模型动作', '原始控件': control,
                      '动作': action.model_dump(mode='json'), '执行错误': error,
                      '操作后选中项': selected, '选中下午': selected['selector'] == control['selector']}
            (out/'结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'控件标签': control['label'], '选中下午': result['选中下午'], '错误': error}, ensure_ascii=False))
        finally:
            await browser.close()
    with serve(raw) as url:
        asyncio.run(run(url))


if __name__ == '__main__':
    main()
