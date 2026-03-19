# ReachSphere 에서 파일 다운로드
import os
import requests
import sys
import json

from oscore.libatomic import atomic_write

def main():
    # 파라미터 확인
    if len(sys.argv) < 6:
        print("Usage: localize-userhome-template.py <username> <uid> <gid> <home_dir> <payload_path>")
        sys.exit(1)

    username: str = sys.argv[1]
    uid: str = sys.argv[2]
    gid: str = sys.argv[3]
    home_dir: str = sys.argv[4]
    payload_path: str = sys.argv[5]

    # int 로 파싱
    try:
        uid: int = int(uid)
        gid: int = int(gid)
    except ValueError:
        print(f"Invalid uid {uid} and gid {gid}")
        sys.exit(1)

    # 페이로드 읽기
    files = {}
    try:
        payload_path: str = payload_path.strip()
        with open(payload_path, "r") as f:
            files = json.load(f)

    except FileNotFoundError:
        print(f"Payload file {payload_path} not found")
        raise

    except json.decoder.JSONDecodeError:
        print(f"Payload file {payload_path} is not a valid JSON file")
        raise

    # 파일 경로가 $HOME/으로 시작하는 경우에만 생성
    # 폴더 생성

    """
    {
        "Documents/welcome.txt": {
            "type": "tinytext",
            "content": "hello world",
            "checksum": "xxxx"
        },
        "Documents/my-document.txt": {
            "type": "cloudfile",
            "content": "https://cloud.example.com/<user>/my-document.txt",
            "checksum": "xxxx"
        }
    }
    """
    for file_path, content in files.items():
        print(f"Processing file {file_path} for user {username}...")

        # 확장
        path = _safe_expand_path(file_path)

        # 디렉터리 생성
        target_dir = os.path.dirname(path)
        os.makedirs(target_dir, exist_ok=True)
        os.chown(target_dir, uid, gid)  # 폴더 소유권 변경

        # 파일 생성


            with open(target_path, "w") as f:
                f.write(content)
            os.chown(target_path, uid, gid)  # 파일 소유권 변경
            logger.debug(f"Created file {target_path} with content from payload and changed ownership to {pam_user}")


def _write_tinytext(element: dict[str, str], path: str, writer = atomic_write):
    content: str = element["content"]
    writer(path, content)

def _safe_expand_path(path: str) -> str:
    path = f"~/{path}"
    path = os.path.expanduser(path)
    path = os.path.abspath(path)
    home = os.path.expanduser("~")

    # Check if escaped user home
    if path.startswith(home):
        return path
    else:
        raise Exception(f"Invalid path {path}")


if __name__ == "__main__":
    main()