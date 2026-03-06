#!/bin/bash

# Uninstall cloudflared
set -e
sudo apt remove --purge cloudflared -y
sudo rm -f /etc/apt/sources.list.d/cloudflared.list
sudo rm -f /usr/share/keyrings/cloudflare-main.gpg
sudo apt update
set +e
