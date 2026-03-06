#!/bin/bash

# Read /opt/aqua/boot/preboot/conf/version
PREBOOT_VERSION="$(cat /opt/aqua/boot/preboot/conf/version 2>/dev/null)"
if [[ -z "$PREBOOT_VERSION" ]]; then
    echo "No preboot version set. Exiting."
    exit 0
fi

# Launch /opt/aqua/boot/preboot/"$PREBOOT_VERSION"/preboot.sh
PREBOOT_SCRIPT="/opt/aqua/boot/preboot/${PREBOOT_VERSION}/preboot.sh"
if [[ -f "$PREBOOT_SCRIPT" ]]; then
    "$PREBOOT_SCRIPT"
    EXIT_CODE=$?
    if [[ $EXIT_CODE -ne 0 ]]; then
        echo "Preboot script $PREBOOT_SCRIPT exited with code $EXIT_CODE. Exiting."
        exit $EXIT_CODE
    fi
else
    echo "Preboot script $PREBOOT_SCRIPT not found. Exiting."
    exit 1
fi
