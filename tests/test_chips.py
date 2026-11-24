"""验证：无主语的问法 + 起点坐标，应该能出结果。"""

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


def show(label: str, **payload) -> None:
    print("=" * 60)
    print(label)
    print("=" * 60)
    d = ask(**payload)
    pois = d.get("pois") or []
    print(f"  intent={d.get('intent')} POI={len(pois)} 耗时={d.get('elapsed')}s")
    for p in pois[:5]:
        print(f"    {p['name']}  {p.get('distance')}m  ⭐{p.get('rating')}")
    if not pois:
        print(f"  答案: {d.get('answer')}")
    print()


def main() -> None:
    # 用户真实情况：定位在临潼校区附近，问无主语的句子
    origin = {"origin_lat": 34.3672, "origin_lon": 109.2225, "origin_name": "我的位置"}

    show("① 附近有什么好吃的（我定位的位置）",
         question="附近有什么好吃的", **origin)
    show("② 附近能去哪玩（我定位的位置）",
         question="附近能去哪玩", **origin)
    show("③ 附近两小时能去哪玩（我定位的位置）",
         question="附近两小时能去哪玩", **origin)
    show("④ 附近有什么景点（我定位的位置）",
         question="附近有什么景点", **origin)


if __name__ == "__main__":
    main()
