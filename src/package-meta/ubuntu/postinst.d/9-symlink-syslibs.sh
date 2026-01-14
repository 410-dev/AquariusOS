#!/bin/bash

# Iterate through all files and directories in /opt/aqua/sys/libs
for item in /opt/aqua/sys/libs/python/*; do
    # Get the base name of the item
    base_item=$(basename "$item")

    # Create a symbolic link in /usr/lib/python3/dist-packages/
    ln -sf "/opt/aqua/sys/libs/python/$base_item" "/usr/lib/python3/dist-packages/$base_item"
done
