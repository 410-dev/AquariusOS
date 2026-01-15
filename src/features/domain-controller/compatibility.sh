#!/bin/bash

# Check Ubuntu Pro enablement
if ! ubuntu-advantage status | grep -q "Enabled"; then
    echo "Error: Ubuntu Pro is not enabled on this system."
    exit 1
fi

exit 0
