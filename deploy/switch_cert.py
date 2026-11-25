"""nginx 换成 Let's Encrypt 真证书。

新配置：
  · 8443 端口，证书用 /etc/letsencrypt/live/agent-city.site/
  · server_name 改成域名（IP 访问也能走，因为只有一个 server 块）
  · 加 80 端口：只用于 certbot 续期验证 + 跳转到 HTTPS
"""

from __future__ import annotations

from pathlib import Path

import paramiko

ENV = Path(__file__).resolve().parent / ".deploy_env"
DOMAIN = "agent-city.site"

NGINX_CONF = f"""# 80 端口：只给 certbot 续期用，其他请求跳 HTTPS
server {{
    listen 80;
    server_name {DOMAIN} www.{DOMAIN} 192.144.254.52;

    location /.well-known/acme-challenge/ {{
        root /var/www/html;
    }}

    location / {{
        return 301 https://$host:8443$request_uri;
    }}
}}

# 8443 端口：Let's Encrypt 真证书
server {{
    listen 8443 ssl;
    server_name {DOMAIN} www.{DOMAIN} 192.144.254.52;

    ssl_certificate     /etc/letsencrypt/live/{DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{DOMAIN}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:SSL:10m;

    proxy_read_timeout 180s;
    proxy_send_timeout 180s;
    proxy_connect_timeout 30s;

    location / {{
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }}
}}
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

    def run(cmd: str, timeout: int = 180) -> str:
        print(f"\n$ {cmd[:110]}")
        print("-" * 60)
        _, out, err = client.exec_command(cmd, timeout=timeout)
        o = out.read().decode("utf-8", "replace")
        e = err.read().decode("utf-8", "replace")
        if o.strip():
            print(o.rstrip()[-2500:])
        if e.strip():
            print("[stderr]", e.rstrip()[-1000:])
        return o

    # ① 写配置
    sftp = client.open_sftp()
    with sftp.file("/tmp/city-agent-new.conf", "w") as f:
        f.write(NGINX_CONF)
    sftp.close()

    run("sudo mv /tmp/city-agent-new.conf /etc/nginx/sites-available/city-agent.conf")
    run("sudo mkdir -p /var/www/html/.well-known/acme-challenge")

    # ② 测试 + reload
    run("sudo nginx -t 2>&1 | tail -4")
    run("sudo systemctl reload nginx")

    # ③ 验证（服务器上用域名访问）
    run(f"curl -s --max-time 15 https://{DOMAIN}:8443/health "
        f"--resolve {DOMAIN}:8443:127.0.0.1 --insecure || echo '本机验证失败'")
    run(f"curl -sI --max-time 15 http://127.0.0.1/ -H 'Host: {DOMAIN}' | head -5")

    # ④ 证书续期测试（dry-run）
    run("sudo certbot renew --dry-run 2>&1 | tail -8", timeout=300)

    client.close()
    print(f"\n现在可以访问: https://{DOMAIN}:8443")


if __name__ == "__main__":
    main()
