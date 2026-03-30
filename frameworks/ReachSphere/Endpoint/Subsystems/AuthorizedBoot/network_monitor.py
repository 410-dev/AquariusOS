# {{SYS_FRAMEWORKS}}/ReachSphere/Endpoint/Subsystems/AuthorizedBoot/network_monitor.py
"""
부팅 후 네트워크 연결을 감시하다가
연결이 감지되면 auth_check.py network-connected 모드 실행
"""
import subprocess
import time
import logging
from pathlib import Path

logging.basicConfig(
    filename='/var/log/boot-auth.log',
    level=logging.INFO,
    format='%(asctime)s [NETMON] %(message)s'
)
log = logging.getLogger(__name__)

NO_NETWORK_FLAG = Path('/run/boot-auth/no-network')
CHECK_INTERVAL = 5  # 초


def is_connected() -> bool:
    try:
        import socket
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except Exception:
        return False


def main():
    # 네트워크 없이 부팅된 경우에만 감시 시작
    if not NO_NETWORK_FLAG.exists():
        log.info("네트워크 플래그 없음 - 감시 불필요, 종료")
        return

    log.info("네트워크 연결 감시 시작...")
    while True:
        if is_connected():
            log.info("네트워크 연결 감지!")
            subprocess.run(
                ['python3', '{{SYS_FRAMEWORKS}}/ReachSphere/Endpoint/Subsystems/AuthorizedBoot/auth_check.py', 'network-connected'],
                check=False
            )
            break  # 인증 후 데몬 종료 (auth_check가 poweroff 처리)
        time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    # /run/boot-auth 디렉토리 생성 (tmpfs, 재부팅마다 초기화)
    Path('/run/boot-auth').mkdir(parents=True, exist_ok=True)
    main()
