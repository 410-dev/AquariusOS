#!/bin/bash

# Reference: https://www.reddit.com/r/btrfs/comments/1dq04qx/convert_ubuntu_btrfs_installation_into_subvolumes/

set -e
#"/opt/aqua/sys/sbin/preboot.sh" SetInstallmentScriptFailRollbackScript "/opt/aqua/features/me.hysong.SnapshotSupport/stages/stage1-rollback.sh"

# Create subvolumes
STEP 1 8 "Creating btrfs subvolumes..."
if [[ -d /@ ]] || [[ -d /@home ]]; then
    STEP 1 8 "Error: Directory /@ or /@home already exist. Unable to create subvolumes."
    sleep 3
    exit 1
fi
btrfs subvolume snapshot / /@
btrfs subvolume create /@home

# Update fstab and move home data
STEP 2 8 "Updating fstab and moving /home data..."
python3 "/opt/aqua/features/me.hysong.SnapshotSupport/fstab_editor.py" "$(findmnt --output=UUID --noheadings --target=/)"
if [[ $? -ne 0 ]]; then
    STEP 2 8 "Error: fstab update failed."
    sleep 3
    exit 1
fi
#mv /@/home/* /@home/   # <-- Make it safe for empty home directories
rsync -aAXv /@/home/ /@home/
if [[ $? -ne 0 ]]; then
    STEP 2 8 "Error: Moving /home data failed."
    sleep 3
    exit 1
fi


# Update grub to boot from new subvolumes
STEP 3 8 "Updating GRUB configuration..."
python3 "/opt/aqua/features/me.hysong.SnapshotSupport/grub_editor_stg1.py"
if [[ $? -ne 0 ]]; then
    STEP 3 8 "Error: GRUB update failed."
    sleep 3
    exit 1
fi
update-grub
if [[ $? -ne 0 ]]; then
    STEP 3 8 "Error: GRUB regeneration failed."
    sleep 3
    exit 1
fi

### FROM GEMINI
### Updating grub without rebooting
echo "Backing up current GRUB configuration..."
STEP 4 8 "Backing up GRUB configuration..."
if [[ ! -f /etc/default/grub ]]; then
    echo "Error: /etc/default/grub not found. Cannot back up."
    STEP 4 8 "Error: Cannot backup GRUB. (1)"
    sleep 3
    exit 1
fi
if [[ ! -f /boot/grub/grub.cfg ]]; then
    echo "Error: /boot/grub/grub.cfg not found. Cannot back up."
    STEP 4 8 "Error: Cannot backup GRUB. (2)"
    sleep 3
    exit 1
fi
cp /etc/default/grub /etc/default/grub.bak
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to back up /etc/default/grub."
    STEP 4 8 "Error: Failed to backup GRUB. (1)"
    sleep 3
    exit 1
fi
cp /boot/grub/grub.cfg /boot/grub/grub.cfg.bak
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to back up /boot/grub/grub.cfg."
    STEP 4 8 "Error: Failed to backup GRUB. (2)"
    sleep 3
    exit 1
fi

# 1. Add rootflags=subvol=@ to /etc/default/grub
# We look for the GRUB_CMDLINE_LINUX_DEFAULT line.
# If "rootflags=subvol=@" is not already there, we inject it inside the quotes.
echo "Modifying /etc/default/grub to include rootflags=subvol=@..."
STEP 5 8 "Modifying /etc/default/grub..."
if grep -q "rootflags=subvol=@" /etc/default/grub; then
    echo "rootflags already present in /etc/default/grub."
else
    echo "Adding rootflags to /etc/default/grub..."
    sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="rootflags=subvol=@ /' /etc/default/grub
    if [[ $? -ne 0 ]]; then
        echo "Error: Failed to modify /etc/default/grub."
        STEP 5 8 "Error: Failed to modify GRUB configuration."
        sleep 3
        exit 1
    fi
fi

# 2. Regenerate the GRUB config file
# This applies the flags we just added.
echo "Regenerating GRUB configuration..."
STEP 6 8 "Regenerating GRUB configuration..."
if command -v update-grub &> /dev/null; then
    update-grub
    if [[ $? -ne 0 ]]; then
        echo "Error: GRUB regeneration failed."
        STEP 6 8 "Error: GRUB regeneration failed."
        sleep 3
        exit 1
    fi
else
    # Fallback for non-Debian/Ubuntu systems (Arch, Fedora, etc.)
    echo "WARNING: update-grub command not found. Using grub-mkconfig instead."
    grub-mkconfig -o /boot/grub/grub.cfg
    if [[ $? -ne 0 ]]; then
        echo "Error: GRUB regeneration failed."
        STEP 6 8 "Error: GRUB regeneration failed."
        sleep 3
        exit 1
    fi
fi

# 3. Force the /@/boot path adjustment (The 'linux' and 'initrd' lines)
# Standard GRUB generation might write '/boot/...' instead of '/@/boot/...'
# We use sed to patch the final grub.cfg file to match your manual instruction requirements.

echo "Patching paths to include subvolume /@/..."
STEP 7 8 "Patching GRUB paths..."

# Replace "linux /boot/" with "linux /@/boot/"
grub_cfg_orig="$(cat /boot/grub/grub.cfg)"
sed -i 's|linux[[:space:]]*/boot/|linux /@/boot/|g' /boot/grub/grub.cfg
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to patch GRUB linux paths."
    STEP 7 8 "Error: Failed to patch GRUB paths."
    sleep 3
    # Restore original grub.cfg before exiting
    echo "$grub_cfg_orig" > /boot/grub/grub.cfg
    exit 1
fi
sed -i 's|linux[[:space:]]*/vmlinuz|linux /@/vmlinuz|g' /boot/grub/grub.cfg
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to patch GRUB linux vmlinuz paths."
    STEP 7 8 "Error: Failed to patch GRUB paths."
    sleep 3
    # Restore original grub.cfg before exiting
    echo "$grub_cfg_orig" > /boot/grub/grub.cfg
    exit 1
fi

# Replace "initrd /boot/" with "initrd /@/boot/"
sed -i 's|initrd[[:space:]]*/boot/|initrd /@/boot/|g' /boot/grub/grub.cfg
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to patch GRUB initrd paths."
    STEP 7 8 "Error: Failed to patch GRUB paths."
    sleep 3
    # Restore original grub.cfg before exiting
    echo "$grub_cfg_orig" > /boot/grub/grub.cfg
    exit 1
fi
sed -i 's|initrd[[:space:]]*/initrd|initrd /@/initrd|g' /boot/grub/grub.cfg
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to patch GRUB initrd initrd paths."
    STEP 7 8 "Error: Failed to patch GRUB paths."
    sleep 3
    # Restore original grub.cfg before exiting
    echo "$grub_cfg_orig" > /boot/grub/grub.cfg
    exit 1
fi

### END GEMINI

STEP 8 8 "Cleaning up and finalizing step 1..."
/opt/aqua/sys/sbin/preboot.sh SetNextInstallmentScript /opt/aqua/features/me.hysong.SnapshotSupport/stages/stage2.sh
if [[ $? -ne 0 ]]; then
    STEP 8 8 "Error: Setting next installment script failed."
    sleep 3
    exit 1
fi
exit 0
