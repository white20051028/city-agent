"""服务器上跑一次真实问答，验证高德 key / DeepSeek key 都通。"""

from __future__ import annotations

from pathlib import Path

import paramiko

ENV = Path(__file__).resolve().parent / ".deploy_env"

SCRIPT = r'''cd ~/city-agent && .venv/bin/python - <<'PY'
import json, urllib.request

def ask(q):
    body = json.dumps({"question": q, "city": "西安市"}, ensure_ascii=False).encode()
    req = urllib.request.Request("http://127.0.0.1:8000/api/ask", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())

for q in ["骊山校区附近有什么好吃的", "骊山校区附近有什么景点"]:
    try:
        d = ask(q)
        print(f"Q: {q}")
        print(f"   intent={d.get('intent')} POI={len(d.get('pois') or [])} 耗时={d.get('elapsed')}s")
        for p in (d.get("pois") or [])[:3]:
            print(f"     {p['name']}  {p.get('distance')}m  ⭐{p.get('rating')}")
    except Exception as e:
        print(f"Q: {q}  → 失败: {type(e).__name__}: {e}")
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

    _, out, err = client.exec_command(SCRIPT, timeout=300)
    print(out.read().decode("utf-8", "replace"))
    e = err.read().decode("utf-8", "replace")
    if e.strip():
        print("[stderr]", e.rstrip()[-1500:])

    client.close()


if __name__ == "__main__":
    main()
