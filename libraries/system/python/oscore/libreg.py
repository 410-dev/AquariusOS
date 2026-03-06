import os
import subprocess
import shlex
import shutil
import uuid
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

# ----------------------------
# Hive configuration (extensible)
# ----------------------------
_DEFAULT_LOCAL_PATH=".local/aqua/registry"
_HIVE_MAP: Dict[str, str] = {
    "HKEY_LOCAL_MACHINE": "/opt/aqua/registry",
    "HKEY_CURRENT_USER": f"$HOME/{_DEFAULT_LOCAL_PATH}",
    "HKEY_VOLATILE_MEMORY": "/opt/aqua/vfs/registry",
    "HKEY_LOCAL_MACHINE_NOINST": "/var/noinstfs/aqua/root.d/registry"
}

_HIVE_SHORT_MAP: Dict[str, str] = {
    "HKLM": "HKEY_LOCAL_MACHINE",
    "HKCU": "HKEY_CURRENT_USER",
    "HKVM": "HKEY_VOLATILE_MEMORY",
    "HKNS": "HKEY_LOCAL_MACHINE_NOINST"
}

# Read priority when NO hive is explicitly specified in the path.
# Earlier entries have higher precedence and override later ones in merged key listings.
_PRIORITY: List[str] = ["HKVM", "HKCU", "HKLM", "HKNS"]

# Supported value types
_TYPES_AVAILABLE = ["dword", "qword", "bool", "str", "list", "hex", "float", "double"]


# ----------------------------
# Internal helpers
# ----------------------------
def _canonical_hive_name(name: str) -> Optional[str]:
    """
    Return canonical long hive name (e.g., 'HKEY_LOCAL_MACHINE') from either long or short form.
    Returns None if not recognized.
    """
    if not name:
        return None
    name = name.strip()
    if name in _HIVE_MAP:
        return name
    if name in _HIVE_SHORT_MAP:
        return _HIVE_SHORT_MAP[name]
    return None


def _expand_hive_paths(hive_map: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Expand environment variables and ~ in hive root paths, return absolute paths.
    $HOME is allowed and resolves per-process.
    """
    hive_map = hive_map or _HIVE_MAP
    out: Dict[str, str] = {}
    for hive, path in hive_map.items():
        # Treat $HOME specially to ensure per-user HKCU
        path = path.replace("$HOME", os.path.expanduser("~"))
        path = os.path.expandvars(path)
        path = os.path.expanduser(path)
        out[hive] = os.path.abspath(path)
    return out


def _split_hive_and_rel(registry_path: str) -> Tuple[Optional[str], str]:
    """
    If path starts with a hive name (long or short), return (canonical_hive, relpath_without_hive).
    Otherwise return (None, normalized_path) meaning hive unspecified.
    Accepts paths with or without leading slash.
    """
    p = registry_path.lstrip("/")
    parts = p.split("/", 1)
    cand = parts[0]
    canon = _canonical_hive_name(cand)
    if canon is not None:
        rel = parts[1] if len(parts) > 1 else ""
        return canon, rel
    return None, p


def _value_file_candidates(base_no_ext: str) -> List[str]:
    return [f"{base_no_ext}.{t}.rv" for t in _TYPES_AVAILABLE]


def _detect_value_file(base_no_ext: str) -> Optional[str]:
    for f in _value_file_candidates(base_no_ext):
        if os.path.isfile(f):
            return f
    return None


def _read_value_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        data = f.read().strip()

    if path.endswith(".dword.rv") or path.endswith(".qword.rv"):
        return int(data)
    if path.endswith(".float.rv") or path.endswith(".double.rv"):
        return float(data)
    if path.endswith(".hex.rv"):
        return int(data, 16)
    if path.endswith(".list.rv"):
        sentinel = uuid.uuid4().hex
        data = data.replace("\\,", sentinel)
        items = [item.strip() for item in data.split(",")]
        return [i.replace(sentinel, ",") for i in items]
    if path.endswith(".bool.rv"):
        return data.lower() in ("1", "true", "yes", "on")
    if path.endswith(".str.rv"):
        return data
    return data  # Fallback raw text


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _priority_hives() -> List[str]:
    """
    Return priority as canonical long names, ignoring unknown entries.
    """
    result: List[str] = []
    for short in _PRIORITY:
        canon = _canonical_hive_name(short) or _canonical_hive_name(short.upper())
        if canon:
            result.append(canon)
    return result


# ----------------------------
# Public API
# ----------------------------
def read(
    registry_path: str,
    default: Any = None,
    *,
    hive_map: Optional[Dict[str, str]] = None,
) -> Any:
    """
    Read a key or value.

    Semantics:
      - If path explicitly starts with a hive (long or short), read ONLY from that hive.
      - If no hive specified, search in the order given by _PRIORITY (earlier wins).
      - Reading a directory returns a merged mapping from ALL searched hives, where
        higher-priority hives override lower-priority names on collision.
    """
    expanded_map = _expand_hive_paths(hive_map)
    explicit_hive, rel = _split_hive_and_rel(registry_path)

    if explicit_hive:
        # Strictly from the specified hive
        root = expanded_map.get(explicit_hive)
        if not root:
            return default

        # URL Encode patch
        # base = os.path.join(root, rel)
        base = get_encoded_path(root, rel)

        if os.path.isdir(base):
            # Single-hive directory listing
            listing: Dict[str, str] = {}
            for fname in os.listdir(base):
                fpath = os.path.join(base, fname)
                if os.path.isfile(fpath) and fpath.endswith(".rv"):
                    try:
                        name, type_ext, _rv = fname.rsplit(".", 2)

                        # URL Decode patch
                        name = decode_key(name)

                        listing[name] = type_ext
                    except ValueError:
                        pass
                elif os.path.isdir(fpath):
                    listing[fname] = "key"
            return listing

        cand = _detect_value_file(base)
        if cand is not None:
            return _read_value_file(cand)
        return default

    # No hive specified: search by priority
    merged_listing: Dict[str, str] = {}
    candidates: List[str] = []
    for hive in _priority_hives():
        root = expanded_map.get(hive)
        if not root:
            continue
        base = os.path.join(root, rel)
        candidates.append(base)

    # Directory read: if ANY candidate dir exists, perform merged listing by priority order
    any_dir = any(os.path.isdir(b) for b in candidates)
    if any_dir:
        for base in candidates:
            if not os.path.isdir(base):
                continue
            for fname in os.listdir(base):
                fpath = os.path.join(base, fname)
                if os.path.isfile(fpath) and fpath.endswith(".rv"):
                    try:
                        name, type_ext, _rv = fname.rsplit(".", 2)

                        # URL Decode patch
                        name = decode_key(name)

                        # Respect priority: first hit wins
                        if name not in merged_listing:
                            merged_listing[name] = type_ext
                    except ValueError:
                        pass
                elif os.path.isdir(fpath):
                    if fname not in merged_listing:
                        merged_listing[fname] = "key"
        return merged_listing

    # Value read: try each hive in priority order
    for base in candidates:
        cand = _detect_value_file(base)
        if cand is not None:
            return _read_value_file(cand)
    return default



def _exec_hook_secure(hook: str, new_value: str):
    try:
        parts = shlex.split(hook)
        cmd_args = [part.replace("{}", new_value) for part in parts]
        subprocess.run(cmd_args, check=True)
    except Exception as e:
        print(f"Warning: Failed to execute hook '{hook}': {e}")
        pass  # Ignore hook execution errors

def encode_key(key_part: str) -> str:
    """
    특수문자, 공백, 유니코드 등을 퍼센트 인코딩하여 파일시스템 호환성 및 보안 확보
    예: "배경 화면" -> "%EB%B0%B0%EA%B2%BD%20%ED%99%94%EB%A9%B4"
    """
    # safe='' 로 설정하여 슬래시(/)를 제외한 모든 특수문자 인코딩
    # 키 경로 자체에 슬래시가 포함된다면 split 후 각각 인코딩해야 함
    return urllib.parse.quote(key_part, safe='')

def decode_key(encoded_part: str) -> str:
    return urllib.parse.unquote(encoded_part)

def get_encoded_path(root: str, rel_path: str) -> str:
    """
    상대 경로(Software/MyConfig)를 받아 인코딩된 절대 경로를 반환
    """
    parts = rel_path.split('/')
    encoded_parts = [encode_key(p) for p in parts]
    return os.path.join(root, *encoded_parts)

def write(
    as_user: str,
    registry_path: str,
    value: Any,
    *,
    hive_map: Optional[Dict[str, str]] = None,
    typedef: Optional[str] = None,
) -> None:
    """
    Write a value.

    Semantics:
      - If path starts with a hive (long or short), write ONLY to that hive.
      - Otherwise, write to HKCU by default.
      - HKCU and HKLM are always modifiable; other hives depend on their mapped paths.
    """
    expanded_map = _expand_hive_paths(hive_map)
    explicit_hive, rel = _split_hive_and_rel(registry_path)

    if explicit_hive:
        target_hive = explicit_hive
    else:
        # Default write hive is HKCU
        target_hive = _canonical_hive_name("HKCU")
        if target_hive is None:
            raise RuntimeError("HKCU is not defined in the hive map.")

    root = expanded_map.get(target_hive)
    if not root:
        raise RuntimeError(f"Hive '{target_hive}' has no valid root path.")


    # URL Encode patch
    # base_no_ext = os.path.join(root, rel)
    base_no_ext = get_encoded_path(root, rel)

    dir_path = os.path.dirname(base_no_ext)
    _ensure_dir(dir_path)

    # Get uid gid of specified user for HKCU ownership
    uid = os.getuid()
    gid = os.getgid()
    if target_hive == "HKEY_CURRENT_USER":
        import pwd
        user_home = os.path.expanduser(f"~{as_user}")
        pw_record = pwd.getpwnam(os.path.basename(user_home))
        uid = pw_record.pw_uid
        gid = pw_record.pw_gid
        # print(f"Writing as user UID: {uid}, GID: {gid}")

    # If current hive is HKCU, make sure to set proper ownership (current user)
    if target_hive == "HKEY_CURRENT_USER":
        dir_components = dir_path.replace(root, "").split(os.sep)
        cumulative_path = root
        for component in dir_components:
            cumulative_path = os.path.join(cumulative_path, component)
            try:
                os.chown(cumulative_path, uid, gid)
            except PermissionError:
                pass  # Ignore if we don't have permission to change ownership

    if typedef is not None:
        typedef = typedef.lower()
        file_path = base_no_ext + f".{typedef}.rv"
        data = str(value)
    elif isinstance(value, bool):
        file_path = base_no_ext + ".bool.rv"
        data = "1" if value else "0"
    elif isinstance(value, int):
        if -(2**31) <= value < 2**31:
            file_path = base_no_ext + ".dword.rv"
        else:
            file_path = base_no_ext + ".qword.rv"
        data = str(value)
    elif isinstance(value, float):
        if abs(value) < 3.4e38:
            file_path = base_no_ext + ".float.rv"
        else:
            file_path = base_no_ext + ".double.rv"
        data = str(value)
    elif isinstance(value, list):
        file_path = base_no_ext + ".list.rv"
        escaped = [str(item).replace(",", "\\,") for item in value]
        data = ", ".join(escaped)
    elif isinstance(value, str):
        file_path = base_no_ext + ".str.rv"
        data = value
    else:
        raise ValueError("Unsupported value type for registry.")

    # This code is unsafe when concurrent writes are possible.
    # Use code below.
    # with open(file_path, "w", encoding="utf-8") as f:
    #     f.write(data)

    temp_file_path = file_path + f".tmp.{uuid.uuid4().hex}"
    try:
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        if os.path.exists(file_path):
            shutil.copymode(file_path, temp_file_path)

        os.replace(temp_file_path, file_path)

    except Exception:
        # Cleanup temp file if something fails
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise

    if target_hive == "HKEY_CURRENT_USER":
        try:
            os.chown(file_path, uid, gid)
        except PermissionError:
            pass  # Ignore if we don't have permission to change ownership

    # Check update hooks
    #
    # keyPath_explicit_path = rel.replace("/", "<d>")
    # keyPath_implicit_path = registry_path.lstrip("/").replace("/", "<d>")
    keyPath_explicit_path = rel
    keyPath_implicit_path = registry_path.lstrip("/")
    hook_path = "HKEY_LOCAL_MACHINE/SYSTEM/Services/me.hysong.aqua/RegistryPropagator/ActionHooks/"
    hooks_explicit_path = read(f"{hook_path}/{keyPath_explicit_path}", default=[])
    hooks_implicit_path = read(f"{hook_path}/{keyPath_implicit_path}", default=[])

    # Explicit goes higher priority than implicit
    if isinstance(hooks_explicit_path, list) and hooks_explicit_path:
        hooks = hooks_explicit_path
    else:
        hooks = hooks_implicit_path

    if isinstance(hooks, list):
        for exec_line in hooks:
            # Each exec_line is a path to an executable hook
            # Split by shell escape
            hook = exec_line.strip()
            _exec_hook_secure(hook, data)
            # Alternative insecure way (vulnerable to injection):
            # hook = hook.replace("{}", f'"{data}"')
            # command_bin = hook.split()[0]
            # if os.path.isfile(command_bin) and os.access(command_bin, os.X_OK):
            #     os.system(hook)

    elif isinstance(hooks, str):
        exec_line = hooks.strip()
        _exec_hook_secure(exec_line, data)
        # Alternative insecure way (vulnerable to injection):
        # exec_line = exec_line.replace("{}", f'"{data}"')
        # command_bin = exec_line.split()[0]
        # if os.path.isfile(command_bin) and os.access(command_bin, os.X_OK):
        #     os.system(exec_line)

    else:
        pass  # No hooks to run

def delete(
    registry_path: str,
    *,
    hive_map: Optional[Dict[str, str]] = None,
) -> bool:
    """
    Delete a value or key.

    Semantics:
      - If path starts with a hive (long or short), delete ONLY in that hive.
      - Otherwise, delete ONLY in HKCU (no implicit cross-hive deletion).
    """
    expanded_map = _expand_hive_paths(hive_map)
    explicit_hive, rel = _split_hive_and_rel(registry_path)

    if explicit_hive:
        target_hive = explicit_hive
    else:
        target_hive = _canonical_hive_name("HKCU")
        if target_hive is None:
            return False

    root = expanded_map.get(target_hive)
    if not root:
        return False

    target = os.path.join(root, rel)

    if os.path.isdir(target):
        for root_dir, dirs, files in os.walk(target, topdown=False):
            for name in files:
                os.remove(os.path.join(root_dir, name))
            for name in dirs:
                os.rmdir(os.path.join(root_dir, name))
        os.rmdir(target)
        return True

    found = False
    for fpath in _value_file_candidates(target):
        if os.path.exists(fpath):
            os.remove(fpath)
            found = True
            break
    return found


# ----------------------------
# CLI utility
# ----------------------------
def _infer_scalar_or_list(raw: str) -> Any:
    low = raw.lower()
    if low in ("1", "true", "yes", "on"):
        return True
    if low in ("0", "false", "no", "off"):
        return False
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        if "," in raw:
            return [item.strip() for item in raw.split(",")]
        return raw


def _main():
    import sys

    if len(sys.argv) < 4:
        print("Usage: python libreg.py <user> <action> <registry_path> [type (for write)] [value (for write)]")
        return

    user = sys.argv[1]
    action = sys.argv[2].lower()
    path = sys.argv[3]

    # Update hive map to set HKCU to the specified user's home
    custom_hive_map = _HIVE_MAP.copy()
    custom_hive_map["HKEY_CURRENT_USER"] = os.path.join(
        os.path.expanduser(f"~{user}"), _DEFAULT_LOCAL_PATH
    )

    if action == "read":
        default = None
        if len(sys.argv) >= 5:
            default = sys.argv[4]
        result = read(path, default, hive_map=custom_hive_map)
        print(f"{result}")
    elif action == "write":
        if len(sys.argv) < 6:
            print("Value and type is required for write action.")
            return
        # value = _infer_scalar_or_list(sys.argv[4])
        typedef = sys.argv[4]
        value = sys.argv[5]
        write(user, path, value, hive_map=custom_hive_map, typedef=typedef)
        # print(f"Wrote to '{path}': {value}")
    elif action == "install":
        # Read a file as an input value
        if len(sys.argv) < 4:
            print("File path is required for install action.")
            return
        file_path = sys.argv[3]
        if not os.path.isfile(file_path):
            print(f"File '{file_path}' does not exist.")
            return
        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()

        # For each line, parse it.
        # If line begins with #, skip it (comment)
        # If line begins with ? and such key or value exists, skip it
        # If the line does not contain '=', treat it as a key creation
        # For each line it looks like: name:type=value
        for line in file_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            skip_if_exists = False
            if line.startswith("?"):
                skip_if_exists = True
                line = line[1:].strip()
            if "=" in line:
                key_path, raw_value = line.split("=", 1)
                key_path = key_path.strip()
                typedef = key_path.rsplit(":")[-1] if ":" in key_path else None
                if ":" in key_path:
                    key_path = key_path.rsplit(":", 1)[0].strip()
                raw_value = raw_value.strip()
                if skip_if_exists:
                    existing = read(key_path, default=None, hive_map=custom_hive_map)
                    if existing is not None:
                        print(f"Skipping existing key/value '{key_path}'")
                        continue
                write(user, key_path, raw_value, hive_map=custom_hive_map, typedef=typedef)
                print(f"Wrote '{key_path}': {raw_value}")
            else:
                key_path = line
                if skip_if_exists:
                    existing = read(key_path, default=None, hive_map=custom_hive_map)
                    if existing is not None:
                        print(f"Skipping existing key '{key_path}'")
                        continue
                # Create the key by writing a dummy value and then deleting it
                write(user, os.path.join(key_path, "__dummy__"), "", hive_map=custom_hive_map)
                delete(os.path.join(key_path, "__dummy__"), hive_map=custom_hive_map)
                print(f"Created key '{key_path}'")

    elif action == "delete":
        ok = delete(path, hive_map=custom_hive_map)
        # print(f"Deleted '{path}': {ok}")
    else:
        print(f"Unknown action: {action}")


if __name__ == "__main__":
    _main()
