import os
import psutil
import sys

def help(session) -> str:
    return "Usage: PartitionDeviceName\nGet the device name of the current boot device without partition number. (ex. /dev/sda)"

# Return input string as bool
def main(session, path) -> tuple[int, str]:
    # Absolute path is required to resolve symlinks or relative paths
    target_path = os.path.abspath(path)

    # Get all mount points
    partitions = psutil.disk_partitions(all=True)

    # We want to find the longest matching mount point
    # (e.g., if /boot is a separate partition, it's a better match than /)
    best_match = None
    for part in partitions:
        if target_path.startswith(part.mountpoint):
            if best_match is None or len(part.mountpoint) > len(best_match.mountpoint):
                best_match = part

    return (0, best_match.device) if best_match else (1, "Unknown")
