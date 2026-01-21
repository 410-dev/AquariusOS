#!/bin/bash

theme_bundle="/opt/aqua/sys/graphics/$1/"
if [[ -f "$theme_bundle/background/light.png" ]] && [[ -f "$theme_bundle/background/dark.png" ]] && [[ -f "$theme_bundle/lockscreen/dark.png" ]]; then
    gsettings set org.gnome.desktop.background picture-uri "file:///opt/aqua/sys/graphics/$1/background/light.png"
    gsettings set org.gnome.desktop.background picture-uri-dark "file:///opt/aqua/sys/graphics/$1/background/dark.png"
    gsettings set org.gnome.desktop.screensaver picture-uri "file:///opt/aqua/sys/graphics/$1/lockscreen/dark.png"
elif [[ -f "$theme_bundle/default.png" ]]; then
    gsettings set org.gnome.desktop.background picture-uri "file:///opt/aqua/sys/graphics/$1/default.png"
    gsettings set org.gnome.desktop.background picture-uri-dark "file:///opt/aqua/sys/graphics/$1/default.png"
    gsettings set org.gnome.desktop.screensaver picture-uri "file:///opt/aqua/sys/graphics/$1/default.png"
else
    echo "Theme bundle $1 is missing required images."
    exit 1
fi

exit 0
