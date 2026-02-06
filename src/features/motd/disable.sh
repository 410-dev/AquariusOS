#!/bin/bash

set -e

# Delete files
file /etc/xdg/autostart/me.hysong.aqua.motd.desktop 2>/dev/null && rm -f /etc/xdg/autostart/me.hysong.aqua.motd.desktop
file /opt/aqua/sbin/motd.py 2>/dev/null && rm -f /opt/aqua/sbin/motd.py

exit 0
