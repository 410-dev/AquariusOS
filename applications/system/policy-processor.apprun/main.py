import json
import sys

from oscore import libreg as reg

import os
import subprocess

def main():
    # Get sys args
    args = sys.argv[1:]

    # Usage
    #   policy-processor <input-json>

    # Check file exists
    if len(args) != 1:
        print("Usage: policy-processor <input-json>")
        sys.exit(1)

    if not os.path.isfile(args[0]):
        print(f"File not found: {args[0]}")
        sys.exit(1)

    # Read input JSON
    # Check if file is wrongly formatted
    try:
        with open(args[0], "r") as f:
            input_data = json.load(f)
    except Exception as e:
        print(f"Failed to read input JSON: {e}")
        sys.exit(1)

    # Get elements: MaintenanceScript
    maintenance_scripts: dict[str, list[list[str]]] = input_data.get("MaintenanceScript", {})
    preinst: list[list[str]] = maintenance_scripts.get("PreInst", [])
    postinst: list[list[str]] = maintenance_scripts.get("PostInst", [])

    # Print maintenance scripts
    for script in preinst:
        print(f"Run            {script}")

    # Get elements: Policy Procedures
    policy_procedures: list[dict] = input_data.get("PolicyProcedures", [])
    process_result = procedure_to_human_readable(policy_procedures)

    print(process_result)

    # Print post install scripts
    for script in postinst:
        print(f"Run            {script}")

    # Ask for continue, unless has --no-interaction flag
    if "--no-interaction" not in args:
        res = input("Type 'yes' to apply.")
        if res.lower() != "yes":
            print("Aborted by user.")
            sys.exit(0)

    #############################
    ###### ACTUAL APPLYING ######
    #############################

    # Verbose output
    print("Applying policy...")

    len_steps: int = len(policy_procedures)
    for idx, script in enumerate(preinst):
        print(f"[1/3 (PreInst) ] [{idx+1}/{len_steps}] Running: {script}")
        try:
            subprocess.run(script, check=True)
        except Exception as e:
            print(f"Failed to run pre-install script {script}: {e}")
            sys.exit(1)

    len_steps: int = len(policy_procedures)
    action_to_str_map: dict[str, str] = {
        "package-add": "Add Package",
        "package-blacklist": "Blacklist Package",
        "registry-update": "Registry Update",
        "file-operation": "File Operation"
    }
    for idx, step in enumerate(policy_procedures):
        print(f"[2/3 (PolicyProc)] [{idx+1}/{len_steps}] Applying step: {action_to_str_map.get(step.get('Type', ''), 'Unknown')}")

        if step.get("Type", "") == "package-add":
            packages: list[dict] = step.get("Packages", [])
            if not action_package_add(packages):
                print("Failed to add packages.")
                sys.exit(1)

        elif step.get("Type", "") == "package-blacklist":
            print("Package blacklisting is not implemented.")
            # Not implemented
            pass

        elif step.get("Type", "") == "registry-update":
            print("Registry update is not implemented.")
            # Not implemented
            pass

        elif step.get("Type", "") == "file-operation":
            print("File operations are not implemented.")
            # Not implemented
            pass

    len_steps: int = len(postinst)
    for idx, script in enumerate(postinst):
        print(f"[3/3 (PostInst)] [{idx+1}/{len_steps}] Running: {script}")
        try:
            subprocess.run(script, check=True)
        except Exception as e:
            print(f"Failed to run post-install script {script}: {e}")
            sys.exit(1)

    print("Policy applied successfully.")

def action_blacklist_package(packages: list[dict]) -> bool:

    reg_path: str = "HKEY_LOCAL_MACHINE/SOFTWARE/Policies/BlacklistedPackages"


def action_package_add(packages: list[dict]) -> bool:

    reg_path: str = "HKEY_LOCAL_MACHINE/SOFTWARE/Policies/ProtectedPackages"

    apt_unhold: list[str] = ["apt-mark", "unhold"]
    apt_params: list[str] = ["apt", "reinstall", "-y"]
    holds: list[str] = ["apt-mark", "hold"]
    mod_lock: list[str] = []
    for pkg in packages:
        pkg_id, pkg_version, hold, mod_lock = decode_package_info(pkg)
        apt_unhold.append(pkg_id)
        if hold: holds.append(pkg_id)
        if mod_lock: mod_lock.append(pkg_id)

        if pkg_version == "latest":
            apt_params.append(pkg_id)
        else:
            apt_params.append(f"{pkg_id}={pkg_version}")

        print(f"Adding package: {pkg_id}, version: {pkg_version}, hold: {hold}")

    # Unlock the modify lock from registry
    try:
        for pkg_id in mod_lock:
            reg_path = f"{reg_path}/{pkg_id}"
            reg.delete(reg_path)
            print(f"Removed modify lock for package: {pkg_id}")

    except Exception as e:
        print(f"Error while unlocking packages: {e}\nAssuming successful..")

    try:
        subprocess.run(apt_unhold, check=True) # Unhold first
        subprocess.run(apt_params, check=True) # Install packages
        if len(holds) > 2:
            subprocess.run(holds, check=True)  # Re-hold packages if needed
    except Exception as e:
        print(f"Failed to add packages: {e}")
        return False

    # Lock the modify lock in registry
    try:
        for pkg_id in mod_lock:
            reg_path = f"{reg_path}/{pkg_id}"
            reg.write(reg_path, "ModifyLock", 1)
            print(f"Set modify lock for package: {pkg_id}")
    except Exception as e:
        print(f"Error while setting modify locks: {e}\nAssuming successful..")

    return True


def decode_package_info(package_info: dict | str) -> tuple[str, str, bool, bool]:
    if isinstance(package_info, str):
        return package_info, "latest", False, False

    elif isinstance(package_info, dict):
        pkg_id = package_info["Id"]
        pkg_version = package_info.get("Version", "latest")
        hold = package_info.get("Hold", False)
        mod_lock = package_info.get("ModifyLock", False)
        return pkg_id, pkg_version, hold, mod_lock

    else:
        raise ValueError("Invalid package info format")

def procedure_to_human_readable(procedure: list[dict]) -> str:
    lines: list[str] = []
    for step in procedure:
        if step.get("Type", "") == "package-add":
            packages: list[dict] = step.get("Packages", [])
            for pkg in packages:
                pkg_id, pkg_version, hold = decode_package_info(pkg)
                hold_str = " (hold)" if hold else ""
                lines.append(f"Add Package: {pkg_id} Version: {pkg_version}{hold_str}")

        elif step.get("Type", "") == "package-blacklist":
            packages: list[str] = step.get("Packages", [])
            for pkg_id in packages:
                pkg_id, _, _ = decode_package_info(pkg_id)
                lines.append(f"Blacklist Package: {pkg_id}")

        elif step.get("Type", "") == "registry-update":
            values: dict[str, dict] = step.get("Values", {})
            for reg_path, val_info in values.items():
                val_type = val_info.get("type", "Unknown")
                val_data = val_info.get("value", "Unknown")
                lines.append(f"Registry Update: {reg_path} Type: {val_type} Data: {val_data}")

        elif step.get("Type", "") == "file-operation":
            operations: list[dict] = step.get("Actions", [])
            for op in operations:
                action = op.get("Action", "Unknown")

                # Actions are in any of
                # copy, delete, move, create, replace, chmod, chown, symlink
                if action not in ["copy", "delete", "move", "create", "replace", "chmod", "chown", "symlink"]:
                    action = "Unknown"

                if action == "Unknown":
                    raise ValueError(f"Invalid file operation action: {action}")

                if action == "copy":
                    src = op.get("Source", "Unknown")
                    dest = op.get("Destination", "Unknown")
                    lines.append(f"Copy           '{src}' -> '{dest}'")
                elif action == "delete":
                    target = op.get("Target", "Unknown")
                    lines.append(f"Delete         '{target}'")
                elif action == "move":
                    src = op.get("Source", "Unknown")
                    dest = op.get("Destination", "Unknown")
                    lines.append(f"Move           '{src}' -> '{dest}'")
                elif action == "create":
                    target = op.get("Target", "Unknown")
                    content = op.get("Content", "Unknown")
                    lines.append(f"Write          '{content}' >>> '{target}'")
                elif action == "replace":
                    target = op.get("Target", "Unknown")
                    search = op.get("Search", "Unknown")
                    replace = op.get("Replace", "Unknown")
                    limit = op.get("Limit", 0)
                    reverse = op.get("Reverse", False)
                    lines.append(f"Replace        '{target}' line '{search}' with '{replace}' Limit: {limit} Reverse: {reverse}")
                elif action == "chmod":
                    target = op.get("Target", "Unknown")
                    mode = op.get("Mode", "Unknown")
                    lines.append(f"Change mod     to {mode} for {target}")
                elif action == "chown":
                    target = op.get("Target", "Unknown")
                    owner = op.get("Owner", "Unknown")
                    lines.append(f"Change owner   of {target} to {owner}")
                elif action == "symlink":
                    src = op.get("Source", "Unknown")
                    link = op.get("Link", "Unknown")
                    lines.append(f"Create symlink '{link}' -> '{src}'")
                else:
                    raise ValueError(f"Invalid file operation action: {action}")
        else:
            raise ValueError(f"Invalid procedure step type: {step.get('Type', '')}")

    return "\n".join(lines)

if __name__ == "__main__":
    # TODO Check root privileges
    main()
