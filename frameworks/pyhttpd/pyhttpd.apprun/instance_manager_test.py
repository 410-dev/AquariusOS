# pyhttpd/instance_manager_test.py

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
from osext.pyhttp.Webhook import WebhookTask


# ── parse_inst_filename ──────────────────────────────────────────

class TestParseInstFilename:
    def test_valid_filename(self):
        key = parse_inst_filename("alice.trading-idea.8080.inst")
        assert key == InstanceKey(user="alice", context="trading-idea", port=8080)

    def test_root_context(self):
        key = parse_inst_filename("bob.root.8081.inst")
        assert key.context == "root"
        assert key.port == 8081

    def test_invalid_no_inst_extension(self):
        assert parse_inst_filename("alice.trading.8080.py") is None

    def test_invalid_missing_part(self):
        assert parse_inst_filename("trading.8080.inst") is None

    def test_invalid_non_numeric_port(self):
        assert parse_inst_filename("alice.trading.abc.inst") is None

    def test_ignores_random_files(self):
        assert parse_inst_filename("README.md") is None
        assert parse_inst_filename(".gitkeep") is None


# ── InstanceManager ──────────────────────────────────────────────

@pytest.fixture
def enabled_dir(tmp_path):
    """임시 enabled 디렉터리를 만들고, ENABLED_DIR 상수를 패치합니다."""
    d = tmp_path / "enabled"
    d.mkdir()
    with patch("instance_manager.ENABLED_DIR", str(d)):
        yield d


@pytest.fixture
def script_factory(tmp_path):
    """유효한 WebhookTask 스크립트 파일을 만들어주는 팩토리."""
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
    """enabled 디렉터리에 .inst 심볼릭 링크를 생성합니다."""
    link = enabled_dir / inst_name
    os.symlink(target, link)
    return link


class TestInstanceManagerReconcile:
    @pytest.mark.asyncio
    async def test_loads_new_inst(self, enabled_dir, script_factory):
        script = script_factory("hook.py")
        make_symlink(enabled_dir, "user.ctx.8080.inst", script)

        router = Router()
        manager = InstanceManager(router)
        await manager._reconcile()

        assert InstanceKey("user", "ctx", 8080) in manager._loaded
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_unloads_removed_inst(self, enabled_dir, script_factory):
        script = script_factory("hook.py")
        link = make_symlink(enabled_dir, "user.ctx.8080.inst", script)

        router = Router()
        manager = InstanceManager(router)
        await manager._reconcile()
        assert InstanceKey("user", "ctx", 8080) in manager._loaded

        link.unlink()
        await manager._reconcile()
        assert InstanceKey("user", "ctx", 8080) not in manager._loaded

    @pytest.mark.asyncio
    async def test_skips_broken_symlink(self, enabled_dir):
        link = enabled_dir / "user.ctx.8080.inst"
        os.symlink("/nonexistent/path.py", link)

        router = Router()
        manager = InstanceManager(router)
        await manager._reconcile()

        assert manager._loaded == set()

    @pytest.mark.asyncio
    async def test_skips_load_error(self, enabled_dir, tmp_path):
        bad = tmp_path / "bad.py"
        bad.write_text("this is not valid python !!!")
        make_symlink(enabled_dir, "user.ctx.8080.inst", str(bad))

        router = Router()
        manager = InstanceManager(router)
        await manager._reconcile()   # 예외 없이 통과해야 함

        assert manager._loaded == set()

    @pytest.mark.asyncio
    async def test_multiple_insts_same_port(self, enabled_dir, script_factory):
        s1 = script_factory("h1.py")
        s2 = script_factory("h2.py")
        make_symlink(enabled_dir, "user.abc.8080.inst", s1)
        make_symlink(enabled_dir, "user.bcd.8080.inst", s2)

        router = Router()
        manager = InstanceManager(router)
        await manager._reconcile()

        assert InstanceKey("user", "abc", 8080) in manager._loaded
        assert InstanceKey("user", "bcd", 8080) in manager._loaded
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_reconcile_is_idempotent(self, enabled_dir, script_factory):
        script = script_factory("hook.py")
        make_symlink(enabled_dir, "user.ctx.8080.inst", script)

        router = Router()
        manager = InstanceManager(router)
        await manager._reconcile()
        await manager._reconcile()   # 두 번 실행해도 중복 등록 없음

        assert len(manager._loaded) == 1
        await router.stop_all()