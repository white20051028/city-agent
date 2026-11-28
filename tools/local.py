"""本地文化数据（目前只有榆林）。

为什么单独抽出来：
  高德 API 给的是「POI + 评分 + 地址」，它不知道「镇北台是明万历年间修的」
  「榆林小曲用城内方言演唱」。这些是文化内容，必须自己维护。

数据结构见 data/yulin.json。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YULIN_FILE = ROOT / "data" / "yulin.json"


@lru_cache(maxsize=1)
def _yulin() -> dict:
    """读榆林数据（缓存，只读一次盘）。"""
    if not YULIN_FILE.exists():
        return {}
    try:
        return json.loads(YULIN_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def is_yulin(city: str | None, district: str | None = None,
             adcode: str | None = None) -> bool:
    """判断当前是不是榆林场景。

    adcode 前缀 6108 是榆林市（610802 榆阳区 等）。
    """
    if adcode and str(adcode).startswith("6108"):
        return True
    text = (city or "") + (district or "")
    return "榆林" in text or any(
        d in text for d in ("榆阳", "神木", "府谷", "横山", "靖边",
                            "定边", "绥德", "米脂", "佳县", "吴堡",
                            "清涧", "子洲")
    )


def find_spot(name: str) -> dict | None:
    """按景点名（模糊）查本地典故。"""
    if not name:
        return None
    d = _yulin()
    for s in d.get("景点", []):
        if s["name"] in name or name in s["name"]:
            return s
        for alias in s.get("alias", []):
            if alias in name:
                return s
    return None


def spot_note(name: str) -> str:
    """给一个景点补一句本地文化说明（没有就返回空串）。"""
    s = find_spot(name)
    if not s:
        return ""
    bits = []
    if s.get("desc"):
        bits.append(s["desc"])
    if s.get("ticket") and s["ticket"] != "—":
        bits.append(f"门票 {s['ticket']}")
    if s.get("hours") and s["hours"] != "—":
        bits.append(f"开放 {s['hours']}")
    if s.get("tip"):
        bits.append(s["tip"])
    return "；".join(bits)


def heritage_list() -> list[dict]:
    """榆林国家级非遗列表。"""
    return _yulin().get("非遗", {}).get("items", [])


def heritage_summary() -> str:
    """非遗总览那句话。"""
    return _yulin().get("非遗", {}).get("summary", "")


def food_list() -> list[dict]:
    """榆林特色美食。"""
    return _yulin().get("美食", [])


def six_towers() -> dict:
    """六楼骑街数据。"""
    return _yulin().get("六楼骑街", {})


def yulin_spots() -> list[dict]:
    """榆林本地景点列表（用于补充搜索）。"""
    return _yulin().get("景点", [])


def feature_words() -> tuple[str, ...]:
    """榆林特色关键词（用于打分加权）。"""
    return tuple(_yulin().get("特色关键词", []))


def intro() -> str:
    """榆林总述。"""
    return _yulin().get("intro", "")


def compose_heritage_answer() -> str:
    """「榆林有什么非遗」的答案。"""
    items = heritage_list()
    if not items:
        return ""
    lines = [f"**榆林的国家级非遗（{len(items)} 项，节选）：**", ""]
    for it in items:
        lvl = f"（{it['level']}）" if it.get("level") else ""
        lines.append(f"**{it['name']}**{lvl} · {it.get('area', '')}")
        lines.append(f"　　{it.get('desc', '')}")
    lines.append("")
    lines.append(f"_{heritage_summary()}_")
    return "\n".join(lines)


def compose_food_answer() -> str:
    """「榆林有什么特色吃的」的答案。"""
    items = food_list()
    if not items:
        return ""
    lines = ["**榆林特色吃食（按县区）：**", ""]
    for it in items:
        lines.append(f"**{it['name']}** · {it.get('area', '')}　{it.get('desc', '')}")
    return "\n".join(lines)


def compose_six_towers_answer() -> str:
    """「六楼骑街是哪六楼」的答案。"""
    d = six_towers()
    towers = d.get("from_south_to_north", [])
    if not towers:
        return ""
    lines = ["**榆林古城「六楼骑街」——由南到北：**", ""]
    for i, t in enumerate(towers, 1):
        alias = f"（{t['alias']}）" if t.get("alias") else ""
        lines.append(f"{i}. **{t['name']}**{alias} · {t.get('era', '')}")
    if d.get("note"):
        lines.append("")
        lines.append(f"_{d['note']}_")
    return "\n".join(lines)
