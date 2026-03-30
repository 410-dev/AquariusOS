# {{SYS_FRAMEWORKS}}/ReachSphere/Endpoint/Subsystems/AuthorizedBoot/auth_check.py
import os
import subprocess
import sys
import time
import logging
import requests
from pathlib import Path

from oscore.libreachsphere.endpoint import EdgeMachine
from oscore.libconfig2 import Config

logging.basicConfig(
    filename='/var/log/boot-auth.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)

config: Config = Config("ReachSphere/Endpoints/AuthorizedBoot", enforce_global=True).fetch()

def ask_auth() -> bool:
    current_machine: EdgeMachine = EdgeMachine.get_current_machine("master")
    key: str = "security.bootable"
    log.info(f"인증 값: {key} of {current_machine}")
    returned: dict = current_machine.get_network_instance("master").get_machine_prop(current_machine, current_machine, [key])
    value = returned.get(key)
    log.info(f"인증 서버로부터 받은 값: {value}")
    return value == config['expected_response']['security.bootable']

def check_network() -> bool:
    """현재 네트워크(인터넷) 연결 여부 확인"""
    try:
        # DNS 없이 IP 직접 접근으로 확인
        import socket
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except Exception:
        return False


def perform_auth() -> bool:
    for attempt in range(1, config['retry_count'] + 1):
        try:
            log.info(f"인증 시도 {attempt}/{config['retry_count']}")
            if ask_auth():
                log.info("인증 성공")
                return True

        except requests.exceptions.ConnectionError:
            log.warning(f"시도 {attempt}: 연결 실패")
        except requests.exceptions.Timeout:
            log.warning(f"시도 {attempt}: 타임아웃")
        except Exception as e:
            log.error(f"시도 {attempt}: 예외 발생 - {e}")

        if attempt < config['retry_count']:
            time.sleep(2)

    log.error("모든 인증 시도 실패")
    return False


def force_poweroff():
    """인증 실패 시 강제 전원 종료"""
    log.critical("인증 실패 - 강제 전원 종료")
    time.sleep(2)
    subprocess.run(['systemctl', 'poweroff', '--force'], check=False)
    # 위 명령이 실패할 경우 커널 직접 제어
    os.system("echo o > /proc/sysrq-trigger")


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'boot'

    if mode == 'boot':
        # Plymouth 단계 이후 부팅 시 실행
        if check_network():
            log.info("부팅 시 네트워크 연결됨 - 즉시 인증 시작")
            if not perform_auth():
                force_poweroff()
            else:
                sys.exit(0)
        else:
            log.info("부팅 시 네트워크 없음 - 인증 보류, USB 차단 활성화")
            # USB 차단 서비스 활성화 신호
            Path('/run/boot-auth/no-network').touch()
            sys.exit(0)

    elif mode == 'network-connected':
        # 나중에 네트워크 연결됐을 때 호출
        log.info("네트워크 연결 감지 - 사후 인증 시작")
        if not perform_auth():
            force_poweroff()
        else:
            # 인증 성공 시 USB 차단 해제 및 플래그 제거
            Path('/run/boot-auth/no-network').unlink(missing_ok=True)
            log.info("사후 인증 성공 - USB 차단 해제")
            sys.exit(0)