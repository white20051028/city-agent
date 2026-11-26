"""Agent 的状态定义。

LangGraph 的 State 是一个 TypedDict：每个节点读它、返回要更新的字段。
**只返回改动的字段**，LangGraph 会合并。
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """一次问答的全部状态。total=False 表示所有字段都可选。"""

    # ---------- 输入（由用户消息解析而来） ----------
    user_input: str          # 用户原话（这一轮的）
    history: list[dict]      # 之前的对话 [{role, content}]，用于拼成完整意图
    intent: str              # eat / sight / travel / stay / fun
    location_name: str       # 地点名，如「西安科技大学骊山校区」
    city: str                # 城市名，用于关键字搜索
    budget: int | None       # 人均预算（元），None 表示不限
    duration_min: int | None # 可用时长（分钟），None 表示不限

    # ---------- 中间结果 ----------
    location: str | None     # "经度,纬度"
    adcode: str              # 行政区码（临潼区 = 610115），sight 按区搜景点用
    district: str            # 区名（如「临潼区」）
    pois: list[dict[str, Any]]      # 检索到的候选池（原始）
    filtered: list[dict[str, Any]]  # 筛选+排序后的
    itinerary: list[dict[str, Any]] # 行程（每项含到下一项的路线）

    # ---------- Critic 相关 ----------
    critic_feedback: str     # Critic 的意见（空字符串表示通过）
    retry_count: int         # 已被打回几次
    max_points: int | None   # Critic 算出的「最多能去几个」，传给 filter
    excluded_ids: list[str]  # Critic 判定要排除的 POI id（太远/超预算）
    now_hour: int            # 当前小时（0–23），用于判断白天/晚上
    user_city: str           # 用户选的城市（如「西安市」），地理编码的约束
    relaxed_time: bool       # 结果不足时放宽了时间限制（夜间推荐可能已闭店）
    origin_lat: float | None # 用户手动设定的起点纬度（拖动地图或输入地名）
    origin_lon: float | None # 用户手动设定的起点经度
    origin_name: str         # 起点的显示名（如「我的位置」「华清池」）
    want_feature: bool       # 用户是否要「地方特色」（特色/本地/传统/民俗）
    category_kw: str         # 用户说的具体品类关键词（KTV/健身房/美甲），空表示没指定
    shown_ids: list[str]     # 之前已经推荐过的 POI id（「还有别的」时排除它们）

    # ---------- 输出 ----------
    answer: str              # 最终回答（Markdown）
    tool_log: list[str]      # 工具调用记录，界面要显示
