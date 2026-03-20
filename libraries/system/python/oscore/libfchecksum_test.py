from oscore.libfchecksum import file_checksum, file_matches, bytes_checksum, bytes_matches
import hashlib

def test_file_checksum(tmp_path):
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello world")

    result = file_checksum(str(f))
    assert result == hashlib.sha256(b"hello world").hexdigest()


def test_file_matches_true(tmp_path):
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello world")
    expected = hashlib.sha256(b"hello world").hexdigest()

    assert file_matches(str(f), expected) is True


def test_file_matches_false(tmp_path):
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello world")

    assert file_matches(str(f), "wrongchecksum") is False


def test_file_checksum_md5(tmp_path):
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello world")

    result = file_checksum(str(f), algorithm="md5")
    assert result == hashlib.md5(b"hello world").hexdigest()

def test_bytes_checksum(tmp_path):
    data = b"hello world"
    result = bytes_checksum(data)
    assert result == hashlib.sha256(data).hexdigest()

def test_bytes_checksum_sha256(tmp_path):
    data = b"hello world"
    result = bytes_checksum(data)
    assert result == hashlib.sha256(data).hexdigest()

def test_bytes_matches_true(tmp_path):
    result = bytes_checksum(b"hello world")
    assert result == hashlib.sha256(b"hello world").hexdigest()

def test_bytes_matches_false(tmp_path):
    assert bytes_matches(b"hello world", hashlib.sha256(b"hello world").hexdigest())
