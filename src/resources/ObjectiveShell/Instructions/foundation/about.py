import os

def help(session) -> str:
    return "Usage: about\nShows about this system"

# Return input string as bool
def main(session, filtering_elements: list[str] = None) -> dict[str, str] | int:
    # Get OS information
    if os.path.isfile("/etc/os-release"):
        with open("/etc/os-release", "r") as f:
            lines = f.readlines()

    data = {}

    for line in lines:
        if line.startswith("NAME="):
            data["Name"] = line.split("=")[1].strip().strip('"')
        if line.startswith("VERSION="):
            data["Version"] = line.split("=")[1].strip().strip('"')
        if line.startswith("ID="):
            data["ID"] = line.split("=")[1].strip().strip('"')
        if line.startswith("VERSION_ID="):
            data["Version ID"] = line.split("=")[1].strip().strip('"')

    if filtering_elements is None:
        for key, value in data.items():
            print(f"{key}: {value}")
        return 0

    else:
        filtered_data = {key: value for key, value in data.items() if key in filtering_elements}
        return filtered_data