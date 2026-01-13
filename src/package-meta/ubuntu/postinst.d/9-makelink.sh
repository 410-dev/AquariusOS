#!/bin/bash

if [ -L /opt/aqua/homes/root/dotlocal ] || [ -e /opt/aqua/homes/root/dotlocal ]; then
    echo "Link or file already exists. Skipping..."
else
    ln -s /root/.local /opt/aqua/homes/root/dotlocal
fi
