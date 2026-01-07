#!/bin/bash

if [ -L /opt/aquariusos/homes/root/dotlocal ] || [ -e /opt/aquariusos/homes/root/dotlocal ]; then
    echo "Link or file already exists. Skipping..."
else
    ln -s /root/.local /opt/aquariusos/homes/root/dotlocal
fi
