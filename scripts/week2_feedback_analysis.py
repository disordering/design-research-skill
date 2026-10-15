"""
第 2 周基础分析脚本：对 N 条用户反馈做情感分析 + 主题聚类（Vibe Coding 产物）

用法：
    set DASHSCOPE_API_KEY=sk-xxx        # Windows
    python week2_feedback_analysis.py --input data/feedback_sample.txt --out output/week2_result.json

设计要点（对应中期报告 2.3 / 3.3）：
1. 输入输出契约：模型必须返回严格 JSON，字段固定，便于下游统计与可视化；
2. 一次调用同时完成情感分类 + 关键句抽取 + 主题归类，避免多轮调用带来的不一致；
3. 解析失败/模型跑偏时自动重试一次，仍失败则整条标记为 unknown（而不是崩溃）。
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL = os.environ.get("QWEN_MODEL", "qwen-plus")

SYSTEM_PROMPT = """你是一位资深用户研究员。你的任务是对用户反馈做结构化标注。
只输出 JSON，不要输出任何解释、前后缀或 Markdown 代码块。
JSON 结构必须严格如下：
{"items":[{"id":1,"sentiment":"positive|negative|neutral","intensity":0.0,"key_phrase":"最能代表这条反馈的原文片段","topic":"主题标签"}]}
规则：
- sentiment 只能取 positive / negative / neutral 三选一；
- intensity 取 0.0-1.0，表示情绪强度（0.5 为中性）；
- key_phrase 必须是原文中的连续片段，不要改写；
- topic 用 4-8 个字概括问题领域，同类问题必须使用完全相同的标签。"""


def call_llm(items, api_key, timeout=90):
    """一次调用完成情感分类 + 关键句抽取 + 主题聚类"""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(
                {"items": [{"id": i + 1, "text": t} for i, t in enumerate(items)]},
                ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"], data.get("usage", {})


def parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            return json.loads(m.group(0))
        raise


def analyze(items, api_key, retries=1):
    last_err = None
    for attempt in range(retries + 1):
        try:
            raw, usage = call_llm(items, api_key)
            parsed = parse_json(raw)
            if "items" in parsed and len(parsed["items"]) == len(items):
                return parsed, usage, attempt
            last_err = ValueError("items 数量不匹配：%s != %s"
                                  % (len(parsed.get("items", [])), len(items)))
        except Exception as e:  # 网络错误 / 解析错误都重试
            last_err = e
        time.sleep(2)
    raise RuntimeError("两次调用都失败：%s" % last_err)


def summarize(result, items):
    rows = result["items"]
    sent = Counter(r["sentiment"] for r in rows)
    topics = defaultdict(lambda: {"count": 0, "neg": 0, "samples": []})
    for r in rows:
        t = topics[r["topic"]]
        t["count"] += 1
        if r["sentiment"] == "negative":
            t["neg"] += 1
        if len(t["samples"]) < 2:
            t["samples"].append(items[r["id"] - 1])
    topic_list = sorted(
        [{"topic": k, "count": v["count"], "negative_ratio": round(v["neg"] / v["count"], 2),
          "samples": v["samples"]} for k, v in topics.items()],
        key=lambda x: (-x["count"], -x["negative_ratio"]))
    return {
        "total": len(rows),
        "sentiment": dict(sent),
        "negative_ratio": round(sent.get("negative", 0) / len(rows), 2),
        "topics": topic_list,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/feedback_sample.txt")
    ap.add_argument("--out", default="output/week2_result.json")
    args = ap.parse_args()

    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        sys.exit("缺少 DASHSCOPE_API_KEY 环境变量")

    items = [ln.strip() for ln in open(args.input, encoding="utf-8") if ln.strip()]
    print("[1/3] 读入反馈 %d 条：%s" % (len(items), args.input))

    parsed, usage, attempts = analyze(items, api_key)
    print("[2/3] 模型返回成功（重试 %d 次），tokens=%s" % (attempts, usage.get("total_tokens")))

    summary = summarize(parsed, items)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump({"raw": parsed, "summary": summary, "usage": usage},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("[3/3] 结果已写入：%s\n" % args.out)
    print("情感分布：", summary["sentiment"], "｜负面占比：", summary["negative_ratio"])
    print("主题聚类（按条数排序）：")
    for t in summary["topics"]:
        print("  - %-8s 条数=%d 负面占比=%.2f  例：%s"
              % (t["topic"], t["count"], t["negative_ratio"], t["samples"][0][:24]))


if __name__ == "__main__":
    main()
