#!/bin/bash


# Ask for network model
# 1. Manual config
# 2. Cloudflared
# 3. Tailscale

usrInput=""
while true; do
    echo "Select the network model for Domain Controller:"
    echo "1) Manual configuration"
    echo "2) Cloudflared"
    echo "3) Tailscale"
    read -rp "Enter choice [1-3]: " usrInput
    case $usrInput in
        1) NETWORK_MODEL="manual"; break ;;
        2) NETWORK_MODEL="cloudflared"; break ;;
        3) NETWORK_MODEL="tailscale"; break ;;
        *) echo "Invalid choice. Please enter 1, 2, or 3." ;;
    esac
done

# Run network model setup scripts
case $NETWORK_MODEL in
    manual)
        echo "You have selected Manual configuration. Please ensure you configure the network settings manually after setup."
        ;;
    cloudflared)
        echo "Setting up Cloudflared for Domain Controller..."
        /opt/aqua/sys/sbin/feature.sh enable cloudflared
        if [[ $? -ne 0 ]]; then
            echo "Error: Failed to enable Cloudflared feature."
            exit 1
        fi
        ;;
    tailscale)
        echo "Setting up Tailscale for Domain Controller..."
        /opt/aqua/sys/sbin/feature.sh enable tailscale
        if [[ $? -ne 0 ]]; then
            echo "Error: Failed to enable Tailscale feature."
            exit 1
        fi
        ;;
esac