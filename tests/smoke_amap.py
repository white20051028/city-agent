"""跑通第一步：验证 amap.py 的五个函数都能用。

跑法（在 D:\\桌面\\city-agent 下）：
    E:\\anaconda3\\envs\\llm-rag\\python.exe -X utf8 tests\\smoke_amap.py

期望：五个函数各打印一行 OK 或数据。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import amap


def main() -> None:
    # ① 地理编码
    print("=" * 60)
    print("① geocode：西安科技大学骊山校区")
    print("=" * 60)
    place = amap.geocode("西安科技大学骊山校区", city="西安")
    assert place, "地理编码失败"
    print(f"  {place['address']}")
    print(f"  坐标 {place['location']}  级别 {place['level']}")
    loc = place["location"]

    # ② 周边搜索：餐饮
    print()
    print("=" * 60)
    print("② search_around：2km 内餐饮")
    print("=" * 60)
    foods = amap.search_around(loc, "050000", radius=2000)
    print(f"  返回 {len(foods)} 条")
    for f in foods[:5]:
        r = f["rating"] if f["rating"] is not None else "无"
        c = f["cost"] if f["cost"] is not None else "无"
        print(f"    · {f['name']}  {f['distance']}m  评分{r}  人均{c}")

    # ③ 周边搜索：景点（半径扩到 5km）
    print()
    print("=" * 60)
    print("③ search_around：5km 内景点")
    print("=" * 60)
    sights = amap.search_around(loc, "110000", radius=5000)
    print(f"  返回 {len(sights)} 条")
    for s in sights[:5]:
        r = s["rating"] if s["rating"] is not None else "无"
        print(f"    · {s['name']}  {s['distance']}m  评分{r}  {s['type']}")

    # ④ 关键字搜索
    print()
    print("=" * 60)
    print("④ search_text：榆林的景点（全城）")
    print("=" * 60)
    city_sights = amap.search_text("景点", city="榆林", poi_type="110000")
    print(f"  返回 {len(city_sights)} 条")
    for s in city_sights[:5]:
        r = s["rating"] if s["rating"] is not None else "无"
        print(f"    · {s['name']}  评分{r}  {s['address']}")

    # ⑤ 路线 + 天气
    print()
    print("=" * 60)
    print("⑤ get_route / get_weather")
    print("=" * 60)
    if foods:
        dest = foods[0]["location"]
        route = amap.get_route(loc, dest, mode="walking")
        if route:
            print(f"  步行到「{foods[0]['name']}」：{route['distance']}m，{route['duration']}秒")
    w = amap.get_weather("610115")
    if w:
        print(f"  临潼天气：{w['weather']} {w['temperature']}℃ {w['wind']}")

    print()
    print("全部通过。")


if __name__ == "__main__":
    main()
