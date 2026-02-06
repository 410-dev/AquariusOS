#!/bin/bash

# Reference: https://www.reddit.com/r/btrfs/comments/1dq04qx/convert_ubuntu_btrfs_installation_into_subvolumes/

set -e

# Verify subvolume boot
if [[ ! -z "$(mount | grep ' / ' | grep 'subvol=/@')" ]]; then
    echo "System is already booted from btrfs subvolume /@."
else
    echo "Error: System is not booted from btrfs subvolume /@. Please check the configuration."
    exit 1
fi

echo "Updating grub configuration..."
STEP 1 4 "Updating GRUB configuration..."
update-grub
if [[ $? -ne 0 ]]; then
    STEP 1 4 "Error: GRUB regeneration failed."
    sleep 2
    exit 1
fi
grub-install --efi-directory=/boot/efi
if [[ $? -ne 0 ]]; then
    STEP 1 4 "Error: GRUB installation failed."
    sleep 2
    exit 1
fi

# Verify subvolumes
echo "Verifying btrfs subvolumes..."
STEP 2 4 "Verifying btrfs subvolumes..."
DEVICE_NAME=$(findmnt --noheadings --output=SOURCE --target=/ | sed 's/\[.*//')
mkdir -p /tmp/subvolmnt
mount "$DEVICE_NAME" /tmp/subvolmnt
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to mount btrfs device $DEVICE_NAME."
    rmdir /tmp/subvolmnt
    sleep 2
    exit 1
fi
if [[ -z "$(ls -1 /tmp/subvolmnt | grep '@home')" ]]; then
    echo "Error: Subvolumes /@ and /@home not found. Please check the configuration."
    umount /tmp/subvolmnt
    rmdir /tmp/subvolmnt
    exit 1
fi

echo "Reclaiming space..."
STEP 3 4 "Reclaiming space by removing old root data..."
return_to_dir=$(pwd)
cd /tmp/subvolmnt
shopt -s extglob
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to enable extglob."
    umount /tmp/subvolmnt
    rmdir /tmp/subvolmnt
    exit 1
fi
rm -rf !(@*)
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to remove old root data."
    umount /tmp/subvolmnt
    rmdir /tmp/subvolmnt
    exit 1
fi
shopt -u extglob
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to disable extglob."
    umount /tmp/subvolmnt
    rmdir /tmp/subvolmnt
    exit 1
fi
cd "$return_to_dir"

echo "Cleanup..."
STEP 4 4 "Cleaning up temporary mount..."
umount /tmp/subvolmnt
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to unmount temporary mount."
    exit 1
fi

set +e

rmdir /tmp/subvolmnt

exit 0
