"""方案 A：自建 CA + 服务器证书。

和「自签自用」的区别：
  自签自用：浏览器完全不认，每次警告
  自建 CA：你自己签发，把 CA 装到设备上后，签发的所有证书都被信任

步骤：
  ① 生成 CA 私钥 + CA 证书（10 年）
  ② 用 CA 签发服务器证书（IP + 域名都用 SAN 覆盖）
  ③ nginx 换成新证书
  ④ 把 CA 证书下载到本地，教用户装
"""

from __future__ import annotations

from pathlib import Path

import paramiko

ENV = Path(__file__).resolve().parent / ".deploy_env"
OUT_DIR = Path(__file__).resolve().parent


def load_env() -> dict:
    cfg = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


# 生成 CA + 服务器证书的脚本（在服务器上跑）
GEN_SCRIPT = r"""set -e
cd /etc/nginx/ssl

# ① CA 私钥 + 自签 CA 证书（10 年）
if [ ! -f ca.key ]; then
  sudo openssl genrsa -out ca.key 4096
  sudo openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 \
    -out ca.crt -subj "/C=CN/ST=Shaanxi/L=Xian/O=CityAgent-CA/CN=CityAgent Local CA"
  echo "CA 已生成"
else
  echo "CA 已存在，跳过"
fi

# ② 服务器私钥 + CSR
sudo openssl genrsa -out city-agent.key 2048
sudo openssl req -new -key city-agent.key -out city-agent.csr \
  -subj "/C=CN/ST=Shaanxi/L=Xian/O=CityAgent/CN=192.144.254.52"

# ③ 用 CA 签发（SAN 覆盖 IP 和可能的域名）
cat > /tmp/san.cnf <<'EOF'
subjectAltName = IP:192.144.254.52, DNS:agent-city.site, DNS:www.agent-city.site
extendedKeyUsage = serverAuth
EOF
sudo openssl x509 -req -in city-agent.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out city-agent.crt -days 825 -sha256 -extfile /tmp/san.cnf
sudo rm -f city-agent.csr /tmp/san.cnf

# ④ 合并成 chain（有些场景需要）
cat city-agent.crt ca.crt | sudo tee city-agent-fullchain.crt > /dev/null

sudo chmod 600 ca.key city-agent.key
sudo chmod 644 ca.crt city-agent.crt city-agent-fullchain.crt

echo "--- 生成完成 ---"
sudo ls -l /etc/nginx/ssl/
echo "--- 服务器证书信息 ---"
sudo openssl x509 -in city-agent.crt -noout -subject -issuer -dates
"""

NGINX_PATCH = r"""sudo python3 - <<'PY'
p = "/etc/nginx/sites-available/city-agent.conf"
s = open(p).read()
s = s.replace("ssl_certificate     /etc/nginx/ssl/city-agent.crt;",
              "ssl_certificate     /etc/nginx/ssl/city-agent-fullchain.crt;")
s = s.replace("ssl_certificate_key /etc/nginx/ssl/city-agent.key;",
              "ssl_certificate_key /etc/nginx/ssl/city-agent.key;")
open(p, "w").write(s)
print("配置已更新")
PY"""


def main() -> None:
    cfg = load_env()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(cfg["HOST"], username=cfg["USER"], password=cfg["PASS"], timeout=20)

    def run(cmd: str, timeout: int = 180) -> str:
        print(f"\n$ {cmd[:100].replace(chr(10), ' ')}")
        print("-" * 60)
        _, out, err = client.exec_command(cmd, timeout=timeout)
        o = out.read().decode("utf-8", "replace")
        e = err.read().decode("utf-8", "replace")
        if o.strip():
            print(o.rstrip()[-2500:])
        if e.strip():
            print("[stderr]", e.rstrip()[-800:])
        return o

    # ① 生成 CA + 证书
    run(GEN_SCRIPT, timeout=300)

    # ② nginx 换成 fullchain
    run(NGINX_PATCH)
    run("sudo nginx -t 2>&1 | tail -3")
    run("sudo systemctl reload nginx")

    # ③ 用 CA 验证一次（-k 不需要了，用 --cacert）
    run("sudo cp /etc/nginx/ssl/ca.crt /tmp/ca.crt && "
        "curl -s --cacert /tmp/ca.crt --max-time 10 https://192.144.254.52:8443/health "
        "|| echo 'CA 验证失败（证书 IP 不匹配？）'")

    # ④ 下载 CA 证书到本地
    sftp = client.open_sftp()
    local_ca = OUT_DIR / "CityAgent-CA.crt"
    sftp.get("/tmp/ca.crt", str(local_ca))
    sftp.close()
    print(f"\nCA 证书已下载到: {local_ca}")

    client.close()
    print("\n完成")


if __name__ == "__main__":
    main()
