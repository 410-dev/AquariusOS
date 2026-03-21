# pyhttpd.apprun/access_logger.py

import json
import logging
import os
import time
from logging.handlers import RotatingFileHandler

LOG_BASE = "/var/log/pyhttpd"
_loggers: dict[str, logging.Logger] = {}


def _log_path(user: str, context: str, port: int) -> str:
    return os.path.join(LOG_BASE, user, f"{context}.{port}.log")


def get_logger(user: str, context: str, port: int) -> logging.Logger:
    """
    인스턴스별 로거를 반환합니다. 이미 생성된 경우 캐시에서 반환.
    """
    key = f"{user}.{context}.{port}"
    if key in _loggers:
        return _loggers[key]

    log_path = _log_path(user, context, port)
    os.makedirs(os.path.dirname(log_path), mode=0o755, exist_ok=True)

    logger = logging.getLogger(f"pyhttpd.access.{key}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # 루트 로거로 전파 차단

    handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

    _loggers[key] = logger
    return logger


def remove_logger(user: str, context: str, port: int):
    """인스턴스 언로드 시 로거 핸들러를 닫고 캐시에서 제거합니다."""
    key = f"{user}.{context}.{port}"
    logger = _loggers.pop(key, None)
    if logger:
        for h in logger.handlers[:]:
            h.close()
            logger.removeHandler(h)


def write_access(
    user: str,
    context: str,
    port: int,
    method: str,
    path: str,
    status: int,
    elapsed_ms: float,
    body: str,
    error: str | None = None,
):
    logger = get_logger(user, context, port)
    entry = {
        "ts":      time.strftime("%Y-%m-%dT%H:%M:%S"),
        "method":  method,
        "path":    path,
        "status":  status,
        "ms":      round(elapsed_ms, 2),
        "body":    body[:2048],          # 최대 2KB만 저장
    }
    if error:
        entry["error"] = error
    logger.info(json.dumps(entry, ensure_ascii=False))
