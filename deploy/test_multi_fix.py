"""测多轮污染是否修好：连续问不同的意图。"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import paramiko

ENV = Path(__file__).resolve().parent / ".deploy_env"

SCRIPT = r'''cd ~/city-agent && .venv/bin/python - <<'PY'
import json, urllib.request

BASE = "http://127.0.0.1:8000"
history = []

def ask(q):
    global history
    payload = {"question": q, "city": "西安市",
               "origin_lat": 34.3667, "origin_lon": 109.2157,
               "origin_name": "我的位置",
               "history": history[-6:]}
    body = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(BASE + "/api/ask", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read())
    history.append({"role": "user", "content": q})
    history.append({"role": "assistant", "content": d.get("answer", "")[:200]})
    return d

# 模拟用户的连续提问
qs = [
    "附近有什么好吃的",
    "附近能去哪玩",
    "附近有什么景点",
    "附近有什么喝的",
    "附近吃什么",
]

for q in qs:
    d = ask(q)
    pois = d.get("pois") or []
    print(f"「{q}」")
    print(f"   intent={d.get('intent')} POI={len(pois)} 耗时={d.get('elapsed')}s")
    for p in pois[:2]:
        print(f"      {p['name']}  [{p.get('type')}]")
    print()
PY'''


def load_env() -> dict:
    cfg = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def main() -> None:
    cfg = load_env()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(cfg["HOST"], username=cfg["USER"], password=cfg["PASS"], timeout=20)
    _, out, err = client.exec_command(SCRIPT, timeout=600)
    print(out.read().decode("utf-8", "replace"))
    e = err.read().decode("utf-8", "replace")
    if e.strip():
        print("[stderr]", e.rstrip()[-600:])
    client.close()


if __name__ == "__main__":
    main()
