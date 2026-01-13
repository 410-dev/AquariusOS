#!/bin/bash

# Check compatibility.
# Host requirement: Ubuntu 24.04 LTS ONLY
# User may bypass version checking by creating a file at /var/noinstfs/aqua/root.d/registry/SYSTEM/Installer/Flags/BypassHostOSCheck.bool.rv with content "1"
BYPASS_CHECK="0"
if [[ -f /var/noinstfs/aqua/root.d/registry/SYSTEM/Installer/Flags/BypassHostOSCheck.bool.rv ]]; then
  BYPASS_CHECK=$(cat /var/noinstfs/aqua/root.d/registry/SYSTEM/Installer/Flags/BypassHostOSCheck.bool.rv | tr -d ' \t\n\r')
fi

if [ "$BYPASS_CHECK" != "1" ]; then
  if [ ! -f /etc/os-release ] || [ -z "$(grep "24.04" /etc/os-release)" ]; then
    echo "This package is intended for Ubuntu 24.04 LTS only. Aborting installation." >&2
    exit 1
  fi
fi


