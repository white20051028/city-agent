"""测榆林文化适配的四种问法。"""

import sys

sys.path.insert(0, r"D:\桌面\city-agent")

from agent.graph import build_graph

g = build_graph(with_critic=True)

CASES = [
    ("榆林有什么非遗", "榆林市"),
    ("六楼骑街是哪六楼", "榆林市"),
    ("榆林有什么特色吃的", "榆林市"),
    ("榆林有什么景点", "榆林市"),
    ("榆林有什么好玩的", "榆林市"),
    # 对照：非榆林不应触发本地数据
    ("西安有什么非遗", "西安市"),
]

for q, city in CASES:
    print("=" * 68)
    print(f"【{q}】 city={city}")
    print("=" * 68)
    r = g.invoke({
        "user_input": q,
        "city": city,
        "origin_lat": 38.2857, "origin_lon": 109.7341,
        "origin_name": "我的位置",
        "user_city": city,
    })
    ans = (r.get("answer") or "")
    pois = r.get("itinerary") or []
    print(f"  intent={r.get('intent')}  POI={len(pois)}  答案长度={len(ans)}")
    print("  --- 答案前 300 字 ---")
    for line in ans[:300].splitlines():
        print("  " + line)
    if pois:
        print("  --- POI ---")
        for p in pois[:5]:
            note = p.get("local_note")
            print(f"    {p['name']}" + (f"  ← 有本地补充" if note else ""))
    print()
