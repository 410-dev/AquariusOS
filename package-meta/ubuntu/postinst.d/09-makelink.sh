#!/bin/bash

if [ -L {{AQUAROOT}}/homes/root/dotlocal ] || [ -e {{AQUAROOT}}/homes/root/dotlocal ]; then
    echo "Link or file already exists. Skipping..."
else
    ln -sf /root/.local {{AQUAROOT}}/homes/root/dotlocal
fi
