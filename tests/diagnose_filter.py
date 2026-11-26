"""诊断：为什么排除 5 个后候选就空了。

直接调 filter 的上下游，看每一步剩多少。
"""

import sys

sys.path.insert(0, r"D:\桌面\city-agent")

from agent import nodes


def main() -> None:
    # 复现「附近能去哪玩」的 state
    state = {
        "user_input": "附近能去哪玩",
        "intent": "play",
        "location": "109.1883,34.3622",
        "city": "西安市",
        "district": "临潼区",
        "adcode": "610115",
        "budget": None,
        "duration_min": None,
        "now_hour": 11,
        "want_feature": False,
        "category_kw": "",
        "history": [],
        "tool_log": [],
    }

    print("=== search ===")
    r = nodes.search(state)
    pois = r.get("pois") or []
    print(f"  返回 {len(pois)} 条")
    for line in r.get("tool_log") or []:
        print(f"  · {line}")

    print("\n=== dedupe（去重后剩多少）===")
    deduped = nodes.dedupe_by_main_spot(pois)
    print(f"  {len(pois)} → {len(deduped)}")

    print("\n=== 排除前 5 个后 ===")
    shown = [p.get("id") for p in deduped[:5]]
    rest = [p for p in deduped if p.get("id") not in shown]
    print(f"  剩 {len(rest)} 条")
    for p in rest[:5]:
        print(f"    {p['name']}  {p.get('distance')}m")


if __name__ == "__main__":
    main()
