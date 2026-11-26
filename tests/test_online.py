"""测线上 API 是否正常工作（用 Python 避开 PowerShell 的编码坑）。"""

import json
import urllib.request

BASE = "https://agent-city.site:8443"


def ask(q: str, city: str = "西安市") -> dict | None:
    body = json.dumps({"question": q, "city": city},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/ask", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:300]}")
        return None
    except Exception as e:  # noqa: BLE001
        print(f"  {type(e).__name__}: {e}")
        return None


def main() -> None:
    print("=== 版本 ===")
    try:
        with urllib.request.urlopen(f"{BASE}/api/version", timeout=15) as r:
            print(f"  {r.read().decode()}")
    except Exception as e:  # noqa: BLE001
        print(f"  失败: {e}")

    print("\n=== 健康 ===")
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=15) as r:
            print(f"  {r.read().decode()}")
    except Exception as e:  # noqa: BLE001
        print(f"  失败: {e}")

    print("\n=== ASK 测试 ===")
    for q in ["附近有什么好吃的", "西安科技大学骊山校区附近有什么景点"]:
        print(f"\n「{q}」")
        d = ask(q)
        if d:
            print(f"  intent={d.get('intent')} POI={len(d.get('pois') or [])} "
                  f"耗时={d.get('elapsed')}s")
            for p in (d.get("pois") or [])[:3]:
                print(f"    {p['name']}  {p.get('distance')}m")
            if not d.get("pois"):
                print(f"  答案: {(d.get('answer') or '')[:100]}")


if __name__ == "__main__":
    main()
