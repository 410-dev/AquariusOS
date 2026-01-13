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

echo "System compatibility check passed."
