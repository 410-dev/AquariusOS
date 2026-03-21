# pyhttpd.apprun/main.py

import asyncio
import logging
import signal
from router import Router
from instance_manager import InstanceManager
from ipc import IPCServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("pyhttpd.daemon")


async def main():
    router = Router()
    manager = InstanceManager(router, poll_interval=2.0)
    ipc = IPCServer(router, manager)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    loop.add_signal_handler(signal.SIGTERM, stop_event.set)
    loop.add_signal_handler(signal.SIGINT,  stop_event.set)

    await ipc.start()
    manager_task = asyncio.create_task(manager.run())

    logger.info("pyhttpd daemon started")
    await stop_event.wait()

    logger.info("Shutting down...")
    manager.stop()
    manager_task.cancel()
    await ipc.stop()
    await router.stop_all()
    logger.info("pyhttpd stopped")


if __name__ == "__main__":
    asyncio.run(main())
