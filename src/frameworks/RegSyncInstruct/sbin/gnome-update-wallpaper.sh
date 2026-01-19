#!/bin/bash

gsettings set org.gnome.desktop.background picture-uri "file:///opt/aqua/sys/graphics/$1/background/light.png"
gsettings set org.gnome.desktop.background picture-uri-dark "file:///opt/aqua/sys/graphics/$1/background/dark.png"
gsettings set org.gnome.desktop.screensaver picture-uri "file:///opt/aqua/sys/graphics/$1/lockscreen/dark.png"

exit 0
