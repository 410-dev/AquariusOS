# pyhttpd/handler_test.py

import json
import pytest
from unittest.mock import AsyncMock, MagicMock
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


def make_request(body: str) -> MagicMock:
    """aiohttp Request 목업을 생성합니다."""
    req = MagicMock(spec=web.Request)
    req.text = AsyncMock(return_value=body)
    return req


# ── 테스트 ───────────────────────────────────────────────────────

class TestMakeHandler:
    def test_returns_callable(self):
        handler = make_handler(SimpleHook)
        assert callable(handler)

    @pytest.mark.asyncio
    async def test_200_on_valid_request(self):
        handler = make_handler(SimpleHook)
        req = make_request('{"key": "value"}')
        resp = await handler(req)
        assert resp.status == 200

    @pytest.mark.asyncio
    async def test_response_body_is_json(self):
        handler = make_handler(SimpleHook)
        req = make_request('{"key": "value"}')
        resp = await handler(req)
        body = json.loads(resp.text)
        assert body["received"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_400_on_failed_validation(self):
        handler = make_handler(BadRequestHook)
        req = make_request("")   # 빈 body → validate() = False
        resp = await handler(req)
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_400_body_contains_error_key(self):
        handler = make_handler(BadRequestHook)
        req = make_request("")
        resp = await handler(req)
        body = json.loads(resp.text)
        assert "error" in body

    @pytest.mark.asyncio
    async def test_500_on_on_request_exception(self):
        handler = make_handler(CrashingHook)
        req = make_request("{}")
        resp = await handler(req)
        assert resp.status == 500

    @pytest.mark.asyncio
    async def test_500_body_contains_error_message(self):
        handler = make_handler(CrashingHook)
        req = make_request("{}")
        resp = await handler(req)
        body = json.loads(resp.text)
        assert "handler crash" in body["error"]

    @pytest.mark.asyncio
    async def test_500_on_validate_exception(self):
        handler = make_handler(CrashingValidateHook)
        req = make_request("{}")
        resp = await handler(req)
        assert resp.status == 500

    @pytest.mark.asyncio
    async def test_content_type_is_json(self):
        handler = make_handler(SimpleHook)
        req = make_request('{}')
        resp = await handler(req)
        assert resp.content_type == "application/json"
