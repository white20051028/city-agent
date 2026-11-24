"""FastAPI 后端：把 LangGraph 包装成 HTTP 接口。

接口：
  POST /api/ask      {"question": "...", "city": "西安市"}  →  答案 + POI
  GET  /api/cities   →  省市表 + 默认城市（IP 定位）
  GET  /             →  单页前端
  GET  /health       →  健康检查

跑法：
    E:\\anaconda3\\envs\\llm-rag\\python.exe -X utf8 server.py
然后浏览器打开 http://127.0.0.1:8000
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agent import geo  # noqa: E402
from agent.graph import build_graph  # noqa: E402
from tools import amap  # noqa: E402


def _read_env(name: str) -> str:
    """读 .env 里的一个值（不引入 python-dotenv，省依赖）。"""
    v = os.environ.get(name, "").strip()
    if v:
        return v
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    return ""


app = FastAPI(title="城市探索 Agent", version="0.1.0")
_graph = None


def get_graph():
    """懒加载图（编译一次就够了，但避免启动时就编译失败）。"""
    global _graph
    if _graph is None:
        _graph = build_graph(with_critic=True)
    return _graph


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    city: str = Field(default="", max_length=30)   # 用户选的当前城市，如「西安市」
    # 起点：用户拖动地图或输入地名后传坐标过来（优先级高于问题里的地名）
    origin_lat: float | None = None
    origin_lon: float | None = None
    origin_name: str = Field(default="", max_length=60)
    # 之前的对话，用于多轮（反问后用户接着答）
    history: list[dict] = Field(default_factory=list)


@app.post("/api/ask")
def ask(req: AskRequest) -> dict:
    """跑一遍 Agent，返回答案 + 地图用的 POI 列表。"""
    t0 = time.time()
    result = get_graph().invoke({
        "user_input": req.question,
        "user_city": req.city,
        "origin_lat": req.origin_lat,
        "origin_lon": req.origin_lon,
        "origin_name": req.origin_name,
        "history": req.history[-6:],   # 只留最近 6 条，防止无限增长
    })

    # 只把地图要用的字段挑出来（别把整个 state 发给前端）
    pois = []
    for p in result.get("itinerary") or []:
        if not p.get("location"):
            continue
        pois.append({
            "name": p.get("name"),
            "location": p.get("location"),
            "rating": p.get("rating"),
            "cost": p.get("cost"),
            "distance": p.get("distance"),
            "type": p.get("type"),
            "address": p.get("address"),
            "walk_min": p.get("walk_min"),
            "travel": p.get("travel"),
            "sub_spots": p.get("sub_spots") or [],
        })

    return {
        "ok": True,
        "answer": result.get("answer", ""),
        "pois": pois,
        "tool_log": result.get("tool_log", []),
        "intent": result.get("intent"),
        "location": result.get("location"),
        "location_name": result.get("location_name") or result.get("city"),
        "elapsed": round(time.time() - t0, 1),
    }


@app.get("/api/cities")
def cities() -> dict:
    """省市表 + 默认城市（IP 定位，失败 fallback 到西安市）。"""
    return geo.list_cities()


@app.get("/api/geocode")
def geocode_endpoint(place: str, city: str = "") -> dict:
    """地名 → 坐标。前端用来把「起点」输入框里的地名转成坐标。"""
    try:
        r = amap.geocode(place, city=city or None)
    except Exception as e:  # noqa: BLE001 高德挂了不该 500
        return {"ok": False, "error": str(e)}
    if not r:
        return {"ok": False, "error": f"找不到「{place}」"}
    return {"ok": True, "location": r["location"], "address": r.get("address")}


@app.get("/health")
def health() -> dict:
    return {"ok": True}


# 静态文件：前端页面 + PWA manifest
STATIC = ROOT / "static"
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
def index():
    """返回前端页面，把 JS API key 注入进去（不写死在 HTML 里）。"""
    page = STATIC / "index.html"
    if not page.exists():
        return HTMLResponse("<h1>static/index.html 不存在</h1>", status_code=500)
    html = page.read_text(encoding="utf-8").replace(
        "__AMAP_KEY__", _read_env("AMAP_JS_KEY")
    )
    return HTMLResponse(html)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
