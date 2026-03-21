# pyhttpd.apprun/instance_manager_test.py

import os
import textwrap
import pytest
from unittest.mock import AsyncMock, patch
from instance_manager import (
    InstanceManager,
    InstanceKey,
    parse_inst_filename,
    ENABLED_DIR,
)
from router import Router


# ── parse_inst_filename ──────────────────────────────────────────

class TestParseInstFilename:
    def test_valid_http(self):
        key = parse_inst_filename("alice.trading.8080.http.inst")
        assert key == InstanceKey("alice", "trading", 8080, "http")

    def test_valid_https(self):
        key = parse_inst_filename("alice.trading.8443.https.inst")
        assert key == InstanceKey("alice", "trading", 8443, "https")

    def test_valid_redirect(self):
        key = parse_inst_filename("alice.trading.8080.redirect.inst")
        assert key == InstanceKey("alice", "trading", 8080, "redirect")

    def test_root_context_http(self):
        key = parse_inst_filename("bob.root.8080.http.inst")
        assert key.context == "root"
        assert key.proto   == "http"

    def test_invalid_no_proto(self):
        assert parse_inst_filename("alice.trading.8080.inst") is None

    def test_invalid_unknown_proto(self):
        assert parse_inst_filename("alice.trading.8080.ftp.inst") is None

    def test_invalid_no_inst_extension(self):
        assert parse_inst_filename("alice.trading.8080.http.py") is None

    def test_invalid_missing_part(self):
        assert parse_inst_filename("trading.8080.http.inst") is None

    def test_invalid_non_numeric_port(self):
        assert parse_inst_filename("alice.trading.abc.http.inst") is None

    def test_ignores_random_files(self):
        assert parse_inst_filename("README.md") is None


# ── InstanceManager fixtures ─────────────────────────────────────

@pytest.fixture
def enabled_dir(tmp_path):
    d = tmp_path / "enabled"
    d.mkdir()
    with patch("instance_manager.ENABLED_DIR", str(d)):
        yield d


@pytest.fixture
def script_factory(tmp_path):
    def _make(filename: str = "hook.py") -> str:
        path = tmp_path / filename
        path.write_text(textwrap.dedent("""
            from osext.pyhttp.Webhook import WebhookTask
            class TestHook(WebhookTask):
                @staticmethod
                def on_request(body):
                    return 200, {}
        """))
        return str(path)
    return _make


def make_symlink(enabled_dir, inst_name: str, target: str):
    link = enabled_dir / inst_name
    os.symlink(target, link)
    return link


# ── reconcile ────────────────────────────────────────────────────

class TestInstanceManagerReconcile:
    @pytest.mark.asyncio
    async def test_loads_http_inst(self, enabled_dir, script_factory):
        script = script_factory()
        make_symlink(enabled_dir, "alice.ctx.8080.http.inst", script)
        router = Router()
        manager = InstanceManager(router)
        await manager._reconcile()
        assert InstanceKey("alice", "ctx", 8080, "http") in manager._loaded
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_loads_https_inst_with_valid_cert(self, enabled_dir,
                                                     script_factory, tmp_path):
        script = script_factory()
        make_symlink(enabled_dir, "alice.ctx.8443.https.inst", script)

        mock_ctx = object()
        router = Router()
        manager = InstanceManager(router)

        with patch("instance_manager.make_ssl_context", return_value=mock_ctx):
            await manager._reconcile()

        assert InstanceKey("alice", "ctx", 8443, "https") in manager._loaded
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_skips_https_inst_when_cert_missing(self, enabled_dir, script_factory):
        script = script_factory()
        make_symlink(enabled_dir, "alice.ctx.8443.https.inst", script)

        router = Router()
        manager = InstanceManager(router)

        with patch("instance_manager.make_ssl_context",
                   side_effect=FileNotFoundError("no cert")):  # 내장 그대로 사용
            await manager._reconcile()

        assert InstanceKey("alice", "ctx", 8443, "https") not in manager._loaded

    @pytest.mark.asyncio
    async def test_loads_redirect_inst(self, enabled_dir, script_factory):
        script = script_factory()
        # https 포트를 먼저 등록
        make_symlink(enabled_dir, "alice.trading.8443.https.inst", script)
        make_symlink(enabled_dir, "alice.trading.8080.redirect.inst", script)

        router = Router()
        manager = InstanceManager(router)

        with patch("instance_manager.make_ssl_context", return_value=object()):
            await manager._reconcile()

        assert InstanceKey("alice", "trading", 8080, "redirect") in manager._loaded
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_unloads_removed_inst(self, enabled_dir, script_factory):
        script = script_factory()
        link = make_symlink(enabled_dir, "alice.ctx.8080.http.inst", script)
        router = Router()
        manager = InstanceManager(router)
        await manager._reconcile()
        link.unlink()
        await manager._reconcile()
        assert InstanceKey("alice", "ctx", 8080, "http") not in manager._loaded

    @pytest.mark.asyncio
    async def test_skips_broken_symlink(self, enabled_dir):
        link = enabled_dir / "alice.ctx.8080.http.inst"
        os.symlink("/nonexistent/path.py", link)
        router = Router()
        manager = InstanceManager(router)
        await manager._reconcile()
        assert manager._loaded == set()

    @pytest.mark.asyncio
    async def test_skips_load_error(self, enabled_dir, tmp_path):
        bad = tmp_path / "bad.py"
        bad.write_text("this is not valid python !!!")
        make_symlink(enabled_dir, "alice.ctx.8080.http.inst", str(bad))
        router = Router()
        manager = InstanceManager(router)
        await manager._reconcile()
        assert manager._loaded == set()

    @pytest.mark.asyncio
    async def test_reconcile_is_idempotent(self, enabled_dir, script_factory):
        script = script_factory()
        make_symlink(enabled_dir, "alice.ctx.8080.http.inst", script)
        router = Router()
        manager = InstanceManager(router)
        await manager._reconcile()
        await manager._reconcile()
        assert len(manager._loaded) == 1
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_multiple_protos_same_context(self, enabled_dir, script_factory):
        s1 = script_factory("h1.py")
        s2 = script_factory("h2.py")
        make_symlink(enabled_dir, "alice.trading.8080.http.inst",   s1)
        make_symlink(enabled_dir, "alice.trading.8443.https.inst",  s2)

        router = Router()
        manager = InstanceManager(router)

        with patch("instance_manager.make_ssl_context", return_value=object()):
            await manager._reconcile()

        assert InstanceKey("alice", "trading", 8080, "http")  in manager._loaded
        assert InstanceKey("alice", "trading", 8443, "https") in manager._loaded
        await router.stop_all()
