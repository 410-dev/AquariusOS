#!/bin/bash

if ! is_marked "AquariusOSSetupDone.PermissionsUpdated.var" ; then
    for u in $(getent group sudo | cut -d: -f4 | tr ',' ' '); do
        usermod -a -G aquariusosusers "$u"
    done
    install -d -m 775 -o root -g aquariusosusers /opt/aqua/appcache
    mark "AquariusOSSetupDone.PermissionsUpdated.var"
else
    echo "Marked as setup done. Skipping..."
fi
