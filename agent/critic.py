"""Critic 节点：检查方案合不合理，不合理就打回。

**这是双 Agent 的第二个角色。**
Planner（前面六个节点）出方案，Critic 验证——
时间够不够、距离合不合理、预算超没超。

为什么要它：
  单 Agent 自己说「这个方案很好」，没有第二双眼睛。
  Critic 拿客观数据（步行时间、预算）复核，能发现 Planner 忽略的问题。
"""

from __future__ import annotations

from .state import AgentState

MAX_RETRY = 2

# 吃饭 + 逛，每个点平均停留这么久（分钟）
STAY_MINUTES = {"eat": 60, "sight": 90, "fun": 120, "stay": 0}

# 出行时间上限：按意图区分，**用最快交通方式的时间，不是步行时间**
# 说「去景点」的人会坐地铁/打车，用步行时间卡他毫无意义。
# 数值是最快方式（步行/骑行/公交/驾车取最小）的上限。
MAX_TRAVEL_MIN_BY_INTENT = {
    "eat": 15,     # 吃饭：一刻钟内能到
    "sight": 45,   # 景点：坐半小时车很正常
    "play": 30,    # 玩：半小时
    "fun": 30,
    "stay": 20,
}
MAX_TRAVEL_MIN = 30  # 兜底


def review(state: AgentState) -> dict:
    """检查方案。返回 critic_feedback（空串=通过）。"""
    itin = state.get("itinerary", [])
    intent = state.get("intent", "sight")
    duration = state.get("duration_min")
    budget = state.get("budget")
    retries = state.get("retry_count", 0)
    log = state.get("tool_log", [])

    # ① 没有候选：不算「方案不合理」，是数据不足，直接给结论
    if not itin:
        return {"critic_feedback": "", "tool_log": log + ["Critic：无候选，跳过"]}

    problems = []
    excluded: list[str] = list(state.get("excluded_ids", []))

    # ② 时间检查（仅当用户给了时长）
    # 思路不是「算总耗时看超没超」，而是「反推最多能去几个」——
    # 用户只有 2 小时，告诉他「5 个点要 543 分钟」没用，他需要知道「只能去 1 个」。
    max_points = None
    if duration:
        per = STAY_MINUTES.get(intent, 60)
        avg_walk = (sum(p.get("walk_min") or 0 for p in itin) / len(itin)) if itin else 0
        max_points = max(1, int(duration // (per + avg_walk)))
        if len(itin) > max_points:
            problems.append(
                f"你只有 {duration} 分钟，每个地方约 {per} 分钟 + 步行 {avg_walk:.0f} 分钟，"
                f"最多去 {max_points} 个"
            )

    # ③ 距离检查（**travel 场景跳过**）
    # 用户说「榆林有什么景点」是在全城范围做功课，
    # 不是「我 15 分钟内要走过去」——用步行时间卡他毫无意义。
    if intent != "travel":
        from .nodes import best_travel_min
        limit = MAX_TRAVEL_MIN_BY_INTENT.get(intent, MAX_TRAVEL_MIN)
        for p in itin:
            bt = best_travel_min(p)
            if bt is not None and bt > limit:
                # **直接排除，不靠 filter 猜**：
                # filter 只有直线距离（distance），和这里的实际出行时间
                # 不是一回事，让 filter 去重算会永远对不上。
                if p.get("id"):
                    excluded.append(p["id"])
                problems.append(f"「{p['name']}」最快也要 {bt} 分钟，太远")
                break

    # ④ 预算检查（仅当用户给了预算）
    if budget:
        over = [p for p in itin
                if isinstance(p.get("cost"), (int, float)) and p["cost"] > budget * 1.2]
        if over:
            for p in over:
                if p.get("id"):
                    excluded.append(p["id"])
            problems.append(
                f"{len(over)} 个地方人均超预算（如「{over[0]['name']}」人均 {int(over[0]['cost'])}）"
            )

    # 打回次数到上限：不再打回，把问题写进答案让用户知道
    if problems and retries < MAX_RETRY:
        return {
            "critic_feedback": "；".join(problems),
            "max_points": max_points,
            "excluded_ids": excluded,
            "retry_count": retries + 1,
            "tool_log": log + [f"Critic 打回（第 {retries + 1} 次）：{problems[0]}"],
        }

    if problems:
        # 到上限仍不合理：保留方案，但标注未通过审核
        note = f"\n\n> ⚠️ 方案复核未通过：{'；'.join(problems)}。以上建议仅供参考。"
        return {
            "critic_feedback": "",
            "answer": state.get("answer", "") + note,
            "tool_log": log + ["Critic：已达重试上限，标注后输出"],
        }

    return {
        "critic_feedback": "",
        "tool_log": log + ["Critic：通过"],
    }


def should_retry(state: AgentState) -> str:
    """条件边：有 feedback 就回 filter，否则结束。"""
    return "retry" if state.get("critic_feedback") else "done"
