#!/bin/bash

# Make symbolic link to {{SYS_FRAMEWORKS}}/pyhttpd/cli.py
set -e
sudo ln -sf {{SYS_FRAMEWORKS}}/pyhttpd/cli.py /usr/local/bin/pyhttpd

# Enable pyhttpd service in {{SYS_FRAMEWORKS}}/pyhttpd/pyhttpd.service
sudo systemctl enable {{SYS_FRAMEWORKS}}/pyhttpd/pyhttpd.service
sudo systemctl start pyhttpd

# Finished
set +e