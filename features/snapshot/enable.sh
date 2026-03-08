#!/bin/bash

# Reference: https://www.reddit.com/r/btrfs/comments/1dq04qx/convert_ubuntu_btrfs_installation_into_subvolumes/

set -e

apt install overlayroot -y

# Add btrfs module to grub
bootdev="$(ObjectiveShell CurrentMachine/Get-SystemDevice)"
echo "Detected boot device: $bootdev"
grub-install --modules=btrfs "$bootdev"

# Copy current bundle patch/* to root
#cp -r "$1/patch"/* /
#ln -sf {{SYS_PYLIBS}}/libsnapshot.py /usr/lib/python3/dist-packages/libsnapshot.py

# Set permission of stages
# file is owned by root and not writable by group/others
chown root "$1/stages/stage1.sh"
chown root "$1/stages/stage2.sh"
chown root "$1/stages/stage3.sh"
chmod 755 "$1/stages/stage1.sh"
chmod 755 "$1/stages/stage2.sh"
chmod 755 "$1/stages/stage3.sh"

{{SYS_CMDS}}/preboot.sh SetNextInstallmentScript "$1/stages/stage1.sh"

echo "Feature enablement will be applied on next reboot. Several reboots may be required to complete the process."
exit 100
