"""测：有定位时哪些问题还能触发追问。"""

from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:8000"
ORIGIN = {"origin_lat": 34.3667, "origin_lon": 109.2157,
          "origin_name": "西安科技大学骊山校区"}

QUESTIONS = [
    "推荐一下",
    "有什么好的",
    "纪念日，人均150，安静点",
    "带父母玩一天",
    "两个人，想庆祝一下",
    "周末想出去",
    "帮我安排一下",
]


def ask(q: str) -> dict:
    payload = {"question": q, "city": "西安市", **ORIGIN}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/ask", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    print("=" * 66)
    print("有定位时，哪些问题会追问")
    print("=" * 66)
    for q in QUESTIONS:
        d = ask(q)
        poi = len(d.get("pois") or [])
        ans = (d.get("answer") or "").replace("\n", " ")[:70]
        if poi == 0 and ans:
            print(f"❓ {q}")
            print(f"   → {ans}")
        else:
            print(f"   {q}  （直接给了 {poi} 个结果）")


if __name__ == "__main__":
    main()
