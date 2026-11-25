"""通过 SSH 执行命令的小工具（部署用）。

用法：
    python deploy/remote.py "命令1" "命令2"

凭据从 deploy/.deploy_env 读（不进 git）：
    HOST=192.144.254.52
    USER=root
    PASS=xxxx
"""

from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ENV = Path(__file__).resolve().parent / ".deploy_env"


def load_env() -> dict:
    cfg = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k.strip()] = v.strip()
    return cfg


def run(commands: list[str], timeout: int = 300) -> None:
    cfg = load_env()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(cfg["HOST"], username=cfg.get("USER", "root"),
                   password=cfg["PASS"], timeout=20)

    for cmd in commands:
        print(f"\n$ {cmd}")
        print("-" * 60)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if out.strip():
            print(out.rstrip())
        if err.strip():
            print("[stderr]", err.rstrip())
        code = stdout.channel.recv_exit_status()
        if code != 0:
            print(f"[exit code: {code}]")

    client.close()


if __name__ == "__main__":
    cmds = sys.argv[1:]
    if not cmds:
        print("用法: python deploy/remote.py \"命令\"")
        sys.exit(1)
    run(cmds)
