# pyhttpd.apprun/access_logger_test.py

import json
import os
import pytest
from unittest.mock import patch
from access_logger import (
    get_logger,
    remove_logger,
    write_access,
    _log_path,
    _loggers,
)


@pytest.fixture(autouse=True)
def clean_loggers():
    """각 테스트 전후로 로거 캐시와 핸들러를 정리합니다."""
    _loggers.clear()
    yield
    for key in list(_loggers.keys()):
        logger = _loggers.pop(key)
        for h in logger.handlers[:]:
            h.close()
            logger.removeHandler(h)


@pytest.fixture
def log_dir(tmp_path):
    with patch("access_logger.LOG_BASE", str(tmp_path)):
        yield tmp_path


class TestGetLogger:
    def test_creates_log_file(self, log_dir):
        get_logger("alice", "trading", 8080)
        assert os.path.isfile(os.path.join(log_dir, "alice", "trading.8080.log"))

    def test_returns_same_instance_on_second_call(self, log_dir):
        l1 = get_logger("alice", "trading", 8080)
        l2 = get_logger("alice", "trading", 8080)
        assert l1 is l2

    def test_different_instances_for_different_keys(self, log_dir):
        l1 = get_logger("alice", "trading", 8080)
        l2 = get_logger("alice", "other",   8080)
        assert l1 is not l2


class TestRemoveLogger:
    def test_removes_from_cache(self, log_dir):
        get_logger("alice", "trading", 8080)
        remove_logger("alice", "trading", 8080)
        assert "alice.trading.8080" not in _loggers

    def test_no_error_on_nonexistent(self, log_dir):
        remove_logger("ghost", "ctx", 9999)  # 예외 없이 통과해야 함


class TestWriteAccess:
    def _read_log(self, log_dir, user, context, port) -> list[dict]:
        path = os.path.join(log_dir, user, f"{context}.{port}.log")
        with open(path) as f:
            return [json.loads(l) for l in f if l.strip()]

    def test_writes_entry(self, log_dir):
        write_access("alice", "trading", 8080, "POST", "/trading", 200, 3.5, "{}")
        entries = self._read_log(log_dir, "alice", "trading", 8080)
        assert len(entries) == 1

    def test_entry_fields(self, log_dir):
        write_access("alice", "trading", 8080, "POST", "/trading", 200, 3.5, '{"k":"v"}')
        entry = self._read_log(log_dir, "alice", "trading", 8080)[0]
        assert entry["method"] == "POST"
        assert entry["path"]   == "/trading"
        assert entry["status"] == 200
        assert entry["ms"]     == 3.5
        assert entry["body"]   == '{"k":"v"}'
        assert "ts" in entry

    def test_error_field_included_when_provided(self, log_dir):
        write_access("alice", "ctx", 8080, "POST", "/", 500, 1.0, "{}", error="boom")
        entry = self._read_log(log_dir, "alice", "ctx", 8080)[0]
        assert entry["error"] == "boom"

    def test_error_field_absent_when_none(self, log_dir):
        write_access("alice", "ctx", 8080, "POST", "/", 200, 1.0, "{}")
        entry = self._read_log(log_dir, "alice", "ctx", 8080)[0]
        assert "error" not in entry

    def test_body_truncated_at_2048(self, log_dir):
        long_body = "x" * 4096
        write_access("alice", "ctx", 8080, "POST", "/", 200, 1.0, long_body)
        entry = self._read_log(log_dir, "alice", "ctx", 8080)[0]
        assert len(entry["body"]) == 2048

    def test_multiple_entries_appended(self, log_dir):
        for i in range(3):
            write_access("alice", "ctx", 8080, "POST", "/", 200, float(i), "{}")
        entries = self._read_log(log_dir, "alice", "ctx", 8080)
        assert len(entries) == 3
