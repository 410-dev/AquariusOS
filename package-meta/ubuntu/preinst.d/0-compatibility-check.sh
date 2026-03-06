#!/bin/bash

# Check if current system is installed in btrfs filesystem
# If not, it is incompatible
if [ "$(findmnt -n -o FSTYPE /)" != "btrfs" ]; then
    echo "Error: The root filesystem is not BTRFS. This system is incompatible."
    exit 1
fi

# Check if /boot is not mounted as separate partition
# If so, then it is incompatible (Meaning: /boot MUST be a separate partition)
if ! mountpoint -q /boot; then
    echo "Error: /boot is not mounted as a separate partition. This system is incompatible."
    exit 1
fi


# Host requirement: Ubuntu 26.04 LTS ONLY
# User may bypass version checking by creating a file at /var/noinstfs/aqua/root.d/registry/SYSTEM/Installer/Flags/BypassHostOSCheck.bool.rv with content "1"
BYPASS_CHECK="0"
if [[ -f /var/noinstfs/aqua/root.d/registry/SYSTEM/Installer/Flags/BypassHostOSCheck.bool.rv ]]; then
  BYPASS_CHECK=$(cat /var/noinstfs/aqua/root.d/registry/SYSTEM/Installer/Flags/BypassHostOSCheck.bool.rv | tr -d ' \t\n\r')
fi

if [ "$BYPASS_CHECK" != "1" ]; then
  if [ ! -f /etc/os-release ] || [ -z "$(grep "26.04" /etc/os-release)" ]; then
    echo "This package is intended for Ubuntu 26.04 LTS only. Aborting installation." >&2
    exit 1
  fi
fi

echo "System compatibility check passed."
