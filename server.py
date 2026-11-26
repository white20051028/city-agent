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

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agent import geo  # noqa: E402
from agent.graph import build_graph  # noqa: E402
from tools import amap, asr  # noqa: E402


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


@app.post("/api/feedback")
def feedback(payload: dict) -> dict:
    """收集用户反馈。

    为什么要带上下文：用户说「这个回答不对」时，光有这句话没法排查，
    必须知道他问的什么、我们答的什么、中间 Agent 做了什么。
    """
    import datetime
    import json

    record = {
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "comment": (payload.get("comment") or "").strip()[:2000],
        "question": (payload.get("question") or "")[:500],
        "answer": (payload.get("answer") or "")[:3000],
        "history": payload.get("history") or [],
        "tool_log": payload.get("tool_log") or [],
        "version": payload.get("version") or "",
        "intent": payload.get("intent") or "",
        "ua": (payload.get("ua") or "")[:200],
    }

    fb = ROOT / "data" / "feedback.jsonl"
    fb.parent.mkdir(parents=True, exist_ok=True)
    with fb.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {"ok": True}


@app.get("/api/version")
def version() -> dict:
    """返回代码版本，前端显示在页面底部。

    用文件的 mtime 当版本号——改了就变，比手写 APP_VERSION 可靠
    （之前手写版本号忘了 bump，导致误判「部署没生效」）。
    """
    import datetime
    import subprocess

    files = ["server.py", "agent/nodes.py", "agent/graph.py",
             "static/index.html", "tools/amap.py"]
    latest = 0.0
    for f in files:
        fp = ROOT / f
        if fp.exists():
            latest = max(latest, fp.stat().st_mtime)

    ts = datetime.datetime.fromtimestamp(latest).strftime("%m-%d %H:%M")

    sha = ""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        pass

    return {"version": ts, "sha": sha}


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


@app.post("/api/asr")
async def speech_to_text(request: Request) -> dict:
    """语音识别：接收浏览器录的音频（raw body），返回文字。

    腾讯云限制：≤60 秒，≤3MB。
    前端录的是 webm，后端用 ffmpeg 转 wav 16k。
    """
    body = await request.body()
    if not body:
        return {"ok": False, "text": "", "error": "没有收到音频数据"}

    # 从 Content-Type 判断源格式
    ctype = request.headers.get("content-type", "audio/webm")
    fmt = "webm"
    if "wav" in ctype:
        fmt = "wav"
    elif "mp4" in ctype or "m4a" in ctype:
        fmt = "m4a"
    elif "ogg" in ctype:
        fmt = "ogg"

    import asyncio

    # ffmpeg 是同步阻塞调用，扔到线程池避免卡住事件循环
    result = await asyncio.get_event_loop().run_in_executor(
        None, asr.transcribe, body, fmt
    )
    return result


@app.get("/health")
def health() -> dict:
    return {"ok": True}


# 静态文件：前端页面 + PWA manifest
STATIC = ROOT / "static"
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/sw.js")
def service_worker():
    """Service Worker 必须在根路径 + 带 Service-Worker-Allowed 头，
    否则 scope 只能是 /static/（浏览器限制）。
    """
    sw = STATIC / "sw.js"
    if not sw.exists():
        return HTMLResponse("// sw.js not found", status_code=404,
                            media_type="application/javascript")
    return HTMLResponse(
        sw.read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


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
