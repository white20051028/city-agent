"""在服务器上手动跑一次 server.py，验证能不能启动 + 能不能查高德。"""

from __future__ import annotations

import time
from pathlib import Path

import paramiko

ENV = Path(__file__).resolve().parent / ".deploy_env"


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

    def run(cmd: str, timeout: int = 120) -> str:
        print(f"\n$ {cmd[:110]}")
        print("-" * 60)
        _, out, err = client.exec_command(cmd, timeout=timeout)
        o = out.read().decode("utf-8", "replace")
        e = err.read().decode("utf-8", "replace")
        if o.strip():
            print(o.rstrip()[-3000:])
        if e.strip():
            print("[stderr]", e.rstrip()[-1500:])
        return o

    # 后台启动，等 12 秒
    run("cd ~/city-agent && nohup .venv/bin/python -X utf8 server.py "
        "> /tmp/server.log 2>&1 & echo started")
    time.sleep(12)

    run("cat /tmp/server.log | tail -20")
    run("curl -s --max-time 10 http://127.0.0.1:8000/health || echo '健康检查失败'")
    run("curl -s --max-time 10 'http://127.0.0.1:8000/api/cities' | head -c 300")

    # 真问一次（用 Python 发，避免 shell 中文编码问题）
    run("""cd ~/city-agent && .venv/bin/python - <<'PY'
import json, urllib.request
body = json.dumps({"question": "骊山校区附近有什么好吃的", "city": "西安市"},
                  ensure_ascii=False).encode()
req = urllib.request.Request("http://127.0.0.1:8000/api/ask", data=body,
    headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
with urllib.request.urlopen(req, timeout=120) as r:
    d = json.loads(r.read())
print("intent:", d.get("intent"), "| POI:", len(d.get("pois") or []), "| 耗时:", d.get("elapsed"))
for p in (d.get("pois") or [])[:3]:
    print("  ", p["name"], p.get("distance"), "m")
PY""", timeout=180)

    client.close()


if __name__ == "__main__":
    main()
