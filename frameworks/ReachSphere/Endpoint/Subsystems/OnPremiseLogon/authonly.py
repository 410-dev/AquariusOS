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
from oscore.libconfig import Config
from oscore.liblog import Logger

endpoint_cfg: Config = Config("ReachSphere/Endpoint/Servers", enforce_global=True).fetch()
rs_user_cfg: Config = Config("ReachSphere/Endpoint/Users", enforce_global=True)
general_cfg: Config = Config("Aqua/System", enforce_global=True)  # MachineName 읽어오기 위함
logger = Logger("ReachSphere_EndpointPAM_v1", debug=True)


def _pwencode(pwin: str) -> str:
    # PAM으로부터 전달된 비밀번호를 해시 처리하여 반환하는 함수입니다.
    return hashlib.sha256(pwin.encode()).hexdigest()


def main():
    # 1. 루트 권한 확인
    if os.geteuid() != 0:
        logger.error("This script must be run as root.")
        sys.exit(1)

    # 2. 설정값 존재 확인
    required_fields: list[str] = [
        "OnPremiseLogonAuth",  # OnPremiseLogon 계정 인증 서버 URL
    ]
    for field in required_fields:
        if field not in general_cfg:
            logger.error(f"Field {field} is required.")
            sys.exit(1)

    # 3. PAM으로부터 사용자 정보 및 비밀번호 읽기
    pam_user = os.environ.get("PAM_USER")
    # expose_authtok 옵션을 통해 전달된 비밀번호를 stdin에서 읽습니다.
    password = sys.stdin.readline().strip()

    # 4. 환경 변수 및 인자 덤프 작성
    logger.debug(f"Timestamp: {datetime.datetime.now().isoformat()}")
    logger.debug(f"Process ID: {os.getpid()}")
    logger.debug(f"Target User: {pam_user}")
    logger.debug("Environment Variables:")
    for key, value in os.environ.items():
        logger.debug(f"{key}={value}")

    logger.debug("------------log------------")
    if not pam_user:
        logger.debug(f"User {pam_user} is not. Exiting.")
        sys.exit(1)  # 사용자 이름이 없으면 인증 실패 처리
    logger.debug(f"User {pam_user} is OK.")

    # 5. 사용자 존재 여부 확인 및 생성 로직
    logger.debug(f"Checking if user '{pam_user}' exists...")

    # 로컬 계정일 경우 (@와 .이 없는 걸로 판단), 시스템의 사용자 계정에서 존재 여부 확인
    if "@" not in pam_user and "." not in pam_user:
        logger.debug(f"User '{pam_user}' is considered a local account. Checking local user database...")
        try:
            pwd.getpwnam(pam_user)
            logger.debug(
                f"pwd.getpwnam({pam_user}) succeeded. User exists as a local account. Skipping user creation and proceeding with authentication.")
            sys.exit(0)  # 더이상 사용자 생성 로직이 필요 없으므로 인증 성공 처리 (unix_pam 모듈이 로그인을 직접 체크하도록)

        except KeyError:
            logger.debug(f"{pam_user} is not a user. Checking if remote server has correct credentials.")

    payload: dict = {}
    try:
        # 서버에 연결하여 사용자 존재 여부 확인
        general_cfg.fetch()
        logger.debug(f"Checking user existence on server for {pam_user}...")
        url = f"{endpoint_cfg.get("OnPremiseLogonAuth")}?machine_name={general_cfg.get("MachineName")}&username={pam_user}&cred={_pwencode(password)}"
        response = requests.get(url, timeout=5)

        # 서버 응답 처리
        if response.status_code == 200:
            data = response.json()

            """
            JSON 응답 예시:
            {
                "status": "OK", // OK 또는 REVOKED 만 해석함
                "authenticated": true,
                "payload": {}   // 계정 정보, 권한, 파일 등 사용자 생성에 필요한 추가 정보가 담긴 객체.
            }

            """

            # OK 모드 - 사용자 정보를 업데이트 하거나 새로 생성하는 로직 예약
            if data.get("status") == "OK" and data.get("authenticated") is True:
                logger.info(f"Server authentication successful for user {pam_user}. Proceeding with user creation.")

            # REVOKE 모드 - 시스템에서 해당 사용자 계정을 삭제하는 로직 예약
            elif data.get("status") == "REVOKED":
                logger.info(
                    f"User {pam_user} is revoked according to server response. Remove account in the background.")

                # 시스템에 해당 사용자가 존재하는 경우, 사용자 계정을 삭제합니다.
                try:
                    pwd.getpwnam(pam_user)  # 사용자 존재 여부 확인
                    logger.debug(f"User {pam_user} exists. Deleting user account...")
                    subprocess.run(["/usr/sbin/userdel", "-r", pam_user], check=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
                    logger.debug(f"User {pam_user} deleted successfully.")
                except KeyError:
                    logger.debug(f"User {pam_user} does not exist. No need to delete.")

                # 로그인 실패 신호 반환
                sys.exit(1)

            # 기타 - 인증 실패 처리
            else:
                logger.debug(f"Server authentication failed for user {pam_user}. Response: {data}")
                sys.exit(1)

            # 페이로드 처리 - 사용자 생성에 필요한 추가 정보가 담긴 객체로, 이후 사용자 생성 로직에서 활용
            payload = data.get("payload", {})

        # 서버 연결 실패
        # 이미 앞에서 로컬 로그인을 확인 했으므로, 서버 연결 실패시 로그인을 거절함.
        #  Q: 만약 이미 계정이 있다면? 이미 계정 데이터를 받아와서 로그인을 성공했다면?
        #  A: 애초에 이 모듈 자체가 온라인 로그인을 위한 것이므로, 이미 로컬에 저장된 비밀번호와 일치하더라도 로그인에 실패해야 함.
        else:
            logger.debug(f"Failed to connect to authentication server. Status code: {response.status_code}")
            sys.exit(1)

    except Exception as e:
        logger.debug(f"Error checking user existence: {e}")
        sys.exit(1)

    # 만약 profile-pic이 payload의 user_info에 profile-pic 키로 존재하는 경우, 해당 URL에서 이미지를 다운로드하여 사용자 홈 디렉터리에 저장
    """
    Payload 예시
    {
        "user_info": {
            "full_name": "John Doe",
            "profile-pic": "https://example.com/profile.jpg",
            "shell": "/bin/bash"
        },
        "permission": ["sudo"]
        "files_profile": {
            "checksum": "xxxx",
            "date": 74719024
        },
        "files": {
            "$HOME/welcome.txt": {
                "type": "tinytext",
                "content": "hello world",
                "checksum": "xxxx"
            },
            "$HOME/my-document.txt": {
                "type": "cloudfile",
                "content": "https://cloud.example.com/<user>/my-document.txt",
                "checksum": "xxxx"
            }
        }
    }
    """
    user_info: dict = payload.get("user_info", {})

    try:
        logger.debug(f"Creating user {pam_user}...")

        # 사용자가 존재하지 않으면 사용자 생성, 존재하면 생성하지 않고 넘어감 (이미 로컬 계정이 있는 경우, 서버에서 인증만 성공하면 된다고 판단하여 사용자 생성 로직을 건너뜁니다.)
        # 이 때 비밀번호는 설정하지 않음.
        if not check_user_exists(pam_user):
            create_user(pam_user, payload, user_info.get("shell", "/bin/bash"))

        # permission 에 sudo 또는 admin이 있는 경우, 사용자에게 sudo 권한 부여
        permissions: list = payload.get("permission", [])
        grant_appropriate_privilege_to_user(pam_user, permissions)

        # 생성한 사용자의 비밀번호 설정
        if password:
            set_password(pam_user, password)

        # --- 바탕화면 환영 파일 생성 시작 ---
        # 방금 생성된 사용자의 UID, GID 및 홈 디렉터리 정보 가져오기
        logger.debug(f"Retrieving user info for {pam_user}...")
        uid, gid, home_dir = get_user_info(pam_user)
        logger.debug(f"User {pam_user}'s UID: {uid}, GID: {gid}, Home Directory: {home_dir}")

    except Exception as e:
        # Write to dump
        logger.debug(f"Failed to create user Error: {e}")
        sys.exit(1)

    # 6. 인증 성공 처리
    # Payload 반환 (pam.py 호출시에 필요한 데이터)
    return 0, payload



# 사용자 존재 여부 확인
def check_user_exists(username: str) -> bool:
    try:
        # 시스템의 사용자 계정에서 존재 여부 확인
        pwd.getpwnam(username)
        logger.debug(
            f"pwd.getpwnam({username}) succeeded. User exists as a local account. Skipping user creation and proceeding with authentication.")
        return True
    except KeyError:
        logger.debug(f"{username} is not a user. Checking if remote server has correct credentials.")
    return False


# 비밀번호 없이 사용자 생성
def create_user(username: str, payload: dict, shell: str) -> bool:
    # full name 정보가 payload의 user_info에 full_name 키로 존재하는 경우, -c 옵션으로 전달하여 사용자 생성
    user_info: dict = payload.get("user_info", {})
    full_name = user_info.get("full_name")

    useradd_command = ["/usr/sbin/useradd", "-m", "-s", shell]
    if full_name:
        useradd_command.extend(["-c", full_name])
    useradd_command.append(username)

    logger.debug(f"Full name for user {username} is {full_name}. Creating user with full name.")
    result = subprocess.run(useradd_command, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    logger.debug(f"Successfully created user {username} with full name {full_name}")
    logger.debug(f"Return code: {result.returncode}")
    return True


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


# 비밀번호 설정하기
def set_password(username: str, password: str):
    chpasswd_input = f"{username}:{password}\n"
    logger.debug(f"Setting password for user {username}...")
    result = subprocess.run(["/usr/sbin/chpasswd"], input=chpasswd_input, text=True, check=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    logger.debug(f"Successfully set password for user {username}")
    logger.debug(f"Exit code: {result.returncode}")
    logger.debug(f"Printed: {result.stdout}")


# uid, gid, homedir 가져오기
def get_user_info(username: str) -> tuple[int, int, str]:
    user_info = pwd.getpwnam(username)
    uid = user_info.pw_uid
    gid = user_info.pw_gid
    home_dir = user_info.pw_dir
    return uid, gid, home_dir


if __name__ == "__main__":
    sys.exit(main()[0])
