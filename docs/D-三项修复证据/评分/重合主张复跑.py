"""调换预测编号和顺序，检验同一主张的不同标题及部分重合。"""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root), str(root / "tests")]
from test_session_evaluation import atom, issue, labels, snapshot
from engine.session_evaluation import evaluate_session


def run():
    result = []
    for expanded in (False, True):
        for swap_ids in (False, True):
            for reverse in (False, True):
                i, j = ("P02", "P01") if swap_ids else ("P01", "P02")
                first = issue(i, "时段错误：下午显示为上午", atom("下午", "上午"))
                second = issue(j, "时段错误：下午显示为上午，无法核对", atom("下午", "上午"))
                refs = labels(("参考甲", "时段错误"), ("参考乙", "无法核对"))
                if expanded:
                    second.title += "；字体错：字号 16 显示为 12"
                    second.detection = second.title
                    second.claims.append(atom("字号 16", "12"))
                    refs = labels(("时段参考", "时段错误"))
                findings = [second, first] if reverse else [first, second]
                scores = evaluate_session(snapshot(findings), refs)
                result.append({"补充未匹配字号主张": expanded, "交换编号": swap_ids, "逆序输入": reverse,
                               "指标": scores["finding_metrics"], "映射": scores["matches"],
                               "重复": scores["duplicates"], "部分重合": scores.get("overlap_pending", [])})
    return result


if __name__ == "__main__":
    with Path(sys.argv[1]).open("x", encoding="utf-8") as output:
        json.dump(run(), output, ensure_ascii=False, indent=2)
