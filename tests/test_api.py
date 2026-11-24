"""测 API：用 Python 发请求（避免 PowerShell 的编码坑）。

跑法：
    E:\\anaconda3\\envs\\llm-rag\\python.exe -X utf8 tests\\test_api.py
"""

from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:8000"

CASES = [
    ("骊山校区附近有什么好吃的", "eat"),
    ("西安科技大学骊山校区附近能去哪玩", "play"),
    ("西安科技大学骊山校区附近有什么景点", "sight"),
    ("榆林有什么景点", "travel"),
]


def ask(question: str, city: str = "西安市") -> dict:
    body = json.dumps({"question": question, "city": city},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/ask", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    for q, label in CASES:
        print("=" * 66)
        print(f"【{label}】{q}")
        print("=" * 66)
        try:
            d = ask(q)
        except Exception as e:  # noqa: BLE001
            print(f"  请求失败: {type(e).__name__}: {e}")
            continue

        print(f"  ok={d.get('ok')} intent={d.get('intent')} "
              f"耗时={d.get('elapsed')}s POI={len(d.get('pois') or [])} 个")
        print(f"  工具链 {len(d.get('tool_log') or [])} 步")
        ans = d.get("answer") or ""
        print("  答案:")
        for line in ans.split("\n")[:8]:
            print("   ", line)
        pois = d.get("pois") or []
        if pois:
            print("  地图标记:")
            for p in pois[:5]:
                print(f"    · {p['name']}  ({p.get('location')})")
        print()


if __name__ == "__main__":
    main()
