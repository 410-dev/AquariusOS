#!/bin/bash

# Add deprecation notice
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ W A R N I N G ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo "The git cloned backend support for Grub Btrfs Support is deprecated."
echo "Option for git clone backend will be removed in future versions."
echo "To enable snapshot feature, enable 'me.hysong.SnapshotSupport' feature instead."
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ W A R N I N G ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
echo ""

# Check for argument starting with "--backend="
BACKEND=""
for arg in "$@"; do
    if [[ $arg == --backend=* ]]; then
        BACKEND="${arg#--backend=}"
    fi
done

# If backend is empty, show interactive message to select the backend
if [[ -z "$BACKEND" ]]; then
    echo "Select the backend for Grub Btrfs Support:"
    echo "1) GRUB"
    echo "2) Git-Obtain"
    read -p "Enter choice [1-2]: " choice
    case $choice in
        1) BACKEND="grub" ;;
        2) BACKEND="git" ;;
        *) echo "Invalid choice. Exiting."; exit 1 ;;
    esac
fi

# Check option
if [[ "$BACKEND" != "grub" && "$BACKEND" != "git" ]]; then
    echo "Error: Invalid backend option '$BACKEND'. Use 'grub' or 'git'."
    exit 1
fi

# If git, perform the following installation
if [[ "$BACKEND" == "git" ]]; then
    set -e

    echo "Installing Grub Btrfs Support using git backend..."
    cd /tmp
    apt update
    apt install build-essential git inotify-tools btrfs-progs -y
    git clone https://github.com/Antynea/grub-btrfs.git
    cd grub-btrfs
    make install
    systemctl enable --now grub-btrfsd
    update-grub
    set +e

# If grub, just enable the module
else
    echo "Enabling Grub Btrfs Support using GRUB backend..."
    grub-install --modules=btrfs
    exit $?
fi