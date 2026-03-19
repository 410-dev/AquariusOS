import hashlib

def file_checksum(path: str, algorithm: str = "sha256") -> str:
    hasher = hashlib.new(algorithm)
    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def file_matches(path: str, checksum: str, algorithm: str = "sha256") -> bool:
    return file_checksum(path, algorithm) == checksum