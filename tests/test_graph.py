"""跑通整条图：三个场景。

跑法（在 D:\\桌面\\city-agent 下）：
    E:\\anaconda3\\envs\\llm-rag\\python.exe -X utf8 tests\\test_graph.py

三个场景：
  ① 简单：骊山校区附近有什么好吃的
  ② 带约束：骊山校区附近两小时能去哪玩
  ③ 全城：榆林有什么景点

每个场景打印：解析结果、工具调用链、最终答案。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.graph import build_graph


def run(question: str, label: str) -> None:
    print()
    print("=" * 70)
    print(f"【{label}】{question}")
    print("=" * 70)

    t0 = time.time()
    graph = build_graph(with_critic=True)
    result = graph.invoke({"user_input": question})
    cost = time.time() - t0

    print(f"\n解析: intent={result.get('intent')} "
          f"地点={result.get('location_name') or '未提'} "
          f"城市={result.get('city') or '-'} "
          f"预算={result.get('budget')} 时长={result.get('duration_min')}分钟")
    print(f"坐标: {result.get('location')}")

    print("\n工具调用链:")
    for line in result.get("tool_log", []):
        print(f"  · {line}")

    print(f"\n最终答案（耗时 {cost:.1f}s）:")
    print("-" * 70)
    print(result.get("answer", "（无答案）"))
    print("-" * 70)


if __name__ == "__main__":
    run("西安科技大学骊山校区附近有什么好吃的", "简单")
    run("骊山校区附近两个小时能去哪玩", "带时长约束")
    run("榆林有什么景点", "全城搜索")
