"""测「带外地朋友去榆林玩，有啥陕北特色的」。"""

from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def ask(q: str, city: str = "", **extra) -> dict:
    payload = {"question": q, "city": city, **extra}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/ask", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


CASES = [
    ("带外地朋友去榆林玩，有啥陕北特色的", {}),
    ("带外地朋友去榆林玩，有啥陕北特色的", {"city": "榆林"}),
    ("榆林有什么陕北特色的", {}),
]


def main() -> None:
    for q, extra in CASES:
        print("=" * 64)
        print(f"【{q}】 {extra or '（不传城市）'}")
        print("=" * 64)
        d = ask(q, **extra)
        print(f"  intent={d.get('intent')} POI={len(d.get('pois') or [])}")
        print(f"  搜索中心: {d.get('location')}")
        print("  工具链:")
        for line in (d.get("tool_log") or []):
            print(f"    · {line}")
        print("  结果:")
        for p in (d.get("pois") or [])[:5]:
            print(f"    · {p['name']}  [{p.get('type')}]  {p.get('distance')}m")
        print()


if __name__ == "__main__":
    main()
