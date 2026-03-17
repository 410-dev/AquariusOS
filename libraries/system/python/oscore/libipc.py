import oscore.libcryptography as crpyto
import oscore.libvfs as vfs
import uuid
import json

def _path_sanitize(path: str) -> str:
    return path.replace("..", "_")

def write(path: str, key: str, content: str) -> str:
    namespace: str = str(uuid.uuid4())
    path = _path_sanitize(path)
    vfs.write(f"ipc/{namespace}/{path}", crpyto.encrypt(content, key, symmetric=True))
    return namespace

def read(namespace: str, path: str, key: str) -> str:
    path = _path_sanitize(path)
    encrypted_content = vfs.read(f"ipc/{namespace}/{path}")
    return crpyto.decrypt(encrypted_content, key, symmetric=True)

def write_json(path: str, key: str, content: dict) -> str:
    json_content = json.dumps(content)
    return write(path, key, json_content)

def read_json(namespace: str, path: str, key: str) -> str:
    return json.loads(read(namespace, path, key))

def exists(namespace: str, path: str) -> bool:
    path = _path_sanitize(path)
    return vfs.is_file(f"ipc/{namespace}/{path}")

def delete(namespace: str, path: str):
    path = _path_sanitize(path)
    vfs.delete(f"ipc/{namespace}/{path}")
