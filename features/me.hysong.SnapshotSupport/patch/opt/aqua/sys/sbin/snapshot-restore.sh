#!/bin/bash

# ==============================================================================
# Btrfs Snapshot Restore Utility
# ==============================================================================
# Usage:
#   snapshot-restore --system
#       (Restores currently booted snapshot to main /@ and /@home)
#
#   snapshot-restore --home [-s=@home_snapshot_name] <file_path>
#       (Restores a specific file/dir from a snapshot to live location)
# ==============================================================================

set -e

# --- Compatibility Guards ---
if [[ "$(/opt/aqua/sys/sbin/reg.sh root read 'HKEY_LOCAL_MACHINE/SYSTEM/Features/me.hysong.SnapshotSupport/Enabled')" != "True" ]]; then
    echo "Error: Snapshot support feature is not enabled."
    exit 1
fi

# --- Configuration ---
MOUNT_POINT="/mnt/btrfs_restore_root"
GRUB_PRIMARY_FILE="/etc/grub.d/09_snapshot_primary"
PROBER_SCRIPT="/opt/aqua/sys/sbin/snapshot-prober.sh"

# --- Variables ---
MODE=""
TARGET_FILE=""
OPT_SNAPSHOT=""
CURRENT_SUBVOL=""
IS_SANDBOX=false

# --- Helper Functions ---
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "  --system                     Overwrite main system with current snapshot"
    echo "  --home [-s=<snap_name>] <path>   Restore specific file/folder"
    exit 1
}
detect_boot_environment() {
    # 1. Check if we are in an overlay (Sandbox)
    # We look specifically at the FSTYPE of / to see if it is 'overlay'
    if findmnt / -n -o FSTYPE | grep -q "overlay"; then
        IS_SANDBOX=true

        # CRITICAL FIX:
        # In Sandbox, the real source is mounted at /media/root-ro.
        # Format is usually: /dev/nvme0n1p2[/@snapshot-name]
        # We extract the subvolume name inside the brackets.
        RAW_SOURCE=$(findmnt /media/root-ro -n -o SOURCE)
        CURRENT_SUBVOL=$(echo "$RAW_SOURCE" | sed 's/.*\[\/\(.*\)\]/\1/')
    else
        # Standard Btrfs mount
        # Format: /dev/nvme0n1p2[/@snapshot-name]
        RAW_SOURCE=$(findmnt / -n -o SOURCE)
        CURRENT_SUBVOL=$(echo "$RAW_SOURCE" | sed 's/.*\[\/\(.*\)\]/\1/')
    fi

    # Clean leading slash if present (safety check)
    CURRENT_SUBVOL=${CURRENT_SUBVOL#/}
}

mount_root() {
    local ROOT_DEVICE=""

    if [[ "$IS_SANDBOX" == "true" ]]; then
        # CRITICAL FIX:
        # Use /media/root-ro to find the physical device.
        # findmnt output: /dev/nvme0n1p2[/@snapshot-...]
        # sed removes everything starting from '['
        ROOT_DEVICE=$(findmnt /media/root-ro -n -o SOURCE | sed 's/\[.*//')

        if [[ -z "$ROOT_DEVICE" ]]; then
            echo "Error: Could not detect physical device from /media/root-ro."
            exit 1
        fi
    else
        # Standard Boot: Source is /
        ROOT_DEVICE=$(findmnt / -n -o SOURCE | sed 's/\[.*//')
    fi

    # Sanity check
    if [[ -z "$ROOT_DEVICE" ]]; then
        echo "Error: Could not detect Btrfs root device."
        exit 1
    fi

    echo "[-] Mounting Btrfs root ($ROOT_DEVICE)..."
    mkdir -p "$MOUNT_POINT"
    # Mount raw btrfs root (ID 5)
    mount -o subvolid=5 "$ROOT_DEVICE" "$MOUNT_POINT"
}

# --- Argument Parsing ---
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --system) MODE="system" ;;
        --home) MODE="home" ;;
        -s=*) OPT_SNAPSHOT="${1#*=}" ;;
        *)
            if [[ "$MODE" == "home" && -z "$TARGET_FILE" ]]; then
                TARGET_FILE="$1"
            else
                echo "Unknown or misplaced argument: $1"
                usage
            fi
            ;;
    esac
    shift
done

if [[ -z "$MODE" ]]; then usage; fi
if [[ $EUID -ne 0 ]]; then echo "Run as root."; exit 1; fi

detect_boot_environment
mount_root

# ==============================================================================
# MODE: SYSTEM RESTORE
# ==============================================================================
if [[ "$MODE" == "system" ]]; then

    # 1. Validation
    if [[ "$CURRENT_SUBVOL" == "@" ]]; then
        echo "Error: You are booted into the main volume (@)."
        echo "You must boot into a snapshot to restore it."
        umount "$MOUNT_POINT"
        exit 1
    fi

    # Validation: Ensure Prober exists
    if [[ ! -f "$PROBER_SCRIPT" ]]; then
        echo "Error: $PROBER_SCRIPT not found. Cannot reconstruct GRUB safely."
        echo "Please install snapshot-prober before restoring."
        umount "$MOUNT_POINT"
        exit 1
    fi

    echo "[-] System Restore Initiated."
    echo "    Source: /$CURRENT_SUBVOL (Sandbox Mode: $IS_SANDBOX)"

    read -p "Are you sure you want to overwrite the main system? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then umount "$MOUNT_POINT"; exit 1; fi

    # 1. Identify paired Home Snapshot
    SNAP_FSTAB="$MOUNT_POINT/$CURRENT_SUBVOL/etc/fstab"
    HOME_SUBVOL=$(grep "[[:space:]]/home[[:space:]]" "$SNAP_FSTAB" | grep -o "subvol=[^, ]*" | cut -d= -f2)

    if [[ -z "$HOME_SUBVOL" ]]; then
        echo "Error: Could not determine /home snapshot from fstab."
        umount "$MOUNT_POINT"; exit 1
    fi

    # 2. Perform Rollback
    BACKUP_TS=$(date +%s)
    echo "[-] Backing up old system to /@_backup_$BACKUP_TS..."
    mv "$MOUNT_POINT/@" "$MOUNT_POINT/@_backup_$BACKUP_TS" || true
    mv "$MOUNT_POINT/@home" "$MOUNT_POINT/@home_backup_$BACKUP_TS" || true

    echo "[-] Restoring System & Home..."
    btrfs subvolume snapshot "$MOUNT_POINT/$CURRENT_SUBVOL" "$MOUNT_POINT/@"
    btrfs subvolume snapshot "$MOUNT_POINT/$HOME_SUBVOL" "$MOUNT_POINT/@home"

    # 3. Fix Fstab in New System
    echo "[-] Reverting fstab configuration..."
    NEW_FSTAB="$MOUNT_POINT/@/etc/fstab"
    sed -i "s/subvol=$HOME_SUBVOL /subvol=@home /g" "$NEW_FSTAB"
    sed -i "s/subvol=$HOME_SUBVOL,/subvol=@home,/g" "$NEW_FSTAB"

    # 4. RECONSTRUCT GRUB (The Safe Way via Chroot)
    echo "[-] Preparing Chroot for GRUB reconstruction..."

    # 4a. Copy the prober script into the restored system
    # We copy it to /tmp inside the restored volume to ensure it's available
    cp "$PROBER_SCRIPT" "$MOUNT_POINT/@/tmp/snapshot-prober"
    chmod +x "$MOUNT_POINT/@/tmp/snapshot-prober"

    # 4b. Bind Mount API Filesystems
    # This allows the chroot to talk to the kernel and hardware
    mount --bind /dev "$MOUNT_POINT/@/dev"
    mount --bind /dev/pts "$MOUNT_POINT/@/dev/pts"
    mount --bind /proc "$MOUNT_POINT/@/proc"
    mount --bind /sys "$MOUNT_POINT/@/sys"

    # Mount EFI if present
    if mountpoint -q /boot/efi; then
        mount --bind /boot/efi "$MOUNT_POINT/@/boot/efi"
    fi

    echo "[-] Reconstructing GRUB menu inside restored volume..."

    # 4c. Execute Prober inside Chroot
    # We run the prober we just copied. It will detect btrfs-snap.info files
    # and create the grub entries, then run update-grub.
    if chroot "$MOUNT_POINT/@" /tmp/snapshot-prober --reconstruct-grub; then
        echo "[+] GRUB successfully reconstructed."
    else
        echo "[!] Warning: GRUB reconstruction encountered errors. Trying to write update script..."
        # At mount point (restored system), create a script to run snapshot-prober on next boot
        UPDATE_SCRIPT="$MOUNT_POINT/@/opt/aqua/boot/preboot/var/install_update.sh"
        mkdir -p "$(dirname "$UPDATE_SCRIPT")"
        echo "#!/bin/bash" > "$UPDATE_SCRIPT"
        echo "/opt/aqua/sys/sbin/snapshot-prober.sh --reconstruct-grub" >> "$UPDATE_SCRIPT"
        echo "" >> "$UPDATE_SCRIPT"
        chmod +x "$UPDATE_SCRIPT"
        echo "[+] Update script written to $UPDATE_SCRIPT. It will run on next boot."
    fi

    # 4d. Cleanup Chroot
    rm "$MOUNT_POINT/@/tmp/snapshot-prober"
    umount "$MOUNT_POINT/@/boot/efi" 2>/dev/null || true
    umount "$MOUNT_POINT/@/sys"
    umount "$MOUNT_POINT/@/proc"
    umount "$MOUNT_POINT/@/dev/pts"
    umount "$MOUNT_POINT/@/dev"

    # 5. Cleanup Primary Override
    if [[ -f "$GRUB_PRIMARY_FILE" ]]; then
        rm "$GRUB_PRIMARY_FILE"
    fi

    echo "[+] Restore Complete. Please reboot."
    umount "$MOUNT_POINT"
    exit 0

# ==============================================================================
# MODE: FILE RESTORE
# ==============================================================================
elif [[ "$MODE" == "home" ]]; then

    if [[ -z "$TARGET_FILE" ]]; then echo "Error: Missing file path."; usage; fi

    # 1. Determine Source Snapshot
    SOURCE_SNAP=""

    if [[ -n "$OPT_SNAPSHOT" ]]; then
        # User specified snapshot manually
        SOURCE_SNAP="$OPT_SNAPSHOT"
    else
        # Auto-detect from current environment
        if [[ "$CURRENT_SUBVOL" == "@" ]]; then
            echo "Error: On Main Volume. Use -s=@snapshot_name"
            umount "$MOUNT_POINT"; exit 1
        fi

        # Read fstab to find the coupled home snapshot
        SNAP_FSTAB="$MOUNT_POINT/$CURRENT_SUBVOL/etc/fstab"
        SOURCE_SNAP=$(grep "[[:space:]]/home[[:space:]]" "$SNAP_FSTAB" | grep -o "subvol=[^, ]*" | cut -d= -f2)
    fi

    # 2. Path Translation
    # User input: /home/user/doc.txt
    # Physical path: /mnt/root/@home_snapshot/user/doc.txt

    # Strip "/home" prefix if present
    REL_PATH="${TARGET_FILE#/home}"
    FULL_SOURCE_PATH="$MOUNT_POINT/$SOURCE_SNAP$REL_PATH"

    if [[ ! -e "$FULL_SOURCE_PATH" ]]; then
        echo "Looked for: $FULL_SOURCE_PATH"
        echo "Error: File not found: $FULL_SOURCE_PATH"
        umount "$MOUNT_POINT"; exit 1
    fi

    echo "[-] Restoring: $REL_PATH"
    echo "    From: $SOURCE_SNAP"
    echo "    To:   $TARGET_FILE"

    # 3. Copy
    # Ensure parent dir exists
    echo "[-] Restoring: $TARGET_FILE from $SOURCE_SNAP"
    mkdir -p "$(dirname "$TARGET_FILE")"
    cp -r --preserve=mode,timestamps,ownership "$FULL_SOURCE_PATH" "$TARGET_FILE"

    echo "[+] File restored."
    umount "$MOUNT_POINT"
    exit 0
fi
