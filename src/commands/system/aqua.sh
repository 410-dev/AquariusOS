#!/bin/bash

# Usage
#   aqua help - List all available commands
#   aqua upgrade

# Load manuals
ManualsPath=("/opt/aqua/sys/man" "/opt/aqua/man")

case "$1" in
    help|--help|-h)
        echo "AquariusOS Command Line Utility"
        echo ""
        echo "Available commands:"
        echo "  update                Try obtaining updates from AquariusOS OTA servers"
        echo "              --branch (Optional): Specify the update branch to use. Default is 'main'."
        echo "  upgrade               Upgrade AquariusOS system components"
        echo "              --hot-install (Optional): Perform a hot installation of the update packages (not recommended)."
        echo "  version               Show AquariusOS version information"
        echo "              --format (Optional): Specify output format, where available keys are:"
        echo "                   Build:            Build number of aqua"
        echo "                   Version:          Version of AquariusOS"
        echo "                   Codename:         Codename"
        echo "                   Type:             Type of build (Release / Experimental)"
        echo "                   StructureVersion: Structure version of AquariusOS"
        echo ""
        echo "Use 'aqua help [command]' to get more information about a specific command."
        exit 0
        ;;

    update)
        echo "Trying to obtain latest commit from AquariusOS OTA servers..."
        BRANCH="main"
        URL="https://github.com/410-dev/AquariusOS"
        shift
        while [[ "$#" -gt 0 ]]; do
            case "$1" in
                --branch)
                    BRANCH="$2"
                    shift 2
                    ;;
                *)
                    echo "Unknown option: $1"
                    exit 1
                    ;;
            esac
        done
        echo "Using branch: $BRANCH"
        echo "Cloning..."
        git clone --branch "$BRANCH" "$URL" /tmp/osaqua-update-temp --recursive
        if [[ $? -ne 0 ]]; then
            echo "ERR@AquariusOS.AquariusOSMiscTool=GIT_CLONE_GENERAL_FAIL: Failed to clone repository."
            exit 1
        fi
        echo "Cloned successfully."
        echo "Building update package..."
        cd /tmp/osaqua-update-temp || {
            echo "ERR@AquariusOS.AquariusOSMiscTool=CD_FAIL: Failed to change directory to /tmp/osaqua-update-temp."
            exit 1
        }
        ./build.sh --silent
        # Here, we expect bunch of .deb files in builds directory

        if [[ $? -ne 0 ]]; then
            echo "ERR@AquariusOS.AquariusOSMiscTool=SILENT_BUILD_SCRIPT_FAILED: Build process failed."
            exit 1
        fi

        ;;

    upgrade)
        if [[ "$2" == "--hot-install" ]]; then
            echo "WRN@AquariusOS.AquariusOSMiscTool=INSTABILITY: Hot installation is not recommended and may lead to system instability."
            echo "Proceeding with hot installation..."
            apt install /opt/aqua/data/update/*.deb
            if [[ $? -ne 0 ]]; then
                echo "ERR@AquariusOS.AquariusOSMiscTool=HOT_INSTALL_FAILED: Hot installation failed."
                exit 1
            fi
            echo "Hot installation completed successfully."
            exit 0
        fi

        echo "Copying package to /opt/aqua/data/update..."
        mkdir -p /opt/aqua/data/update
        if [[ ! -d /tmp/osaqua-update-temp/builds ]]; then
            echo "ERR@AquariusOS.AquariusOSMiscTool=NO_SUCH_FILE_OR_DIRECTORY: Builds directory not found. Use 'aqua update' first."
            exit 1
        fi
        cp /tmp/osaqua-update-temp/builds/*.deb /opt/aqua/data/update/
        if [[ $? -ne 0 ]]; then
            echo "ERR@AquariusOS.AquariusOSMiscTool=FILE_OPERATION_COPY_FAILED: Failed to copy update packages."
            exit 1
        fi

        # Create installation script
        echo "Creating installation script..."
        INSTALL_SCRIPT="/opt/aqua/data/update/install_update.sh"
        cat << 'EOF' > "$INSTALL_SCRIPT"
#!/bin/bash
STEP 1 3 "Installing update packages..."
apt install /opt/aqua/data/update/*.deb
VALIDATE $? "Package installation"
STEP 2 3 "Finalizing update..."
# Placeholder for any finalization steps
sleep 2
VALIDATE $? "Finalization"
STEP 3 3 "Cleaning up..."
rm -rf /opt/aqua/data/update/*.deb
rm -f /opt/aqua/data/update/install_update.sh
exit 0
EOF

        chmod +x "$INSTALL_SCRIPT"

        # Register using preboot update mechanism
        echo "Registering update with preboot mechanism..."
        /opt/aqua/sys/sbin/preboot.sh EnablePreboot 3
        /opt/aqua/sys/sbin/preboot.sh QueueUpdate "$INSTALL_SCRIPT" "true"

        echo "Upgrade packages are ready. Reboot the system to apply updates."
        ;;

    version)

        # Substitute with actual version retrieval logic
        avblKeys=("Build" "Version" "Codename" "Type" "StructureVersion")

        # Get format option
        defaultFormat="===AquariusOS Version Information===\nBuild: {Build}\nVersion: {Version}\nCodename: {Codename}\nType: {Type}\nStructure Version: {StructureVersion}"
        FORMAT_STRING="$defaultFormat"
        shift
        while [[ "$#" -gt 0 ]]; do
            case "$1" in
                --format)
                    FORMAT_STRING="$2"
                    shift 2
                    ;;
                *)
                    echo "Unknown option: $1"
                    exit 1
                    ;;
            esac
        done

        # Read registry keys
        declare -A versionInfo
        for key in "${avblKeys[@]}"; do
            value=$(/opt/aqua/sys/sbin/reg.sh root read HKEY_LOCAL_MACHINE/SYSTEM/ControlSet/Current${key} 2>/dev/null)
            versionInfo["$key"]="$value"
        done

        # Format output
        output="$FORMAT_STRING"
        for key in "${avblKeys[@]}"; do
            output="${output//\{$key\}/${versionInfo[$key]}}"
        done
        echo -e "$output"
        ;;
    
    *)
        echo "Unknown command: $1"
        echo "Use 'aqua help' to see available commands."
        exit 1
esac