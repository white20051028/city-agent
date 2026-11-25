"""打包 + 上传 + 解压。

用 tar（不用 zip，之前踩过 Windows zip 反斜杠的坑）。
.env 不上传 —— 服务器上单独生成。
"""

from __future__ import annotations

import tarfile
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent.parent
ENV = Path(__file__).resolve().parent / ".deploy_env"
TARBALL = Path(__file__).resolve().parent / "city-agent.tar.gz"

# 不打进包里的
EXCLUDE_DIRS = {"__pycache__", ".git", "cache", "node_modules"}
EXCLUDE_FILES = {".env", "city-agent.tar.gz"}
EXCLUDE_EXT = {".pyc", ".log"}


def load_env() -> dict:
    cfg = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def make_tarball() -> Path:
    with tarfile.open(TARBALL, "w:gz") as tar:
        for p in ROOT.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT)
            parts = set(rel.parts)
            if parts & EXCLUDE_DIRS:
                continue
            if p.name in EXCLUDE_FILES or p.suffix in EXCLUDE_EXT:
                continue
            # deploy/.deploy_env 也不能传
            if str(rel).replace("\\", "/") == "deploy/.deploy_env":
                continue
            tar.add(p, arcname=str(rel).replace("\\", "/"))
    return TARBALL


def upload_and_extract(cfg: dict) -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(cfg["HOST"], username=cfg["USER"], password=cfg["PASS"], timeout=20)

    sftp = client.open_sftp()
    remote = "/tmp/city-agent.tar.gz"
    print(f"上传 {TARBALL.name} ({TARBALL.stat().st_size / 1024:.0f} KB) → {remote}")
    sftp.put(str(TARBALL), remote)
    sftp.close()

    cmds = [
        "mkdir -p ~/city-agent",
        "tar -xzf /tmp/city-agent.tar.gz -C ~/city-agent",
        "rm -f /tmp/city-agent.tar.gz",
        "ls -la ~/city-agent | head -15",
        "du -sh ~/city-agent",
    ]
    for cmd in cmds:
        print(f"\n$ {cmd}")
        _, out, err = client.exec_command(cmd, timeout=120)
        o = out.read().decode("utf-8", "replace")
        e = err.read().decode("utf-8", "replace")
        if o.strip():
            print(o.rstrip())
        if e.strip():
            print("[stderr]", e.rstrip())

    client.close()


if __name__ == "__main__":
    cfg = load_env()
    tb = make_tarball()
    print(f"打包完成: {tb} ({tb.stat().st_size / 1024:.0f} KB)")
    upload_and_extract(cfg)
    print("\n完成")
