"""修 Text file busy：杀旧进程、删旧文件、换个名字传。"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import paramiko

ENV = Path(__file__).resolve().parent / ".deploy_env"
LOCAL_BIN = Path(os.environ.get("TEMP", "C:/Windows/Temp")) / "cloudflared.exe"


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
            print(o.rstrip()[-2500:])
        if e.strip():
            print("[stderr]", e.rstrip()[-800:])
        return o

    # ① 清理
    run("sudo systemctl stop cloudflared 2>/dev/null || true")
    run("pkill -9 -f 'curl.*cloudflared' 2>/dev/null || true")
    run("pkill -9 -f cloudflared 2>/dev/null || true")
    run("sleep 2; sudo rm -f /usr/local/bin/cloudflared /tmp/cloudflared*; echo 已清理")

    # ② 换个名字上传
    print(f"\n上传 ({LOCAL_BIN.stat().st_size / 1e6:.1f} MB)…")
    sftp = client.open_sftp()
    sftp.put(str(LOCAL_BIN), "/tmp/cf-new")
    sftp.close()
    run("ls -l /tmp/cf-new")

    # ③ 安装
    run("sudo install -m 755 /tmp/cf-new /usr/local/bin/cloudflared && "
        "sudo rm -f /tmp/cf-new && cloudflared --version")

    # ④ 启动
    run("sudo systemctl restart cloudflared")
    print("\n等隧道（25 秒）…")
    time.sleep(25)
    log = run("sudo journalctl -u cloudflared -n 80 --no-pager", timeout=60)

    m = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", log)
    if m:
        url = m[-1]
        print(f"\n{'=' * 62}")
        print(f"  Cloudflare 隧道： {url}")
        print(f"{'=' * 62}")
        run(f"curl -s --max-time 25 {url}/health || echo '外网访问失败'", timeout=60)
    else:
        print("\n没抓到 URL")
        run("sudo systemctl status cloudflared --no-pager | head -10")

    client.close()


if __name__ == "__main__":
    main()
