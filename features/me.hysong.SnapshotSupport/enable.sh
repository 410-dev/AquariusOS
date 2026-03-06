#!/bin/bash

# Reference: https://www.reddit.com/r/btrfs/comments/1dq04qx/convert_ubuntu_btrfs_installation_into_subvolumes/

set -e

apt install overlayroot -y

# Add btrfs module to grub
grub-install --modules=btrfs

chown root "$1/stages/stage1.sh"
chown root "$1/stages/stage2.sh"
chmod 755 "$1/stages/stage1.sh"
chmod 755 "$1/stages/stage2.sh"

/opt/aqua/sys/sbin/preboot.sh SetNextInstallmentScript /opt/aqua/features/me.hysong.SnapshotSupport/stages/stage1.sh

echo "Feature enablement will be applied on next reboot. Several reboots may be required to complete the process."
exit 0
