#!/bin/bash

if [[ "$(/opt/aqua/sys/sbin/reg.sh root read 'HKEY_LOCAL_MACHINE/SYSTEM/Features/me.hysong.SnapshotSupport/Enabled')" != "True" ]]; then
    echo "Service incompatible: Snapshot support feature is not enabled."
    exit 0
fi

# Wait a few seconds to ensure the GNOME shell is fully ready
sleep 3

function SET_SAFE_WALLPAPER() {
    for bus in /run/user/*/bus; do
        uid=$(basename "$(dirname "$bus")")
        user=$(getent passwd "$uid" | cut -d: -f1)

        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.background picture-uri "file:///opt/aqua/sys/graphics/safe/snapshot-mode.png"
        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.background picture-uri-dark "file:///opt/aqua/sys/graphics/safe/snapshot-mode.png"
        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.screensaver picture-uri "file:///opt/aqua/sys/graphics/safe/snapshot-mode.png"

    done

    gsettings set org.gnome.desktop.background picture-uri "file:///opt/aqua/sys/graphics/safe/snapshot-mode.png"
    gsettings set org.gnome.desktop.background picture-uri-dark "file:///opt/aqua/sys/graphics/safe/snapshot-mode.png"
    gsettings set org.gnome.desktop.screensaver picture-uri "file:///opt/aqua/sys/graphics/safe/snapshot-mode.png"
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