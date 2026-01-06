#!/bin/bash

# Options:
# --iterations N : Number of overwrite iterations (default: 1)
# --type [random/zero] : Type of overwrite (default: random)
# Default values
#    files as list of files to securely delete

# Run python code
python3 /opt/aqua/lib/python/security/zerofill.py "$@"
