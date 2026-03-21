# pyhttpd.apprun/instance_manager.py

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from loader import load_webhook, LoadError
from ssl_manager import make_ssl_context, renew_acme_all

logger = logging.getLogger("instance_manager")

ENABLED_DIR = "/etc/pyhttpd/enabled"

# <user>.<context>.<port>.<proto>.inst
# proto: http | https | redirect
INST_PATTERN = re.compile(
    r"^(?P<user>[^.]+)\.(?P<context>[^.]+)\.(?P<port>\d+)"
    r"\.(?P<proto>http|https|redirect)\.inst$"
)

ACME_RENEW_INTERVAL = 12 * 60 * 60  # 12시간


@dataclass(frozen=True)
class InstanceKey:
    user:    str
    context: str
    port:    int
    proto:   str          # "http" | "https" | "redirect"


def parse_inst_filename(filename: str) -> InstanceKey | None:
    m = INST_PATTERN.match(filename)
    if not m:
        return None
    return InstanceKey(
        user=m.group("user"),
        context=m.group("context"),
        port=int(m.group("port")),
        proto=m.group("proto"),
    )


class InstanceManager:
    def __init__(self, router, poll_interval: float = 2.0):
        self._router = router
        self._poll_interval = poll_interval
        self._loaded: set[InstanceKey] = set()
        self._running = False

    async def _scan(self) -> set[InstanceKey]:
        found: set[InstanceKey] = set()
        if not os.path.isdir(ENABLED_DIR):
            return found
        for filename in os.listdir(ENABLED_DIR):
            key = parse_inst_filename(filename)
            if key is None:
                continue
            inst_path = os.path.join(ENABLED_DIR, filename)
            if not os.path.islink(inst_path) or not os.path.exists(inst_path):
                logger.warning(f"Broken symlink: {filename}, skipping")
                continue
            found.add(key)
        return found

    def _resolve_script_path(self, key: InstanceKey) -> str:
        filename = f"{key.user}.{key.context}.{key.port}.{key.proto}.inst"
        return os.path.realpath(os.path.join(ENABLED_DIR, filename))

    async def _load(self, key: InstanceKey):
        # redirect 인스턴스는 스크립트 로딩 없이 바로 등록
        if key.proto == "redirect":
            await self._router.register_redirect(
                key.port, key.user, key.context
            )
            self._loaded.add(key)
            logger.info(f"Loaded redirect: {key}")
            return

        script_path = self._resolve_script_path(key)
        try:
            task_cls = load_webhook(script_path)

            ssl_ctx = None
            if key.proto == "https":
                try:
                    ssl_ctx = make_ssl_context(key.user, key.context, key.port)
                except FileNotFoundError as e:
                    logger.error(f"SSL cert missing for {key}: {e}")
                    return

            await self._router.register(
                key.port, key.user, key.context, task_cls, ssl_ctx=ssl_ctx
            )
            self._loaded.add(key)
            logger.info(f"Loaded: {key}")
        except LoadError as e:
            logger.error(f"Failed to load {key}: {e}")

    async def _unload(self, key: InstanceKey):
        try:
            if key.proto == "redirect":
                await self._router.unregister_redirect(key.port, key.user, key.context)
            else:
                await self._router.unregister(key.port, key.user, key.context)
            self._loaded.discard(key)
            logger.info(f"Unloaded: {key}")
        except KeyError as e:
            logger.warning(f"Tried to unload non-existent key {key}: {e}")

    async def _reconcile(self):
        desired = await self._scan()
        for key in self._loaded - desired:
            await self._unload(key)
        for key in desired - self._loaded:
            await self._load(key)

    async def run(self):
        self._running = True
        logger.info(f"InstanceManager started (poll every {self._poll_interval}s)")
        await self._reconcile()

        renew_elapsed = 0.0
        while self._running:
            await asyncio.sleep(self._poll_interval)
            renew_elapsed += self._poll_interval
            await self._reconcile()

            # 12시간마다 ACME 갱신 시도
            if renew_elapsed >= ACME_RENEW_INTERVAL:
                renew_elapsed = 0.0
                asyncio.ensure_future(renew_acme_all())

    def stop(self):
        self._running = False