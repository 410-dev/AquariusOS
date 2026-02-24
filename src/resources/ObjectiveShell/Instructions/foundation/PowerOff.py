
def help(session) -> str:
    return "Usage: PowerOff\nShuts down the system."

# Return input string as bool
def main(session) -> tuple[int, list[str]]:
    import subprocess
    subprocess.run(["poweroff"])
