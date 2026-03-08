
def help(session) -> str:
    return "Usage: RebootUEFI\nReboots the system using UEFI."

# Return input string as bool
def main(session) -> tuple[int, list[str]]:
    import subprocess
    subprocess.run(["systemctl", "reboot", "--firmware-setup"])
