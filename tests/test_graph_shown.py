"""本地跑 graph，看 shown_ids 到底能不能传到 filter。"""

import sys

sys.path.insert(0, r"D:\桌面\city-agent")

from agent.graph import build_graph

g = build_graph(with_critic=True)

print("=" * 66)
print("第 1 轮：附近能去哪玩")
print("=" * 66)
r1 = g.invoke({
    "user_input": "附近能去哪玩",
    "origin_lat": 34.3622, "origin_lon": 109.1883,
    "origin_name": "我的位置",
    "user_city": "西安市",
})
p1 = r1.get("itinerary") or []
ids = [p.get("id") for p in p1 if p.get("id")]
print(f"  {len(p1)} 个：{[p['name'] for p in p1]}")
print(f"  ids: {ids}")

print()
print("=" * 66)
print(f"第 2 轮：还有别的吗（传 shown_ids={len(ids)} 个）")
print("=" * 66)
r2 = g.invoke({
    "user_input": "还有别的吗",
    "origin_lat": 34.3622, "origin_lon": 109.1883,
    "origin_name": "我的位置",
    "user_city": "西安市",
    "shown_ids": ids,          # ← 关键
    "history": [
        {"role": "user", "content": "附近能去哪玩"},
        {"role": "assistant", "content": (r1.get("answer") or "")[:200]},
    ],
})
p2 = r2.get("itinerary") or []
print(f"  {len(p2)} 个：{[p['name'] for p in p2]}")
print("\n  工具链：")
for line in (r2.get("tool_log") or []):
    print(f"    · {line}")

dup = [p["name"] for p in p2 if p.get("id") in ids]
print(f"\n  重复的：{dup if dup else '无'}")
