# {{SYS_FRAMEWORKS}}/ReachSphere/Endpoint/Subsystems/AuthorizedBoot/usb_block.py
"""
udev 룰과 연동하여 외부 저장장치(USB, SD카드 등) 마운트 차단
네트워크 없이 부팅 시 활성화
"""
import subprocess
import logging
import sys
from pathlib import Path

logging.basicConfig(
    filename='/var/log/boot-auth.log',
    level=logging.INFO,
    format='%(asctime)s [USBBLOCK] %(message)s'
)
log = logging.getLogger(__name__)

NO_NETWORK_FLAG = Path('/run/boot-auth/no-network')

UDEV_RULE_PATH = Path('/etc/udev/rules.d/99-block-external-storage.rules')
UDEV_RULE_CONTENT = """
# boot-auth: 외부 저장장치 차단
# USB 대용량 저장장치(Mass Storage) 차단
SUBSYSTEM=="block", ENV{ID_BUS}=="usb", ENV{ID_USB_DRIVER}=="usb-storage", \
    RUN+="/bin/sh -c 'echo 1 > /sys/bus/usb/devices/%k/authorized'"

# 실제 마운트 거부
SUBSYSTEM=="block", ENV{ID_BUS}=="usb", ACTION=="add", \
    RUN+="/usr/bin/logger -t boot-auth USB storage blocked", \
    GOTO="storage_block_end"

SUBSYSTEM=="block", ENV{DEVTYPE}=="disk", ENV{ID_BUS}=="usb", ACTION=="add", \
    RUN+="/sbin/blockdev --setro /dev/%k"

LABEL="storage_block_end"
""".strip()


def enable_usb_block():
    """udev 룰 작성 및 적용"""
    UDEV_RULE_PATH.write_text(UDEV_RULE_CONTENT)
    subprocess.run(['udevadm', 'control', '--reload-rules'], check=False)
    subprocess.run(['udevadm', 'trigger'], check=False)
    log.info("USB 차단 udev 룰 적용 완료")


def disable_usb_block():
    """udev 룰 제거"""
    if UDEV_RULE_PATH.exists():
        UDEV_RULE_PATH.unlink()
        subprocess.run(['udevadm', 'control', '--reload-rules'], check=False)
        subprocess.run(['udevadm', 'trigger'], check=False)
        log.info("USB 차단 udev 룰 제거 완료")


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'check'

    if action == 'enable':
        enable_usb_block()
    elif action == 'disable':
        disable_usb_block()
    elif action == 'check':
        if NO_NETWORK_FLAG.exists():
            enable_usb_block()
        else:
            disable_usb_block()