#!/bin/bash

source {{SYS_SHELLLIBS}}/guarding.shx


# Emulate $DISPLAY for postinst script - as DBUS fails without it, and we need it to show the notification.
if [[ -z "$DISPLAY" ]]; then
    export DISPLAY=:0
fi
