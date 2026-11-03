"""六个独立上下文分别试读同一顺序槽内的两份工作产物。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def grade(pair, runs, target):
    target.mkdir()
    inputs = []
    for round in pair:
        folder = runs / round["编号"]
        raw = read(folder / "网页走查.json")
        data = {"轮次": round["编号"], "阅读顺序": len(inputs)+1, "方式": round["方式"],
                "原始任务卡": raw["任务卡"], "逐步界面观察": raw["各步"]}
        if round["方式"] == "工作台模拟模式":
            data["交付物"] = (folder/"工作台原始导出.md").read_text(encoding="utf-8-sig")
        else:
            data["交付物"] = {"检查结果": raw["检查结果"], "走查记录": raw["工作备注"],
                             "可引用证据": "本文件保留逐步观察，另存01-选择.png、02-完成.png两张图。"}
        inputs.append(data)
    prompt = """你是内部试读者，以AI身份阅读下列相邻两轮的两份产物。只凭给出的交付内容和原始可见观察判断，不能使用工具，也无须扮演真人或编写个人感受。
请分别实际完成两项试读任务：先从交付物找出该题的核心结论，再定位到支持或反驳结论的那次界面观察。
接着对本次试读的三个方面各给1–5分，并写一句对应证据。评分办法：5=在报告主体直接读出，4=阅读一个标明的附件或步骤后可得，3=需跨段落或在日志中追踪，2=需从散落信息重新推断，1=找不到，null=材料未展示。三个方面分别是理解结论、找到证据、取回已保存的结论。第三项只评交付文件里能否找回，不评写入前操作难度。
每轮仅交一个对象。仅输出JSON {"rounds":[{"id":"与轮次相同","finding":"读到的重要结论","anchor":"找到的证据位置","understand":{"score":数字或null,"basis":"依据"},"locate":{"score":数字或null,"basis":"依据"},"retrieve":{"score":数字或null,"basis":"依据"}}]}。材料：""" + json.dumps(inputs, ensure_ascii=False)
    (target/"试读输入.txt").write_text(prompt,encoding="utf-8")
    with TemporaryDirectory(prefix="d-output-review-") as tmp:
        cli = os.environ.get("CODEX_APP_RUNTIME_CLI_PATH") or shutil.which("codex.cmd")
        args = [cli, "exec","--ignore-user-config","--ephemeral","--skip-git-repo-check","--sandbox","read-only",
                "-m","gpt-6-astra","-c","model_reasoning_effort=low","--json","-"]
        start = datetime.now(timezone.utc).isoformat()
        p = subprocess.run(args, cwd=tmp, input=prompt.encode("utf-8"),capture_output=True,timeout=300)
        (target/"会话.jsonl").write_bytes(p.stdout)
        p.check_returncode()
    events = [json.loads(x) for x in p.stdout.decode("utf-8").splitlines() if x.strip().startswith("{")]
    items = [e["item"] for e in events if e.get("type") == "item.completed"]
    assert all(i["type"] in ("agent_message","reasoning") for i in items)
    txt = [i["text"] for i in items if i["type"]=="agent_message"][-1].strip()
    if txt.startswith("```"):
        txt = txt.split("\n",1)[1].rsplit("```",1)[0]
    results = json.loads(txt)["rounds"]
    assert {x["id"] for x in results} == {r["编号"] for r in pair}
    assert all(x[k]["score"] is None or x[k]["score"] in range(1,6)
               for x in results for k in ("understand", "locate", "retrieve"))
    dump(target/"试读结果.json", {"参与方式":"AI 对两份操作产物的独立事后试读","模型":"gpt-6-astra",
         "开始UTC":start, "结束UTC":datetime.now(timezone.utc).isoformat(), "两轮":results})
    return results


def main(runs, out):
    out.mkdir(parents=True,exist_ok=False)
    rows = read(runs/"12轮汇总.json")["原始记录"]
    pairs = [[r for r in rows if r["编号"].startswith(f"AI-{n:02}-")] for n in range(1,7)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(grade,p,runs,out/f"试读{i}") for i,p in enumerate(pairs,1)]
        scores = {item["id"]: item for f in futures for item in f.result()}
    summary = []
    for r in rows:
        got = scores[r["编号"]]
        summary.append({"轮次":r["编号"],"方式":r["方式"],"任务":r["任务"],
                        **{zh:got[k]["score"] for k,zh in (("understand","理解"),("locate","定位"),("retrieve","取回"))}})
    dump(out/"12份产物试读评分.json",summary)


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    main(args.runs,args.out)

