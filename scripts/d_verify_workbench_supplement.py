"""复跑 H04/H05，再走旧工作台的补记、重评、修改稿和导出。"""
import hashlib
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
import socket
import sys
import threading
import time

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.api import create_app
from engine.criteria import CriteriaLibrary
from engine.service import ReviewEngine
from engine.stub import StubModel

OUT = ROOT / 'docs/D-本轮续测证据/工作台补记'
SOURCE = ROOT / 'docs/D-新版真人执行/03-匿名原始任务'


def export(page, dest):
    with page.expect_download() as pending:
        page.locator('#export').click()
    pending.value.save_as(dest)
    return dest.read_text('utf-8-sig')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    criteria = CriteriaLibrary.load(ROOT/'判据库_v1.json')
    def fixed_model(provider, model):
        return ReviewEngine(criteria, StubModel(), provider='stub', model_name='contract-stub-v1', is_stub=True)
    app = FastAPI()
    app.mount('/engine', create_app(engine_factory=fixed_model))
    app.mount('/', StaticFiles(directory=ROOT/'frontend/dist', html=True))
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False))
    results = []
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        address = f'http://127.0.0.1:{sock.getsockname()[1]}/'
        worker = threading.Thread(target=server.run, kwargs={'sockets':[sock]}, daemon=True)
        worker.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(.05)
            assert server.started
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                for task, folder in [('H04','B-H04'), ('H05','C-H05')]:
                    dest = OUT/task
                    dest.mkdir(exist_ok=True)
                    source = SOURCE/folder/'打开界面.html'
                    context = browser.new_context(locale='zh-CN', viewport={'width':1440,'height':1000}, accept_downloads=True)
                    page = context.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(source.as_uri())
                    page.get_by_role('radio').nth(1).check()
                    page.get_by_role('button', name='核对信息', exact=True).click()
                    before = page.locator('dd').all_text_contents()
                    page.screenshot(path=str(dest/'01-原题核对.png'))
                    page.get_by_role('button', name='返回选择', exact=True).click()
                    retained = page.get_by_role('radio').nth(1).is_checked()
                    if task=='H04':
                        assert not retained
                        page.screenshot(path=str(dest/'02-原题返回.png'))
                        page.get_by_role('button', name='核对信息', exact=True).click()
                        actual = page.locator('dd').all_text_contents()
                        title = '织物工具借用返回选择后丢失下午时段'
                        steps = '选择下午东侧工坊，核对信息，返回选择，再次核对。'
                        evidence = '返回前：'+'／'.join(before)+'；返回后：'+'／'.join(actual)
                    else:
                        assert retained
                        page.get_by_role('button', name='核对信息', exact=True).click()
                        page.get_by_role('button', name='提交登记', exact=True).click()
                        actual = page.locator('dd').all_text_contents()
                        title = '修书登记回执的时段和地点与提交前不符'
                        steps = '选择下午二层服务台，核对并返回选择，再核对并提交登记。'
                        evidence = '提交前：'+'／'.join(before)+'；回执：'+'／'.join(actual)
                    assert before!=actual
                    image = dest/'03-原题结果.png'
                    page.screenshot(path=str(image))
                    page.goto(address)
                    expect(page.locator('#sourceUrl')).to_be_visible()
                    page.locator('#operatorType').select_option('ai_simulation')
                    page.locator('#sourceUrl').fill('https://example.com/'+task)
                    page.locator('#addSource').click()
                    page.locator('#mode').select_option('engine')
                    page.locator('#imageInput').set_input_files(str(image))
                    expect(page.locator('#preview')).to_be_visible()
                    page.locator('#name').fill(task+' 工作台补记复测')
                    page.locator('#audience').fill('登记服务使用者')
                    page.locator('#goal').fill('按所选下午时段完成登记，并核对返回与回执信息。')
                    requests = []
                    def call(button):
                        with page.expect_response(lambda r:r.url.endswith('/engine/api/review-audit') and r.request.method=='POST') as response:
                            button.click()
                        raw = response.value.json()
                        assert response.value.status==200
                        assert raw['model']['is_stub']
                        assert all(f['title']!=title for f in raw['findings'])
                        (dest/f'接口-{len(requests)+1}.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                        expect(page.locator('#status')).to_contain_text('已完成')
                        requests.append({'状态码':200,'模型':raw['model']['model'],'原生补记数':0,'引擎ID':raw['review_id']})
                    call(page.locator('#form button[type=submit]'))
                    # 确认 C 最新的材料登记与审核理由要求仍然有效。
                    expect(page.locator('#sessionPanel')).to_contain_text('1 个链接')
                    page.locator('#addFinding').click()
                    expect(page.locator('#findingDialog')).to_be_visible()
                    page.locator('#cancelFinding').click()
                    page.locator('#feedback').fill(steps)
                    initial_version = 1
                    if task=='H05':
                        # 普通反馈不会生成问题，历史反馈须再次明确保存才进入正文。
                        call(page.locator('#revise'))
                        initial_version = 2
                        plain = export(page,dest/'v2-普通反馈.md')
                        assert '## '+title not in plain
                        page.locator('details').filter(has=page.locator('#logs')).locator('summary').click()
                        page.locator('#logs [data-feedback-log]').first.click()
                    else:
                        page.locator('#feedbackToFinding').click()
                    form = page.locator('#findingForm')
                    expect(form.locator('[name=steps]')).to_have_value(steps)
                    expect(form.locator('[name=authorType]')).to_have_value('ai_simulation')
                    form.locator('[name=title]').fill(title)
                    form.locator('[name=evidence]').fill(evidence)
                    form.locator('[name=severity]').select_option('high')
                    form.get_by_role('button',name='保存到问题列表').click()
                    card = page.locator('article').filter(has=page.get_by_role('heading',name=title,exact=True))
                    expect(card).to_contain_text(evidence)
                    finding_id = card.get_attribute('data-id')
                    card.get_by_role('button',name='确认问题',exact=True).click()
                    expect(page.locator('#status')).to_contain_text('请先填写审核理由')
                    expect(card.get_by_role('button',name='确认问题',exact=True)).to_have_attribute('aria-pressed','false')
                    note = 'AI 浏览器逐步操作，已核对前后两个画面的时段和地点。'
                    card.locator('[data-note]').fill(note)
                    card.get_by_role('button',name='确认问题',exact=True).click()
                    expect(card.get_by_role('button',name='确认问题',exact=True)).to_have_attribute('aria-pressed','true')
                    page.locator('#feedback').fill('复看同一张图，保留原观察记录。')
                    call(page.locator('#revise'))
                    version = initial_version+1
                    expect(page.locator('#version')).to_contain_text('v'+str(version))
                    card = page.locator('article[data-id="'+finding_id+'"]')
                    expect(card).to_contain_text(evidence)
                    expect(card.locator('[data-note]')).to_have_value(note)
                    expect(card.get_by_role('button',name='确认问题',exact=True)).to_have_attribute('aria-pressed','true')
                    current = export(page,dest/f'v{version}-同图重评.md')
                    body = current.split('## 本轮提交上下文')[0]
                    assert body.count('## '+title)==1
                    assert all(text in body for text in [evidence, note, '来源：AI 模拟补记', f'首次记录版本：v{initial_version}', '严重度：高'])
                    assert '"actor_type":"human"' not in current
                    assert '"actor_type":"ai_simulation"' in current
                    assert all(text not in current for text in ['人工反馈','人工意见','人工审核','人工对照'])
                    assert '评审反馈' in current and '评审意见' in current
                    page.screenshot(path=str(dest/'04-同图补记.png'),full_page=True)
                    # 刷新恢复和重新上传相同文件分别覆盖保存与换图边界。
                    page.reload()
                    page.locator('#history button').first.click()
                    expect(page.locator('article[data-id="'+finding_id+'"]')).to_contain_text(evidence)
                    page.locator('#operatorType').select_option('ai_simulation')
                    page.locator('#recheckInput').set_input_files(str(image))
                    call(page.locator('#recheck'))
                    expect(page.locator('article[data-id="'+finding_id+'"]')).to_have_count(0)
                    item = page.locator('[data-recheck-index]').filter(has=page.get_by_role('heading',name=title,exact=False))
                    expect(item).to_contain_text(evidence)
                    expect(item.locator('[name=resolution]')).to_have_value('unable_to_determine')
                    changed = export(page,dest/f'v{version+1}-修改稿待核对.md')
                    assert '## '+title not in changed.split('## 本轮提交上下文')[0]
                    assert '原版本证据：'+evidence in changed
                    assert '结果：无法判断' in changed
                    page.screenshot(path=str(dest/'05-换图待核对.png'),full_page=True)
                    assert not errors, errors
                    results.append({'任务':task,'执行来源':'AI 浏览器自动走查','原题SHA256':hashlib.sha256(source.read_bytes()).hexdigest(),
                        '返回前或提交前':before,'实际结果':actual,'返回保留下午选择':retained,'补记标题':title,'补记编号':finding_id,
                        '首次补记版本':initial_version,'同图保留补记与理由':True,'刷新恢复成功':True,'换图原证据仅留在历史与复审表':True,
                        '换图结论':'无法判断','导出正文补记次数':1,'审核理由校验保留':True,'C材料登记保留':True,
                        '普通反馈未自动成问题':True,'确认事件来源':'ai_simulation','请求':requests,'浏览器错误':errors})
                    context.close()
                browser.close()
        finally:
            server.should_exit=True
            worker.join(8)
    (OUT/'核对结果.json').write_text(json.dumps({'执行时间':datetime.now(timezone.utc).isoformat(),
        '方式':'Chromium 实际操作冻结 H04/H05 页面，使用截图与操作证据在旧工作台补记；真实 HTTP 请求进入本机产品 FastAPI，模型使用固定 stub 响应。',
        '范围':'验证补记、明确转问题、同图保留、换图待核对与导出，不计为模型准确率或真人实验。','任务结果':results},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('H04/H05 通过：补记与理由同图保留，换图进入待核对，导出准确记录 AI 来源。')


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT, help='本轮证据输出目录')
    OUT = parser.parse_args().output.resolve()
    main()
