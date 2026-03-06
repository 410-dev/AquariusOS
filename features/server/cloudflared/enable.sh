#!/bin/bash

# Get Ubuntu codename
. /etc/os-release
UBUNTU_CODENAME_LOWER=$(echo "$UBUNTU_CODENAME" | tr '[:upper:]' '[:lower:]')

# Install cloudflared
set -e
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared ${UBUNTU_CODENAME_LOWER} main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update
sudo apt install cloudflared -y
set +e
