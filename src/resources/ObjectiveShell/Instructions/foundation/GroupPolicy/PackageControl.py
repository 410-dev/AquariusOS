import os

from oscore import libreg as reg

# Command
# GroupPolicy/PackageControl <Protection/Blacklist> <Add/Remove/Get/List> [package_name (if applicable)]

def help(session) -> str:
    return "Usage: GroupPolicy/PackageControl <Protection/Blacklist> <Add/Remove/Get/List> [package_name]\nManages package protection and blacklisting policies."

# Return input string as bool
def main(session, section: str, action: str, package_name: str = None):

    # This requires root privileges.
    if os.geteuid() != 0:
        return 1, "This command requires root privileges."


    # For each actions:
    if section == "Protection":
        section = "ProtectedPackages"
    elif section == "Blacklist":
        section = "BlacklistedPackages"
    else:
        return 1, "Invalid section. Use 'Protection' or 'Blacklist'."

    # Check if action is valid
    if action not in ["Add", "Remove", "Get", "List"]:
        return 1, "Invalid action. Use 'Add', 'Remove', 'Get', or 'List'."

    # Check if package name is provided when needed
    if action in ["Add", "Remove", "Get"] and not package_name:
        return 1, "Package name is required for 'Add', 'Remove', and 'Get' actions."

    path = f"HKEY_LOCAL_MACHINE/SOFTWARE/Policies/{section}"

    if action == "List":
        # List all packages in the section
        packages = reg.read(path, {})

        # Format output
        output = "\n".join([f"{pkg}" for pkg, value in packages.items()])

        # Print output
        print(output)

        return 0, output

    elif action == "Add":
        # Add package to the section
        reg.write("root", f"{path}/{package_name}", 1)
        return 0, f"Package '{package_name}' added to {section}."

    elif action == "Remove":
        # Remove package from the section
        reg.delete(f"{path}/{package_name}")
        return 0, f"Package '{package_name}' removed from {section}."

    elif action == "Get":
        # Get package status
        status = reg.read(f"{path}/{package_name}", 0)
        return 0, f"Package '{package_name}' status in {section}: {status}."

    return 1, "Unknown error."