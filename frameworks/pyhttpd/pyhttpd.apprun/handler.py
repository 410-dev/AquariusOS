# pyhttpd.apprun/handler.py

import io
import json
import sys
import time
import traceback
from aiohttp import web
from osext.pyhttp.Webhook import WebhookTask
from access_logger import write_access


def make_handler(task_cls: type[WebhookTask], user: str, context: str, port: int):

    async def handler(request: web.Request) -> web.Response:
        body = await request.text()
        t0 = time.monotonic()
        error_detail: str | None = None
        stdout_capture = io.StringIO()

        # 1. validate (validate는 짧고 단순해야 하므로 stdout 캡처 범위 밖)
        try:
            ok = task_cls.validate(body)
        except Exception as e:
            error_detail = traceback.format_exc()
            status, data = task_cls.on_error(e)
            _log(request, status, t0, body, error_detail, None)
            return _resp(status, data)

        if not ok:
            _log(request, 400, t0, body, None, None)
            return _resp(400, {"error": "Validation failed"})

        # 2. on_request — stdout 캡처 구간
        old_stdout = sys.stdout
        sys.stdout = stdout_capture
        try:
            status, data = task_cls.on_request(body)
        except Exception as e:
            error_detail = traceback.format_exc()
            status, data = task_cls.on_error(e)
        finally:
            sys.stdout = old_stdout

        captured = stdout_capture.getvalue() or None
        _log(request, status, t0, body, error_detail, captured)
        return _resp(status, data)

    def _log(request, status, t0, body, error, stdout):
        write_access(
            user=user,
            context=context,
            port=port,
            method=request.method,
            path=request.path,
            status=status,
            elapsed_ms=(time.monotonic() - t0) * 1000,
            body=body,
            error=error,
            stdout=stdout,
        )

    def _resp(status: int, data: dict) -> web.Response:
        return web.Response(
            status=status,
            text=json.dumps(data, ensure_ascii=False),
            content_type="application/json",
        )

    return handler
