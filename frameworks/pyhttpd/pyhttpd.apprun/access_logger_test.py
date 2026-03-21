# pyhttpd.apprun/access_logger_test.py

import json
import os
import pytest
from unittest.mock import patch
from access_logger import (
    get_logger,
    remove_logger,
    write_access,
    _loggers,
)


@pytest.fixture(autouse=True)
def clean_loggers():
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


def read_log(log_dir, user, context, port) -> list[dict]:
    path = os.path.join(log_dir, user, f"{context}.{port}.log")
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


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

    def test_no_error_on_nonexistent(self):
        remove_logger("ghost", "ctx", 9999)


class TestWriteAccess:
    def test_writes_entry(self, log_dir):
        write_access("alice", "trading", 8080, "POST", "/trading", 200, 3.5, "{}")
        assert len(read_log(log_dir, "alice", "trading", 8080)) == 1

    def test_required_fields_present(self, log_dir):
        write_access("alice", "trading", 8080, "POST", "/trading", 200, 3.5, '{"k":"v"}')
        e = read_log(log_dir, "alice", "trading", 8080)[0]
        assert e["method"] == "POST"
        assert e["path"]   == "/trading"
        assert e["status"] == 200
        assert e["ms"]     == 3.5
        assert e["body"]   == '{"k":"v"}'
        assert "ts" in e

    def test_error_field_included_when_provided(self, log_dir):
        write_access("alice", "ctx", 8080, "POST", "/", 500, 1.0, "{}", error="boom")
        e = read_log(log_dir, "alice", "ctx", 8080)[0]
        assert e["error"] == "boom"

    def test_error_field_absent_when_none(self, log_dir):
        write_access("alice", "ctx", 8080, "POST", "/", 200, 1.0, "{}")
        e = read_log(log_dir, "alice", "ctx", 8080)[0]
        assert "error" not in e

    def test_stdout_field_included_when_provided(self, log_dir):
        write_access("alice", "ctx", 8080, "POST", "/", 200, 1.0, "{}",
                     stdout="hello\nworld")
        e = read_log(log_dir, "alice", "ctx", 8080)[0]
        assert e["stdout"] == ["hello", "world"]

    def test_stdout_empty_lines_filtered(self, log_dir):
        write_access("alice", "ctx", 8080, "POST", "/", 200, 1.0, "{}",
                     stdout="hello\n\n\nworld\n")
        e = read_log(log_dir, "alice", "ctx", 8080)[0]
        assert e["stdout"] == ["hello", "world"]

    def test_stdout_field_absent_when_none(self, log_dir):
        write_access("alice", "ctx", 8080, "POST", "/", 200, 1.0, "{}", stdout=None)
        e = read_log(log_dir, "alice", "ctx", 8080)[0]
        assert "stdout" not in e

    def test_stdout_field_absent_when_empty_string(self, log_dir):
        write_access("alice", "ctx", 8080, "POST", "/", 200, 1.0, "{}", stdout="")
        e = read_log(log_dir, "alice", "ctx", 8080)[0]
        assert "stdout" not in e

    def test_body_truncated_at_2048(self, log_dir):
        write_access("alice", "ctx", 8080, "POST", "/", 200, 1.0, "x" * 4096)
        e = read_log(log_dir, "alice", "ctx", 8080)[0]
        assert len(e["body"]) == 2048

    def test_multiple_entries_appended(self, log_dir):
        for i in range(3):
            write_access("alice", "ctx", 8080, "POST", "/", 200, float(i), "{}")
        assert len(read_log(log_dir, "alice", "ctx", 8080)) == 3
