"""连问几次同一个问题，看结果数量稳不稳定。"""

from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def ask(q: str, city: str = "西安市") -> dict:
    body = json.dumps({"question": q, "city": city}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/ask", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    qs = ["骊山校区附近能去哪玩"] * 3
    for i, q in enumerate(qs, 1):
        d = ask(q)
        pois = d.get("pois") or []
        print(f"\n第 {i} 次：POI {len(pois)} 个，耗时 {d.get('elapsed')}s")
        for line in (d.get("tool_log") or []):
            print(f"  · {line}")
        for p in pois[:5]:
            print(f"    {p['name']}  {p.get('distance')}m  评分{p.get('rating')}")
        ans = d.get("answer") or ""
        if "放宽" in ans:
            print("  [有放宽提示]")


if __name__ == "__main__":
    main()
