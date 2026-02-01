#!/bin/bash

# Wrapper script to specifically handle for:
# install, remove, reinstall, upgrade operations with dpkg

set -e

# Check policy here


exec /usr/bin/dpkg.distrib "$@"