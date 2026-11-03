"""在隔离的浏览器上下文中验证四个样本的主要路径，写入实际观察及材料指纹。"""
import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright
from serve import CASES, ROOT, make_server


def click(page, label):
    page.get_by_role('button', name=label, exact=True).click()


def observation(page, target, expected, steps):
    expect(target).to_contain_text(expected)
    steps.append({'页面': page.locator('h1').inner_text(), '观察': target.inner_text()})


def room(page, steps):
    page.get_by_label('参与人数').fill('7')
    click(page, '核对预约')
    observation(page, page.get_by_role('alert'), '请输入 1 至 6 人', steps)
    page.get_by_label('参与人数').fill('4')
    click(page, '核对预约')
    click(page, '确认预约')
    observation(page, page.get_by_role('alert'), '此时段刚被预约', steps)
    click(page, '返回选择')
    expect(page.get_by_label('参与人数')).to_have_value('4')
    expect(page.get_by_label('使用时段')).to_have_value('16:00–17:00')
    click(page, '核对预约')
    observation(page, page.locator('.card'), '4 人', steps)
    click(page, '确认预约')
    observation(page, page.get_by_role('status'), 'R-204', steps)


def print_shop(page, steps):
    page.get_by_label('原稿页数').fill('13')
    page.get_by_label('份数').fill('2')
    page.get_by_label('取件方式').select_option('校内配送')
    click(page, '查看报价')
    observation(page, page.get_by_role('alert'), '请填写配送楼栋', steps)
    page.get_by_label('配送楼栋').fill('六号楼')
    click(page, '查看报价')
    observation(page, page.locator('.card'), '合计 ¥5.80', steps)
    click(page, '返回修改')
    expect(page.get_by_label('配送楼栋')).to_have_value('六号楼')
    page.get_by_label('取件方式').select_option('到店自取')
    click(page, '查看报价')
    observation(page, page.locator('.card'), '合计 ¥2.80', steps)
    click(page, '提交打印单')
    observation(page, page.get_by_role('status'), 'P-106', steps)


def repair(page, steps):
    click(page, '核对工单')
    observation(page, page.get_by_role('alert'), '请填写房间号和故障描述', steps)
    page.get_by_label('房间号').fill('R-204')
    page.get_by_label('故障描述').fill('接通电源后没有画面')
    click(page, '保存草稿')
    observation(page, page.get_by_role('status'), '草稿已保存', steps)
    page.reload()
    expect(page.get_by_label('房间号')).to_have_value('R-204')
    click(page, '核对工单')
    click(page, '返回编辑')
    expect(page.get_by_label('故障描述')).to_have_value('接通电源后没有画面')
    click(page, '核对工单')
    click(page, '提交工单')
    observation(page, page.get_by_role('alert'), '网络暂不可用', steps)
    click(page, '重新提交')
    observation(page, page.get_by_role('status'), 'M-318', steps)
    page.reload()
    observation(page, page.get_by_role('status'), 'M-318', steps)


def workshop(page, steps):
    click(page, '查看陶艺体验')
    click(page, '报名参加')
    observation(page, page.get_by_role('alert'), '本场已满', steps)
    click(page, '返回活动')
    click(page, '查看篆刻入门')
    click(page, '报名参加')
    observation(page, page.locator('.card'), '已报名', steps)
    click(page, '取消报名')
    click(page, '保留报名')
    observation(page, page.locator('.card'), 'A-071', steps)
    click(page, '返回活动')
    page.reload()
    observation(page, page.locator('.card').filter(has_text='篆刻入门'), '余位 1', steps)
    click(page, '我的报名')
    click(page, '取消报名')
    click(page, '确认取消')
    observation(page, page.locator('.card').filter(has_text='篆刻入门'), '余位 2', steps)
    expect(page.get_by_role('button', name='我的报名')).to_have_count(0)


def material_hashes():
    inputs = [ROOT / 'public', ROOT / 'requirements']
    inputs = [file for folder in inputs for file in folder.rglob('*') if file.is_file()]
    inputs += [ROOT / 'cases.json', ROOT / 'serve.py', ROOT / 'smoke.py']
    return {file.relative_to(ROOT).as_posix():
            hashlib.sha256(file.read_text(encoding='utf-8').encode('utf-8')).hexdigest()
            for file in sorted(inputs)}


def main():
    results = []
    headings = ['预约讨论室', '设置打印单', '填写工单', '周末活动']
    with make_server(quiet=True) as server, sync_playwright() as pw:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        browser = pw.chromium.launch(headless=True)
        try:
            for case, test, heading in zip(CASES, [room, print_shop, repair, workshop], headings):
                context = browser.new_context(locale='zh-CN', viewport={'width': 1280, 'height': 800})
                try:
                    page = context.new_page()
                    steps, errors = [], []
                    page.on('pageerror', lambda err: errors.append(str(err)))
                    entry = f'http://127.0.0.1:{server.server_port}/{case}/'
                    page.goto(entry)
                    expect(page.locator('h1')).to_have_text(heading)
                    test(page, steps)
                    page.goto(entry + '?reset=1')
                    expect(page.locator('h1')).to_have_text(heading)
                    expect(page).to_have_url(entry)
                    if case == 'w01':
                        expect(page.get_by_label('使用时段')).to_have_value('15:00–16:00')
                    if case == 'w02':
                        expect(page.get_by_label('原稿页数')).to_have_value('12')
                    if case == 'w03':
                        expect(page.get_by_label('房间号')).to_have_value('')
                    if case == 'w04':
                        expect(page.get_by_role('button', name='我的报名')).to_have_count(0)
                    assert not errors, errors
                    for private in ('/requirements/w01.md', '/smoke.py', '/cases.json', '/smoke-results.json'):
                        assert context.request.get(entry.split(f'/{case}/')[0] + private).status == 404
                    results.append({'任务': case.upper(), '状态': '通过', '观察步骤': steps,
                                    '复位': heading, '页面脚本错误': errors})
                finally:
                    context.close()
            record = {'材料版本': 'D-WEB-1.0', '执行时间': datetime.now(timezone.utc).isoformat(),
                      '浏览器': 'Chromium ' + browser.version, 'Playwright': version('playwright'),
                      '环境': '每站独立上下文，1280×800，zh-CN，本机 HTTP 临时端口',
                      '结果': results, '材料指纹_SHA256_UTF8_LF': material_hashes()}
            output = ROOT / 'smoke-results.json'
            output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print('4/4 browser workflows passed: ' + str(output))
        finally:
            browser.close()
            server.shutdown()
            thread.join()


if __name__ == '__main__':
    main()
