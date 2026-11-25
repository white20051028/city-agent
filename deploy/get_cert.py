"""申请 Let's Encrypt 证书（HTTP-01 验证）。

步骤：
  ① 装 certbot
  ② 临时停 nginx（standalone 模式要独占 80）
  ③ certbot certonly --standalone
  ④ 失败就恢复 nginx 并报告
"""

from __future__ import annotations

from pathlib import Path

import paramiko

ENV = Path(__file__).resolve().parent / ".deploy_env"
DOMAIN = "agent-city.site"


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

    def run(cmd: str, timeout: int = 300) -> str:
        print(f"\n$ {cmd[:110]}")
        print("-" * 60)
        _, out, err = client.exec_command(cmd, timeout=timeout)
        o = out.read().decode("utf-8", "replace")
        e = err.read().decode("utf-8", "replace")
        if o.strip():
            print(o.rstrip()[-2500:])
        if e.strip():
            print("[stderr]", e.rstrip()[-1200:])
        return o

    # ① 装 certbot
    run("sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq certbot 2>&1 | tail -3")
    run("certbot --version")

    # ② 先测 80 端口从外网能不能通（用服务器的 curl 测自己不靠谱，直接申请看）
    run("sudo systemctl stop nginx")

    # ③ 申请证书
    out = run(
        f"sudo certbot certonly --standalone --non-interactive --agree-tos "
        f"--email 2271552484@qq.com -d {DOMAIN} -d www.{DOMAIN} "
        f"--keep-until-expiring 2>&1 | tail -25",
        timeout=300,
    )

    # ④ 检查结果
    run("sudo ls -l /etc/letsencrypt/live/ 2>/dev/null || echo '没有证书目录'")

    if "Congratulations" in out or "Certificate not yet due" in out:
        print("\n>>> 证书申请成功")
        run(f"sudo openssl x509 -in /etc/letsencrypt/live/{DOMAIN}/fullchain.pem "
            f"-noout -subject -issuer -dates")
    else:
        print("\n>>> 证书申请失败，恢复 nginx")
        run("sudo systemctl start nginx")

    client.close()


if __name__ == "__main__":
    main()
