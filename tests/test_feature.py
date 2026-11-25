"""验证地方特色能力：V7 那条 + 新增几条榆林特色问法。"""

from __future__ import annotations

import json
import sys
import urllib.request

sys.path.insert(0, r"D:\桌面\city-agent")

BASE = "http://127.0.0.1:8000"
ORIGIN = {"origin_lat": 34.3667, "origin_lon": 109.2157,
          "origin_name": "西安科技大学骊山校区"}


def ask(q: str, **extra) -> dict:
    payload = {"question": q, "city": "西安市", **ORIGIN, **extra}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/ask", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


CASES = [
    ("带外地朋友玩，有啥陕北特色的", "西安"),
    ("榆林有什么特色", "榆林"),
    ("临潼有什么本地特色的", "西安"),
    ("附近能去哪玩", "西安"),        # 对照：不该被特色逻辑影响
]


def main() -> None:
    for q, city in CASES:
        print("=" * 62)
        print(f"【{q}】 city={city}")
        print("=" * 62)
        d = ask(q, city=city)
        pois = d.get("pois") or []
        print(f"  intent={d.get('intent')} POI={len(pois)}")
        for p in pois[:5]:
            print(f"    · {p['name']}  [{p.get('type')}]")
        print()


if __name__ == "__main__":
    main()
