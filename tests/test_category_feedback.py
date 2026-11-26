"""验证品类搜索 + 反馈接口（线上）。"""

import json
import urllib.request

BASE = "https://agent-city.site:8443"


def ask(q: str) -> dict | None:
    body = json.dumps({"question": q, "city": "西安市",
                       "origin_lat": 34.3667, "origin_lon": 109.2157,
                       "origin_name": "我的位置"}, ensure_ascii=False).encode()
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
    cases = [
        "在附近找点儿KTV",
        "附近有健身房吗",
        "附近有美甲店吗",
        "附近能去哪玩",
        "附近有什么好吃的",
    ]
    for q in cases:
        print("=" * 60)
        print(f"「{q}」")
        print("=" * 60)
        d = ask(q)
        if not d:
            continue
        pois = d.get("pois") or []
        print(f"  intent={d.get('intent')} POI={len(pois)}")
        for line in (d.get("tool_log") or []):
            if "品类" in line or "搜索" in line:
                print(f"    · {line}")
        for p in pois[:5]:
            print(f"    {p['name']}  [{p.get('type')}]  {p.get('distance')}m")
        print()

    # 反馈接口
    print("=" * 60)
    print("反馈接口")
    print("=" * 60)
    body = json.dumps({
        "comment": "自动化测试：验证反馈接口能写入",
        "question": "测试问题",
        "answer": "测试回答",
        "history": [{"role": "user", "content": "测试问题"}],
        "tool_log": ["步骤1", "步骤2"],
        "version": "test",
        "ua": "python",
    }, ensure_ascii=False).encode()
    req = urllib.request.Request(
        f"{BASE}/api/feedback", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"  {r.read().decode()}")
    except Exception as e:  # noqa: BLE001
        print(f"  失败: {e}")


if __name__ == "__main__":
    main()
