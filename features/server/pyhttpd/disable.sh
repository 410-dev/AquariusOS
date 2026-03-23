#!/bin/bash

# Remove symbolic link to {{SYS_FRAMEWORKS}}/pyhttpd/cli.py
set -e
sudo rm -f /usr/local/bin/pyhttpd

# Disable pyhttpd service
sudo systemctl stop pyhttpd
sudo systemctl disable pyhttpd

# Finished
set +e
