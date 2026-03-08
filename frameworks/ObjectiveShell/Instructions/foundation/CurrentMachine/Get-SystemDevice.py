import psutil
import re

def help(session) -> str:
    return "Usage: SystemDevice\nGet the device name of the current boot device without partition number. (ex. /dev/sda)"

# Return input string as bool
def main(session) -> tuple[int, str]:
    partitions = psutil.disk_partitions()
    for part in partitions:
        if part.mountpoint == '/':
            # Regex removes trailing digits (e.g., /dev/nvme0n1p1 -> /dev/nvme0n1)
            # or (/dev/sda1 -> /dev/sda)
            drive = re.sub(r'\d+$', '', part.device)
            # Handle NVMe specifically as they often end in 'p' before the number
            return 0, drive.rstrip('p')
    return 1, "Not found"
