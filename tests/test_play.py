"""验证 play 意图 + 时间感知 + 交通推算。

跑法：
    E:\\anaconda3\\envs\\llm-rag\\python.exe -X utf8 tests\\test_play.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.graph import build_graph


def run(question: str, label: str) -> None:
    print()
    print("=" * 70)
    print(f"【{label}】{question}")
    print("=" * 70)

    graph = build_graph(with_critic=True)
    r = graph.invoke({"user_input": question})

    print(f"解析: intent={r.get('intent')} 地点={r.get('location_name')} "
          f"时长={r.get('duration_min')} 当前 {datetime.now().strftime('%H:%M')}")
    print("\n工具链:")
    for line in r.get("tool_log", []):
        print(f"  · {line}")
    print("\n答案:")
    print("-" * 70)
    print(r.get("answer", "（无）"))
    print("-" * 70)


if __name__ == "__main__":
    # 开放式「能去哪玩」——现在 20 点左右，应该推夜间能去的
    run("西安科技大学骊山校区附近能去哪玩", "开放式 play")
    # 明确要景点——商场应该被降权
    run("西安科技大学骊山校区附近有什么景点", "明确 sight")
