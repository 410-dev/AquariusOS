# pyhttpd.apprun/ssl_manager_test.py

import os
import ssl
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ssl_manager import (
    cert_paths,
    make_ssl_context,
    install_cert,
    provision_acme,
)


@pytest.fixture
def cert_dir(tmp_path):
    with patch("ssl_manager.CERTS_DIR", str(tmp_path)):
        yield tmp_path


@pytest.fixture
def dummy_cert_files(tmp_path):
    """
    실제 서명된 인증서 대신 self-signed 인증서를 생성합니다.
    ssl_manager의 파일 존재 여부 및 경로 테스트에 사용합니다.
    """
    import subprocess
    cert = tmp_path / "test.crt"
    key  = tmp_path / "test.key"
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048",
        "-keyout", str(key), "-out", str(cert),
        "-days", "1", "-nodes",
        "-subj", "/CN=test"
    ], check=True, capture_output=True)
    return str(cert), str(key)


# ── cert_paths ────────────────────────────────────────────────────

class TestCertPaths:
    def test_returns_crt_and_key_paths(self, cert_dir):
        crt, key = cert_paths("alice", "trading", 8443)
        assert crt.endswith("trading.8443.crt")
        assert key.endswith("trading.8443.key")

    def test_paths_are_under_user_dir(self, cert_dir):
        crt, key = cert_paths("alice", "trading", 8443)
        assert "/alice/" in crt
        assert "/alice/" in key


# ── make_ssl_context ──────────────────────────────────────────────

class TestMakeSslContext:
    def test_raises_if_cert_missing(self, cert_dir):
        with pytest.raises(FileNotFoundError, match="Certificate not found"):
            make_ssl_context("alice", "trading", 8443)

    def test_raises_if_key_missing(self, cert_dir):
        crt, _ = cert_paths("alice", "trading", 8443)
        os.makedirs(os.path.dirname(crt), exist_ok=True)
        open(crt, "w").close()  # cert만 만들고 key는 없음
        with pytest.raises(FileNotFoundError, match="Private key not found"):
            make_ssl_context("alice", "trading", 8443)

    def test_returns_ssl_context_with_valid_cert(self, cert_dir, dummy_cert_files):
        src_cert, src_key = dummy_cert_files
        install_cert("alice", "trading", 8443, src_cert, src_key)
        ctx = make_ssl_context("alice", "trading", 8443)
        assert isinstance(ctx, ssl.SSLContext)

    def test_minimum_tls_version_is_1_2(self, cert_dir, dummy_cert_files):
        src_cert, src_key = dummy_cert_files
        install_cert("alice", "trading", 8443, src_cert, src_key)
        ctx = make_ssl_context("alice", "trading", 8443)
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2


# ── install_cert ──────────────────────────────────────────────────

class TestInstallCert:
    def test_copies_cert_and_key(self, cert_dir, dummy_cert_files):
        src_cert, src_key = dummy_cert_files
        install_cert("alice", "trading", 8443, src_cert, src_key)
        crt, key = cert_paths("alice", "trading", 8443)
        assert os.path.isfile(crt)
        assert os.path.isfile(key)

    def test_cert_permissions_are_600(self, cert_dir, dummy_cert_files):
        src_cert, src_key = dummy_cert_files
        install_cert("alice", "trading", 8443, src_cert, src_key)
        crt, key = cert_paths("alice", "trading", 8443)
        assert oct(os.stat(crt).st_mode)[-3:] == "600"
        assert oct(os.stat(key).st_mode)[-3:] == "600"

    def test_creates_user_directory(self, cert_dir, dummy_cert_files):
        src_cert, src_key = dummy_cert_files
        install_cert("newuser", "ctx", 8443, src_cert, src_key)
        assert os.path.isdir(os.path.join(str(cert_dir), "newuser"))


# ── provision_acme ────────────────────────────────────────────────

class TestProvisionAcme:
    @pytest.mark.asyncio
    async def test_raises_if_certbot_not_installed(self, cert_dir):
        with patch("ssl_manager.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="certbot is not installed"):
                await provision_acme("alice", "trading", 443, "example.com")

    @pytest.mark.asyncio
    async def test_calls_certbot_with_domain(self, cert_dir):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("ssl_manager.shutil.which", return_value="/usr/bin/certbot"), \
             patch("ssl_manager.asyncio.create_subprocess_exec",
                   return_value=mock_proc) as mock_exec:
            await provision_acme("alice", "trading", 443, "trading.example.com")
            args = mock_exec.call_args.args
            assert "certbot" in args
            assert "trading.example.com" in args

    @pytest.mark.asyncio
    async def test_raises_on_certbot_failure(self, cert_dir):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"certbot error"))

        with patch("ssl_manager.shutil.which", return_value="/usr/bin/certbot"), \
             patch("ssl_manager.asyncio.create_subprocess_exec",
                   return_value=mock_proc):
            with pytest.raises(RuntimeError, match="certbot failed"):
                await provision_acme("alice", "trading", 443, "example.com")
