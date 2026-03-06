#!/bin/bash

# ==============================================================================
# Btrfs Snapshot Deletion Tool
# ==============================================================================
# Usage:
#   snapshot-delete                (Interactive Mode)
#   snapshot-delete --target <name> (Delete specific snapshot by name)
#   snapshot-delete --prune <days>  (Delete snapshots older than X days)
# ==============================================================================

set -e

# --- Compatibility Guards ---
if [[ "$(/opt/aqua/sys/sbin/reg.sh root read 'HKEY_LOCAL_MACHINE/SYSTEM/Features/me.hysong.SnapshotSupport/Enabled')" != "True" ]]; then
    echo "Error: Snapshot support feature is not enabled."
    exit 1
fi

# --- Config ---
MOUNT_POINT="/mnt/btrfs_delete_root"
GRUB_CUSTOM_FILE="/etc/grub.d/40_custom"
REGISTRY_FILE="/var/log/btrfs_snapshot_registry.log"

# --- Variables ---
TARGET_SNAP=""
PRUNE_DAYS=""
IS_SANDBOX=false

# --- Helper: Detect & Mount ---
detect_and_mount() {
    if findmnt / -n -o FSTYPE | grep -q "overlay"; then
        IS_SANDBOX=true
        RAW_SOURCE=$(findmnt /media/root-ro -n -o SOURCE 2>/dev/null) || true
    else
        RAW_SOURCE=$(findmnt / -n -o SOURCE 2>/dev/null) || true
    fi

    # Extract device path (remove [subvol] part)
    ROOT_DEVICE=$(echo "$RAW_SOURCE" | sed 's/\[.*//')

    if [[ -z "$ROOT_DEVICE" ]]; then
        echo "Error: Could not detect Btrfs root device."
        exit 1
    fi

    mkdir -p "$MOUNT_POINT"
    mount -o subvolid=5 "$ROOT_DEVICE" "$MOUNT_POINT"
}

# --- Helper: Remove Snapshot Pair ---
delete_snapshot_pair() {
    local snap_name=$1
    local sys_path="$MOUNT_POINT/$snap_name"

    echo "[-] Processing: $snap_name"

    # 1. Identify paired Home Snapshot
    # We try to read fstab inside the snapshot to find the specific home it used
    local home_snap=""
    if [[ -f "$sys_path/etc/fstab" ]]; then
        home_snap=$(grep "[[:space:]]/home[[:space:]]" "$sys_path/etc/fstab" | grep -o "subvol=[^, ]*" | cut -d= -f2)
    fi

    # Fallback: If fstab read failed, try to guess based on naming convention
    if [[ -z "$home_snap" ]]; then
        # Replace @snapshot with @home_snapshot
        local guessed_name="${snap_name/@snapshot/@home_snapshot}"
        if [[ -d "$MOUNT_POINT/$guessed_name" ]]; then
            home_snap="$guessed_name"
        fi
    fi

    # 2. Delete System Snapshot
    if [[ -d "$sys_path" ]]; then
        # Must be RW to delete? No, but let's be safe.
        # Actually btrfs subvolume delete works on RO snapshots too.
        btrfs subvolume delete "$sys_path"
        echo "    [+] Deleted System: $snap_name"
    else
        echo "    [!] System snapshot not found: $snap_name"
    fi

    # 3. Delete Home Snapshot
    if [[ -n "$home_snap" && -d "$MOUNT_POINT/$home_snap" ]]; then
        btrfs subvolume delete "$MOUNT_POINT/$home_snap"
        echo "    [+] Deleted Home:   $home_snap"
    elif [[ -n "$home_snap" ]]; then
        echo "    [!] Home snapshot not found: $home_snap"
    fi

    # 4. Clean Registry (Optional visual cleanup)
    if [[ -f "$REGISTRY_FILE" ]]; then
        # Use a temp file to grep out the deleted line
        grep -v "$snap_name" "$REGISTRY_FILE" > "${REGISTRY_FILE}.tmp" && mv "${REGISTRY_FILE}.tmp" "$REGISTRY_FILE"
    fi
}

# --- Helper: Clean GRUB ---
clean_grub() {
    echo "[-] Cleaning GRUB entries..."
    # We need to regenerate the grub.cfg to remove the missing entries.
    # However, if using the manual 40_custom approach, update-grub WON'T remove them
    # unless we edit 40_custom.

    # If you are using snapshot-prober (42_btrfs_snapshots), simply re-running it fixes it.
    if [[ -x "/usr/local/bin/snapshot-prober.sh" ]]; then
        /usr/local/bin/snapshot-prober.sh --reconstruct-grub
    else
        # Fallback for 40_custom manual entries:
        # This is tricky with sed. It is safer to tell user to run prober if available.
        echo "    [!] Note: If you manually added entries to 40_custom, they might persist."
        echo "    Running update-grub to clear stale auto-detected entries..."
        update-grub
    fi
}

# --- Mode: Interactive ---
interactive_mode() {
    echo "Scanning for snapshots..."
    # Array of snapshots
    local options=()

    # Read directory listing
    for d in "$MOUNT_POINT"/@snapshot*; do
        if [[ -d "$d" ]]; then
            options+=("$(basename "$d")")
        fi
    done

    if [ ${#options[@]} -eq 0 ]; then
        echo "No snapshots found."
        return
    fi

    echo "Select a snapshot to DELETE (Ctrl+C to cancel):"

    PS3="Enter number (or 'q' to quit): "
    select opt in "${options[@]}"; do
        if [[ -n "$opt" ]]; then
            read -p "Are you SURE you want to delete '$opt' and its home? [y/N] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                delete_snapshot_pair "$opt"
                clean_grub
            else
                echo "Cancelled."
            fi
            break
        elif [[ "$REPLY" == "q" ]]; then
            break
        else
            echo "Invalid option."
        fi
    done
}

# --- Execution ---

# Check Root
if [[ $EUID -ne 0 ]]; then echo "Run as root."; exit 1; fi

detect_and_mount

# Argument Parsing
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --target) TARGET_SNAP="$2"; shift ;;
        --prune) PRUNE_DAYS="$2"; shift ;;
        *)
            # If no args provided, break to interactive
            break
            ;;
    esac
    shift
done

if [[ -n "$TARGET_SNAP" ]]; then
    # Direct deletion
    if [[ -d "$MOUNT_POINT/$TARGET_SNAP" ]]; then
        delete_snapshot_pair "$TARGET_SNAP"
        clean_grub
    else
        echo "Error: Snapshot '$TARGET_SNAP' not found."
        umount "$MOUNT_POINT"
        exit 1
    fi

elif [[ -n "$PRUNE_DAYS" ]]; then
    # Time-based deletion
    echo "[-] Pruning snapshots older than $PRUNE_DAYS days..."
    # Find directories named @snapshot* modified +N days ago
    find "$MOUNT_POINT" -maxdepth 1 -name "@snapshot*" -mtime +"$PRUNE_DAYS" | while read snap_path; do
        NAME=$(basename "$snap_path")
        delete_snapshot_pair "$NAME"
    done
    clean_grub

else
    # Default to Interactive
    interactive_mode
fi

# Cleanup
umount "$MOUNT_POINT"
rmdir "$MOUNT_POINT"
