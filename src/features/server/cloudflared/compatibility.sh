#!/bin/bash

if [[ -z "$(which curl)" ]]; then
    echo "curl is required to install cloudflared."
    exit 1
fi


# Check if repository for current version is available
. /etc/os-release
UBUNTU_CODENAME_LOWER=$(echo "$UBUNTU_CODENAME" | tr '[:upper:]' '[:lower:]')
url="https://pkg.cloudflare.com/cloudflared/dists/${UBUNTU_CODENAME_LOWER}/main/binary-amd64/Packages"
if ! curl -fsSL --head "$url" | grep -q "200"; then
    echo "Error: cloudflared is not available for Ubuntu ${UBUNTU_CODENAME_LOWER}."
    exit 1
fi
