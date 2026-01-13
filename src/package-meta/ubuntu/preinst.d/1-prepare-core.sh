#!/bin/bash

# Check compatibility.
# Host requirement: Ubuntu 24.04 LTS ONLY
# User may bypass version checking by creating a file at /var/noinstfs/aquariusos/root.d/registry/SYSTEM/Installer/Flags/BypassHostOSCheck.bool.rv with content "1"
BYPASS_CHECK="0"
if [[ -f /var/noinstfs/aquariusos/root.d/registry/SYSTEM/Installer/Flags/BypassHostOSCheck.bool.rv ]]; then
  BYPASS_CHECK=$(cat /var/noinstfs/aquariusos/root.d/registry/SYSTEM/Installer/Flags/BypassHostOSCheck.bool.rv | tr -d ' \t\n\r')
fi

if [ "$BYPASS_CHECK" != "1" ]; then
  if [ ! -f /etc/os-release ] || ! grep -q "VERSION_ID=\"24.04" /etc/os-release; then
    echo "This package is intended for Ubuntu 24.04 LTS only. Aborting installation." >&2
    exit 1
  fi
fi


# Perform dpkg divert for existing logo file at
# /usr/share/icons/Yaru/scalable/places/start-here-symbolic.svg

DIVERT_PATH="/usr/share/icons/Yaru/scalable/places/start-here-symbolic.svg"
dpkg-divert --package="$DPKG_MAINTSCRIPT_PACKAGE" --add --rename --divert "$DIVERT_PATH".diverted "$DIVERT_PATH"
DIVERT_PATH="/etc/os-release"
dpkg-divert --package="$DPKG_MAINTSCRIPT_PACKAGE" --add --rename --divert "$DIVERT_PATH".diverted "$DIVERT_PATH"
