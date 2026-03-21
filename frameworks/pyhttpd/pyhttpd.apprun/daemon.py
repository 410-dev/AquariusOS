# pyhttpd/daemon.py

import asyncio
import logging
import signal
from router import Router
from instance_manager import InstanceManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("daemon")


async def main():
    router = Router()
    manager = InstanceManager(router, poll_interval=2.0)

    loop = asyncio.get_running_loop()

    # SIGTERM / SIGINT → graceful shutdown
    stop_event = asyncio.Event()

    def _shutdown():
        logger.info("Shutdown signal received")
        stop_event.set()

    loop.add_signal_handler(signal.SIGTERM, _shutdown)
    loop.add_signal_handler(signal.SIGINT,  _shutdown)

    # SIGHUP → 즉시 재스캔 (reload)
    def _reload():
        logger.info("SIGHUP received, forcing rescan...")
        asyncio.ensure_future(manager._reconcile())

    loop.add_signal_handler(signal.SIGHUP, _reload)

    # InstanceManager를 백그라운드 태스크로 실행
    manager_task = asyncio.create_task(manager.run())

    # 종료 신호 대기
    await stop_event.wait()

    # Graceful shutdown
    manager.stop()
    manager_task.cancel()
    await router.stop_all()
    logger.info("pyhttpd stopped")


def run():
    asyncio.run(main())