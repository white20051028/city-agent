"""验证：连续两次换批，意图链条不断。"""

import sys

sys.path.insert(0, r"D:\桌面\city-agent")

from agent.intent import build_effective_query, is_self_contained

print("=" * 66)
print("用户的真实场景：连续两次换批推荐饮品")
print("=" * 66)

# 第 1 轮
h1 = []
q1 = "附近有什么喝的"
print(f"\n① {q1}")
print(f"   独立? {is_self_contained(q1)}")
print(f"   拼接: {build_effective_query(q1, h1)}")

# 第 2 轮：换一批
h2 = [
    {"role": "user", "content": "附近有什么喝的"},
    {"role": "assistant", "content": "（给了奶茶店）"},
]
q2 = "换一批"
print(f"\n② {q2}")
print(f"   独立? {is_self_contained(q2)}")
print(f"   拼接: {build_effective_query(q2, h2)}")

# 第 3 轮：还有别的吗
h3 = h2 + [
    {"role": "user", "content": "换一批"},
    {"role": "assistant", "content": "（给了另一些奶茶店）"},
]
q3 = "还有别的吗"
print(f"\n③ {q3}")
print(f"   独立? {is_self_contained(q3)}")
ef3 = build_effective_query(q3, h3)
print(f"   拼接: {ef3}")
print()
if "喝的" in ef3:
    print("   ✅ 保留了「喝的」这个意图")
else:
    print("   ❌ 又丢了意图")

# 对照：不能破坏之前修好的场景
print("\n" + "=" * 66)
print("对照 1：不同意图切换（之前修过的）")
print("=" * 66)
h4 = [
    {"role": "user", "content": "附近能去哪玩"},
    {"role": "assistant", "content": "（公园）"},
    {"role": "user", "content": "附近有什么好吃的"},
    {"role": "assistant", "content": "（餐厅）"},
]
print(f"   「便宜点」→ {build_effective_query('便宜点', h4)}")

print("\n" + "=" * 66)
print("对照 2：安静点的餐厅（补充词优先）")
print("=" * 66)
h5 = [{"role": "user", "content": "纪念日，人均150，安静点"}]
print(f"   「安静点的餐厅」→ {build_effective_query('安静点的餐厅', h5)}")
