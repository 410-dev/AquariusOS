#!/bin/bash

graphic_code="new-york"
if mark_equals "AquariusOSSetupDone.GraphicCode.var" "$graphic_code" ; then
    echo "Marked as setup done for graphic code $graphic_code. Skipping..."
else
    for bus in /run/user/*/bus; do
        uid=$(basename "$(dirname "$bus")")
        user=$(getent passwd "$uid" | cut -d: -f1)

        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.background picture-uri "file:///opt/aquariusos/sys/graphics/$graphic_code/background/light.jpg"
        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.background picture-uri-dark "file:///opt/aquariusos/sys/graphics/$graphic_code/background/dark.jpg"
        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.screensaver picture-uri "file:///opt/aquariusos/sys/graphics/$graphic_code/lockscreen/dark.jpg"
        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.interface gtk-theme 'Yaru-blue'
        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.interface icon-theme 'Yaru-blue'
        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'

    done

    gsettings set org.gnome.desktop.background picture-uri "file:///opt/aquariusos/sys/graphics/$graphic_code/background/light.jpg"
    gsettings set org.gnome.desktop.background picture-uri-dark "file:///opt/aquariusos/sys/graphics/$graphic_code/background/dark.jpg"
    gsettings set org.gnome.desktop.screensaver picture-uri "file:///opt/aquariusos/sys/graphics/$graphic_code/lockscreen/dark.jpg"
    gsettings set org.gnome.desktop.interface gtk-theme 'Yaru-blue'
    gsettings set org.gnome.desktop.interface icon-theme 'Yaru-blue'
    gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'

    dconf update

    mark "AquariusOSSetupDone.GraphicCode.var" "$graphic_code"
fi
