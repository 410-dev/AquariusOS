# pyhttpd.apprun/router_test.py

import ssl
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import web
from osext.pyhttp.Webhook import WebhookTask
from router import Router, PortRouter, RedirectRouter


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


def make_request(path: str, method: str = "POST",
                 host: str = "localhost") -> MagicMock:
    req = MagicMock(spec=web.Request)
    req.path = path
    req.method = method
    req.host = host
    req.query_string = ""
    req.text = AsyncMock(return_value="{}")
    return req


def make_ssl_context() -> MagicMock:
    """실제 인증서 없이 SSLContext를 mock으로 대체합니다."""
    return MagicMock(spec=ssl.SSLContext)


# ── PortRouter ────────────────────────────────────────────────────

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
        assert PortRouter(9000).list_contexts() == []

    def test_is_https_false_without_ssl(self):
        assert PortRouter(9000).is_https is False

    def test_is_https_true_with_ssl_context(self):
        pr = PortRouter(9000, ssl_context=make_ssl_context())
        assert pr.is_https is True


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

    @pytest.mark.asyncio
    async def test_dispatch_subpath_routes_to_top_context(self):
        """'/trading/foo/bar' 는 context 'trading' 으로 라우팅됩니다."""
        pr = PortRouter(9004)
        pr.register("alice", "trading", DummyHook)
        await pr.start()
        resp = await pr._dispatch(make_request("/trading/foo/bar"))
        assert resp.status == 200
        await pr.stop()


# ── RedirectRouter ────────────────────────────────────────────────

class TestRedirectRouter:
    @pytest.mark.asyncio
    async def test_redirect_returns_301(self):
        rr = RedirectRouter(8080)
        rr.register("trading", 8443)
        await rr.start()
        resp = await rr._redirect(make_request("/trading", host="example.com"))
        assert resp.status == 301
        await rr.stop()

    @pytest.mark.asyncio
    async def test_redirect_location_uses_https(self):
        rr = RedirectRouter(8080)
        rr.register("trading", 8443)
        await rr.start()
        resp = await rr._redirect(make_request("/trading", host="example.com"))
        assert resp.headers["Location"].startswith("https://")
        await rr.stop()

    @pytest.mark.asyncio
    async def test_redirect_location_contains_correct_port(self):
        rr = RedirectRouter(8080)
        rr.register("trading", 8443)
        await rr.start()
        resp = await rr._redirect(make_request("/trading", host="example.com"))
        assert ":8443" in resp.headers["Location"]
        await rr.stop()

    @pytest.mark.asyncio
    async def test_redirect_preserves_path(self):
        rr = RedirectRouter(8080)
        rr.register("root", 443)
        await rr.start()
        resp = await rr._redirect(make_request("/some/path", host="example.com"))
        assert "/some/path" in resp.headers["Location"]
        await rr.stop()

    @pytest.mark.asyncio
    async def test_redirect_preserves_query_string(self):
        rr = RedirectRouter(8080)
        rr.register("root", 443)
        await rr.start()
        req = make_request("/path", host="example.com")
        req.query_string = "foo=bar"
        resp = await rr._redirect(req)
        assert "foo=bar" in resp.headers["Location"]
        await rr.stop()

    def test_unregister_removes_context(self):
        rr = RedirectRouter(8080)
        rr.register("trading", 8443)
        rr.unregister("trading")
        assert "trading" not in rr.list_contexts()

    def test_unregister_nonexistent_is_safe(self):
        rr = RedirectRouter(8080)
        rr.unregister("ghost")  # 예외 없이 통과


# ── Router (통합) ─────────────────────────────────────────────────

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
    async def test_stop_all_clears_ports(self):
        router = Router()
        await router.register(19087, "alice", "abc", DummyHook)
        await router.stop_all()
        assert router._ports == {}

    @pytest.mark.asyncio
    async def test_status_returns_proto_and_contexts(self):
        router = Router()
        await router.register(19088, "alice", "abc", DummyHook)
        status = router.status()
        assert status[19088]["proto"] == "http"
        assert "abc" in status[19088]["contexts"]
        await router.stop_all()

    # ── SSL 관련 ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_register_https_port_is_https(self):
        router = Router()
        ssl_ctx = make_ssl_context()
        await router.register(19089, "alice", "abc", DummyHook, ssl_ctx=ssl_ctx)
        assert router._ports[19089].is_https is True
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_register_https_status_shows_https_proto(self):
        router = Router()
        ssl_ctx = make_ssl_context()
        await router.register(19090, "alice", "abc", DummyHook, ssl_ctx=ssl_ctx)
        assert router.status()[19090]["proto"] == "https"
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_http_and_https_on_different_ports(self):
        router = Router()
        await router.register(19091, "alice", "abc", DummyHook)
        await router.register(19092, "alice", "abc", DummyHook,
                               ssl_ctx=make_ssl_context())
        assert router._ports[19091].is_https is False
        assert router._ports[19092].is_https is True
        await router.stop_all()

    # ── Redirect 관련 ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_register_redirect(self):
        router = Router()
        # https 포트를 먼저 등록해야 redirect가 포트를 자동으로 찾습니다
        ssl_ctx = make_ssl_context()
        await router.register(19093, "alice", "trading", DummyHook,
                               ssl_ctx=ssl_ctx)
        await router.register_redirect(19094, "alice", "trading")
        assert 19094 in router._redirects
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_register_redirect_status_shows_redirect_proto(self):
        router = Router()
        ssl_ctx = make_ssl_context()
        await router.register(19095, "alice", "trading", DummyHook,
                               ssl_ctx=ssl_ctx)
        await router.register_redirect(19096, "alice", "trading")
        assert router.status()[19096]["proto"] == "redirect"
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_unregister_redirect_removes_port_when_empty(self):
        router = Router()
        ssl_ctx = make_ssl_context()
        await router.register(19097, "alice", "trading", DummyHook,
                               ssl_ctx=ssl_ctx)
        await router.register_redirect(19098, "alice", "trading")
        await router.unregister_redirect(19098, "alice", "trading")
        assert 19098 not in router._redirects
        await router.stop_all()

    @pytest.mark.asyncio
    async def test_stop_all_clears_redirects(self):
        router = Router()
        ssl_ctx = make_ssl_context()
        await router.register(19099, "alice", "trading", DummyHook,
                               ssl_ctx=ssl_ctx)
        await router.register_redirect(19100, "alice", "trading")
        await router.stop_all()
        assert router._redirects == {}
