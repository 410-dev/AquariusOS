#!/bin/bash

# Wrapper script to specifically handle for:
# install, remove, reinstall, upgrade operations with dpkg

set -e

# Block based on pattern
if [[ ! -z "$(echo "$@" | grep \\--remove)" ]] ||                 # Removal
    [[ ! -z "$(echo "$@" | grep \\-r)" ]] ||                      # Removal
    [[ ! -z "$(echo "$@" | grep \\--purge)" ]] ||                 # Purge
    [[ ! -z "$(echo "$@" | grep \\--install)" ]] ||               # Install
    [[ ! -z "$(echo "$@" | grep \\-i)" ]] ||                      # Install
    [[ ! -z "$(echo "$@" | grep \\--reinstall)" ]] ||             # Reinstall
    [[ ! -z "$(echo "$@" | grep \\--upgrade)" ]] ||               # Upgrade
    [[ ! -z "$(echo "$@" | grep \\-U)" ]] ||                      # Upgrade
    [[ ! -z "$(echo "$@" | grep \\--unpack)" ]] ||                # apt install?
    [[ ! -z "$(echo "$@" | grep \\--auto-deconfigure)" ]]; then   # apt install?

    echo "Checking system policy for dpkg operation..."
    echo "Packager called: dpkg $@"

    # Read registry
    # Not-removables:    HKEY_LOCAL_MACHINE/SOFTWARE/Policies/ProtectedPackages/<package>.dword.rv = 1
    # Install blacklist: HKEY_LOCAL_MACHINE/SOFTWARE/Policies/BlacklistedPackages/<package>.dword.rv = 1

    # Trigger python script to handle the logic
    python3 /opt/aqua/sys/frameworks/GroupPolicyPropagationFramework/dpkg-wrapper/dpkgCmdParser.py "$@"

    # Check exit code
    if [ $? -ne 0 ]; then
        echo "Operation not permitted by system policy."
        exit 1
    fi
fi

exec /usr/bin/dpkg.distrib "$@"