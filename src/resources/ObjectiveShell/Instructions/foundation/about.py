import os

def help(session) -> str:
    return "Usage: about\nShows about this system"

# Return input string as bool
def main(session, filtering_elements: list[str]) -> dict[str, str]:
    # Get OS information
    if os.path.isfile("/etc/os-release"):
        with open("/etc/os-release", "r") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("PRETTY_NAME="):
                    os_name = line.split("=")[1].strip().strip('"')
                    data = {
                        "Name": os_name
                    }
                    return data

    data = {
        "Name": ""
    }

    return data

