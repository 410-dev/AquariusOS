#!/bin/bash

# ==============================================================================
# Btrfs Snapshot Manager (Ubuntu/GRUB)
# ==============================================================================
# Options:
#   --bootable : Standard RW snapshot (changes persist)
#   --integrity: RO snapshot (backup only, not in GRUB)
#   --sandbox  : RO snapshot + RAM Overlay (changes vanish on reboot)
# ==============================================================================

set -e

if [[ "$(/opt/aqua/sys/sbin/reg.sh root read 'HKEY_LOCAL_MACHINE/SYSTEM/Features/me.hysong.SnapshotSupport/Enabled')" != "True" ]]; then
    echo "snapshot-make incompatible: Snapshot support feature is not enabled."
    exit 1
fi
if [[ -z "$(mount | grep ' / ' | grep 'subvol=/@')" ]]; then
    echo "snapshot-make incompatible: System is not booted from btrfs subvolume /@."
    exit 1
fi


# --- Configuration ---
REGISTRY_FILE="/var/log/btrfs_snapshot_registry.log"
GRUB_CUSTOM_FILE="/etc/grub.d/40_custom"
MOUNT_POINT="/mnt/btrfs_temp_root"

# --- Variables ---
MODE=""
IS_PRIMARY="false"
CUSTOM_NAME=""
TIMESTAMP=$(date +%Y-%m-%d-%H%M%S)

# --- Helper Functions ---
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  --bootable        RW snapshot (Persistent changes)"
    echo "  --integrity       RO snapshot (Backup only)"
    echo "  --sandbox         RO snapshot + RAM Overlay (Changes lost on reboot)"
    echo "  --name <string>   Add label to snapshot"
    exit 1
}

log_registry() {
    echo "$TIMESTAMP | ${CUSTOM_NAME:-"N/A"} | $1 | $2 | $3" >> "$REGISTRY_FILE"
}

# --- Argument Parsing ---
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --bootable) MODE="bootable" ;;
        --integrity) MODE="integrity" ;;
        --sandbox) MODE="sandbox" ;;
        --name) CUSTOM_NAME="$2"; shift ;;
        *) echo "Unknown parameter: $1"; usage ;;
    esac
    shift
done

if [[ -z "$MODE" ]]; then usage; fi
if [[ $EUID -ne 0 ]]; then echo "Run as root."; exit 1; fi

# --- Naming ---
CLEAN_NAME=$(echo "$CUSTOM_NAME" | tr ' ' '_')
if [[ -n "$CLEAN_NAME" ]]; then SNAP_SUFFIX="-${CLEAN_NAME}-${TIMESTAMP}"; else SNAP_SUFFIX="-${TIMESTAMP}"; fi
SNAP_SYS="@snapshot${SNAP_SUFFIX}"
SNAP_HOME="@home_snapshot${SNAP_SUFFIX}"

# --- Execution ---
ROOT_DEVICE=$(findmnt / -n -o SOURCE | sed 's/\[.*//')
FS_UUID=$(blkid -s UUID -o value "$ROOT_DEVICE")

echo "[-] Mounting Btrfs root ($ROOT_DEVICE)..."
mkdir -p "$MOUNT_POINT"
mount -o subvolid=5 "$ROOT_DEVICE" "$MOUNT_POINT"

# 1. INTEGRITY MODE (Pure Backup)
if [[ "$MODE" == "integrity" ]]; then
    echo "[-] Creating Integrity Backups..."
    # We create them as RW first to write metadata, then lock them.
    btrfs subvolume snapshot "$MOUNT_POINT/@" "$MOUNT_POINT/$SNAP_SYS"
    btrfs subvolume snapshot "$MOUNT_POINT/@home" "$MOUNT_POINT/$SNAP_HOME"

    # Write Metadata
    echo "TYPE=integrity" > "$MOUNT_POINT/$SNAP_SYS/etc/btrfs-snap.info"

    # Lock to Read-Only
    btrfs property set "$MOUNT_POINT/$SNAP_SYS" ro true
    btrfs property set "$MOUNT_POINT/$SNAP_HOME" ro true

    log_registry "INTEGRITY (RO)" "$SNAP_SYS" "$SNAP_HOME"
    echo "[+] Done. No GRUB entry created."

# 2. BOOTABLE or SANDBOX MODE
else
    echo "[-] Creating Snapshots..."

    # For Sandbox, we technically want the source on disk to be Read-Only,
    # but we create it as RW first to edit fstab, then flip it to RO later.
    btrfs subvolume snapshot "$MOUNT_POINT/@" "$MOUNT_POINT/$SNAP_SYS"
    btrfs subvolume snapshot "$MOUNT_POINT/@home" "$MOUNT_POINT/$SNAP_HOME"

    echo "[-] Updating fstab..."
    SNAP_FSTAB="$MOUNT_POINT/$SNAP_SYS/etc/fstab"
    sed -i "s/subvol=@home /subvol=$SNAP_HOME /g" "$SNAP_FSTAB"
    sed -i "s/subvol=@home,/subvol=$SNAP_HOME,/g" "$SNAP_FSTAB"

    # BOOT ARGS PREPARATION
    CURRENT_KERNEL=$(uname -r)
    VMLINUZ="vmlinuz-${CURRENT_KERNEL}"
    INITRD="initrd.img-${CURRENT_KERNEL}"
    # Strip existing root flags
    BOOT_ARGS=$(cat /proc/cmdline | sed 's/root=UUID=[^ ]*//g' | sed 's/rootflags=[^ ]*//g')


    if [[ "$MODE" == "sandbox" ]]; then
        echo "[-] Configuring Sandbox (RAM Overlay)..."

        # FIX: Write Metadata BEFORE setting to Read-Only
        echo "TYPE=sandbox" > "$MOUNT_POINT/$SNAP_SYS/etc/btrfs-snap.info"

        # Now we can safely lock it
        btrfs property set "$MOUNT_POINT/$SNAP_SYS" ro true
        btrfs property set "$MOUNT_POINT/$SNAP_HOME" ro true

        # 2. Add overlayroot config to kernel arguments
        # overlayroot=tmpfs tells Ubuntu to mount root RO and overlay RAM on top
        BOOT_ARGS="$BOOT_ARGS overlayroot=tmpfs"
        MENU_TITLE="Sandbox: $TIMESTAMP (Resets on Reboot)"
        REG_TYPE="SANDBOX (RAM)"
        RO_FLAG="ro"
    else
        echo "[-] Configuring Bootable Snapshot..."

        # Write Metadata
        echo "TYPE=bootable" > "$MOUNT_POINT/$SNAP_SYS/etc/btrfs-snap.info"

        MENU_TITLE="Snapshot: $TIMESTAMP (Persistent)"
        REG_TYPE="BOOTABLE (RW)"
        RO_FLAG="rw"
    fi

    echo "[-] Generating GRUB Entry..."

    cat <<EOF >> "$GRUB_CUSTOM_FILE"
menuentry '$MENU_TITLE' --class ubuntu --class gnu-linux --class gnu --class os {
    recordfail
    load_video
    gfxmode \$linux_gfx_mode
    insmod gzio
    insmod part_gpt
    insmod btrfs
    search --no-floppy --fs-uuid --set=root $FS_UUID
    echo 'Loading Kernel...'
    linux /${SNAP_SYS}/boot/${VMLINUZ} root=UUID=${FS_UUID} rootflags=subvol=${SNAP_SYS} $RO_FLAG ${BOOT_ARGS}
    echo 'Loading Initrd...'
    initrd /${SNAP_SYS}/boot/${INITRD}
}
EOF

    update-grub
    log_registry "$REG_TYPE" "$SNAP_SYS" "$SNAP_HOME"
    echo "[+] Success! Entry '$MENU_TITLE' added."
fi

# Cleanup
umount "$MOUNT_POINT"
rmdir "$MOUNT_POINT"
