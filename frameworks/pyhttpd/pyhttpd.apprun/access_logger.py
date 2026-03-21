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
    key = f"{user}.{context}.{port}"
    if key in _loggers:
        return _loggers[key]

    log_path = _log_path(user, context, port)
    os.makedirs(os.path.dirname(log_path), mode=0o755, exist_ok=True)

    logger = logging.getLogger(f"pyhttpd.access.{key}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    _loggers[key] = logger
    return logger


def remove_logger(user: str, context: str, port: int):
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
    stdout: str | None = None,       # 추가
):
    logger = get_logger(user, context, port)
    entry = {
        "ts":     time.strftime("%Y-%m-%dT%H:%M:%S"),
        "method": method,
        "path":   path,
        "status": status,
        "ms":     round(elapsed_ms, 2),
        "body":   body[:2048],
    }
    if stdout:
        # 빈 줄 제거 후 줄 단위 리스트로 저장
        entry["stdout"] = [l for l in stdout.splitlines() if l.strip()]
    if error:
        entry["error"] = error

    logger.info(json.dumps(entry, ensure_ascii=False))
