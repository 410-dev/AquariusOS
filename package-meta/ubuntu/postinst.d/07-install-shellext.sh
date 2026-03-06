#!/bin/bash

if ! is_marked "AquariusOSSetupDone.ShellExtensions.var" ; then
    # Install system-wide hook for bash and POSIX shells
    echo "source /etc/profile.d/aqua.sh" >> /etc/bash.bashrc
    mark "AquariusOSSetupDone.ShellExtensions.var"
else
    echo "Marked as setup done. Skipping..."
fi