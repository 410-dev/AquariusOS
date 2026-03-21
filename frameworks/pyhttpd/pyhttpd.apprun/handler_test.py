# pyhttpd.apprun/handler_test.py

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import web
from handler import make_handler
from osext.pyhttp.Webhook import WebhookTask


# ── 픽스처 ───────────────────────────────────────────────────────

class SimpleHook(WebhookTask):
    @staticmethod
    def on_request(body: str) -> tuple[int, dict]:
        data = json.loads(body)
        return 200, {"received": data}


class BadRequestHook(WebhookTask):
    @staticmethod
    def validate(body: str) -> bool:
        return len(body) > 0

    @staticmethod
    def on_request(body: str) -> tuple[int, dict]:
        return 200, {}


class CrashingHook(WebhookTask):
    @staticmethod
    def on_request(body: str) -> tuple[int, dict]:
        raise RuntimeError("handler crash")


class CrashingValidateHook(WebhookTask):
    @staticmethod
    def validate(body: str) -> bool:
        raise ValueError("validate crash")

    @staticmethod
    def on_request(body: str) -> tuple[int, dict]:
        return 200, {}


def make_request(body: str, method: str = "POST", path: str = "/test") -> MagicMock:
    req = MagicMock(spec=web.Request)
    req.text = AsyncMock(return_value=body)
    req.method = method
    req.path = path
    return req


# write_access를 mock으로 대체해서 파일 I/O 없이 테스트
@pytest.fixture(autouse=True)
def mock_write_access():
    with patch("handler.write_access") as m:
        yield m


# ── make_handler ─────────────────────────────────────────────────

class TestMakeHandler:
    def test_returns_callable(self):
        handler = make_handler(SimpleHook, "alice", "trading", 8080)
        assert callable(handler)

    @pytest.mark.asyncio
    async def test_200_on_valid_request(self):
        handler = make_handler(SimpleHook, "alice", "trading", 8080)
        resp = await handler(make_request('{"key": "value"}'))
        assert resp.status == 200

    @pytest.mark.asyncio
    async def test_response_body_is_json(self):
        handler = make_handler(SimpleHook, "alice", "trading", 8080)
        resp = await handler(make_request('{"key": "value"}'))
        body = json.loads(resp.text)
        assert body["received"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_400_on_failed_validation(self):
        handler = make_handler(BadRequestHook, "alice", "trading", 8080)
        resp = await handler(make_request(""))
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_500_on_on_request_exception(self):
        handler = make_handler(CrashingHook, "alice", "trading", 8080)
        resp = await handler(make_request("{}"))
        assert resp.status == 500

    @pytest.mark.asyncio
    async def test_500_on_validate_exception(self):
        handler = make_handler(CrashingValidateHook, "alice", "trading", 8080)
        resp = await handler(make_request("{}"))
        assert resp.status == 500

    @pytest.mark.asyncio
    async def test_content_type_is_json(self):
        handler = make_handler(SimpleHook, "alice", "trading", 8080)
        resp = await handler(make_request("{}"))
        assert resp.content_type == "application/json"


# ── access log 기록 검증 ──────────────────────────────────────────

class TestHandlerLogging:
    @pytest.mark.asyncio
    async def test_logs_on_success(self, mock_write_access):
        handler = make_handler(SimpleHook, "alice", "trading", 8080)
        await handler(make_request('{}', path="/trading"))
        mock_write_access.assert_called_once()
        kwargs = mock_write_access.call_args.kwargs
        assert kwargs["user"]    == "alice"
        assert kwargs["context"] == "trading"
        assert kwargs["port"]    == 8080
        assert kwargs["status"]  == 200
        assert kwargs["error"]   is None

    @pytest.mark.asyncio
    async def test_logs_on_validation_failure(self, mock_write_access):
        handler = make_handler(BadRequestHook, "alice", "trading", 8080)
        await handler(make_request(""))
        kwargs = mock_write_access.call_args.kwargs
        assert kwargs["status"] == 400

    @pytest.mark.asyncio
    async def test_logs_error_traceback_on_crash(self, mock_write_access):
        handler = make_handler(CrashingHook, "alice", "trading", 8080)
        await handler(make_request("{}"))
        kwargs = mock_write_access.call_args.kwargs
        assert kwargs["status"] == 500
        assert kwargs["error"] is not None
        assert "handler crash" in kwargs["error"]

    @pytest.mark.asyncio
    async def test_logs_method_and_path(self, mock_write_access):
        handler = make_handler(SimpleHook, "alice", "trading", 8080)
        await handler(make_request("{}", method="POST", path="/trading"))
        kwargs = mock_write_access.call_args.kwargs
        assert kwargs["method"] == "POST"
        assert kwargs["path"]   == "/trading"

    @pytest.mark.asyncio
    async def test_elapsed_ms_is_positive(self, mock_write_access):
        handler = make_handler(SimpleHook, "alice", "trading", 8080)
        await handler(make_request("{}"))
        kwargs = mock_write_access.call_args.kwargs
        assert kwargs["elapsed_ms"] >= 0
