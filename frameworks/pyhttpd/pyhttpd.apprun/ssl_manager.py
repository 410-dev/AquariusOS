# pyhttpd.apprun/ssl_manager.py

import asyncio
import logging
import os
import ssl
import shutil

logger = logging.getLogger("pyhttpd.ssl")

CERTS_DIR = "/etc/pyhttpd/certs"


def cert_paths(user: str, context: str, port: int) -> tuple[str, str]:
    base = os.path.join(CERTS_DIR, user, f"{context}.{port}")
    return f"{base}.crt", f"{base}.key"


def make_ssl_context(user: str, context: str, port: int) -> ssl.SSLContext:
    """
    저장된 인증서로 SSLContext를 생성합니다.
    인증서가 없으면 FileNotFoundError를 발생시킵니다.
    """
    cert, key = cert_paths(user, context, port)

    if not os.path.isfile(cert):
        raise FileNotFoundError(f"Certificate not found: {cert}")
    if not os.path.isfile(key):
        raise FileNotFoundError(f"Private key not found: {key}")

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    # 안전하지 않은 프로토콜/암호화 스위트 비활성화
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.set_ciphers("ECDH+AESGCM:ECDH+CHACHA20:!aNULL:!MD5")
    return ctx


def install_cert(user: str, context: str, port: int,
                 cert_src: str, key_src: str):
    """
    인증서 파일을 pyhttpd 관리 디렉터리에 복사합니다.
    CLI의 register에서 호출합니다.
    """
    cert_dst, key_dst = cert_paths(user, context, port)
    os.makedirs(os.path.dirname(cert_dst), mode=0o700, exist_ok=True)
    shutil.copy2(cert_src, cert_dst)
    shutil.copy2(key_src,  key_dst)
    os.chmod(cert_dst, 0o600)
    os.chmod(key_dst,  0o600)
    logger.info(f"Installed cert for {user}/{context}:{port}")


# ── ACME (Let's Encrypt) ─────────────────────────────────────────

async def provision_acme(user: str, context: str, port: int, domain: str):
    """
    certbot을 이용해 인증서를 발급하고 pyhttpd 경로에 설치합니다.
    certbot이 없으면 RuntimeError를 발생시킵니다.
    """
    if not shutil.which("certbot"):
        raise RuntimeError("certbot is not installed. Install it and try again.")

    cert_dst, key_dst = cert_paths(user, context, port)
    os.makedirs(os.path.dirname(cert_dst), mode=0o700, exist_ok=True)

    logger.info(f"Provisioning ACME cert for {domain}...")

    # certbot standalone 모드로 발급
    # 발급 중 해당 포트를 잠깐 점유하므로 pyhttpd가 해당 포트를 쓰고 있으면
    # 일시적으로 내려야 합니다. 여기서는 --standalone을 사용합니다.
    proc = await asyncio.create_subprocess_exec(
        "certbot", "certonly",
        "--standalone",
        "--non-interactive",
        "--agree-tos",
        "--register-unsafely-without-email",
        "-d", domain,
        "--cert-path",    cert_dst,
        "--key-path",     key_dst,
        "--fullchain-path", cert_dst,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(
            f"certbot failed (exit {proc.returncode}):\n"
            + stderr.decode()
        )

        # 파일이 실제로 생성된 경우에만 권한 설정
    if os.path.isfile(cert_dst):
        os.chmod(cert_dst, 0o600)
    if os.path.isfile(key_dst):
        os.chmod(key_dst, 0o600)
    logger.info(f"ACME cert installed for {domain}")


async def renew_acme_all():
    """
    certbot renew를 실행해 만료 예정 인증서를 갱신합니다.
    데몬에서 주기적으로 호출합니다 (예: 12시간마다).
    갱신된 인증서는 reload를 통해 반영합니다.
    """
    import shutil
    if not shutil.which("certbot"):
        return

    proc = await asyncio.create_subprocess_exec(
        "certbot", "renew", "--quiet",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode == 0:
        logger.info("certbot renew completed")
    else:
        logger.warning(f"certbot renew exited {proc.returncode}: {stderr.decode()}")
