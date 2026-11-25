"""重测榆林（不传 origin，避免骊山坐标覆盖城市）。"""

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


def show(q: str, **kw) -> None:
    print("=" * 62)
    print(f"【{q}】 {kw}")
    print("=" * 62)
    d = ask(q, **kw)
    print(f"  intent={d.get('intent')} POI={len(d.get('pois') or [])} "
          f"搜索中心={d.get('location')}")
    for p in (d.get("pois") or [])[:5]:
        print(f"    · {p['name']}  [{p.get('type')}]  {p.get('distance')}m")
    print()


if __name__ == "__main__":
    show("榆林有什么特色", city="榆林")
    show("榆林有什么景点", city="榆林")
    show("榆林有什么好吃的", city="榆林")
