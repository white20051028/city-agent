"""跑留出验证集（10 条，不参与调参）。

**只跑一次，不做任何调整**——这才是真实准确率。

跑法：
    E:\\anaconda3\\envs\\llm-rag\\python.exe -X utf8 tests\\eval_holdout.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.graph import build_graph  # noqa: E402


def load() -> list[dict]:
    f = ROOT / "data" / "eval_set_holdout.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]


def run_one(graph, case: dict) -> dict:
    t0 = time.time()
    r = graph.invoke({
        "user_input": case["question"],
        "origin_lat": 34.3667,
        "origin_lon": 109.2157,
        "origin_name": "西安科技大学骊山校区",
    })
    pois = r.get("itinerary") or []
    answer = r.get("answer") or ""

    allow_clarify = case.get("allow_clarify", False)
    is_clarify = allow_clarify and not pois and answer.strip() and "？" in answer

    return {
        "id": case["id"],
        "type": case["type"],
        "question": case["question"],
        "intent": r.get("intent"),
        "expect_intent": case["expect_intent"],
        "poi_count": len(pois),
        "expect_min_poi": case["expect_min_poi"],
        "elapsed": round(time.time() - t0, 1),
        "intent_ok": r.get("intent") == case["expect_intent"] or is_clarify,
        "poi_ok": len(pois) >= case["expect_min_poi"] or is_clarify,
        "clarified": bool(is_clarify),
        "pois": [p.get("name") for p in pois[:3]],
        "answer_head": answer[:100].replace("\n", " "),
    }


def main() -> None:
    cases = load()
    graph = build_graph(with_critic=True)

    print(f"留出验证集：{len(cases)} 条（不参与调参）\n")
    results = []
    for c in cases:
        r = run_one(graph, c)
        results.append(r)
        flag = "✓" if (r["intent_ok"] and r["poi_ok"]) else "✗"
        mark = " [反问]" if r["clarified"] else ""
        print(f"[{r['id']:>3}] {flag} intent={r['intent']:<7} POI={r['poi_count']} "
              f"{r['elapsed']:>4}s  {r['question'][:22]}{mark}")
        if r["pois"]:
            print(f"       {', '.join(r['pois'])}")

    n = len(results)
    passed = sum(1 for r in results if r["intent_ok"] and r["poi_ok"])
    intent_ok = sum(1 for r in results if r["intent_ok"])
    poi_ok = sum(1 for r in results if r["poi_ok"])

    print()
    print("=" * 62)
    print("留出集结果（这才是真实准确率）")
    print("=" * 62)
    print(f"  完全通过      {passed}/{n} = {passed / n:.0%}")
    print(f"  意图准确      {intent_ok}/{n} = {intent_ok / n:.0%}")
    print(f"  结果充足      {poi_ok}/{n} = {poi_ok / n:.0%}")
    print()

    fails = [r for r in results if not (r["intent_ok"] and r["poi_ok"])]
    if fails:
        print("未通过：")
        for r in fails:
            print(f"  [{r['id']}] {r['question']}")
            print(f"       intent {r['intent']} vs 期望 {r['expect_intent']}，"
                  f"POI {r['poi_count']} vs 期望 {r['expect_min_poi']}")
            print(f"       {r['answer_head'][:80]}")

    out = ROOT / "data" / "eval_holdout_result.json"
    out.write_text(json.dumps({
        "n": n,
        "passed": passed,
        "pass_rate": round(passed / n, 3),
        "intent_accuracy": round(intent_ok / n, 3),
        "poi_sufficiency": round(poi_ok / n, 3),
        "details": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已存: {out}")


if __name__ == "__main__":
    main()
