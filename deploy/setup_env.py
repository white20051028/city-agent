"""在服务器上：建 .env + 装 Python 依赖（venv）。"""

from __future__ import annotations

import sys
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


# 服务器上的 .env（key 从本地 .env 读，不写死在脚本里）
def read_local_env() -> dict:
    local = Path(__file__).resolve().parent.parent / ".env"
    d = {}
    for line in local.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def run(client, cmd: str, timeout: int = 600) -> tuple[str, str, int]:
    print(f"\n$ {cmd[:100]}{'...' if len(cmd) > 100 else ''}")
    print("-" * 60)
    _, out, err = client.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    code = out.channel.recv_exit_status()
    if o.strip():
        print(o.rstrip()[-2000:])
    if e.strip():
        print("[stderr]", e.rstrip()[-1000:])
    if code != 0:
        print(f"[exit code: {code}]")
    return o, e, code


def main() -> None:
    cfg = load_env()
    keys = read_local_env()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(cfg["HOST"], username=cfg["USER"], password=cfg["PASS"], timeout=20)

    # ① 写 .env
    env_content = (
        f"AMAP_KEY={keys['AMAP_KEY']}\n"
        f"AMAP_JS_KEY={keys['AMAP_JS_KEY']}\n"
        f"DEEPSEEK_API_KEY={keys['DEEPSEEK_API_KEY']}\n"
    )
    sftp = client.open_sftp()
    with sftp.file("/home/ubuntu/city-agent/.env", "w") as f:
        f.write(env_content)
    sftp.close()
    run(client, "ls -l ~/city-agent/.env && wc -l ~/city-agent/.env")

    # ② 建 venv
    run(client, "cd ~/city-agent && python3 -m venv .venv && .venv/bin/pip install -q --upgrade pip")

    # ③ 装依赖
    pkgs = "fastapi uvicorn openai mcp langgraph pydantic"
    run(client, f"cd ~/city-agent && .venv/bin/pip install -q {pkgs} 2>&1 | tail -5", timeout=900)

    # ④ 验证
    run(client, "cd ~/city-agent && .venv/bin/python -c "
                "'import fastapi,uvicorn,openai,mcp,langgraph;"
                "print(\"fastapi\",fastapi.__version__);"
                "print(\"langgraph\",__import__(\"importlib.metadata\",fromlist=[\"x\"]).version(\"langgraph\"))'")

    client.close()
    print("\n完成")


if __name__ == "__main__":
    main()
