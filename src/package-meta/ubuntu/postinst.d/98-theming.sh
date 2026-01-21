#!/bin/bash

#graphic_code="{{{CODENAME}}}"
graphic_code="aqua-simple"
if mark_equals "AquariusOSSetupDone.GraphicCode.var" "$graphic_code" ; then
    echo "Marked as setup done for graphic code $graphic_code. Skipping..."
else
    theme_bundle="/opt/aqua/sys/graphics/$graphic_code/"
    for bus in /run/user/*/bus; do
        uid=$(basename "$(dirname "$bus")")
        user=$(getent passwd "$uid" | cut -d: -f1)

        if [[ -f "$theme_bundle/background/light.png" ]] && [[ -f "$theme_bundle/background/dark.png" ]] && [[ -f "$theme_bundle/lockscreen/dark.png" ]]; then
            sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.background picture-uri "file:///opt/aqua/sys/graphics/$graphic_code/background/light.png"
            sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.background picture-uri-dark "file:///opt/aqua/sys/graphics/$graphic_code/background/dark.png"
            sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.screensaver picture-uri "file:///opt/aqua/sys/graphics/$graphic_code/lockscreen/dark.png"
        elif [[ -f "$theme_bundle/default.png" ]]; then
            sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.background picture-uri "file:///opt/aqua/sys/graphics/$graphic_code/default.png"
            sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.background picture-uri-dark "file:///opt/aqua/sys/graphics/$graphic_code/default.png"
            sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.screensaver picture-uri "file:///opt/aqua/sys/graphics/$graphic_code/default.png"
        fi

#        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.background picture-uri "file:///opt/aqua/sys/graphics/$graphic_code/background/light.jpg"
#        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.background picture-uri-dark "file:///opt/aqua/sys/graphics/$graphic_code/background/dark.jpg"
#        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.screensaver picture-uri "file:///opt/aqua/sys/graphics/$graphic_code/lockscreen/dark.jpg"
        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.interface gtk-theme 'Yaru-blue'
        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.interface icon-theme 'Yaru-blue'
        sudo -u "$user" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'

    done

    if [[ -f "$theme_bundle/background/light.png" ]] && [[ -f "$theme_bundle/background/dark.png" ]] && [[ -f "$theme_bundle/lockscreen/dark.png" ]]; then
        gsettings set org.gnome.desktop.background picture-uri "file:///opt/aqua/sys/graphics/$graphic_code/background/light.png"
        gsettings set org.gnome.desktop.background picture-uri-dark "file:///opt/aqua/sys/graphics/$graphic_code/background/dark.png"
        gsettings set org.gnome.desktop.screensaver picture-uri "file:///opt/aqua/sys/graphics/$graphic_code/lockscreen/dark.png"
    elif [[ -f "$theme_bundle/default.png" ]]; then
        gsettings set org.gnome.desktop.background picture-uri "file:///opt/aqua/sys/graphics/$graphic_code/default.png"
        gsettings set org.gnome.desktop.background picture-uri-dark "file:///opt/aqua/sys/graphics/$graphic_code/default.png"
        gsettings set org.gnome.desktop.screensaver picture-uri "file:///opt/aqua/sys/graphics/$graphic_code/default.png"
    fi

#    gsettings set org.gnome.desktop.background picture-uri "file:///opt/aqua/sys/graphics/$graphic_code/background/light.jpg"
#    gsettings set org.gnome.desktop.background picture-uri-dark "file:///opt/aqua/sys/graphics/$graphic_code/background/dark.jpg"
#    gsettings set org.gnome.desktop.screensaver picture-uri "file:///opt/aqua/sys/graphics/$graphic_code/lockscreen/dark.jpg"
    gsettings set org.gnome.desktop.interface gtk-theme 'Yaru-blue'
    gsettings set org.gnome.desktop.interface icon-theme 'Yaru-blue'
    gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'

    dconf update

    mark "AquariusOSSetupDone.GraphicCode.var" "$graphic_code"
fi
