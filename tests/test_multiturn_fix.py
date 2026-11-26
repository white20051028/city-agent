"""复现用户的对话流，验证修复。

用户原话：
  第三句「便宜点」是在回复第二句「附近有什么好吃的」，不是第一句。
"""

import sys

sys.path.insert(0, r"D:\桌面\city-agent")

from agent.intent import build_effective_query, is_self_contained

# 用户的真实对话流
history = [
    {"role": "user", "content": "附近能去哪玩"},
    {"role": "assistant", "content": "（给了公园和 KTV）"},
    {"role": "user", "content": "附近有什么好吃的"},
    {"role": "assistant", "content": "（给了餐厅）"},
]

q = "便宜点"
ef = build_effective_query(q, history)
print("=" * 60)
print(f"当前问题：{q}")
print(f"是否独立：{is_self_contained(q)}")
print(f"拼接结果：{ef}")
print("=" * 60)

# 期望：只拼「附近有什么好吃的」，不拼「附近能去哪玩」
if "能去哪玩" in ef:
    print("❌ 仍然拼了更早的「能去哪玩」")
else:
    print("✅ 只拼了最近一轮")

# 再测「安静点的」场景（应该拼上一轮的人均150）
history2 = [
    {"role": "user", "content": "纪念日，人均150，安静点"},
    {"role": "assistant", "content": "（反问）"},
]
ef2 = build_effective_query("安静点的餐厅", history2)
print()
print(f"「安静点的餐厅」+ 历史「纪念日人均150」")
print(f"拼接结果：{ef2}")
