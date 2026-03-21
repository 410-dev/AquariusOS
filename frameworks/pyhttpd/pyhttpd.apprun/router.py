# pyhttpd.apprun/router.py

import asyncio
import logging
import ssl
from aiohttp import web
from osext.pyhttp.Webhook import WebhookTask
from handler import make_handler
from access_logger import remove_logger

logger = logging.getLogger("pyhttpd.router")


class PortRouter:
    """단일 포트 담당. ssl_context가 있으면 HTTPS로 시작합니다."""

    def __init__(self, port: int, ssl_context: ssl.SSLContext | None = None):
        self.port = port
        self.ssl_context = ssl_context
        self._routes: dict[str, object] = {}
        self._app = web.Application()
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._app.router.add_route("POST", "/{path_info:.*}", self._dispatch)
        self._app.router.add_route("GET",  "/{path_info:.*}", self._dispatch)

    @property
    def is_https(self) -> bool:
        return self.ssl_context is not None

    async def _dispatch(self, request: web.Request) -> web.Response:
        segments = request.path.lstrip("/").split("/")
        context = segments[0] if segments[0] else "root"
        handler = self._routes.get(context)
        if handler is None:
            return web.Response(status=404,
                                text=f"No handler for context: '{context}'")
        return await handler(request)

    async def start(self):
        self._runner = web.AppRunner(self._app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(
            self._runner,
            host="0.0.0.0",
            port=self.port,
            ssl_context=self.ssl_context,   # None이면 HTTP
        )
        await self._site.start()
        proto = "HTTPS" if self.is_https else "HTTP"
        logger.info(f"[:{self.port}] {proto} Listening")

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()
        logger.info(f"[:{self.port}] Stopped")

    def register(self, user: str, context: str, task_cls: type[WebhookTask]):
        if context in self._routes:
            remove_logger(user, context, self.port)
        self._routes[context] = make_handler(task_cls, user, context, self.port)
        logger.info(f"[:{self.port}] Registered /{'' if context == 'root' else context}")

    def unregister(self, user: str, context: str):
        if context not in self._routes:
            raise KeyError(f"Context '{context}' not registered on :{self.port}")
        del self._routes[context]
        remove_logger(user, context, self.port)

    def list_contexts(self) -> list[str]:
        return list(self._routes.keys())


class RedirectRouter:
    """
    HTTP → HTTPS 리다이렉트 전용 포트 라우터.
    모든 요청을 https://<host>:<https_port><path> 로 301 리다이렉트합니다.
    """

    def __init__(self, port: int):
        self.port = port
        self._https_ports: dict[str, int] = {}  # context → https_port
        self._app = web.Application()
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._app.router.add_route("*", "/{path_info:.*}", self._redirect)

    async def _redirect(self, request: web.Request) -> web.Response:
        segments = request.path.lstrip("/").split("/")
        context = segments[0] if segments[0] else "root"
        https_port = self._https_ports.get(context, 443)
        location = f"https://{request.host.split(':')[0]}:{https_port}{request.path}"
        if request.query_string:
            location += f"?{request.query_string}"
        return web.Response(status=301, headers={"Location": location})

    async def start(self):
        self._runner = web.AppRunner(self._app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host="0.0.0.0", port=self.port)
        await self._site.start()
        logger.info(f"[:{self.port}] HTTP→HTTPS redirect listening")

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()

    def register(self, context: str, https_port: int):
        self._https_ports[context] = https_port

    def unregister(self, context: str):
        self._https_ports.pop(context, None)

    def list_contexts(self) -> list[str]:
        return list(self._https_ports.keys())


class Router:
    def __init__(self):
        self._ports: dict[int, PortRouter] = {}
        self._redirects: dict[int, RedirectRouter] = {}

    async def register(self, port: int, user: str, context: str,
                       task_cls: type[WebhookTask],
                       ssl_ctx: ssl.SSLContext | None = None):
        if port not in self._ports:
            pr = PortRouter(port, ssl_context=ssl_ctx)
            await pr.start()
            self._ports[port] = pr
        self._ports[port].register(user, context, task_cls)

    async def unregister(self, port: int, user: str, context: str):
        if port not in self._ports:
            raise KeyError(f"Port {port} not active")
        pr = self._ports[port]
        pr.unregister(user, context)
        if not pr.list_contexts():
            await pr.stop()
            del self._ports[port]

    async def register_redirect(self, port: int, user: str, context: str):
        """
        redirect 인스턴스 등록. https_port는 inst 메타데이터에서 읽습니다.
        inst 파일명에 https_port를 인코딩하는 대신 인증서가 있는
        같은 context의 https 포트를 자동으로 찾습니다.
        """
        # 같은 context의 https PortRouter 포트를 탐색
        https_port = next(
            (p for p, pr in self._ports.items() if pr.is_https
             and context in pr.list_contexts()),
            443,
        )
        if port not in self._redirects:
            rr = RedirectRouter(port)
            await rr.start()
            self._redirects[port] = rr
        self._redirects[port].register(context, https_port)
        logger.info(f"[:{port}] Redirect /{context} → https://...:{https_port}")

    async def unregister_redirect(self, port: int, user: str, context: str):
        if port not in self._redirects:
            raise KeyError(f"Redirect port {port} not active")
        rr = self._redirects[port]
        rr.unregister(context)
        if not rr.list_contexts():
            await rr.stop()
            del self._redirects[port]

    async def stop_all(self):
        for pr in self._ports.values():
            await pr.stop()
        for rr in self._redirects.values():
            await rr.stop()
        self._ports.clear()
        self._redirects.clear()

    def status(self) -> dict:
        result = {}
        for port, pr in self._ports.items():
            result[port] = {
                "proto":    "https" if pr.is_https else "http",
                "contexts": pr.list_contexts(),
            }
        for port, rr in self._redirects.items():
            result[port] = {
                "proto":    "redirect",
                "contexts": rr.list_contexts(),
            }
        return result