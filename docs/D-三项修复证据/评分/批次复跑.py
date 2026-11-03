"""取上轮七项原始预测和参考，按项目正常输入结构评估整批，保留原始材料指纹。"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

here = Path(__file__).resolve().parent
repo = here.parents[2]
sys.path.insert(0, str(repo))

from engine.session_contracts import Finding, SessionCreate
from engine.session_evaluation import BatchEvaluationInput, evaluate_batch
from engine.session_service import SessionService
from engine.session_store import SessionStore


def main(output):
    source = repo / 'docs/D-续测证据/方法验收/评分器实际输出.json'
    data = source.read_bytes()
    cases = []
    snapshots = {}
    with tempfile.TemporaryDirectory() as directory:
        service = SessionService(SessionStore(Path(directory)))
        for row in json.loads(data):
            session = service.create(SessionCreate(
                purpose='复核课程样本计数',
                sources=[{'kind': 'document', 'content': '核对回执时段和地点'}],
            ))
            session.findings = [Finding(
                **item, run_id=session.run_id, check_ids=['R18'], evidence_ids=['e1'],
                principle='选择应保留', description='当前选择与提交内容应一致',
                suggestion='从已选记录读取时段及地点', severity_reason='影响提交结果',
            ) for item in row['预测']]
            service.store.save(session)
            snapshots[session.session_id] = service.store.get(session.session_id)
            cases.append({'session_id': session.session_id,
                          'labels': {'dataset': row['场景'], 'findings': row['参考']}})
        result = evaluate_batch(snapshots, BatchEvaluationInput(dataset='D-七项联合对照', cases=cases))
    with output.open('x', encoding='utf-8') as target:
        json.dump({'冻结原件SHA256': hashlib.sha256(data).hexdigest(), '批次结果': result},
                  target, ensure_ascii=False, indent=2)
    print(result['aggregate'])


if __name__ == '__main__':
    main(Path(sys.argv[1]))
