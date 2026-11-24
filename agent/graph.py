"""LangGraph 建图：把七个节点连成一个有向图。

图的形状：

    START
      ↓
    intake ──(需要反问)──→ END
      ↓
    resolve
      ↓
    search
      ↓
    filter ←──────────────┐
      ↓                   │ (Critic 不通过，最多 2 次)
    route                 │
      ↓                   │
    compose               │
      ↓                   │
    critic ───────────────┘
      ↓ (通过)
     END

**为什么 Critic 打回时回 filter 而不是 search**：
问题通常是「时间超了」「距离太远」，不需要重新搜数据，
只是换筛选条件重排——这一步能省 2–3 次 API 调用。
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import AgentState


def _after_intake(state: AgentState) -> str:
    """intake 后判断：需要反问就直接结束，否则继续。"""
    return "clarify" if state.get("answer") else "go"


def build_graph(*, with_critic: bool = True):
    """建图并编译。

    with_critic=False 时不接 Critic 节点，用于先跑通主链路。
    """
    g = StateGraph(AgentState)

    g.add_node("intake", nodes.intake)
    g.add_node("resolve", nodes.resolve)
    g.add_node("search", nodes.search)
    g.add_node("filter", nodes.filter_pois)
    g.add_node("route", nodes.route)
    g.add_node("compose", nodes.compose)

    g.add_edge(START, "intake")
    g.add_conditional_edges("intake", _after_intake, {"clarify": END, "go": "resolve"})
    g.add_edge("resolve", "search")
    g.add_edge("search", "filter")
    g.add_edge("filter", "route")
    g.add_edge("route", "compose")

    if with_critic:
        from .critic import review, should_retry

        g.add_node("critic", review)
        g.add_edge("compose", "critic")
        g.add_conditional_edges(
            "critic",
            should_retry,
            {"retry": "filter", "done": END},
        )
    else:
        g.add_edge("compose", END)

    return g.compile()
