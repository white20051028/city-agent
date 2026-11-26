"""线上复现用户的对话流，确认修复。"""

import json
import urllib.request

BASE = "https://agent-city.site:8443"
ORIGIN = {"origin_lat": 34.3622, "origin_lon": 109.1883,
          "origin_name": "我的位置"}


def ask(q: str, history: list) -> dict | None:
    body = json.dumps({"question": q, "city": "西安市", **ORIGIN,
                       "history": history[-6:]},
                      ensure_ascii=False).encode()
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
    history = []

    def roundtrip(q: str) -> dict | None:
        d = ask(q, history)
        if d:
            history.append({"role": "user", "content": q})
            history.append({"role": "assistant", "content": d.get("answer", "")[:300]})
        return d

    print("=" * 64)
    print("复现用户的对话流")
    print("=" * 64)

    for q in ["附近能去哪玩", "附近有什么好吃的", "便宜点"]:
        d = roundtrip(q)
        if not d:
            continue
        pois = d.get("pois") or []
        print(f"\n「{q}」")
        print(f"  intent={d.get('intent')} POI={len(pois)}")
        for line in (d.get("tool_log") or [])[:3]:
            print(f"    · {line}")
        for p in pois[:3]:
            print(f"    {p['name']}  [{p.get('type')}]  {p.get('distance')}m")


if __name__ == "__main__":
    main()
