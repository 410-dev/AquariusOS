import os
import threading
import tempfile
import pytest

from libatomic import (
    atomic_write,
    atomic_write_bin,
    locking_write,
    locking_write_bin,
    _atomic_write_core,
    _locking_write_core,
)


# ==========================================
# Fixtures
# ==========================================

@pytest.fixture
def tmp_file(tmp_path):
    """테스트용 임시 파일 경로를 반환합니다 (파일은 미리 생성하지 않음)"""
    return str(tmp_path / "test_file.txt")


@pytest.fixture
def existing_file(tmp_path):
    """이미 내용이 있는 임시 파일을 반환합니다"""
    f = tmp_path / "existing.txt"
    f.write_text("original content", encoding="utf-8")
    return str(f)


# ==========================================
# atomic_write 테스트
# ==========================================

class TestAtomicWrite:

    def test_creates_file_with_content(self, tmp_file):
        """파일이 없을 때 새로 생성되어야 한다"""
        atomic_write(tmp_file, "hello world")
        assert os.path.exists(tmp_file)
        with open(tmp_file, encoding="utf-8") as f:
            assert f.read() == "hello world"

    def test_overwrites_existing_file(self, existing_file):
        """기존 파일이 있을 때 내용이 완전히 교체되어야 한다"""
        atomic_write(existing_file, "new content")
        with open(existing_file, encoding="utf-8") as f:
            assert f.read() == "new content"

    def test_empty_string(self, tmp_file):
        """빈 문자열도 정상 처리되어야 한다"""
        atomic_write(tmp_file, "")
        assert os.path.exists(tmp_file)
        with open(tmp_file, encoding="utf-8") as f:
            assert f.read() == ""

    def test_unicode_content(self, tmp_file):
        """유니코드 문자열이 올바르게 저장되어야 한다"""
        content = "한글 테스트 🎉 日本語"
        atomic_write(tmp_file, content, encoding="utf-8")
        with open(tmp_file, encoding="utf-8") as f:
            assert f.read() == content

    def test_large_content(self, tmp_file):
        """대용량 문자열도 정상 처리되어야 한다"""
        content = "A" * 10_000_000  # 10MB
        atomic_write(tmp_file, content)
        with open(tmp_file, encoding="utf-8") as f:
            assert f.read() == content

    def test_no_temp_file_left_on_success(self, tmp_path, tmp_file):
        """성공 후 임시 파일(.tmp~)이 남아 있으면 안 된다"""
        atomic_write(tmp_file, "data")
        leftovers = list(tmp_path.glob("*.tmp~*"))
        assert leftovers == []

    def test_temp_file_cleaned_up_on_error(self, tmp_path, monkeypatch):
        """쓰기 도중 예외 발생 시 임시 파일이 정리되어야 한다"""
        target = str(tmp_path / "target.txt")

        # f.write()가 예외를 던지도록 패치
        original_open = open
        call_count = {"n": 0}

        def fake_open(fd, mode, **kwargs):
            obj = original_open(fd, mode, **kwargs)
            call_count["n"] += 1
            if call_count["n"] == 1:
                obj.write = lambda _: (_ for _ in ()).throw(IOError("disk full"))
            return obj

        monkeypatch.setattr("builtins.open", fake_open)

        with pytest.raises(IOError):
            atomic_write(target, "data")

        leftovers = list(tmp_path.glob("*.tmp~*"))
        assert leftovers == []

    def test_original_preserved_on_error(self, existing_file, monkeypatch):
        """쓰기 실패 시 원본 파일이 유지되어야 한다"""
        original_replace = os.replace

        def fail_replace(src, dst):
            raise OSError("replace failed")

        monkeypatch.setattr(os, "replace", fail_replace)

        with pytest.raises(OSError):
            atomic_write(existing_file, "corrupted")

        with open(existing_file, encoding="utf-8") as f:
            assert f.read() == "original content"

    def test_concurrent_writes_last_one_wins(self, tmp_file):
        """여러 스레드가 동시에 써도 파일이 손상되지 않아야 한다"""
        results = []
        errors = []

        def writer(val: str):
            try:
                atomic_write(tmp_file, val * 1000)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(str(i),)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        with open(tmp_file, encoding="utf-8") as f:
            data = f.read()
        # 파일이 깨지지 않았는지: 길이가 정확히 1000이어야 한다
        assert len(data) == 1000
        assert len(set(data)) == 1  # 단일 문자로만 이루어진 일관된 내용


# ==========================================
# atomic_write_bin 테스트
# ==========================================

class TestAtomicWriteBin:

    def test_creates_binary_file(self, tmp_file):
        atomic_write_bin(tmp_file, b"\x00\x01\x02\x03")
        with open(tmp_file, "rb") as f:
            assert f.read() == b"\x00\x01\x02\x03"

    def test_overwrites_binary_file(self, tmp_path):
        path = str(tmp_path / "bin.bin")
        atomic_write_bin(path, b"old")
        atomic_write_bin(path, b"new_data")
        with open(path, "rb") as f:
            assert f.read() == b"new_data"

    def test_empty_bytes(self, tmp_file):
        atomic_write_bin(tmp_file, b"")
        with open(tmp_file, "rb") as f:
            assert f.read() == b""

    def test_null_bytes(self, tmp_file):
        """널 바이트가 포함된 바이너리도 정확히 저장되어야 한다"""
        content = bytes(range(256))
        atomic_write_bin(tmp_file, content)
        with open(tmp_file, "rb") as f:
            assert f.read() == content


# ==========================================
# locking_write 테스트
# ==========================================

class TestLockingWrite:

    def test_creates_file_with_content(self, tmp_file):
        locking_write(tmp_file, "locked content")
        with open(tmp_file, encoding="utf-8") as f:
            assert f.read() == "locked content"

    def test_overwrites_existing_file(self, existing_file):
        """기존 내용이 완전히 교체되어야 한다 (append 후 truncate)"""
        locking_write(existing_file, "replaced")
        with open(existing_file, encoding="utf-8") as f:
            assert f.read() == "replaced"

    def test_empty_string(self, tmp_file):
        locking_write(tmp_file, "something")
        locking_write(tmp_file, "")
        with open(tmp_file, encoding="utf-8") as f:
            assert f.read() == ""

    def test_unicode_content(self, tmp_file):
        content = "한글 🔒 테스트"
        locking_write(tmp_file, content)
        with open(tmp_file, encoding="utf-8") as f:
            assert f.read() == content

    def test_multiple_sequential_writes(self, tmp_file):
        """순차적 덮어쓰기 시 항상 마지막 내용만 남아야 한다"""
        for i in range(5):
            locking_write(tmp_file, f"write_{i}")
        with open(tmp_file, encoding="utf-8") as f:
            assert f.read() == "write_4"

    def test_concurrent_writes_no_corruption(self, tmp_file):
        """동시 쓰기 시 파일 내용이 섞이거나 손상되면 안 된다"""
        errors = []
        barrier = threading.Barrier(10)

        def writer(val: str):
            try:
                barrier.wait()  # 모든 스레드가 동시에 시작하도록 동기화
                locking_write(tmp_file, val * 500)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(str(i),)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        with open(tmp_file, encoding="utf-8") as f:
            data = f.read()
        assert len(data) == 500
        assert len(set(data)) == 1  # 단일 문자로만 이루어진 일관된 내용

    def test_lock_is_released_after_write(self, tmp_file):
        """쓰기 완료 후 락이 해제되어 다음 쓰기가 가능해야 한다"""
        locking_write(tmp_file, "first")
        locking_write(tmp_file, "second")  # 락이 안 풀리면 deadlock
        with open(tmp_file, encoding="utf-8") as f:
            assert f.read() == "second"

    def test_lock_released_on_exception(self, tmp_file, monkeypatch):
        """예외 발생 시에도 finally 블록에서 락이 반드시 해제되어야 한다"""
        import fcntl as _fcntl

        original_flock = _fcntl.flock
        call_count = {"n": 0}

        def patched_flock(fd, operation):
            original_flock(fd, operation)
            call_count["n"] += 1
            # 첫 번째 LOCK_EX 이후 write에서 예외 발생 시뮬레이션
            if call_count["n"] == 1:
                raise RuntimeError("simulated error after lock")

        monkeypatch.setattr(_fcntl, "flock", patched_flock)

        with pytest.raises(RuntimeError):
            locking_write(tmp_file, "data")

        # 락 해제 후 다음 쓰기가 정상 동작해야 한다
        monkeypatch.undo()
        locking_write(tmp_file, "after error")
        with open(tmp_file, encoding="utf-8") as f:
            assert f.read() == "after error"


# ==========================================
# locking_write_bin 테스트
# ==========================================

class TestLockingWriteBin:

    def test_creates_binary_file(self, tmp_file):
        locking_write_bin(tmp_file, b"\xDE\xAD\xBE\xEF")
        with open(tmp_file, "rb") as f:
            assert f.read() == b"\xDE\xAD\xBE\xEF"

    def test_overwrites_binary_file(self, tmp_path):
        path = str(tmp_path / "lock_bin.bin")
        locking_write_bin(path, b"old_bytes")
        locking_write_bin(path, b"new_bytes")
        with open(path, "rb") as f:
            assert f.read() == b"new_bytes"

    def test_empty_bytes(self, tmp_file):
        locking_write_bin(tmp_file, b"something")
        locking_write_bin(tmp_file, b"")
        with open(tmp_file, "rb") as f:
            assert f.read() == b""

    def test_concurrent_binary_writes(self, tmp_file):
        """동시 바이너리 쓰기 시 파일이 손상되지 않아야 한다"""
        errors = []
        chunk = bytes(range(256))  # 256바이트 고정 패턴
        barrier = threading.Barrier(8)

        def writer():
            try:
                barrier.wait()
                locking_write_bin(tmp_file, chunk)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        with open(tmp_file, "rb") as f:
            data = f.read()
        assert len(data) == 256
        assert data == chunk  # 패턴이 깨지지 않아야 한다


# ==========================================
# _atomic_write_core / _locking_write_core 공통 엣지 케이스
# ==========================================

class TestEdgeCases:

    def test_atomic_write_invalid_encoding(self, tmp_file):
        """잘못된 인코딩 지정 시 예외가 발생해야 한다"""
        with pytest.raises((LookupError, UnicodeEncodeError)):
            atomic_write(tmp_file, "test", encoding="invalid-encoding-xyz")

    def test_atomic_write_to_nonexistent_directory(self):
        """존재하지 않는 디렉토리에 쓰기 시도 시 예외가 발생해야 한다"""
        with pytest.raises(FileNotFoundError):
            atomic_write("/nonexistent_dir_xyz/file.txt", "data")

    def test_locking_write_to_nonexistent_directory(self):
        with pytest.raises(FileNotFoundError):
            locking_write("/nonexistent_dir_xyz/file.txt", "data")

    def test_atomic_write_newlines(self, tmp_file):
        """개행 문자가 변환되지 않고 그대로 저장되어야 한다"""
        content = "line1\nline2\r\nline3\r"
        atomic_write(tmp_file, content)
        with open(tmp_file, encoding="utf-8", newline="") as f:
            assert f.read() == content

    def test_locking_write_newlines(self, tmp_file):
        content = "line1\nline2\r\nline3\r"
        locking_write(tmp_file, content)
        with open(tmp_file, encoding="utf-8", newline="") as f:
            assert f.read() == content

    def test_atomic_vs_locking_same_result(self, tmp_path):
        """두 방식 모두 동일한 결과를 만들어야 한다"""
        content = "동일한 내용 테스트 123"
        a_path = str(tmp_path / "atomic.txt")
        l_path = str(tmp_path / "locking.txt")

        atomic_write(a_path, content)
        locking_write(l_path, content)

        with open(a_path, encoding="utf-8") as f:
            a_data = f.read()
        with open(l_path, encoding="utf-8") as f:
            l_data = f.read()

        assert a_data == l_data == content
