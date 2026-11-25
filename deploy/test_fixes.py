"""测三个之前失败的情况。"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import paramiko

ENV = Path(__file__).resolve().parent / ".deploy_env"

SCRIPT = r'''cd ~/city-agent && .venv/bin/python - <<'PY'
import json, urllib.request

def ask(payload):
    body = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request("http://127.0.0.1:8000/api/ask", data=body,
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read()), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

cases = [
    ("手机端场景：无起点无定位，问两小时玩",
     {"question": "附近两小时能去哪玩", "city": "西安市"}),
    ("华阳城（之前 500）",
     {"question": "华阳城附近有啥好吃的", "city": "西安市"}),
    ("华阳城 + 起点输入",
     {"question": "附近有啥好吃的", "city": "西安市",
      "origin_name": "华阳城"}),
]

for label, payload in cases:
    d, err = ask(payload)
    print(f"【{label}】")
    if err:
        print(f"   ❌ {err}")
    else:
        print(f"   intent={d.get('intent')} POI={len(d.get('pois') or [])} 耗时={d.get('elapsed')}s")
        for p in (d.get("pois") or [])[:3]:
            print(f"      {p['name']}  {p.get('distance')}m  ⭐{p.get('rating')}")
        if not d.get("pois"):
            print(f"      答案: {(d.get('answer') or '')[:80]}")
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
    _, out, err = client.exec_command(SCRIPT, timeout=400)
    print(out.read().decode("utf-8", "replace"))
    e = err.read().decode("utf-8", "replace")
    if e.strip():
        print("[stderr]", e.rstrip()[-800:])
    client.close()


if __name__ == "__main__":
    main()
