"""沿用已冻结的 12 轮交叉次序、原页面、操作与浏览器设置，另验收问题补记。"""
import argparse
import importlib.util
import json
from pathlib import Path
from playwright.sync_api import expect

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
original = REPO / 'docs/D-续测证据/模拟评审/两种方式走查.py'
spec = importlib.util.spec_from_file_location('d_rounds', original)
rounds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rounds)


def download(page, path):
    with page.expect_download() as result:
        page.locator('#export').click()
    result.value.save_as(path)
    return path.read_text('utf-8-sig')


def check_workbench(page, origin, task, image, observed, out):
    page.goto(origin)
    page.locator('#imageInput').set_input_files(str(image))
    expect(page.locator('#preview')).to_be_visible()
    page.locator('#name').fill(f'AI 任务{task} · {out.name}')
    page.locator('#audience').fill('首次办理登记的使用者')
    page.locator('#goal').fill('选择下午的' + rounds.TARGETS[task] + '，返回核对所选时段及地点，提交后核对回执。')
    page.locator('#intent').fill('选择时并列显示时段和地点，返回时保留选择，回执反映最终确认的信息。')
    page.locator('#form button[type=submit]').click()
    expect(page.locator('#version')).to_contain_text('v1')
    for finding_id,decision,reason in [
        ('issue-01','驳回','选择页只有一个实心“核对信息”主按钮。'),
        ('issue-02','驳回','这个页面是时段单选，两项都直接显示时间和地点。'),
        ('issue-03','待验证','本轮核对选项、返回和回执，未测等待过程。'),
    ]:
        card=page.locator(f'article[data-id="{finding_id}"]')
        card.get_by_role('button',name=decision,exact=True).click()
        card.locator('textarea').fill(reason)
        card.locator('textarea').press('Tab')

    observation=observed['工作备注']
    page.locator('#feedback').fill(observation)
    # 从本轮实际提交/返回的结果判断是否出现问题，正常 A 只走普通反馈。
    failed_return=not observed['检查结果']['R2返回保留']
    failed_receipt=not observed['检查结果']['R3回执匹配']
    finding=failed_return or failed_receipt
    title='返回核对后重置为上午工坊' if failed_return else '下午修书登记回执显示上午地点'
    severity='medium' if failed_return else 'high'
    level='中' if failed_return else '高'
    step='选择下午 → 核对信息 → 返回选择。' if failed_return else '选下午 → 核对时段与地点 → 提交登记 → 查看完成页。'
    if finding:
        page.locator('#feedbackToFinding' if task=='C' else '#addFinding').click()
        form=page.locator('#findingForm')
        expect(form.locator('[name=steps]')).to_have_value(observation)
        form.locator('[name=title]').fill(title)
        form.locator('[name=steps]').fill(step)
        form.locator('[name=evidence]').fill(observation)
        form.locator('[name=severity]').select_option(severity)
        form.locator('[name=authorType]').select_option('ai_simulation')
        form.get_by_role('button',name='保存到问题列表').click()
        card=page.locator('article').filter(has=page.get_by_role('heading',name=title,exact=True))
        expect(card).to_contain_text('AI 模拟补记')
        expect(card).to_contain_text(observation)
        stable_id=card.get_attribute('data-id')
        page.screenshot(path=out/'03-补记问题卡.png')
    initial=download(page,out/'v1-保存后.md')
    page.locator('#revise').click()
    expect(page.locator('#version')).to_contain_text('v2')
    cards=page.locator('#issues article')
    expect(cards).to_have_count(4 if finding else 3)
    report=download(page,out/'工作台原始导出.md')
    main,sep,log=report.partition('## 操作记录')
    assert sep and observation in log
    assert all(s in main for s in ['人工审核：rejected','人工审核：verify'])
    if finding:
        assert all(s in doc.partition('## 本轮提交上下文')[0] for doc in (initial,report)
                   for s in ['## '+title,observation,step,'记录来源：AI 模拟补记','严重度：'+level,'首次记录版本：v1'])
        expect(page.locator('article[data-id="'+stable_id+'"]')).to_contain_text(observation)
        assert main.count('## '+title)==1
        page.locator('article[data-id="'+stable_id+'"] textarea[data-note]').fill('本次重评已复看原始步骤。')
        page.locator('article[data-id="'+stable_id+'"] textarea[data-note]').press('Tab')
    else:
        assert 'AI 模拟补记' not in main and observation not in main
    page.reload()
    for version in [1,2]:
        page.locator('#history .history-item').filter(has_text=f'v{version}').click()
        expect(page.locator('#version')).to_contain_text(f'v{version}')
        expect(cards).to_have_count(4 if finding else 3)
        if finding:
            same=page.locator('article[data-id="'+stable_id+'"]')
            expect(same).to_contain_text(observation)
            expect(same).to_contain_text('AI 模拟补记')
            expect(same.locator('select[data-severity]')).to_have_value(severity)
            expect(same.locator('textarea[data-note]')).to_have_value('' if version==1 else '本次重评已复看原始步骤。')
    restored=download(page,out/'刷新后从历史导出.md')
    assert ('## '+title in restored)==finding
    if finding:
        assert all(value in restored for value in ['记录来源：AI 模拟补记','严重度：'+level,step,observation])
    recheck=False
    if task=='C':
        # 换成当轮完成页验证旧截图的证据归属。
        page.locator('#recheckInput').set_input_files(str(out/'02-完成.png'))
        page.locator('#recheck').click()
        expect(page.locator('#version')).to_contain_text('v3')
        expect(cards).to_have_count(3)
        rechecks=page.locator('#recheckResults form').filter(has_text=title)
        expect(rechecks).to_contain_text(observation)
        expect(rechecks.locator('select[name=resolution]')).to_have_value('unable_to_determine')
        revised=download(page,out/'v3-换图复审.md')
        now,sep,previous=revised.partition('## 逐问题复审结果')
        assert sep and '## '+title not in now and title in previous and '原版本证据：'+observation in previous
        recheck=True
    raw={'是否有实际问题':finding,'自由反馈进入日志':observation in log,'实际发现进入正文':observation in main,
         '首版重开和新版重开':True,'同图重评保留补记':True if finding else None,'记录来源':'AI 模拟补记' if finding else None,
         '原步骤':step if finding else None,'依据':observation,'原等级':level if finding else None,'补记编号':stable_id if finding else None,
         '不同截图待核且保留原证据':recheck if task=='C' else None,'审核状态读回':True,
         '修复前原料哈希一致':observed['材料哈希']==json.loads((HERE/'修前'/out.name/'网页走查.json').read_text('utf-8'))['材料哈希']}
    assert raw['修复前原料哈希一致']
    rounds.write_json(out/'工作台核对.json',raw)
    return raw


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    rounds.check_workbench=check_workbench
    rounds.main(args.out)
