#!/usr/bin/env python3
import datetime
import os
import shutil
import sys
import subprocess
import pwd
import hashlib
import requests
import json
import random
import authonly as auth
from oscore.libconfig import Config
from oscore.liblog import Logger
from oscore.libatomic import atomic_write

rs_user_cfg: Config = Config("ReachSphere/Endpoint/users", enforce_global=True)
logger = Logger("ReachSphere_EndpointPAM_v1", debug = True)

def _pwencode(pwin: str) -> str:
    # PAM으로부터 전달된 비밀번호를 해시 처리하여 반환하는 함수입니다.
    return hashlib.sha256(pwin.encode()).hexdigest()

def main():
    # 1. 루트 권한 확인
    if os.geteuid() != 0:
        logger.error("This script must be run as root.")
        sys.exit(1)

    # 2. PAM으로부터 사용자 이름과 비밀번호 읽기
    pam_user = os.getenv("PAM_USER")

    # 3. authonly.py 로 계정 인증
    exit_code, payload = auth.main()

    user_info: dict = payload.get("user_info", {})
    profile_pic_url: str = user_info.get("profile-pic")
    profile_pic_path: str = ""
    if profile_pic_url:
        profile_pic_url = download_profile_pic(pam_user, profile_pic_url)

    try:

        # 사용자 프로파일 사진이 다운로드된 경우, 해당 사진을 사용자의 홈 디렉터리에 .face 로 복사
        if profile_pic_url and os.path.exists(profile_pic_path):
            # 명령어 {{SYS_CMDS}}/chuserface.py <username> <picture path> 실행
            result = subprocess.run(
                [f"{{SYS_CMDS}}/chuserface.py", pam_user, profile_pic_path],
                capture_output=True, text=True
            )
            if result and result.returncode == 0:
                logger.debug(f"Profile picture for user {pam_user} set successfully.")
            else:
                logger.debug(f"WARNING: Profile picture for user {pam_user} not set.")

        # 방금 생성된 사용자의 UID, GID 및 홈 디렉터리 정보 가져오기
        logger.debug(f"Retrieving user info for {pam_user}...")
        uid, gid, home_dir = get_user_info(pam_user)
        logger.debug(f"User {pam_user}'s UID: {uid}, GID: {gid}, Home Directory: {home_dir}")

        # 홈폴더 아래 폴더 경로 지정 및 생성
        # (한글 OS 환경에서 첫 로그인 전이므로 강제로 Desktop을 만들어줍니다)
        prepare_home_directory(pam_user, uid, gid, home_dir, ["Desktop", "Documents", "Downloads", "Public"])

        # Payload 의 files 항목에서 파일 경로와 내용을 읽어와서 바탕화면에 파일로 생성
        # files_profile.checksum 이 바뀌었을 때만 다운로드 및 파일 생성을 진행하도록 하여, 매 로그인마다 파일이 새로 생성되는 것을 방지
        rs_user_cfg.fetch()
        user_cached: dict = rs_user_cfg.get(pam_user, {})
        files_profile: dict = payload.get("files_profile", {})
        if user_cached.get("files_digest", "") != files_profile.get("checksum", ""):
            files: dict = payload.get("files", {})
            if len(files) > 0:
                sync_home_template(pam_user, uid, gid, home_dir, files)
                rs_user_cfg[pam_user]["files_digest"] = files_profile.get("checksum", "")
                rs_user_cfg.sync()


        logger.debug(f"Welcome to {pam_user}")
        # --- 바탕화면 환영 파일 생성 끝 ---

    except Exception as e:
        # Write to dump
        logger.debug(f"Failed to create user Error: {e}")
        sys.exit(1)

    # 6. 인증 성공 처리 (Do stuff here)
    sys.exit(0)


# 프로파일 이미지 다운로드
def download_profile_pic(username: str, url: str) -> str:
    profile_pic_path = f"/tmp/{username}_profile.png"
    try:
        logger.debug(f"Downloading profile picture for user {username} from {url}...")
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            with open(profile_pic_path, "wb") as f:
                f.write(response.content)
            logger.debug(f"Profile picture downloaded successfully for user {username} and saved to {profile_pic_path}")
        else:
            logger.error(f"Failed to download profile picture for user {username}. Status code: {response.status_code}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error downloading profile picture for user {username}: {e}")
        sys.exit(1)

    return profile_pic_path

# 적절한 권한 부여
def grant_appropriate_privilege_to_user(username: str, privileges: list[str]):
    SUDOERS_PATH = "/etc/sudoers"
    TMP_PATH = "/etc/sudoers.tmp"

    if os.path.exists(TMP_PATH):
        # TODO 런타임 에러 발생시 문제 생길 수 있음. False 반환을 고려.
        raise RuntimeError("sudoers is being updated")

    try:
        # 1. 현재 파일 읽기
        with open(SUDOERS_PATH, "r") as f:
            lines = f.readlines()

        rule = f"{username} ALL=(ALL) NOPASSWD:ALL\n"

        if "sudo" in privileges:
            logger.debug(f"Granting sudo to {username}...")
            # 중복 방지: 없을 때만 추가
            if rule not in lines:
                lines.append(rule)

        elif "user" in privileges:
            logger.debug(f"Removing sudo from {username}...")
            lines = [l for l in lines if l != rule]

        # temp 파일에 쓰기
        with open(TMP_PATH, "w") as f:
            f.writelines(lines)
            f.flush()
            os.fsync(f.fileno())

        # 권한 설정
        os.chown(TMP_PATH, 0, 0)
        os.chmod(TMP_PATH, 0o440)

        # 문법 검증
        result = subprocess.run(
            ["visudo", "-c", "-f", TMP_PATH],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise ValueError(f"sudoers 문법 오류: {result.stderr}")

        # Atomic rename
        os.rename(TMP_PATH, SUDOERS_PATH)
        logger.debug("sudoers 업데이트 완료")

    except Exception:
        if os.path.exists(TMP_PATH):
            os.unlink(TMP_PATH)
        raise


# uid, gid, homedir 가져오기
def get_user_info(username: str) -> tuple[int, int, str]:
    user_info = pwd.getpwnam(username)
    uid = user_info.pw_uid
    gid = user_info.pw_gid
    home_dir = user_info.pw_dir
    return uid, gid, home_dir


# 사용자 홈 디렉터리 준비하기
def prepare_home_directory(username: str, uid: int, gid: int, home_directory: str, subdirectories: list[str] = None) -> None:
    if subdirectories is None:
        subdirectories = []

    for subdirectory in subdirectories:
        logger.debug(f"Creating {subdirectory} directory for user {username} at {home_directory}...")
        subdirectory_abspath = os.path.join(home_directory, subdirectory)
        os.makedirs(subdirectory_abspath, exist_ok=True)
        logger.debug(f"{subdirectories} directory created at {subdirectory_abspath}")
        os.chown(subdirectory_abspath, uid, gid)  # 폴더 소유권 변경
        logger.debug(f"Changed ownership of {subdirectory_abspath} to {username}")

# 사용자 홈 템플릿 가져오기 (셸로 새 프로세스를 만들어 백그라운드에서 진행하도록 실행)
def sync_home_template(username: str, uid: int, gid: int, home_directory: str, files: dict[str, dict[str, str]]) -> None:
    files_payload: str = f"/tmp/dat_{username}_{random.randint(1000000,9999999)}.json"
    atomic_write(files_payload, json.dumps(files))

    # Executable: {{SYS_FRAMEWORKS}}/ReachSphere/Endpoint/Subsystems/OnPremiseLogon/localize-userhome-template.py
    # exec.py <username> <uid> <gid> <homedir> <payload file>
    subprocess.Popen(
        ["/usr/bin/python3", f"{{SYS_FRAMEWORK}}/ReachSphere/Endpoint/Subsystems/OnPremiseLogon/localize-userhome-template.py", username, uid, gid, home_directory, files_payload],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

if __name__ == "__main__":
    main()
