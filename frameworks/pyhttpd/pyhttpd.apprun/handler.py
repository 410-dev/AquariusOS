# # pyhttpd/handler.py
#
# import json
# from aiohttp import web
# from osext.pyhttp.Webhook import WebhookTask
#
#
# def make_handler(task_cls: type[WebhookTask]):
#     """
#     WebhookTask 클래스를 받아 aiohttp 핸들러 함수를 반환합니다.
#     """
#
#     async def handler(request: web.Request) -> web.Response:
#         body = await request.text()
#
#         # 1. validate
#         try:
#             ok = task_cls.validate(body)
#         except Exception as e:
#             status, data = task_cls.on_error(e)
#             return web.Response(
#                 status=status,
#                 text=json.dumps(data),
#                 content_type="application/json",
#             )
#
#         if not ok:
#             return web.Response(
#                 status=400,
#                 text=json.dumps({"error": "Validation failed"}),
#                 content_type="application/json",
#             )
#
#         # 2. on_request
#         try:
#             status, data = task_cls.on_request(body)
#         except Exception as e:
#             status, data = task_cls.on_error(e)
#
#         return web.Response(
#             status=status,
#             text=json.dumps(data),
#             content_type="application/json",
#         )
#
#     return handler
# pyhttpd.apprun/handler.py

import json
import time
import traceback
from aiohttp import web
from osext.pyhttp.Webhook import WebhookTask
from access_logger import write_access


def make_handler(task_cls: type[WebhookTask], user: str, context: str, port: int):
    """
    WebhookTask 클래스를 받아 aiohttp 핸들러 함수를 반환합니다.
    user / context / port 는 access log 기록에 사용됩니다.
    """

    async def handler(request: web.Request) -> web.Response:
        body = await request.text()
        t0 = time.monotonic()
        error_detail: str | None = None

        # 1. validate
        try:
            ok = task_cls.validate(body)
        except Exception as e:
            error_detail = traceback.format_exc()
            status, data = task_cls.on_error(e)
            _log(request, status, t0, body, error_detail)
            return _resp(status, data)

        if not ok:
            status, data = 400, {"error": "Validation failed"}
            _log(request, status, t0, body)
            return _resp(status, data)

        # 2. on_request
        try:
            status, data = task_cls.on_request(body)
        except Exception as e:
            error_detail = traceback.format_exc()
            status, data = task_cls.on_error(e)

        _log(request, status, t0, body, error_detail)
        return _resp(status, data)

    def _log(request, status, t0, body, error=None):
        elapsed = (time.monotonic() - t0) * 1000
        write_access(
            user=user,
            context=context,
            port=port,
            method=request.method,
            path=request.path,
            status=status,
            elapsed_ms=elapsed,
            body=body,
            error=error,
        )

    def _resp(status: int, data: dict) -> web.Response:
        return web.Response(
            status=status,
            text=json.dumps(data, ensure_ascii=False),
            content_type="application/json",
        )

    return handler