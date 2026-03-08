import psutil

def help(session) -> str:
    return "Usage: SystemPartition\nGet the device name of the current boot device with partition number. (ex. /dev/sda3)"

# Return input string as bool
def main(session) -> tuple[int, str]:
    partitions = psutil.disk_partitions()
    for part in partitions:
        if part.mountpoint == '/':
            return 0, part.device
    return 1, "Not found"
