# pyhttpd/instance_manager.py

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from loader import load_webhook, LoadError
from router import Router

logger = logging.getLogger("instance_manager")

ENABLED_DIR = "/etc/pyhttpd/enabled"

# 파일명 컨벤션: <user>.<context>.<port>.inst
INST_PATTERN = re.compile(
    r"^(?P<user>[^.]+)\.(?P<context>[^.]+)\.(?P<port>\d+)\.inst$"
)


@dataclass(frozen=True)
class InstanceKey:
    user: str
    context: str
    port: int


def parse_inst_filename(filename: str) -> InstanceKey | None:
    m = INST_PATTERN.match(filename)
    if not m:
        return None
    return InstanceKey(
        user=m.group("user"),
        context=m.group("context"),
        port=int(m.group("port")),
    )


class InstanceManager:
    """
    /etc/pyhttpd/enabled/ 디렉토리를 주기적으로 스캔하여
    .inst 심볼릭 링크의 추가/제거를 감지하고 Router에 반영합니다.

    inotify/watchdog 대신 polling 방식으로 구현하여
    의존성을 최소화합니다. (추후 watchdog으로 교체 가능)
    """

    def __init__(self, router: Router, poll_interval: float = 2.0):
        self._router = router
        self._poll_interval = poll_interval
        # 현재 로드된 인스턴스 추적
        self._loaded: set[InstanceKey] = set()
        self._running = False

    async def _scan(self) -> set[InstanceKey]:
        """enabled 디렉토리를 스캔해서 현재 있어야 할 인스턴스 집합을 반환합니다."""
        found: set[InstanceKey] = set()

        if not os.path.isdir(ENABLED_DIR):
            return found

        for filename in os.listdir(ENABLED_DIR):
            key = parse_inst_filename(filename)
            if key is None:
                continue

            inst_path = os.path.join(ENABLED_DIR, filename)

            # 심볼릭 링크가 유효한지 확인
            if not os.path.islink(inst_path) or not os.path.exists(inst_path):
                logger.warning(f"Broken or non-symlink .inst file: {filename}, skipping")
                continue

            found.add(key)

        return found

    def _resolve_script_path(self, key: InstanceKey) -> str:
        """
        .inst 심볼릭 링크가 가리키는 실제 .py 파일 경로를 반환합니다.
        """
        filename = f"{key.user}.{key.context}.{key.port}.inst"
        inst_path = os.path.join(ENABLED_DIR, filename)
        return os.path.realpath(inst_path)

    async def _load(self, key: InstanceKey):
        script_path = self._resolve_script_path(key)
        try:
            task_cls = load_webhook(script_path)
            # user를 router에 함께 전달
            await self._router.register(key.port, key.user, key.context, task_cls)
            self._loaded.add(key)
            logger.info(f"Loaded: {key}")
        except LoadError as e:
            logger.error(f"Failed to load {key}: {e}")

    async def _unload(self, key: InstanceKey):
        try:
            await self._router.unregister(key.port, key.user, key.context)
            self._loaded.discard(key)
            logger.info(f"Unloaded: {key}")
        except KeyError as e:
            logger.warning(f"Tried to unload non-existent key {key}: {e}")

    async def _reconcile(self):
        """
        현재 상태(loaded)와 원하는 상태(scanned)를 비교해서
        추가/제거가 필요한 인스턴스를 처리합니다.
        """
        desired = await self._scan()

        to_add    = desired - self._loaded
        to_remove = self._loaded - desired

        for key in to_remove:
            await self._unload(key)

        for key in to_add:
            await self._load(key)

    async def run(self):
        """
        폴링 루프. 데몬의 메인 태스크로 실행됩니다.
        """
        self._running = True
        logger.info(f"InstanceManager started (poll every {self._poll_interval}s)")

        # 초기 스캔
        await self._reconcile()

        while self._running:
            await asyncio.sleep(self._poll_interval)
            await self._reconcile()

    def stop(self):
        self._running = False