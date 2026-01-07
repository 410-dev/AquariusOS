#!/bin/bash

if ! is_marked "AquariusOSSetupDone.ServicesEnabled.var" ; then
    # Search /opt/aquariusos/sys/services/ for .service files and enable them
#            find /opt/aquariusos/sys/services/ -name '*.service' -exec systemctl enable {} \;
    # Code above is deprecated!
    # Using /opt/aquariusos/sys/sbin/reg.sh to see if service is disabled. If not disabled, enable it.
    service_files=$(find /opt/aquariusos/sys/services/ -name '*.service')
    for service_file in $service_files; do
        service_name=$(basename "$service_file")
        result=$(/opt/aquariusos/sys/sbin/reg.sh root read HKEY_LOCAL_MACHINE/SYSTEM/Services/"$service_name"/Enabled 2>/dev/null || echo "1")
        if [[ "$result" != "0" ]]; then
            systemctl enable "$service_file"
        else
            echo "Service $service_name is marked as disabled. Skipping enable..."
        fi
    done
    mark "AquariusOSSetupDone.ServicesEnabled.var"
else
    echo "Marked as setup done. Skipping..."
fi