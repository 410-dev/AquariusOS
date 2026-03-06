import os
import hashlib
import uuid
import time
import errno
import json
from typing import Optional, Dict, Any

# ---------- Configuration ----------
VFS_ROOT = '/opt/aqua/vfs'
# Poll interval used by read(wait-for-file) earlier
_DEFAULT_POLL = 0.05


# ---------- Helpers ----------
def _ensure_vfs_root():
    if not os.path.exists(VFS_ROOT):
        # Read registry without libreg to avoid circular import
        # If value of EnablePersistentVFS is true, then mkdirs
        # Otherwise, raise error
        try:
            enable_persistent = False
            try:
                with open('/opt/aqua/registry/SYSTEM/Services/VFS/EnablePersistentVFS', 'r', encoding='utf-8') as f:
                    val = f.read().strip().lower()
                    enable_persistent = val in ('1', 'true', 'yes')
            except Exception:
                pass

            if enable_persistent:
                os.makedirs(VFS_ROOT, exist_ok=True)
            else:
                raise RuntimeError(f"VFS root {VFS_ROOT} does not exist and persistent VFS is disabled.")
        except Exception as e:
            raise RuntimeError(f"Failed to ensure VFS root {VFS_ROOT}: {e}") from e


def _get_vfs_path(filename: str) -> str:
    _ensure_vfs_root()
    hash_object = hashlib.sha512(filename.encode())
    hash_hex = hash_object.hexdigest()
    return os.path.join(VFS_ROOT, hash_hex)


def _get_meta_path_for_target(target_path: str) -> str:
    # meta file stored next to content file, deterministic name
    return f"{target_path}.access.json"


def _fsync_dir(path: str) -> None:
    """Best-effort fsync of containing directory."""
    try:
        dirfd = os.open(os.path.dirname(path) or '.', os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except Exception:
        pass


def _atomic_write_bytes(path: str, data: bytes) -> bool:
    """
    Atomically write bytes to `path` by creating unique temp file in same dir
    and os.replace(temp, path). Returns True on success, False on failure.
    """
    dirname = os.path.dirname(path) or '.'
    temp_name = os.path.join(dirname, f".tmp.{os.getpid()}.{uuid.uuid4().hex}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(temp_name, flags, 0o600)
    except FileExistsError:
        # extremely unlikely due to uuid; retry a few times
        for _ in range(3):
            temp_name = os.path.join(dirname, f".tmp.{os.getpid()}.{uuid.uuid4().hex}")
            try:
                fd = os.open(temp_name, flags, 0o600)
                break
            except FileExistsError:
                continue
        else:
            return False
    except Exception:
        return False

    try:
        total_written = 0
        L = len(data)
        while total_written < L:
            written = os.write(fd, data[total_written:])
            if written == 0:
                raise IOError("write returned 0")
            total_written += written
        os.fsync(fd)
        os.close(fd)
        fd = None
        # Atomic replace
        os.replace(temp_name, path)
        # ensure directory entry persisted (best-effort)
        _fsync_dir(path)
        return True
    except Exception:
        try:
            if 'fd' in locals() and fd:
                try:
                    os.close(fd)
                except Exception:
                    pass
            if os.path.exists(temp_name):
                try:
                    os.unlink(temp_name)
                except Exception:
                    pass
        except:
            pass
        return False


def _read_json_file(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, 'rb') as f:
            content = f.read()
        return json.loads(content.decode('utf-8'))
    except FileNotFoundError:
        return None
    except Exception:
        # corrupt or unreadable -> treat as None
        return None


def _write_json_file_atomic(path: str, obj: Dict[str, Any]) -> bool:
    data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    return _atomic_write_bytes(path, data)


# ---------- Access record (metadata) management ----------
def get_access_record(filename: str) -> Optional[Dict[str, Any]]:
    """
    Return the access record dict for `filename`, or None if not present or unreadable.
    Fields: created_at, last_written_at, last_read_at (epoch floats or None).
    """
    target = _get_vfs_path(filename)
    meta_path = _get_meta_path_for_target(target)
    return _read_json_file(meta_path)


def _create_initial_access_record(target_path: str, now: float) -> Dict[str, Any]:
    return {
        "created_at": now,
        "last_written_at": now,
        "last_read_at": None
    }


def update_access_on_write(filename: str) -> bool:
    """
    Called after a successful write: create meta file if missing, otherwise update last_written_at.
    Returns True on success.
    """
    target = _get_vfs_path(filename)
    meta_path = _get_meta_path_for_target(target)
    now = time.time()

    current = _read_json_file(meta_path)
    if current is None:
        record = _create_initial_access_record(target, now)
    else:
        # preserve created_at if present
        created = current.get("created_at", now)
        record = {
            "created_at": created,
            "last_written_at": now,
            "last_read_at": current.get("last_read_at")
        }
    return _write_json_file_atomic(meta_path, record)


def update_access_on_read(filename: str) -> bool:
    """
    Called after a successful read: update last_read_at. Returns True on success.
    If no access record exists, create one with created_at set to last_read_at (best-effort).
    """
    target = _get_vfs_path(filename)
    meta_path = _get_meta_path_for_target(target)
    now = time.time()

    current = _read_json_file(meta_path)
    if current is None:
        # create a record where created_at == last_read_at (file may have been created outside this service)
        record = {
            "created_at": now,
            "last_written_at": None,
            "last_read_at": now
        }
    else:
        record = {
            "created_at": current.get("created_at", now),
            "last_written_at": current.get("last_written_at"),
            "last_read_at": now
        }
    return _write_json_file_atomic(meta_path, record)

def get_all_access_records() -> Dict[str, Dict[str, Any]]:
    """
    Return a dict mapping filenames (hashed) to their access records.
    Only includes files that have an access record.
    """
    records = {}
    _ensure_vfs_root()
    for entry in os.listdir(VFS_ROOT):
        if entry.endswith('.access.json'):
            meta_path = os.path.join(VFS_ROOT, entry)
            target_hash = entry[:-len('.access.json')]
            record = _read_json_file(meta_path)
            if record is not None:
                records[target_hash] = record
    return records

def delete_access_record(filename: str) -> bool:
    """
    Delete the access-record file for `filename`. Return True if file deleted or not present.
    """
    target = _get_vfs_path(filename)
    meta_path = _get_meta_path_for_target(target)
    try:
        if os.path.exists(meta_path):
            os.unlink(meta_path)
        return True
    except FileNotFoundError:
        return True
    except Exception:
        return False


# ---------- Primary VFS operations (content) ----------
def write(filename: str, data: str | bytes, enable_public_read: bool = True, timeout: int = 30) -> bool:
    """
    Atomically write 'data' for key 'filename'. On first write, create access record.
    On success, update access record's last_written_at.
    Returns True on success, False on failure.
    """
    target = _get_vfs_path(filename)
    _ensure_vfs_root()

    # Normalize bytes
    if isinstance(data, str):
        data_bytes = data.encode('utf-8')
    else:
        data_bytes = bytes(data)

    # Perform atomic write of content
    ok = _atomic_write_bytes(target, data_bytes)
    if not ok:
        return False
    
    # Set permissions if needed
    if enable_public_read:
        try:
            os.chmod(target, 0o644)
        except Exception:
            pass
    else:
        try:
            os.chmod(target, 0o600)
        except Exception:
            pass

    # Update access record (create if needed)
    return update_access_on_write(filename)


def read(filename: str, timeout: int = 30) -> Optional[str]:
    """
    Read content for 'filename'. If file not present, wait up to timeout seconds (polling).
    On successful read, update access record's last_read_at.
    Returns decoded utf-8 str on success, None on timeout/failure.
    """
    target = _get_vfs_path(filename)
    deadline = time.monotonic() + timeout

    while True:
        if os.path.exists(target) and os.path.isfile(target):
            try:
                with open(target, 'rb') as f:
                    data = f.read()
                # Update metadata about read (best-effort)
                try:
                    update_access_on_read(filename)
                except Exception:
                    pass
                try:
                    return data.decode('utf-8')
                except Exception:
                    # fallback: return bytes decoded latin-1 if not utf-8
                    return data.decode('latin-1')
            except FileNotFoundError:
                # rare race: file removed between exists() and open(); retry until timeout
                pass
            except Exception:
                return None
        if time.monotonic() >= deadline:
            return None
        time.sleep(_DEFAULT_POLL)


def is_file(filename: str) -> bool:
    target = _get_vfs_path(filename)
    return os.path.exists(target) and os.path.isfile(target)


def delete(filename: str) -> bool:
    """
    Delete content file and its access record. Return True if both removed or absent, False on error.
    """
    target = _get_vfs_path(filename)
    success = True
    try:
        if os.path.exists(target):
            os.unlink(target)
    except Exception:
        success = False
    # remove meta
    if not delete_access_record(filename):
        success = False
    return success
