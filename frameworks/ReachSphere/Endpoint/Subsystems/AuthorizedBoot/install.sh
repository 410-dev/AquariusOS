#!/bin/bash
# install.sh

set -e

echo "[1/3] requests 라이브러리 설치..."
sudo apt install python3-requests -y

echo "[2/3] systemd 서비스 등록..."
systemctl daemon-reload
systemctl enable {{SYS_FRAMEWORKS}}/ReachSphere/Endpoint/Subsystems/AuthorizedBoot/systemd-units/boot-auth.service
systemctl enable {{SYS_FRAMEWORKS}}/ReachSphere/Endpoint/Subsystems/AuthorizedBoot/systemd-units/usb-block.service
systemctl enable {{SYS_FRAMEWORKS}}/ReachSphere/Endpoint/Subsystems/AuthorizedBoot/systemd-units/network-auth-monitor.service

echo "[3/3] 로그 파일 초기화..."
touch /var/log/boot-auth.log
chmod 600 /var/log/boot-auth.log

echo "설치 완료!"
