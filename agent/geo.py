"""城市定位与选择。

**为什么需要城市**：
  用户说「骊山校区」，不带上城市，高德会匹配到：
    city=''        → 新疆乌鲁木齐头屯河区骊山  ❌
    city='陕西省'   → 安康市汉滨区骊山        ❌（省内有同名）
    city='西安'     → 临潼骊山               ✅
  所以必须精确到地级市。

**方案**：
  省份列表 + 每省主要城市（静态 JSON，34 省约 100 个城市，零 API 调用）
  默认城市用 IP 定位（失败 fallback 到西安市）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import amap

ROOT = Path(__file__).resolve().parent.parent
CITIES_FILE = ROOT / "data" / "cities.json"

# IP 定位失败时的兜底
FALLBACK = {"province": "陕西省", "city": "西安市", "source": "fallback"}


def city_map() -> dict[str, list[str]]:
    """读静态省市表：{"陕西省": ["西安市", ...], ...}。"""
    return json.loads(CITIES_FILE.read_text(encoding="utf-8"))


def ip_location() -> dict:
    """用高德 IP 定位拿当前城市。

    返回 {"province", "city", "source"}；失败返回 FALLBACK，不抛异常。
    **本地开发时会失败**（127.0.0.1 没有公网 IP），部署到服务器才准。
    """
    try:
        data = amap._request("ip")  # noqa: SLF001
    except Exception:  # noqa: BLE001
        return dict(FALLBACK)

    province = data.get("province") or ""
    city = data.get("city") or ""

    # 高德 IP 定位返回的是数组（有时），转成字符串
    if isinstance(province, list):
        province = province[0] if province else ""
    if isinstance(city, list):
        city = city[0] if city else ""

    if not city:
        return dict(FALLBACK)

    # 直辖市：city 可能为空，用 province 补
    if not city and province:
        city = province

    # 校验：city 必须在静态表里，否则用 fallback
    try:
        table = city_map()
        if city not in sum(table.values(), []):
            # 用省里的第一个城市兜底
            if province in table:
                city = table[province][0]
            else:
                return dict(FALLBACK)
    except Exception:  # noqa: BLE001
        return dict(FALLBACK)

    return {"province": province, "city": city, "source": "ip"}


def list_cities() -> dict:
    """给前端用的省市表 + 默认城市。"""
    return {
        "map": city_map(),
        "default": ip_location(),
    }
