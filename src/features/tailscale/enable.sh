#!/bin/bash

# Get Ubuntu codename
. /etc/os-release
UBUNTU_CODENAME_LOWER=$(echo "$UBUNTU_CODENAME" | tr '[:upper:]' '[:lower:]')

# Install tailscale
set -e
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/"${UBUNTU_CODENAME_LOWER}".noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/"${UBUNTU_CODENAME_LOWER}".tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list
sudo apt update
sudo apt install tailscale -y
set +e

