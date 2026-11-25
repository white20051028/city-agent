"""跑 20 条评测，出三个指标。

指标：
  ① 意图准确率：intent 是否符合预期
  ② 结果充足率：POI 数量 >= expect_min_poi
  ③ 事实准确率：返回的 POI 坐标都真实存在（有 location 字段）

跑法：
    E:\\anaconda3\\envs\\llm-rag\\python.exe -X utf8 tests\\eval.py

注意：这跑的是本地 LangGraph（不经过 HTTP），省掉网络开销。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.graph import build_graph  # noqa: E402


def load_cases() -> list[dict]:
    f = ROOT / "data" / "eval_set.jsonl"
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_one(graph, case: dict) -> dict:
    """跑一条，返回结果摘要。"""
    t0 = time.time()
    # 统一给一个起点，模拟「已定位」状态
    r = graph.invoke({
        "user_input": case["question"],
        "origin_lat": 34.3667,
        "origin_lon": 109.2157,
        "origin_name": "西安科技大学骊山校区",
    })
    pois = r.get("itinerary") or []
    answer = r.get("answer") or ""

    # **反问也算通过**：信息模糊时该问，不该硬猜（case 6 就是这种情况）
    allow_clarify = case.get("allow_clarify", False)
    is_clarify = allow_clarify and len(pois) == 0 and answer.strip() and "？" in answer

    intent_ok = r.get("intent") == case["expect_intent"] or is_clarify
    poi_ok = len(pois) >= case["expect_min_poi"] or is_clarify

    return {
        "id": case["id"],
        "type": case["type"],
        "question": case["question"],
        "intent": r.get("intent"),
        "poi_count": len(pois),
        "elapsed": round(time.time() - t0, 1),
        "has_location": all(p.get("location") for p in pois),
        "expect_intent": case["expect_intent"],
        "expect_min_poi": case["expect_min_poi"],
        "intent_ok": intent_ok,
        "poi_ok": poi_ok,
        "clarified": bool(is_clarify),
        "answer_head": answer[:80].replace("\n", " "),
    }


def main() -> None:
    cases = load_cases()
    graph = build_graph(with_critic=True)

    print(f"跑 {len(cases)} 条评测…\n")
    results = []
    for c in cases:
        res = run_one(graph, c)
        results.append(res)
        flags = ("✓" if res["intent_ok"] else "✗") + ("✓" if res["poi_ok"] else "✗")
        mark = " [反问]" if res.get("clarified") else ""
        print(f"[{res['id']:>2}] {flags} intent={res['intent']:<7} "
              f"POI={res['poi_count']:<2} {res['elapsed']:>4}s  {res['question'][:26]}{mark}")

    # ---------- 汇总 ----------
    n = len(results)
    intent_ok = sum(1 for r in results if r["intent_ok"])
    poi_ok = sum(1 for r in results if r["poi_ok"])
    fact_ok = sum(1 for r in results if r["has_location"])
    total_time = sum(r["elapsed"] for r in results)

    print()
    print("=" * 62)
    print("汇总")
    print("=" * 62)
    print(f"  ① 意图准确率   {intent_ok}/{n} = {intent_ok / n:.1%}")
    print(f"  ② 结果充足率   {poi_ok}/{n} = {poi_ok / n:.1%}")
    print(f"  ③ 事实准确率   {fact_ok}/{n} = {fact_ok / n:.1%}（POI 都有坐标）")
    print(f"  平均耗时       {total_time / n:.1f}s")
    print()

    # 失败明细
    fails = [r for r in results if not r["intent_ok"] or not r["poi_ok"]]
    if fails:
        print("未通过:")
        for r in fails:
            why = []
            if not r["intent_ok"]:
                why.append(f"意图 {r['intent']}≠{r['expect_intent']}")
            if not r["poi_ok"]:
                why.append(f"POI {r['poi_count']}<{r['expect_min_poi']}")
            print(f"  [{r['id']}] {r['question'][:30]}")
            print(f"       {' / '.join(why)}")
            print(f"       {r['answer_head']}")

    # 存结果
    out = ROOT / "data" / "eval_result.json"
    out.write_text(json.dumps({
        "n": n,
        "intent_accuracy": round(intent_ok / n, 3),
        "poi_sufficiency": round(poi_ok / n, 3),
        "fact_accuracy": round(fact_ok / n, 3),
        "avg_seconds": round(total_time / n, 1),
        "details": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已存: {out}")


if __name__ == "__main__":
    main()
