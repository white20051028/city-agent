"""验证 agent-city.site:8443 的证书是不是真证书（受信任）。"""

import socket
import ssl

HOST = "agent-city.site"
PORT = 8443

# ① 用系统信任库验证（不是自签就该通过）
ctx = ssl.create_default_context()
try:
    with socket.create_connection((HOST, PORT), timeout=15) as sock:
        with ctx.wrap_socket(sock, server_hostname=HOST) as ssock:
            cert = ssock.getpeercert()
            print("✅ 证书验证通过（系统信任库认可）")
            print(f"   subject: {dict(x[0] for x in cert['subject'])}")
            print(f"   issuer:  {dict(x[0] for x in cert['issuer'])}")
            print(f"   有效期:  {cert['notBefore']} → {cert['notAfter']}")
            san = [v for k, v in cert.get("subjectAltName", []) if k == "DNS"]
            print(f"   覆盖域名: {san}")
except ssl.SSLCertVerificationError as e:
    print(f"❌ 证书验证失败: {e}")
except Exception as e:
    print(f"❌ 连接失败: {type(e).__name__}: {e}")

# ② 再测一下 IP 访问（自签证书那条路还在不在）
print()
print("=== 对照：用 IP 访问（应该还是自签，会失败）===")
try:
    with socket.create_connection(("192.144.254.52", 8443), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname="192.144.254.52") as ssock:
            print("✅ IP 访问也通过")
except ssl.SSLCertVerificationError as e:
    print(f"⚠️ IP 访问证书不匹配（正常，证书只签了域名）: {str(e)[:80]}")
except Exception as e:
    print(f"❌ {type(e).__name__}: {e}")
