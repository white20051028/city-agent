"""测多轮：第一轮反问，第二轮带着历史回答。"""

from __future__ import annotations

import json
import sys
import urllib.request

sys.path.insert(0, r"D:\桌面\city-agent")

BASE = "http://127.0.0.1:8000"


def ask(question: str, history: list | None = None, **extra) -> dict:
    payload = {"question": question, "city": "西安市",
               "history": history or [], **extra}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/ask", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def show(label: str, d: dict) -> None:
    print(f"  intent={d.get('intent')} POI={len(d.get('pois') or [])} "
          f"耗时={d.get('elapsed')}s")
    for p in (d.get("pois") or [])[:4]:
        print(f"    {p['name']}  {p.get('distance')}m  ⭐{p.get('rating')}  "
              f"人均{p.get('cost')}")
    if not d.get("pois"):
        print(f"    答案: {(d.get('answer') or '')[:100]}")

    print()


def main() -> None:
    origin = {"origin_lat": 34.3667, "origin_lon": 109.2157,
              "origin_name": "西安科技大学骊山校区"}

    # 第一轮：模糊问题，应该反问
    print("=" * 62)
    print("第 1 轮：纪念日，人均150，安静点")
    print("=" * 62)
    r1 = ask("纪念日，人均150，安静点", **origin)
    show("", r1)
    answer1 = r1.get("answer", "")

    # 第二轮：带历史 + 用户的补充
    print("=" * 62)
    print("第 2 轮：安静点的餐厅（带第 1 轮的历史）")
    print("=" * 62)
    history = [
        {"role": "user", "content": "纪念日，人均150，安静点"},
        {"role": "assistant", "content": answer1},
    ]
    r2 = ask("安静点的餐厅", history=history, **origin)
    show("", r2)

    # 对比：不带历史直接问「安静点的餐厅」
    print("=" * 62)
    print("对照组：安静点的餐厅（不带历史）")
    print("=" * 62)
    r3 = ask("安静点的餐厅", **origin)
    show("", r3)


if __name__ == "__main__":
    main()
