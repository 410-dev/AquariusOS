#!/bin/bash

# ==============================================================================
# Btrfs Conversion Stage 1: Structure & Boot Prep
# ==============================================================================

set -e

# --- Helper Functions ---
log_step() {
    # Usage: log_step <current> <total> <message>
    echo "[Step $1/$2] $3"
    # Call original logging hook if it exists
    if type STEP &>/dev/null; then STEP "$1" "$2" "$3"; fi
}

error_exit() {
    echo "ERROR: $1"
    # Call original logging hook if it exists
    if type STEP &>/dev/null; then STEP "$2" "$3" "Error: $1"; fi
    sleep 3
    exit 1
}

# --- Detection ---
IS_SEPARATE_BOOT=false
if mountpoint -q /boot; then
    IS_SEPARATE_BOOT=true
    echo "[-] Detected separate /boot partition."
else
    echo "[-] Detected /boot is part of root filesystem."
fi

# ==============================================================================
# 1. Create Subvolumes
# ==============================================================================
log_step 1 8 "Creating btrfs subvolumes..."

if [[ -d /@ ]] || [[ -d /@home ]]; then
    error_exit "Directory /@ or /@home already exists. Conversion aborted." 1 8
fi

# Create snapshots/subvolumes
btrfs subvolume snapshot / /@
btrfs subvolume create /@home

# ==============================================================================
# 2. Migrate Data
# ==============================================================================
log_step 2 8 "Updating fstab and moving /home data..."

# Call existing python helper for fstab (Assuming it handles UUIDs correctly)
python3 "/opt/aqua/features/me.hysong.SnapshotSupport/fstab_editor.py" "$(findmnt --output=UUID --noheadings --target=/)"
if [[ $? -ne 0 ]]; then error_exit "fstab update failed." 2 8; fi

# Move Home Data
# We use rsync to move data from the snapshot's home to the new @home subvolume
rsync -aAXv /@/home/ /@home/
if [[ $? -ne 0 ]]; then error_exit "Moving /home data failed." 2 8; fi

# Clean up source home in the new root snapshot to avoid duplicate space usage
# (Optional, but good practice: leave an empty dir as mount point)
rm -rf /@/home/*

# ==============================================================================
# 3. Update GRUB (Configuration)
# ==============================================================================
log_step 3 8 "Updating GRUB configuration..."

# 3a. Call stage1 python editor (likely handles basic grub file edits)
python3 "/opt/aqua/features/me.hysong.SnapshotSupport/grub_editor_stg1.py"
if [[ $? -ne 0 ]]; then error_exit "GRUB python update failed." 3 8; fi

# ==============================================================================
# 4. Backup GRUB
# ==============================================================================
log_step 4 8 "Backing up GRUB configuration..."

[[ -f /etc/default/grub ]] || error_exit "/etc/default/grub not found." 4 8
[[ -f /boot/grub/grub.cfg ]] || error_exit "/boot/grub/grub.cfg not found." 4 8

cp /etc/default/grub /etc/default/grub.bak
cp /boot/grub/grub.cfg /boot/grub/grub.cfg.bak

# ==============================================================================
# 5. Inject Root Flags
# ==============================================================================
log_step 5 8 "Modifying /etc/default/grub..."

# We MUST inject rootflags=subvol=@ so the kernel knows to mount @ as root.
if grep -q "rootflags=subvol=@" /etc/default/grub; then
    echo "[-] rootflags already present."
else
    echo "[-] Injecting rootflags=subvol=@..."
    sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="rootflags=subvol=@ /' /etc/default/grub
    if [[ $? -ne 0 ]]; then error_exit "Failed to modify /etc/default/grub." 5 8; fi
fi

# ==============================================================================
# 6. Regenerate GRUB Config
# ==============================================================================
log_step 6 8 "Regenerating GRUB configuration..."

if command -v update-grub &> /dev/null; then
    update-grub || error_exit "GRUB regeneration failed." 6 8
else
    grub-mkconfig -o /boot/grub/grub.cfg || error_exit "GRUB regeneration failed." 6 8
fi

# ==============================================================================
# 7. Patch GRUB Paths (Conditional)
# ==============================================================================
log_step 7 8 "Patching GRUB paths..."

if [[ "$IS_SEPARATE_BOOT" == "true" ]]; then
    echo "[-] Separate /boot detected. Skipping path patching."
    echo "    (Kernel paths in grub.cfg are relative to /boot partition and do not need /@ prefix.)"
else
    echo "[-] /boot is on root. Patching paths to include /@/..."

    # We only run this if /boot is NOT separate.
    # In this case, the kernel files physically moved to /@/boot/,
    # but GRUB's search root is still the FS root.

    # 1. Linux Kernel Path
    sed -i 's|linux[[:space:]]*/boot/|linux /@/boot/|g' /boot/grub/grub.cfg
    sed -i 's|linux[[:space:]]*/vmlinuz|linux /@/vmlinuz|g' /boot/grub/grub.cfg

    # 2. Initrd Path
    sed -i 's|initrd[[:space:]]*/boot/|initrd /@/boot/|g' /boot/grub/grub.cfg
    sed -i 's|initrd[[:space:]]*/initrd|initrd /@/initrd|g' /boot/grub/grub.cfg

    if [[ $? -ne 0 ]]; then
        # Rollback on sed failure
        cp /boot/grub/grub.cfg.bak /boot/grub/grub.cfg
        error_exit "Failed to patch GRUB paths." 7 8
    fi
fi

# ==============================================================================
# 8. Finalize
# ==============================================================================
log_step 8 8 "Cleaning up and setting next stage..."

sync

/opt/aqua/sys/sbin/preboot.sh SetNextInstallmentScript /opt/aqua/features/me.hysong.SnapshotSupport/stages/stage2.sh
if [[ $? -ne 0 ]]; then error_exit "Setting next installment script failed." 8 8; fi

echo "[+] Stage 1 Complete. Ready for reboot."
exit 0
