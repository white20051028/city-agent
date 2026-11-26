"""查两件事：
  ① 后端返回的 pois 里到底有没有 id
  ② 连续问「还有别的吗」时，shown_ids 是否真的生效
"""

import json
import urllib.request

BASE = "https://agent-city.site:8443"
ORIGIN = {"origin_lat": 34.3622, "origin_lon": 109.1883, "origin_name": "我的位置"}


def ask(q: str, shown: list | None = None) -> dict | None:
    payload = {"question": q, "city": "西安市", **ORIGIN}
    if shown is not None:
        payload["shown_ids"] = shown
    body = json.dumps(payload, ensure_ascii=False).encode()
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
    print("=" * 66)
    print("① 返回的 pois 里有没有 id")
    print("=" * 66)
    d = ask("附近能去哪玩")
    if not d:
        return
    pois = d.get("pois") or []
    print(f"  POI 数：{len(pois)}")
    for p in pois[:3]:
        print(f"    name={p['name']}")
        print(f"    id={p.get('id')!r}   keys={sorted(p.keys())}")
    print()

    print("=" * 66)
    print("② 模拟前端：连续三次「还有别的吗」，每次把前一批 id 加到 shown")
    print("=" * 66)
    shown = [p["id"] for p in pois if p.get("id")]
    print(f"  第 1 轮后 shown_ids ({len(shown)} 个): {shown}")

    for i in range(2, 5):
        d = ask("还有别的吗", shown)
        if not d:
            return
        items = d.get("pois") or []
        print(f"\n  第 {i} 轮：POI={len(items)}")
        # 看工具链里有没有「排除」
        has_exclude = any("排除" in l for l in (d.get("tool_log") or []))
        print(f"    有排除步骤：{has_exclude}")
        for p in items[:3]:
            dup = "【重复】" if p.get("id") in shown else ""
            print(f"      {p['name']}  id={p.get('id')} {dup}")
        for p in items:
            if p.get("id") and p["id"] not in shown:
                shown.append(p["id"])
        print(f"    shown_ids 累计：{len(shown)}")


if __name__ == "__main__":
    main()
