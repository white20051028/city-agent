"""城市探索 Agent 的 MCP Server。

把 amap.py 的五个函数暴露成 MCP 工具，任何支持 MCP 的客户端
（Cherry Studio / Claude Desktop / 我们自己的 Agent）都能调用。

跑法（stdio 模式，由客户端启动）：
    E:\\anaconda3\\envs\\llm-rag\\python.exe -X utf8 tools\\mcp_server.py

手动验证（用 mcp 自带的 client 测）：
    E:\\anaconda3\\envs\\llm-rag\\python.exe -X utf8 tests\\test_mcp_client.py

注意：用的是 mcp 2.x 的 MCPServer（旧版叫 FastMCP）。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 让 `python tools/mcp_server.py` 也能 import 到 tools.amap
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.mcpserver import MCPServer

from tools import amap


def _fmt_pois(pois: list[dict]) -> str:
    """把 POI 列表压成一行一个的紧凑文本。

    为什么不用 JSON：25 条 POI 的完整 JSON 是 6267 字符，
    精简 JSON 是 3651，而这种文本只要 1816——省 71% 的 token。

    格式：序号. 名称 | 类型 | 距离 | 评分 | 人均 | 经纬度
    """
    if not pois:
        return "（没搜到结果）"
    lines = []
    for i, p in enumerate(pois, 1):
        segs = [p.get("name", "?")]
        if p.get("type"):
            segs.append(p["type"])
        if p.get("distance") is not None:
            segs.append(f"{p['distance']}m")
        if p.get("rating") is not None:
            segs.append(f"评分{p['rating']}")
        if p.get("cost") is not None:
            segs.append(f"人均{int(p['cost'])}")
        if p.get("location"):
            segs.append(p["location"])
        lines.append(f"{i}. " + " | ".join(segs))
    return "\n".join(lines)

server = MCPServer(
    name="city-explorer",
    title="城市探索助手",
    description="查询地点周边的景点、美食、娱乐、住宿，以及路线和天气",
    instructions=(
        "所有数据来自高德地图。poi_type 取值："
        "050000=餐饮、110000=景点、080000=娱乐、100000=住宿、061000=商业街。"
        "附近搜索用 search_pois；全城搜索用 search_city。"
    ),
    version="0.1.0",
)


# ---------------------------------------------------------------- 工具定义

@server.tool()
def resolve_location(name: str, city: str = "") -> dict:
    """把地点名（如「西安科技大学骊山校区」）转成经纬度坐标。

    返回 {location, address, level}。查不到返回 {"error": ...}。
    """
    try:
        result = amap.geocode(name, city=city or None)
    except RuntimeError as e:
        return {"error": str(e)}
    if not result:
        return {"error": f"查不到地点「{name}」"}
    return result


@server.tool()
def search_pois(location: str, poi_type: str, radius: int = 2000,
                sort: str = "0") -> str:
    """在某坐标附近搜索 POI（周边搜索）。返回紧凑文本，一行一个。

    参数：
        location: "经度,纬度"
        poi_type: 050000=餐饮 / 110000=景点 / 080000=娱乐 /
                  100000=住宿 / 061000=商业街
        radius: 半径（米），默认 2000
        sort: "0"=距离优先，"1"=综合优先
    每行格式：序号. 名称 | 类型 | 距离 | 评分 | 人均 | 经纬度
    """
    try:
        pois = amap.search_around(location, poi_type, radius=radius, sort=sort)
    except RuntimeError as e:
        return f"搜索失败：{e}"
    return _fmt_pois(pois)


@server.tool()
def search_city(keywords: str, city: str, poi_type: str = "") -> str:
    """在全城范围按关键字搜索（适合「XX 市有什么景点」）。返回紧凑文本。

    参数：
        keywords: 搜索词，如「景点」「美食」
        city: 城市名或 adcode，如「榆林」或「610800」
        poi_type: 可选，限制类型
    """
    try:
        pois = amap.search_text(keywords, city=city, poi_type=poi_type or None)
    except RuntimeError as e:
        return f"搜索失败：{e}"
    return _fmt_pois(pois)


@server.tool()
def get_route(origin: str, destination: str, mode: str = "walking") -> dict:
    """算两点之间的路线。

    参数：
        origin / destination: "经度,纬度"
        mode: "walking" 或 "driving"
    返回 {"distance": 米, "duration": 秒, "mode": ...}。
    """
    if mode not in ("walking", "driving"):
        return {"error": f"不支持的 mode: {mode}，只能是 walking / driving"}
    try:
        route = amap.get_route(origin, destination, mode=mode)
    except RuntimeError as e:
        return {"error": str(e)}
    if not route:
        return {"error": "算不出路线（可能距离太远或没有路网数据）"}
    return route


@server.tool()
def get_weather(city: str) -> dict:
    """查某个城市的当前天气。city 传城市名或 adcode。"""
    try:
        w = amap.get_weather(city)
    except RuntimeError as e:
        return {"error": str(e)}
    if not w:
        return {"error": f"查不到「{city}」的天气"}
    return w


if __name__ == "__main__":
    server.run()
