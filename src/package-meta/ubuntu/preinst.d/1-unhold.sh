#!/bin/sh
set -e

# Define the package name explicitly or use dpkg variable
PKG_NAME="$DPKG_MAINTSCRIPT_PACKAGE"

case "$1" in
    upgrade)
        # We are upgrading FROM an old version TO a new version.
        # We should unhold the package to allow the transition to complete cleanly.

        if command -v apt-mark >/dev/null 2>&1; then
            echo "Preparing for upgrade: Unholding '$PKG_NAME'..."
            apt-mark unhold "$PKG_NAME"
        fi
        ;;

    install)
        # First time install. No hold exists yet, so nothing to do.
        ;;

    abort-upgrade)
        # If the upgrade fails and we roll back, we might want to ensure
        # the hold is re-applied, but usually the old postinst handles state.
        ;;

    *)
        echo "preinst called with unknown argument \`$1'" >&2
        exit 1
        ;;
esac
