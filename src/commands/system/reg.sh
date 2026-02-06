#!/bin/bash
# Wrapper script to call libreg.py
export PYTHONPYCACHEPREFIX=/tmp
python3 /opt/aqua/sys/lib/python/oscore/libreg.py "$@"
