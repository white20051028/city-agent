"""验证「还有别的吗」不再返回重复。"""

import json
import urllib.request

BASE = "https://agent-city.site:8443"
ORIGIN = {"origin_lat": 34.3622, "origin_lon": 109.1883, "origin_name": "我的位置"}


def ask(q: str, shown: list) -> dict | None:
    body = json.dumps({"question": q, "city": "西安市", **ORIGIN,
                       "shown_ids": shown}, ensure_ascii=False).encode()
    req = urllib.request.Request(
        f"{BASE}/api/ask", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001
        print(f"  失败: {e}")
        return None


def main() -> None:
    shown = []

    for i, q in enumerate(["附近能去哪玩", "还有别的吗", "还有别的吗"], 1):
        print("=" * 60)
        print(f"第 {i} 轮：「{q}」  已排除 {len(shown)} 个")
        print("=" * 60)
        d = ask(q, shown)
        if not d:
            continue
        pois = d.get("pois") or []
        print(f"  POI={len(pois)}")
        for line in (d.get("tool_log") or []):
            if "排除" in line:
                print(f"    · {line}")
        for p in pois:
            print(f"    {p['name']}  {p.get('distance')}m  (id={p.get('id')})")
            if p.get("id"):
                shown.append(p["id"])
        print()


if __name__ == "__main__":
    main()
