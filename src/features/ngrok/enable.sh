#!/bin/bash

## Get Ubuntu codename
#. /etc/os-release
#UBUNTU_CODENAME_LOWER=$(echo "$UBUNTU_CODENAME" | tr '[:upper:]' '[:lower:]')
#


## Install ngrok
set -e
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com bookworm main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update
sudo apt install ngrok -y
set +e

# Check if parameter contains --no-interaction
if [[ ! -z $(echo "$@" | grep \\--no-interaction) ]]; then
    echo "User selected not to use interactive token configuration."
    exit 0
fi

# Trigger token config
echo -n "Enter your ngrok token: "
read token
ngrok config add-authtoken "$token"
if [[ "$?" == "0" ]]; then
    echo "Ngrok enablement was successful."
else
    echo "Ngrok failed to configure user token."
    echo "This is not critical."
    echo "Use 'ngrok config add-authtoken <token>' to configure."
fi
exit 0
