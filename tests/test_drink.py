"""验证两个修复：不反问地点 + 饮品店分离。"""

from __future__ import annotations

import json
import urllib.request

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


def show(label: str, d: dict) -> None:
    print("=" * 62)
    print(label)
    print("=" * 62)
    print(f"  intent={d.get('intent')} POI={len(d.get('pois') or [])}")
    for p in (d.get("pois") or []):
        print(f"    {p['name']}  [{p.get('type')}]  人均{p.get('cost')}")
    if not d.get("pois"):
        print(f"  答案: {(d.get('answer') or '')[:120]}")
    print()


def main() -> None:
    show("① 纪念日人均150（有定位，不该反问地点）",
         ask("纪念日，人均150，安静点"))
    show("② 附近吃什么（不该有奶茶店）",
         ask("附近有什么好吃的"))
    show("③ 附近有什么喝的（应该只有饮品）",
         ask("附近有什么喝的"))


if __name__ == "__main__":
    main()
