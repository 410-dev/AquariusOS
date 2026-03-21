# pyhttpd.apprun/router_test.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import web
from osext.pyhttp.Webhook import WebhookTask
from router import Router, PortRouter


# ── 픽스처 ───────────────────────────────────────────────────────

class DummyHook(WebhookTask):
    @staticmethod
    def on_request(body: str) -> tuple[int, dict]:
        return 200, {}


class AnotherHook(WebhookTask):
    @staticmethod
    def on_request(body: str) -> tuple[int, dict]:
        return 201, {}


@pytest.fixture(autouse=True)
def mock_write_access():
    with patch("handler.write_access"):
        yield


def make_request(path: str, method: str = "POST") -> MagicMock:
    req = MagicMock(spec=web.Request)
    req.path = path
    req.method = method
    req.text = AsyncMock(return_value="{}")
    return req


# ── PortRouter 단위 테스트 ────────────────────────────────────────

class TestPortRouter:
    def test_register_adds_context(self):
        pr = PortRouter(9000)
        pr.register("alice", "abc", DummyHook)
        assert "abc" in pr.list_contexts()

    def test_register_multiple_contexts(self):
        pr = PortRouter(9000)
        pr.register("alice", "abc", DummyHook)
        pr.register("alice", "bcd", AnotherHook)
        assert set(pr.list_contexts()) == {"abc", "bcd"}

    def test_register_replaces_existing(self):
        pr = PortRouter(9000)
        pr.register("alice", "abc", DummyHook)
        pr.register("alice", "abc", AnotherHook)
        assert len(pr.list_contexts()) == 1

    def test_unregister_removes_context(self):
        pr = PortRouter(9000)
        pr.register("alice", "abc", DummyHook)
        pr.unregister("alice", "abc")
        assert "abc" not in pr.list_contexts()

    def test_unregister_nonexistent_raises(self):
        pr = PortRouter(9000)
        with pytest.raises(KeyError):
            pr.unregister("alice", "ghost")

    def test_list_contexts_empty_initially(self):
        pr = PortRouter(9000)
        assert pr.list_contexts() == []


class TestPortRouterDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_known_context(self):
        pr = PortRouter(9001)
        pr.register("alice", "trading", DummyHook)
        await pr.start()
        resp = await pr._dispatch(make_request("/trading"))
        assert resp.status == 200
        await pr.stop()

    @pytest.mark.asyncio
    async def test_dispatch_root_context(self):
        pr = PortRouter(9002)
        pr.register("alice", "root", DummyHook)
        await pr.start()
        resp = await pr._dispatch(make_request("/"))
        assert resp.status == 200
        await pr.stop()

    @pytest.mark.asyncio
    async def test_dispatch_unknown_context_returns_404(self):
        pr = PortRouter(9003)
        await pr.start()
        resp = await pr._dispatch(make_request("/ghost"))
        assert resp.status == 404
        await pr.stop()


# ── Router 통합 테스트 ────────────────────────────────────────────

class TestRouter:
    @pytest.mark.asyncio
    async def test_register_starts_port(self):
        router = Router()
        await router.register(19080, "alice", "abc", DummyHook)
        assert 19080 in router._ports
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_register_two_contexts_same_port(self):
        router = Router()
        await router.register(19081, "alice", "abc", DummyHook)
        await router.register(19081, "alice", "bcd", AnotherHook)
        assert set(router._ports[19081].list_contexts()) == {"abc", "bcd"}
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_register_two_ports(self):
        router = Router()
        await router.register(19082, "alice", "abc", DummyHook)
        await router.register(19083, "alice", "abc", DummyHook)
        assert 19082 in router._ports
        assert 19083 in router._ports
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_unregister_removes_context(self):
        router = Router()
        await router.register(19084, "alice", "abc", DummyHook)
        await router.unregister(19084, "alice", "abc")
        assert 19084 not in router._ports

    @pytest.mark.asyncio
    async def test_unregister_one_of_two_keeps_port(self):
        router = Router()
        await router.register(19085, "alice", "abc", DummyHook)
        await router.register(19085, "alice", "bcd", AnotherHook)
        await router.unregister(19085, "alice", "abc")
        assert 19085 in router._ports
        assert "bcd" in router._ports[19085].list_contexts()
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_unregister_unknown_port_raises(self):
        router = Router()
        with pytest.raises(KeyError):
            await router.unregister(19999, "alice", "abc")

    @pytest.mark.asyncio
    async def test_status_returns_port_context_map(self):
        router = Router()
        await router.register(19086, "alice", "abc", DummyHook)
        await router.register(19086, "alice", "bcd", AnotherHook)
        status = router.status()
        assert 19086 in status
        assert set(status[19086]) == {"abc", "bcd"}
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_stop_all_clears_ports(self):
        router = Router()
        await router.register(19087, "alice", "abc", DummyHook)
        await router.stop_all()
        assert router._ports == {}