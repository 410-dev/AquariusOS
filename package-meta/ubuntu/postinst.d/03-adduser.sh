#!/bin/bash

if ! is_marked "AquariusOSSetupDone.UserRole.var" ; then
    if ! getent group aquariusosusers >/dev/null; then
        addgroup --system --gid 1320 aquariusosusers
    fi
    if ! getent group vfsusers >/dev/null; then
        addgroup --system --gid 1321 vfsusers # For VFS write access - This is automatically added by hook in /etc/shadow-maint/useradd-post.d/01aquariusosgroups
    fi
    if [[ -z "$(cat /etc/passwd | grep "aquariusos:" | grep "/home/aquariusos")" ]]; then
        sudo useradd -r -s /bin/false aquariusos
    fi
    mark "AquariusOSSetupDone.UserRole.var"
else
    echo "Marked as setup done. Skipping..."
fi
