"""高德地图 API 封装。

只做四件事：
  1. 发请求（带节流、重试、错误识别）
  2. 缓存（同参数 5 分钟内不重复调）
  3. 把高德的响应整理成统一的 dict
  4. 提供五个高层函数：geocode / search_around / search_text / get_route / get_weather

**为什么要节流**：高德免费额度约 3 QPS，连续调用会返回
CUQPS_HAS_EXCEEDED_THE_LIMIT；连续超限还会被临时封（返回 SERVICE_NOT_AVAILABLE
约 30 秒）。所以请求间隔固定 1 秒。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://restapi.amap.com/v3"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE_TTL = 300          # 缓存 5 分钟
MIN_INTERVAL = 1.0       # 两次请求最小间隔（秒）

_last_call = [0.0]


# ---------------------------------------------------------------- 底层

def _api_key() -> str:
    """从环境变量或 .env 读 key。没有就报错，不返回空串。"""
    key = os.environ.get("AMAP_KEY", "").strip()
    if key:
        return key
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("AMAP_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("缺少 AMAP_KEY：请在项目根目录 .env 里写 AMAP_KEY=<你的key>")


def _throttle() -> None:
    """保证两次请求间隔至少 MIN_INTERVAL 秒。"""
    gap = time.monotonic() - _last_call[0]
    if gap < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - gap)
    _last_call[0] = time.monotonic()


def _cache_path(url: str) -> Path:
    """把 URL 哈希成文件名。"""
    h = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{h}.json"


def _read_cache(url: str):
    """读缓存。过期或不存在返回 None。"""
    p = _cache_path(url)
    if not p.exists():
        return None
    if time.time() - p.stat().st_mtime > CACHE_TTL:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(url: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(url).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _request(path: str, retries: int = 3, **params) -> dict:
    """发一次请求，带缓存 + 节流 + 限流重试。

    返回高德的原始 JSON（dict）。失败抛异常，不返回 None，
    免得调用方以为「没结果」。
    """
    params["key"] = _api_key()
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)

    cached = _read_cache(url)
    if cached is not None:
        return cached

    last_err = ""
    for _ in range(retries):
        _throttle()
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                data = json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001 网络异常统一重试
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(1.0)
            continue

        info = data.get("info", "")
        # 限流：等久一点再重试
        if "QPS" in info or "LIMIT" in info:
            last_err = info
            time.sleep(2.0)
            continue
        # 临时封禁：等 30 秒
        if info == "SERVICE_NOT_AVAILABLE":
            last_err = info
            time.sleep(30.0)
            continue
        # 服务端瞬时错误：重试（实测会偶发 30001，重试一次基本就过）
        if "ENGINE_RESPONSE" in info or data.get("infocode") == "30001":
            last_err = info
            time.sleep(1.5)
            continue
        # 其他错误：直接抛，不浪费配额
        if data.get("status") != "1":
            raise RuntimeError(f"高德返回错误: {info} ({data.get('infocode')})")

        _write_cache(url, data)
        return data

    raise RuntimeError(f"高德请求重试 {retries} 次仍失败: {last_err}")


# ---------------------------------------------------------------- 五个高层函数

def geocode(address: str, city: str | None = None) -> dict | None:
    """地点名 → 坐标。

    返回 {"name": ..., "location": "经度,纬度", "address": ...}；
    查不到返回 None（不是抛异常，"查不到"是正常结果）。
    """
    params = {"address": address}
    if city:
        params["city"] = city
    data = _request("geocode/geo", **params)
    geos = data.get("geocodes") or []
    if not geos:
        return None
    g = geos[0]
    return {
        "name": address,
        "location": g.get("location"),
        "address": g.get("formatted_address"),
        "level": g.get("level"),
        # adcode 用于「按行政区搜景点」：临潼区 = 610115
        "adcode": g.get("adcode"),
        "city": g.get("city"),
        "district": g.get("district"),
    }


def regeo(location: str) -> dict | None:
    """逆地理编码：坐标 → 地址 + 行政区。

    **别用 geocode 反查**：geocode 是「地址→坐标」，
    传坐标进去它会把 "109.2225,34.3672" 当成地址字符串去匹配，
    实测匹配到了江苏张家港（离谱）。
    """
    data = _request("geocode/regeo", location=location, extensions="base")
    rc = data.get("regeocode") or {}
    comp = rc.get("addressComponent") or {}
    if not rc:
        return None
    return {
        "address": rc.get("formatted_address"),
        "province": comp.get("province"),
        "city": comp.get("city") or comp.get("province"),
        "district": comp.get("district"),
        "adcode": comp.get("adcode"),
    }


def _poi_brief(p: dict) -> dict:
    """把高德 POI 压成我们需要的字段，丢掉没用的。"""
    biz = p.get("biz_ext") or {}
    if not isinstance(biz, dict):
        biz = {}
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "type": (p.get("type") or "").split(";")[-1],
        "typecode": p.get("typecode"),
        "address": p.get("address"),
        "distance": int(p["distance"]) if str(p.get("distance", "")).isdigit() else None,
        "location": p.get("location"),
        "rating": float(biz["rating"]) if str(biz.get("rating", "")).replace(".", "").isdigit() else None,
        "cost": float(biz["cost"]) if str(biz.get("cost", "")).replace(".", "").isdigit() else None,
        "open_time": biz.get("open_time") or None,
        "business_area": p.get("business_area") or None,
    }


def search_around(location: str, poi_type: str, radius: int = 2000,
                  page: int = 1, sort: str = "0") -> list[dict]:
    """周边搜索：以 location 为中心，radius 米内某类 POI。

    poi_type: 050000 餐饮 / 110000 景点 / 080000 娱乐 / 100000 住宿 / 061000 商业街
    sort: 0=距离优先，1=综合优先
    """
    data = _request("place/around", location=location, types=poi_type,
                    radius=radius, offset=25, page=page, sortrule=sort,
                    extensions="all")
    return [_poi_brief(p) for p in (data.get("pois") or [])]


def search_text(keywords: str, city: str, poi_type: str | None = None,
                page: int = 1) -> list[dict]:
    """关键字搜索：全城范围，适合「XX 市有什么景点」这类问题。"""
    params = {"keywords": keywords, "city": city, "offset": 25,
              "page": page, "extensions": "all"}
    if poi_type:
        params["types"] = poi_type
    data = _request("place/text", **params)
    return [_poi_brief(p) for p in (data.get("pois") or [])]


def get_route(origin: str, destination: str, mode: str = "walking") -> dict | None:
    """两点之间的路线。mode: walking / driving。

    返回 {"distance": 米, "duration": 秒}；算不出返回 None。
    """
    data = _request(f"direction/{mode}", origin=origin, destination=destination)
    paths = (data.get("route") or {}).get("paths") or []
    if not paths:
        return None
    p = paths[0]
    return {
        "mode": mode,
        "distance": int(p.get("distance", 0)),
        "duration": int(p.get("duration", 0)),
    }


def get_weather(city: str) -> dict | None:
    """当前天气。city 传 adcode（如 610800）或城市名。"""
    data = _request("weather/weatherInfo", city=city, extensions="base")
    lives = data.get("lives") or []
    if not lives:
        return None
    w = lives[0]
    return {
        "city": w.get("city"),
        "weather": w.get("weather"),
        "temperature": w.get("temperature"),
        "wind": f"{w.get('winddirection')}风 {w.get('windpower')}级",
        "report_time": w.get("reporttime"),
    }
