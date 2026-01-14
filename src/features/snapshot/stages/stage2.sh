#!/bin/bash

# ==============================================================================
# Btrfs Conversion Stage 2: Cleanup & Finalization
# ==============================================================================
# This script runs AFTER rebooting into the new /@ subvolume.
# It cleans up the old "root" files that are left outside the subvolumes.
# ==============================================================================

set -e

# --- Configuration ---
MOUNT_POINT="/tmp/btrfs_cleanup_root"
IS_EFI=false
if [[ -d "/sys/firmware/efi" ]]; then IS_EFI=true; fi

# --- Helper Functions ---
log_step() {
    echo "[Step $1/$2] $3"
    if type STEP &>/dev/null; then STEP "$1" "$2" "$3"; fi
}

error_exit() {
    echo "ERROR: $1"
    if type STEP &>/dev/null; then STEP "$2" "$3" "Error: $1"; fi
    sleep 3
    exit 1
}

# Cleanup trap to ensure unmount happens on exit/error
cleanup() {
    if mountpoint -q "$MOUNT_POINT"; then
        echo "[-] Trap: Unmounting cleanup root..."
        umount "$MOUNT_POINT"
    fi
    if [[ -d "$MOUNT_POINT" ]]; then
        rmdir "$MOUNT_POINT" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# ==============================================================================
# 1. Verification
# ==============================================================================
# Logic parity: Ensure we are booted into the expected subvolume.
if findmnt / -n -o OPTIONS | grep -q "subvol=/@"; then
    echo "[-] Verification passed: Booted from subvolume /@."
else
    # Fallback check: sometimes options string varies, check source path
    if findmnt / -n -o SOURCE | grep -q "\[/@\]"; then
        echo "[-] Verification passed: Booted from subvolume /@ (detected via source)."
    else
        error_exit "System is NOT booted from /@. Aborting cleanup to prevent data loss." 0 4
    fi
fi

# ==============================================================================
# 2. Update Bootloader
# ==============================================================================
log_step 1 4 "Finalizing GRUB configuration..."

# Now that we are booted in /@, update-grub will naturally detect the subvolume
# and write the correct rootflags=subvol=@ into grub.cfg automatically.
update-grub
if [[ $? -ne 0 ]]; then error_exit "GRUB regeneration failed." 1 4; fi

if [[ "$IS_EFI" == "true" ]]; then
    # Ensure the EFI executable points to the correct config location
    grub-install --efi-directory=/boot/efi
    if [[ $? -ne 0 ]]; then error_exit "GRUB EFI installation failed." 1 4; fi
else
    echo "[-] Legacy BIOS detected. Skipping EFI installation."
    # Optional: You might want to run 'grub-install /dev/sdX' here for BIOS,
    # but detecting the correct drive automatically is risky.
    # Usually update-grub is sufficient for BIOS if the MBR is already set.
fi

# ==============================================================================
# 3. Mount Raw Root (subvolid=5)
# ==============================================================================
log_step 2 4 "Mounting raw Btrfs root..."

# Logic parity: Identify physical device using findmnt, stripping [subvol] info
ROOT_DEVICE=$(findmnt / -n -o SOURCE | sed 's/\[.*//')

if [[ -z "$ROOT_DEVICE" ]]; then
    error_exit "Could not detect root device." 2 4
fi

mkdir -p "$MOUNT_POINT"

# Mount subvolid=5 explicitly to see the top-level structure
mount -o subvolid=5 "$ROOT_DEVICE" "$MOUNT_POINT"
if [[ $? -ne 0 ]]; then error_exit "Failed to mount raw root ($ROOT_DEVICE)." 2 4; fi

# Verify we see the subvolumes we expect before deleting anything
if [[ ! -d "$MOUNT_POINT/@" ]] || [[ ! -d "$MOUNT_POINT/@home" ]]; then
    error_exit "Safety check failed: /@ or /@home missing from top-level. Aborting." 2 4
fi

# ==============================================================================
# 4. Reclaim Space
# ==============================================================================
log_step 3 4 "Reclaiming space (removing old root data)..."

# Save current dir to return later (though we are running from a script, good practice)
pushd "$MOUNT_POINT" > /dev/null

# Enable extended globbing to use the negation pattern !()
shopt -s extglob

# Safety: We are about to delete everything that does NOT start with @
# This assumes your subvolumes are named @, @home, @snapshot, etc.
# Any standard file (bin, etc, usr, var) in the top level will be deleted.
echo "[-] Removing files in top-level that do not match '@*'..."

# Explicitly check we are in the mount point before running rm
if [[ "$(pwd)" == "$MOUNT_POINT" ]]; then
    rm -rf !(@*)
    if [[ $? -ne 0 ]]; then
        popd > /dev/null
        error_exit "Failed to remove old root data." 3 4
    fi
else
    popd > /dev/null
    error_exit "Working directory mismatch. Aborting delete." 3 4
fi

shopt -u extglob
popd > /dev/null

# ==============================================================================
# 5. Finish
# ==============================================================================
log_step 4 4 "Cleanup complete."

# The trap will handle unmounting, but we can do it explicitly to be clean.
umount "$MOUNT_POINT"
rmdir "$MOUNT_POINT"

echo "[+] Conversion confirmed successful. System is optimized."
exit 0
