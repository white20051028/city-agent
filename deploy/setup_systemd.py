"""配 systemd 服务：city-agent.service

只监听 127.0.0.1:8000，对外由 nginx 代理。
"""

from __future__ import annotations

from pathlib import Path

import paramiko

ENV = Path(__file__).resolve().parent / ".deploy_env"

UNIT = """[Unit]
Description=City Agent (LangGraph + FastAPI)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/city-agent
Environment="PYTHONUNBUFFERED=1"
Environment="MALLOC_ARENA_MAX=2"
ExecStart=/home/ubuntu/city-agent/.venv/bin/python -X utf8 server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""


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

    # 先杀掉之前手动起的进程
    def run(cmd: str, timeout: int = 120, quiet: bool = False) -> str:
        if not quiet:
            print(f"\n$ {cmd[:100]}")
            print("-" * 60)
        _, out, err = client.exec_command(cmd, timeout=timeout)
        o = out.read().decode("utf-8", "replace")
        e = err.read().decode("utf-8", "replace")
        if not quiet:
            if o.strip():
                print(o.rstrip()[-2000:])
            if e.strip():
                print("[stderr]", e.rstrip()[-1000:])
        return o

    run("pkill -f 'python.*server.py' || true; sleep 1; echo 已清理旧进程")

    # 写 unit 文件
    sftp = client.open_sftp()
    with sftp.file("/tmp/city-agent.service", "w") as f:
        f.write(UNIT)
    sftp.close()

    run("sudo mv /tmp/city-agent.service /etc/systemd/system/city-agent.service")
    run("sudo systemctl daemon-reload")
    run("sudo systemctl enable city-agent 2>&1 | tail -3")
    run("sudo systemctl restart city-agent")
    run("sleep 10; sudo systemctl status city-agent --no-pager | head -12")
    run("curl -s --max-time 10 http://127.0.0.1:8000/health || echo '健康检查失败'")
    run("sudo journalctl -u city-agent -n 15 --no-pager | tail -15")

    client.close()
    print("\n完成")


if __name__ == "__main__":
    main()
