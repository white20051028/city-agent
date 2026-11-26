"""线上复现用户的真实操作：连续两次换批推荐饮品。"""

import json
import urllib.request

BASE = "https://agent-city.site:8443"
ORIGIN = {"origin_lat": 34.3622, "origin_lon": 109.1883, "origin_name": "我的位置"}


def ask(q: str, history: list, shown: list) -> dict | None:
    body = json.dumps({"question": q, "city": "西安市", **ORIGIN,
                       "history": history[-6:], "shown_ids": shown},
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
    history, shown = [], []

    for q in ["附近有什么喝的", "换一批", "还有别的吗"]:
        print("=" * 66)
        print(f"「{q}」")
        print("=" * 66)
        d = ask(q, history, shown)
        if not d:
            return

        pois = d.get("pois") or []
        print(f"  intent={d.get('intent')}  POI={len(pois)}")
        for line in (d.get("tool_log") or [])[:3]:
            print(f"    · {line}")
        for p in pois:
            dup = "【重复】" if p.get("id") in shown else ""
            print(f"    {p['name']}  [{p.get('type')}] {dup}")
            if p.get("id") and p["id"] not in shown:
                shown.append(p["id"])

        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": (d.get("answer") or "")[:200]})
        print()


if __name__ == "__main__":
    main()
