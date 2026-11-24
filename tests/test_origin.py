"""验证起点功能：拖动/输入地名后，搜索中心应该跟着变。"""

from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read().decode())


def ask(question: str, city: str = "西安市", **extra) -> dict:
    payload = {"question": question, "city": city, **extra}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/ask", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    # ① 地名转坐标接口
    print("=" * 60)
    print("① /api/geocode 华清池")
    print("=" * 60)
    d = get("/api/geocode?place=" + urllib.parse.quote("华清池") + "&city=" + urllib.parse.quote("西安市"))
    print(f"  ok={d.get('ok')} location={d.get('location')}")
    print(f"  {d.get('address')}")

    # ② 不传 origin（走问题里的地名）
    print()
    print("=" * 60)
    print("② 不传 origin")
    print("=" * 60)
    r = ask("骊山校区附近有什么好吃的")
    print(f"  POI {len(r['pois'])} 个，第一个: {r['pois'][0]['name']}")
    print(f"  坐标: {r['location']}")

    # ③ 传 origin = 华清池坐标，问题不变
    print()
    print("=" * 60)
    print("③ 传 origin（华清池），问题还是「骊山校区附近有什么好吃的」")
    print("=" * 60)
    loc = d.get("location", "")
    if loc:
        lon, lat = map(float, loc.split(","))
        r2 = ask("附近有什么好吃的", origin_lat=lat, origin_lon=lon,
                 origin_name="华清池")
        print(f"  POI {len(r2['pois'])} 个")
        for p in r2["pois"][:5]:
            print(f"    {p['name']}  {p.get('distance')}m  ⭐{p.get('rating')}")
        print(f"  搜索中心: {r2['location']}")
        # 说清楚起点日志
        for line in r2.get("tool_log", [])[:2]:
            print(f"  · {line}")


if __name__ == "__main__":
    import urllib.parse
    main()
