
def help(session) -> str:
    return "Usage: Reboot\nReboots the system."

# Return input string as bool
def main(session) -> tuple[int, list[str]]:
    import subprocess
    subprocess.run(["systemctl", "reboot"])
