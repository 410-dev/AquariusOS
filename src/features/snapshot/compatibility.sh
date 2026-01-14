#!/bin/bash

# Check current disk is in btrfs and is not running in subvolume
if ! btrfs subvolume show / >/dev/null 2>&1; then
    echo "Error: Current root filesystem is not a btrfs subvolume."
    exit 1
fi

exit 0