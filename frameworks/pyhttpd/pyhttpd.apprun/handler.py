# pyhttpd/handler.py

import json
from aiohttp import web
from osext.pyhttp.Webhook import WebhookTask


def make_handler(task_cls: type[WebhookTask]):
    """
    WebhookTask 클래스를 받아 aiohttp 핸들러 함수를 반환합니다.
    """

    async def handler(request: web.Request) -> web.Response:
        body = await request.text()

        # 1. validate
        try:
            ok = task_cls.validate(body)
        except Exception as e:
            status, data = task_cls.on_error(e)
            return web.Response(
                status=status,
                text=json.dumps(data),
                content_type="application/json",
            )

        if not ok:
            return web.Response(
                status=400,
                text=json.dumps({"error": "Validation failed"}),
                content_type="application/json",
            )

        # 2. on_request
        try:
            status, data = task_cls.on_request(body)
        except Exception as e:
            status, data = task_cls.on_error(e)

        return web.Response(
            status=status,
            text=json.dumps(data),
            content_type="application/json",
        )

    return handler
