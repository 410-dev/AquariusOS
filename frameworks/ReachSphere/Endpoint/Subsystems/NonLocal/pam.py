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
from oscore.libatomic import atomic_write

endpoint_cfg: Config = Config("ReachSphere/Endpoint/endpoints", enforce_global=True).fetch()
rs_user_cfg: Config = Config("ReachSphere/Endpoint/users", enforce_global=True)
general_cfg: Config = Config("Aqua/System", enforce_global=True) # MachineName 읽어오기 위함
logger = Logger("ReachSphere_EndpointPAM_v1", debug = True)

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
        "NonLocalAuth", # NonLocal 계정 인증 서버 URL
        ""
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
            logger.debug(f"pwd.getpwnam({pam_user}) succeeded. User exists as a local account. Skipping user creation and proceeding with authentication.")
            sys.exit(0) # 더이상 사용자 생성 로직이 필요 없으므로 인증 성공 처리 (unix_pam 모듈이 로그인을 직접 체크하도록)

        except KeyError:
            logger.debug(f"{pam_user} is not a user. Checking if remote server has correct credentials.")


    payload: dict = {}
    try:
        # 서버에 연결하여 사용자 존재 여부 확인
        general_cfg.fetch()
        logger.debug(f"Checking user existence on server for {pam_user}...")
        url = f"{endpoint_cfg.get("NonLocalAuth")}?machine_name={general_cfg.get("MachineName")}&username={pam_user}&cred={_pwencode(password)}"
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
                logger.info(f"User {pam_user} is revoked according to server response. Remove account in the background.")

                # 시스템에 해당 사용자가 존재하는 경우, 사용자 계정을 삭제합니다.
                try:
                    pwd.getpwnam(pam_user)  # 사용자 존재 여부 확인
                    logger.debug(f"User {pam_user} exists. Deleting user account...")
                    subprocess.run(["/usr/sbin/userdel", "-r", pam_user], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    profile_pic_url: str = user_info.get("profile-pic")
    profile_pic_path: str = ""
    if profile_pic_url:
        profile_pic_url = download_profile_pic(pam_user, profile_pic_url)

    try:
        logger.debug(f"Creating user {pam_user}...")

        # 사용자가 존재하지 않으면 사용자 생성, 존재하면 생성하지 않고 넘어감 (이미 로컬 계정이 있는 경우, 서버에서 인증만 성공하면 된다고 판단하여 사용자 생성 로직을 건너뜁니다.)
        # 이 때 비밀번호는 설정하지 않음.
        if not check_user_exists(pam_user):
            create_user(pam_user, payload, user_info.get("shell", "/bin/bash"))

        # 사용자 프로파일 사진이 다운로드된 경우, 해당 사진을 사용자의 홈 디렉터리에 .face 로 복사
        if profile_pic_url and os.path.exists(profile_pic_path):
            copy_profile_picture_to_face(pam_user, profile_pic_path)
            dbus_set_profile_picture(pam_user, profile_pic_path)


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

        # TODO 정책 설정


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


# 사용자 존재 여부 확인
def check_user_exists(username: str) -> bool:
    try:
        # 시스템의 사용자 계정에서 존재 여부 확인
        pwd.getpwnam(username)
        logger.debug(f"pwd.getpwnam({username}) succeeded. User exists as a local account. Skipping user creation and proceeding with authentication.")
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

# 프로필 사진 사본 만들기 (.face)
def copy_profile_picture_to_face(username: str, profile_pic_path: str):
    user_home_dir = f"/home/{username}"
    target_profile_pic_path = os.path.join(user_home_dir, ".face")
    logger.debug(f"Copying profile picture for user {username} to {target_profile_pic_path}...")
    subprocess.run(["cp", profile_pic_path, target_profile_pic_path], check=True)
    subprocess.run(["chown", f"{username}:{username}", target_profile_pic_path], check=True)
    logger.debug(f"Profile picture copied and ownership changed for user {username}")


# 프로필 사진 설정
def dbus_set_profile_picture(username: str, profile_pic_path: str):
    try:
        # dbus-send --system --dest=org.freedesktop.Accounts --print-reply /org/freedesktop/Accounts/User"$USER_ID" org.freedesktop.Accounts.User.SetIconFile string:"$IMAGE_PATH"
        user_info = pwd.getpwnam(username)
        user_id = user_info.pw_uid

        icons_dir = "/var/lib/AccountsService/icons"
        os.makedirs(icons_dir, exist_ok=True)
        shutil.copy(profile_pic_path, icons_dir)

        file_name = os.path.basename(profile_pic_path)
        stage_image = os.path.join(icons_dir, file_name)

        os.chmod(stage_image, 0o644)

        logger.debug(f"Waking up AccountsService for {username}...")

        wake_cmd = [
            "dbus-send",
            "--system",
            "--dest=org.freedesktop.Accounts",
            "--print-reply",
            "/org/freedesktop/Accounts",
            "org.freedesktop.Accounts.FindUserByName",
            f"string:{username}"
        ]
        result = subprocess.run(wake_cmd, capture_output=True, text=True)
        logger.debug(f"AccountsService wake-up command executed for {username}. Return code: {result.returncode}")
        logger.debug(f"Stdout: {result.stdout}")
        logger.debug(f"Stderr: {result.stderr}")

        logger.debug(f"Setting user icon for {username} using dbus-send...")
        result = subprocess.run([
            "dbus-send",
            "--system",
            "--dest=org.freedesktop.Accounts",
            "--print-reply",
            f"/org/freedesktop/Accounts/User{user_id}",
            "org.freedesktop.Accounts.User.SetIconFile",
            f"string:{stage_image}"
        ], check=True, capture_output=True, text=True)
        logger.debug(f"User icon set successfully for {username}")
        logger.debug(f"Stdout: {result.stdout}")
        logger.debug(f"Stderr: {result.stderr}")
    except Exception as e:
        logger.error(f"Failed to set user icon for {username} using dbus-send: {e}")

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

    # Executable: {{SYS_FRAMEWORKS}}/ReachSphere/Endpoint/Subsystems/NonLocal/localize-userhome-template.py
    # exec.py <username> <uid> <gid> <homedir> <payload file>
    subprocess.Popen(
        ["/usr/bin/python3", f"{{SYS_FRAMEWORK}}/ReachSphere/Endpoint/Subsystems/NonLocal/localize-userhome-template.py", username, uid, gid, home_directory, files_payload],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

if __name__ == "__main__":
    main()
