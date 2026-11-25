"""方案 B：nginx + 自签证书，https://IP:8443

为什么用 8443 而不是 443：
  国内服务器用 443 需要备案。8443 是非标端口，不触发备案检查。
  自签证书下浏览器会警告，但点「继续前往」后 isSecureContext=true，
  navigator.geolocation 可用（这是"定位能用"的关键）。
"""

from __future__ import annotations

from pathlib import Path

import paramiko

ENV = Path(__file__).resolve().parent / ".deploy_env"

NGINX_CONF = r"""server {
    listen 8443 ssl;
    server_name _;

    ssl_certificate     /etc/nginx/ssl/city-agent.crt;
    ssl_certificate_key /etc/nginx/ssl/city-agent.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    # 单次问可能要 10 秒以上，超时放宽
    proxy_read_timeout 180s;
    proxy_send_timeout 180s;
    proxy_connect_timeout 30s;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
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

    def run(cmd: str, timeout: int = 120) -> str:
        print(f"\n$ {cmd[:110]}")
        print("-" * 60)
        _, out, err = client.exec_command(cmd, timeout=timeout)
        o = out.read().decode("utf-8", "replace")
        e = err.read().decode("utf-8", "replace")
        if o.strip():
            print(o.rstrip()[-2000:])
        if e.strip():
            print("[stderr]", e.rstrip()[-1200:])
        return o

    # ① 生成自签证书（CN 用 IP，有效期 10 年）
    run(
        "sudo mkdir -p /etc/nginx/ssl && "
        "sudo openssl req -x509 -nodes -newkey rsa:2048 -days 3650 "
        "-keyout /etc/nginx/ssl/city-agent.key "
        "-out /etc/nginx/ssl/city-agent.crt "
        "-subj '/C=CN/ST=Shaanxi/L=Xian/O=CityAgent/CN=192.144.254.52' 2>&1 | tail -3"
    )
    run("sudo ls -l /etc/nginx/ssl/")

    # ② 写 nginx 配置
    sftp = client.open_sftp()
    with sftp.file("/tmp/city-agent.conf", "w") as f:
        f.write(NGINX_CONF)
    sftp.close()
    run("sudo mv /tmp/city-agent.conf /etc/nginx/sites-available/city-agent.conf")
    run("sudo ln -sf /etc/nginx/sites-available/city-agent.conf /etc/nginx/sites-enabled/city-agent.conf")
    run("sudo nginx -t 2>&1 | tail -5")
    run("sudo systemctl reload nginx")
    run("sudo systemctl status nginx --no-pager | head -5")

    # ③ 开防火墙（腾讯云轻量有 ufw 和云控制台两层）
    run("sudo ufw status | head -3 || echo '无 ufw'")
    run("sudo ufw allow 8443/tcp 2>&1 | tail -2 || true")

    # ④ 本机验证
    run("curl -sk --max-time 10 https://127.0.0.1:8443/health || echo 'HTTPS 健康检查失败'")
    run("curl -sk --max-time 10 https://127.0.0.1:8443/ | head -c 200")

    client.close()
    print("\n完成。注意：腾讯云控制台的「防火墙」还要放行 8443（Web 控制台 > 防火墙）")


if __name__ == "__main__":
    main()
