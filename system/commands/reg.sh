#!/bin/bash
# Wrapper script to call libreg.py
export PYTHONPYCACHEPREFIX=/tmp
python3 {{SYS_PYLIBS}}/oscore/libreg.py "$@"
