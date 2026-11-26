"""看「还有别的吗」的完整调用链，找出为什么返回 0。"""

import json
import urllib.request

BASE = "https://agent-city.site:8443"
ORIGIN = {"origin_lat": 34.3622, "origin_lon": 109.1883, "origin_name": "我的位置"}


def ask(q: str, shown: list, history: list) -> dict | None:
    body = json.dumps({"question": q, "city": "西安市", **ORIGIN,
                       "shown_ids": shown, "history": history[-6:]},
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
    shown, history = [], []

    print("=" * 70)
    print("第 1 轮：附近能去哪玩")
    print("=" * 70)
    d = ask("附近能去哪玩", shown, history)
    if not d:
        return
    print(f"  intent={d.get('intent')} POI={len(d.get('pois') or [])}")
    for line in (d.get("tool_log") or []):
        print(f"    · {line}")
    for p in (d.get("pois") or []):
        print(f"    {p['name']}  (id={p.get('id')})")
        if p.get("id"):
            shown.append(p["id"])
    history.append({"role": "user", "content": "附近能去哪玩"})
    history.append({"role": "assistant", "content": d.get("answer", "")[:200]})

    print("\n" + "=" * 70)
    print(f"第 2 轮：还有别的吗（排除 {len(shown)} 个）")
    print("=" * 70)
    print(f"  传入的 shown_ids: {shown}")
    d2 = ask("还有别的吗", shown, history)
    if not d2:
        return
    print(f"  intent={d2.get('intent')} POI={len(d2.get('pois') or [])}")
    print("  完整调用链：")
    for line in (d2.get("tool_log") or []):
        print(f"    · {line}")
    if d2.get("pois"):
        for p in d2["pois"]:
            print(f"    {p['name']}  (id={p.get('id')})")
    else:
        print(f"  答案：{(d2.get('answer') or '')[:200]}")


if __name__ == "__main__":
    main()
