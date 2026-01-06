#!/bin/bash

# Check if current machine is exclusively x64 (amd64 only)
if lscpu | grep -q "Architecture: *x86_64" && ! lscpu | grep -q "Architecture: *i[3-6]86"; then
    exit 0
else
    echo "Error: This feature is only compatible with x64 (amd64) architecture."
    exit 1
fi
