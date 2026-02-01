#!/bin/bash

# Wrapper script to specifically handle for:
# install, remove, reinstall, upgrade operations with dpkg

set -e

# Block based on pattern
if [[ ! -z "$(echo "$@" | grep \\--remove)" ]] ||                # Removal
    [[ ! -z "$(echo "$@" | grep \\--unpack)" ]] ||               # Install?
    [[ ! -z "$(echo "$@" | grep \\--auto-deconfigure)" ]]; then  # Install?

    # Read registry
    # Not-removables:    HKEY_LOCAL_MACHINE/SOFTWARE/Policies/ProtectedPackages/<package>.dword.rv = 1
    # Install blacklist: HKEY_LOCAL_MACHINE/SOFTWARE/Policies/BlacklistedPackages/<package>.dword.rv = 1


    # On check triggered
    exit 100

fi

exec /usr/bin/dpkg.distrib "$@"