"""复现：定位后问「附近有什么好吃的」为什么 0 结果。"""

from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def ask(**payload) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/ask", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    # 模拟用户定位：西科大临潼校区大致坐标（截图里起点标记的位置）
    cases = [
        ("无主语 + 定位起点", {"question": "附近有什么好吃的",
                            "origin_lat": 34.3672, "origin_lon": 109.2225,
                            "origin_name": "我的位置"}),
        ("有主语 + 没起点", {"question": "骊山校区附近有什么好吃的"}),
        ("无主语 + 没起点", {"question": "附近有什么好吃的"}),
    ]

    for label, payload in cases:
        print("=" * 62)
        print(label)
        print("=" * 62)
        d = ask(**payload)
        print(f"  intent={d.get('intent')} POI={len(d.get('pois') or [])} "
              f"耗时={d.get('elapsed')}s")
        print(f"  搜索中心: {d.get('location')}")
        for line in (d.get("tool_log") or []):
            print(f"    · {line}")
        for p in (d.get("pois") or [])[:3]:
            print(f"    {p['name']}  {p.get('distance')}m")
        print()


if __name__ == "__main__":
    main()
