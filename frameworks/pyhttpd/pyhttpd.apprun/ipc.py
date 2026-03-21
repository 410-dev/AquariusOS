# pyhttpd.apprun/ipc.py

import asyncio
import json
import logging
import os

logger = logging.getLogger("pyhttpd.ipc")

SOCKET_PATH = "/run/pyhttpd/pyhttpd.sock"
_MAX_BYTES = 65536


async def read_message(reader: asyncio.StreamReader) -> dict:
    raw = await reader.read(_MAX_BYTES)
    return json.loads(raw.decode())


async def write_message(writer: asyncio.StreamWriter, payload: dict):
    writer.write(json.dumps(payload).encode())
    await writer.drain()
    writer.close()
    await writer.wait_closed()


class IPCServer:
    """
    데몬 내부에서 실행되는 Unix socket 서버.
    router와 manager를 주입받아 명령을 처리합니다.
    """

    def __init__(self, router, manager):
        self._router = router
        self._manager = manager
        self._server = None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            msg = await read_message(reader)
            cmd = msg.get("cmd")

            if cmd == "ping":
                await write_message(writer, {"ok": True})

            elif cmd == "reload":
                await self._manager._reconcile()
                await write_message(writer, {"ok": True})

            elif cmd == "status":
                await write_message(writer, {
                    "ok": True,
                    "ports": self._router.status(),
                })

            else:
                await write_message(writer, {"ok": False, "error": f"Unknown command: {cmd}"})

        except Exception as e:
            logger.error(f"IPC handle error: {e}")
            try:
                await write_message(writer, {"ok": False, "error": str(e)})
            except Exception:
                pass

    async def start(self):
        os.makedirs(os.path.dirname(SOCKET_PATH), exist_ok=True)

        # 이전 소켓 파일 정리
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)

        self._server = await asyncio.start_unix_server(self._handle, path=SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o660)
        logger.info(f"IPC listening on {SOCKET_PATH}")

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
