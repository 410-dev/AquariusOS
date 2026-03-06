#!/bin/bash

if [[ "$(/opt/aqua/sys/sbin/reg.sh root read 'HKEY_LOCAL_MACHINE/SYSTEM/Features/snapshot/Enabled')" != "True" ]]; then
    echo "Service incompatible: Snapshot support feature is not enabled."
    exit 0
fi

# Wait a few seconds to ensure the GNOME shell is fully ready
sleep 3

function SET_SAFE_WALLPAPER() {
    echo "SET_SAFE_WALLPAPER called"
    /opt/aisp/sys/sbin/aqua.sh wallpaper --snapshot-mode
}

# 1. Check for Sandbox (OverlayFS)
if findmnt / | grep -q "overlay"; then
    SET_SAFE_WALLPAPER
    notify-send \
        --urgency=critical \
        --expire-time=0 \
        --icon=dialog-warning \
        --app-name="AquariusOS Snapshot Support" \
        "⚠️ Sandbox Mode Active" \
        "You are in a volatile environment.\nChanges are written to RAM and will vanish on reboot."
    exit 0
fi

# 2. Check for Snapshot (Read-Write)
# Get the subvolume name (e.g., @snapshot-2025...)
CURRENT_SUBVOL=$(findmnt / -n -o SOURCE | sed 's/.*\[\/\(.*\)\]/\1/')

# If the subvolume is NOT "@", we are in a snapshot
if [[ "$CURRENT_SUBVOL" != "@" ]]; then
    SET_SAFE_WALLPAPER
    notify-send \
        --urgency=critical \
        --expire-time=0 \
        --icon=drive-multidisk \
        --app-name="AquariusOS Snapshot Support" \
        "⚠️ Snapshot Boot Detected" \
        "You are currently running inside: $CURRENT_SUBVOL\n\nThis is NOT your main system."
fi