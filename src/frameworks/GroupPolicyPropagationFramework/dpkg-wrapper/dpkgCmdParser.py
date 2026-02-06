# Read registry
# Not-removables:    HKEY_LOCAL_MACHINE/SOFTWARE/Policies/ProtectedPackages/<package>.dword.rv = 1
# Install blacklist: HKEY_LOCAL_MACHINE/SOFTWARE/Policies/BlacklistedPackages/<package>.dword.rv = 1

import sys
import subprocess
import os

# Include /opt/aqua/sys/lib/python
sys.path.insert(0, "/opt/aqua/sys/lib/python")

from oscore import libreg as reg


def _chk_registry_protect_mode(package_name: str) -> bool:
    key_path = f"SOFTWARE/Policies/ProtectedPackages/{package_name}"
    protected = reg.read(key_path, 0)
    if protected == 1:
        return False  # Cannot remove protected package
    return True


def _chk_registry_install_mode(package_name: str) -> bool:
    key_path = f"SOFTWARE/Policies/BlacklistedPackages/{package_name}"
    protected = reg.read(key_path, 0)
    if protected == 1:
        return False  # Cannot install blacklisted package
    return _chk_registry_protect_mode(package_name)


def _local_id(raw_args: list[str], install_mode: bool) -> int:
    # Parse package names
    # This usually looks like this:
    # --status-fd 21 --no-triggers --unpack --auto-deconfigure libyyjson0 fastfetch
    # Parsing will directly read the package names from the arguments.

    for element in raw_args:

        # Package name
        # Note: This does not guarantee the element is a valid package name.
        if not element.startswith("-"):
            package_name = element

            # Note: package name contains : architecture suffix
            if ":" in package_name:
                package_name = package_name.split(":", 1)[0]

            if install_mode:
                if not _chk_registry_install_mode(package_name):
                    return 1  # Block installation
            else:
                if not _chk_registry_protect_mode(package_name):
                    return 1  # Block removal

        # Not package name
        else:
            pass

    return 0 # Allow operation


def _file_path(raw_args: list[str], install_mode: bool) -> int:
    # Parse package names
    # This usually looks like this:
    # --status-fd 21 --no-triggers --unpack --auto-deconfigure /var/cache/apt/archives/libyyjson0_0.12.0+ds-1_amd64.deb /var/cache/apt/archives/fastfetch_2.57.1+dfsg-1_amd64.deb
    # or if alot, then looks like this:
    # --status-fd 21 --no-triggers --unpack --auto-deconfigure --recursive <path>
    # Parsing will execute 'dpkg-deb -f <filename.deb> Package' in subprocess to fetch the package name.

    if "--recursive" in raw_args:
        recurse_index = raw_args.index("--recursive")
        if recurse_index + 1 < len(raw_args):
            dir_path = raw_args[recurse_index + 1]
            if os.path.isdir(dir_path):
                for root, _, files in os.walk(dir_path):
                    for file in files:
                        if file.endswith(".deb"):
                            deb_path = os.path.join(root, file)
                            raw_args.append(deb_path)

    for element in raw_args:

        # Deb file
        if element.endswith(".deb") and os.path.isfile(element):
            try:
                result = subprocess.run(
                    ["/usr/bin/dpkg-deb", "-f", element, "Package"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                package_name = result.stdout.strip()
                if package_name:
                    if install_mode:
                        if not _chk_registry_install_mode(package_name):
                            return 1  # Block installation
                    else:
                        if not _chk_registry_protect_mode(package_name):
                            return 1  # Block removal
            except subprocess.CalledProcessError as e:
                print(f"Error fetching package name from {element}: {e}", file=sys.stderr)
                return 1

        # Not deb file
        else:
            pass

    return 0 # Allow operation


def main() -> int:
    args: list[str] = sys.argv[1:]
    using_local_id = any(flag in args for flag in [
        "--remove",
        "-r",
        "--purge",
        "--uninstall",
        "--configure",
        "--upgrade",
        "-U"])
    is_removal = any(flag in args for flag in ["--remove", "--purge", "-r", "--uninstall"])


    return _local_id(args, not is_removal) if using_local_id else _file_path(args, not is_removal)

if __name__ == "__main__":
    import sys
    sys.exit(main())