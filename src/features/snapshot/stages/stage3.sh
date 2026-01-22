#!/bin/bash

# Perform stage 3 of snapshot feature setup

log_step() {
    echo "[Step $1/$2] $3"
    if type STEP &>/dev/null; then STEP "$1" "$2" "[3/3] [$1/$2] $3"; fi
}

sleep 1
log_step 1 3 "Patching GRUB configuration for snapshot support..."
python3 "/opt/aqua/features/snapshot/grub_editor_stg1.py"
log_step 2 3 "Updating GRUB bootloader..."
update-grub
log_step 3 3 "Enabling snapshot feature in system registry..."
sudo /opt/aqua/sys/sbin/reg.sh root write "HKEY_LOCAL_MACHINE/SYSTEM/Features/snapshot/Enabled" bool 1
sudo /opt/aqua/sys/sbin/reg.sh root write "HKEY_LOCAL_MACHINE/SOFTWARE/Services/MoTD/NextOnly/Noti/Message/snapshot-enable-success" str "Snapshot feature enabled successfully."
sleep 1
exit 100
