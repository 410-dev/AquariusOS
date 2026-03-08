#!/bin/bash

# Perform stage 3 of snapshot feature setup

if [[ ! -f "/var/log/aqua/snapshot-conversion-stage3.log" ]]; then
    mkdir -p /var/log/aqua
    touch /var/log/aqua/snapshot-conversion-stage3.log
fi

log_step() {
    echo "[Step $1/$2] $3"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Step $1/$2] $3" >> /var/log/aqua/snapshot-conversion-stage3.log
    sync
    if type STEP &>/dev/null; then STEP "$1" "$2" "[3/3] [$1/$2] $3"; fi
}

sleep 1
log_step 1 3 "Patching GRUB configuration for snapshot support..."
python3 "{{FEATURES}}/snapshot/grub_editor_stg1.py"
log_step 2 3 "Updating GRUB bootloader..."
update-grub
log_step 3 3 "Enabling snapshot feature in system registry..."
sudo {{SYS_CMDS}}/reg.sh root write "HKEY_LOCAL_MACHINE/SYSTEM/Features/snapshot/Enabled" bool 1
sudo {{SYS_CMDS}}/reg.sh root write "HKEY_LOCAL_MACHINE/SOFTWARE/Services/MoTD/NextOnly/Noti/Message/snapshot-enable-success" str "Snapshot feature enabled successfully."
sleep 1
exit 100
