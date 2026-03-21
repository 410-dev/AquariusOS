# pyhttpd/router.py

import asyncio
import logging
from aiohttp import web
from osext.pyhttp.Webhook import WebhookTask
from handler import make_handler
from access_logger import remove_logger

logger = logging.getLogger("router")


class PortRouter:
    """
    단일 포트에 대한 aiohttp 서버 + 동적 라우팅 관리.

    aiohttp는 AppRunner가 시작된 후 라우트를 추가할 수 없기 때문에
    내부적으로 중간 디스패처(dispatcher)를 두고,
    실제 라우트 테이블은 dict로 직접 관리합니다.
    """

    def __init__(self, port: int):
        self.port = port
        # context -> handler 함수 매핑
        # context "root" → path "/"
        self._routes: dict[str, web.Request] = {}
        self._app = web.Application()
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

        # 모든 요청을 받는 단일 캐치올 핸들러 등록
        self._app.router.add_route("POST", "/{path_info:.*}", self._dispatch)
        self._app.router.add_route("GET",  "/{path_info:.*}", self._dispatch)

    async def _dispatch(self, request: web.Request) -> web.Response:
        """
        URL path를 보고 적절한 WebhookTask 핸들러로 디스패치합니다.
        """
        # 첫 번째 path segment를 context로 사용
        # /trading-idea/... → "trading-idea"
        # /               → "root"
        segments = request.path.lstrip("/").split("/")
        context = segments[0] if segments[0] else "root"

        handler = self._routes.get(context)

        if handler is None:
            return web.Response(
                status=404,
                text=f"No handler registered for context: '{context}'",
            )

        return await handler(request)

    async def start(self):
        """aiohttp AppRunner + TCPSite를 시작합니다."""
        self._runner = web.AppRunner(self._app, access_log=logger)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host="0.0.0.0", port=self.port)
        await self._site.start()
        logger.info(f"[:{self.port}] Listening")

    async def stop(self):
        """포트 서버를 완전히 종료합니다."""
        if self._runner:
            await self._runner.cleanup()
        logger.info(f"[:{self.port}] Stopped")

    # def register(self, context: str, task_cls: type[WebhookTask]):
    #     """
    #     context에 WebhookTask를 등록합니다. 이미 존재하면 교체(hot-reload).
    #     서버 재시작 없이 즉시 반영됩니다.
    #     """
    #     if context in self._routes:
    #         logger.warning(f"[:{self.port}] Replacing existing context '{context}'")
    #     self._routes[context] = make_handler(task_cls)
    #     logger.info(f"[:{self.port}] Registered /{'' if context == 'root' else context}")
    #
    # def unregister(self, context: str):
    #     """context를 제거합니다."""
    #     if context not in self._routes:
    #         raise KeyError(f"Context '{context}' not registered on port {self.port}")
    #     del self._routes[context]
    #     logger.info(f"[:{self.port}] Unregistered context '{context}'")

    def register(self, user: str, context: str, task_cls: type[WebhookTask]):
        # 기존 핸들러 교체 시 로거도 교체
        if context in self._routes:
            remove_logger(user, context, self.port)
        self._routes[context] = make_handler(task_cls, user, context, self.port)
        logger.info(f"[:{self.port}] Registered /{'' if context == 'root' else context}")

    def unregister(self, user: str, context: str):
        if context not in self._routes:
            raise KeyError(f"Context '{context}' not registered on port {self.port}")
        del self._routes[context]
        remove_logger(user, context, self.port)
        logger.info(f"[:{self.port}] Unregistered context '{context}'")

    def list_contexts(self) -> list[str]:
        return list(self._routes.keys())


class Router:
    """
    전체 포트 → PortRouter 매핑을 관리하는 최상위 라우터.
    데몬이 이 클래스 하나만 들고 있으면 됩니다.
    """

    def __init__(self):
        self._ports: dict[int, PortRouter] = {}

    # async def register(self, port: int, context: str, task_cls: type[WebhookTask]):
    #     """
    #     포트+컨텍스트에 WebhookTask를 등록합니다.
    #     해당 포트의 서버가 없으면 새로 시작합니다.
    #     """
    #     if port not in self._ports:
    #         port_router = PortRouter(port)
    #         await port_router.start()
    #         self._ports[port] = port_router
    #
    #     self._ports[port].register(context, task_cls)
    #
    # async def unregister(self, port: int, context: str):
    #     """
    #     컨텍스트를 제거합니다.
    #     해당 포트에 남은 컨텍스트가 없으면 서버도 종료합니다.
    #     """
    #     if port not in self._ports:
    #         raise KeyError(f"Port {port} not active")
    #
    #     port_router = self._ports[port]
    #     port_router.unregister(context)
    #
    #     if not port_router.list_contexts():
    #         await port_router.stop()
    #         del self._ports[port]
    #         logger.info(f"Port {port} has no more contexts, server stopped")
    async def register(self, port: int, user: str, context: str, task_cls):
        if port not in self._ports:
            port_router = PortRouter(port)
            await port_router.start()
            self._ports[port] = port_router
        self._ports[port].register(user, context, task_cls)

    async def unregister(self, port: int, user: str, context: str):
        if port not in self._ports:
            raise KeyError(f"Port {port} not active")
        port_router = self._ports[port]
        port_router.unregister(user, context)
        if not port_router.list_contexts():
            await port_router.stop()
            del self._ports[port]

    async def stop_all(self):
        """모든 포트 서버를 종료합니다. 데몬 종료 시 호출."""
        for port_router in self._ports.values():
            await port_router.stop()
        self._ports.clear()

    def status(self) -> dict:
        """현재 활성 포트/컨텍스트 목록을 반환합니다."""
        return {
            port: pr.list_contexts()
            for port, pr in self._ports.items()
        }