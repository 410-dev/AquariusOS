# pyhttpd/router_test.py

import pytest
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


# ── PortRouter 단위 테스트 ────────────────────────────────────────

class TestPortRouter:
    def test_register_adds_context(self):
        pr = PortRouter(9000)
        pr.register("abc", DummyHook)
        assert "abc" in pr.list_contexts()

    def test_register_multiple_contexts(self):
        pr = PortRouter(9000)
        pr.register("abc", DummyHook)
        pr.register("bcd", AnotherHook)
        assert set(pr.list_contexts()) == {"abc", "bcd"}

    def test_register_replaces_existing(self):
        pr = PortRouter(9000)
        pr.register("abc", DummyHook)
        pr.register("abc", AnotherHook)   # 교체
        assert len(pr.list_contexts()) == 1

    def test_unregister_removes_context(self):
        pr = PortRouter(9000)
        pr.register("abc", DummyHook)
        pr.unregister("abc")
        assert "abc" not in pr.list_contexts()

    def test_unregister_nonexistent_raises(self):
        pr = PortRouter(9000)
        with pytest.raises(KeyError):
            pr.unregister("ghost")

    def test_list_contexts_empty_initially(self):
        pr = PortRouter(9000)
        assert pr.list_contexts() == []


class TestPortRouterDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_known_context(self):
        from unittest.mock import AsyncMock, MagicMock
        from aiohttp import web

        pr = PortRouter(9001)
        pr.register("trading", DummyHook)
        await pr.start()

        req = MagicMock(spec=web.Request)
        req.path = "/trading"
        req.text = AsyncMock(return_value="{}")

        resp = await pr._dispatch(req)
        assert resp.status == 200
        await pr.stop()

    @pytest.mark.asyncio
    async def test_dispatch_root_context(self):
        from unittest.mock import AsyncMock, MagicMock
        from aiohttp import web

        pr = PortRouter(9002)
        pr.register("root", DummyHook)
        await pr.start()

        req = MagicMock(spec=web.Request)
        req.path = "/"
        req.text = AsyncMock(return_value="{}")

        resp = await pr._dispatch(req)
        assert resp.status == 200
        await pr.stop()

    @pytest.mark.asyncio
    async def test_dispatch_unknown_context_returns_404(self):
        from unittest.mock import AsyncMock, MagicMock
        from aiohttp import web

        pr = PortRouter(9003)
        await pr.start()

        req = MagicMock(spec=web.Request)
        req.path = "/ghost"
        req.text = AsyncMock(return_value="{}")

        resp = await pr._dispatch(req)
        assert resp.status == 404
        await pr.stop()


# ── Router 통합 테스트 ────────────────────────────────────────────

class TestRouter:
    @pytest.mark.asyncio
    async def test_register_starts_port(self):
        router = Router()
        await router.register(19080, "abc", DummyHook)
        assert 19080 in router._ports
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_register_two_contexts_same_port(self):
        router = Router()
        await router.register(19081, "abc", DummyHook)
        await router.register(19081, "bcd", AnotherHook)
        assert set(router._ports[19081].list_contexts()) == {"abc", "bcd"}
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_register_two_ports(self):
        router = Router()
        await router.register(19082, "abc", DummyHook)
        await router.register(19083, "abc", DummyHook)
        assert 19082 in router._ports
        assert 19083 in router._ports
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_unregister_removes_context(self):
        router = Router()
        await router.register(19084, "abc", DummyHook)
        await router.unregister(19084, "abc")
        # context가 없어지면 포트도 종료
        assert 19084 not in router._ports

    @pytest.mark.asyncio
    async def test_unregister_one_of_two_keeps_port(self):
        router = Router()
        await router.register(19085, "abc", DummyHook)
        await router.register(19085, "bcd", AnotherHook)
        await router.unregister(19085, "abc")
        assert 19085 in router._ports
        assert "bcd" in router._ports[19085].list_contexts()
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_unregister_unknown_port_raises(self):
        router = Router()
        with pytest.raises(KeyError):
            await router.unregister(19999, "abc")

    @pytest.mark.asyncio
    async def test_status_returns_port_context_map(self):
        router = Router()
        await router.register(19086, "abc", DummyHook)
        await router.register(19086, "bcd", AnotherHook)
        status = router.status()
        assert 19086 in status
        assert set(status[19086]) == {"abc", "bcd"}
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_stop_all_clears_ports(self):
        router = Router()
        await router.register(19087, "abc", DummyHook)
        await router.stop_all()
        assert router._ports == {}
