#!/bin/bash

set -e

case "$1" in
    configure)
        # 1. Identify the package name automatically
        PKG_NAME="$DPKG_MAINTSCRIPT_PACKAGE"

        # 2. Check if apt-mark is available (it is part of the apt package)
        if command -v apt-mark >/dev/null 2>&1; then
            echo "Locking package '$PKG_NAME' to prevent accidental removal or upgrade..."

            # 3. Apply the hold
            apt-mark hold "$PKG_NAME"

            # Verify the hold was successful in the logs
            if [ $? -eq 0 ]; then
                echo "Package '$PKG_NAME' is now on hold."
            else
                echo "WARNING: Failed to place '$PKG_NAME' on hold."
            fi
        else
            echo "WARNING: apt-mark command not found. Package could not be locked."
        fi
        ;;

    abort-upgrade|abort-remove|abort-deconfigure)
        ;;

    *)
        echo "postinst called with unknown argument \`$1'" >&2
        exit 1
        ;;
esac
