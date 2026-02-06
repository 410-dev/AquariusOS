#!/bin/bash

# Usage
#   feature enable <feature name> [--experimental] - Enable a feature
#   feature disable <feature name> - Disable a feature
#   feature list - List all available features

FEATURES_DIR=("/opt/aqua/sys/features" "/opt/aqua/features")

if [[ "$#" -lt 1 ]]; then
    echo "Usage: feature <enable|disable|list> [feature name] [--experimental]"
    exit 1
fi

ACTION="$1"
FEATURE_NAME="$2"

if [[ "$ACTION" == "enable" || "$ACTION" == "disable" || "$ACTION" == "status" ]]; then
    if [[ -z "$FEATURE_NAME" ]]; then
        echo "Error: Feature name is required for action '$ACTION'."
        exit 1
    fi
fi

find_feature_path() {
    local feature="$1"
    for dir in "${FEATURES_DIR[@]}"; do
        if [[ -d "$dir/$feature" ]]; then
            echo "$dir/$feature"
            return 0
        fi
    done
    return 1
}

case "$ACTION" in
    enable)
        FEATURE_PATH=$(find_feature_path "$FEATURE_NAME")
        if [[ -z "$FEATURE_PATH" ]]; then
            echo "Error: Feature '$FEATURE_NAME' not found."
            exit 1
        fi

        blacklisted=",$(/opt/aqua/sys/sbin/reg.sh root read "HKEY_LOCAL_MACHINE/SYSTEM/Policies/Features/Blacklisted" 2>/dev/null),"
        if [[ "$blacklisted" == *",$FEATURE_NAME,"* ]]; then
            echo "Error: Feature '$FEATURE_NAME' is blacklisted and cannot interact."
            exit 1
        fi

        # If --one-way-enablement is not specified, check for disable script
        if [[ ! -f "$FEATURE_PATH/disable.sh" ]] && [[ -z "$(echo "$@" | grep \\--one-way-enablement)" ]]; then
            echo "Error: Feature '$FEATURE_NAME' cannot be disabled once enabled. Use --one-way-enablement to override."
            exit 1
        fi

        if [[ -f "$FEATURE_PATH/compatibility.sh" ]] && [[ -z "$(echo "$@" | grep \\--skip-compatibility-check)" ]]; then
            sudo bash "$FEATURE_PATH/compatibility.sh" "$FEATURE_PATH" "$@"
            if [[ $? -ne 0 ]]; then
                echo "Error: Feature '$FEATURE_NAME' is not compatible with the current system."
                exit 1
            fi
        elif [[ ! -z "$(echo "$@" | grep \\--skip-compatibility-check)" ]]; then
            echo "Warning: Feature compatibility check skipped."
        fi

        if [[ -f "$FEATURE_PATH/ExperimentalFeature" ]] && [[ -z "$(echo "$@" | grep \\--experimental)" ]]; then
            echo "Error: Feature '$FEATURE_NAME' is experimental and cannot be enabled without the --experimental flag."
            exit 1
        fi

        # Check registry
        REG_STATUS=$(/opt/aqua/sys/sbin/reg.sh root read "HKEY_LOCAL_MACHINE/SYSTEM/Features/$FEATURE_NAME/Enabled" 2>/dev/null)
        if [[ "$REG_STATUS" == "1" ]] || [[ "$REG_STATUS" == "True" ]]; then
            echo "Feature '$FEATURE_NAME' is already enabled."
            exit 0
        fi

        if [[ -f "$FEATURE_PATH/enable.sh" ]]; then
            sudo bash "$FEATURE_PATH/enable.sh" "$FEATURE_PATH" "$@"
            ec=$?
            if [[ $ec -ne 0 ]] && [[ $ec -ne 100 ]]; then
                echo "Error: Failed to enable feature '$FEATURE_NAME'."
                exit 1
            fi
            if [[ $ec -eq 0 ]]; then
                sudo /opt/aqua/sys/sbin/reg.sh root write "HKEY_LOCAL_MACHINE/SYSTEM/Features/$FEATURE_NAME/Enabled" bool 1
                echo "Feature '$FEATURE_NAME' enabled."
            elif [[ $ec -eq 100 ]]; then
                echo "Feature '$FEATURE_NAME' enabled. A system restart is required for changes to take effect."
                # If GUI environment, use zenity to prompt for restart
                if [[ -n "$DISPLAY" ]] && command -v zenity >/dev/null
                then
                    zenity --question --title="System Restart Required" --text="Feature '$FEATURE_NAME' has been enabled. A system restart is required for changes to take effect.\n\nWould you like to restart now?" --width=400
                    if [[ $? -eq 0 ]]; then
                        sudo systemctl reboot
                    else
                        echo "Please remember to restart your system later."
                    fi
                elif [[ -z "$(echo "$@" | grep \\--no-interaction)" ]]; then
                    read -p "Feature '$FEATURE_NAME' has been enabled. A system restart is required for changes to take effect. Restart now? (y/N): " response
                    if [[ "$response" == "y" || "$response" == "Y" ]]; then
                        sudo systemctl reboot
                    else
                        echo "Please remember to restart your system later."
                    fi
                else
                    echo "Please remember to restart your system later."
                fi
            fi
        else
            echo "Error: Enable script not found for feature '$FEATURE_NAME'."
            exit 1
        fi
        ;;

    disable)
        FEATURE_PATH=$(find_feature_path "$FEATURE_NAME")
        if [[ -z "$FEATURE_PATH" ]]; then
            echo "Error: Feature '$FEATURE_NAME' not found."
            exit 1
        fi

        blacklisted=",$(/opt/aqua/sys/sbin/reg.sh root read "HKEY_LOCAL_MACHINE/SYSTEM/Policies/Features/Blacklisted" 2>/dev/null),"
        if [[ "$blacklisted" == *",$FEATURE_NAME,"* ]]; then
            echo "Error: Feature '$FEATURE_NAME' is blacklisted and cannot interact."
            exit 1
        fi

        # Check registry
        REG_STATUS=$(/opt/aqua/sys/sbin/reg.sh root read "HKEY_LOCAL_MACHINE/SYSTEM/Features/$FEATURE_NAME/Enabled" 2>/dev/null)
        if [[ "$REG_STATUS" != "1" && "$REG_STATUS" != "True" ]]; then
            echo "Feature '$FEATURE_NAME' is already disabled."
            exit 0
        fi

        if [[ -f "$FEATURE_PATH/disable.sh" ]]; then
            sudo bash "$FEATURE_PATH/disable.sh" "$FEATURE_PATH" "$@"

            ec=$?
            if [[ $ec -ne 0 ]]; then
                echo "Error: Failed to disable feature '$FEATURE_NAME'."
                exit 1
            fi
            if [[ $ec -eq 0 ]]; then
                sudo /opt/aqua/sys/sbin/reg.sh root write "HKEY_LOCAL_MACHINE/SYSTEM/Features/$FEATURE_NAME/Enabled" bool 0
                echo "Feature '$FEATURE_NAME' disabled."
            elif [[ $ec -eq 100 ]]; then
                echo "Feature '$FEATURE_NAME' disabled. A system restart is required for changes to take effect."
                # If GUI environment, use zenity to prompt for restart
                if [[ -n "$DISPLAY" ]] && command -v zenity >/dev/null
                then
                    zenity --question --title="System Restart Required" --text="Feature '$FEATURE_NAME' has been disabled. A system restart is required for changes to take effect.\n\nWould you like to restart now?" --width=400
                    if [[ $? -eq 0 ]]; then
                        sudo systemctl reboot
                    else
                        echo "Please remember to restart your system later."
                    fi
                elif [[ -z "$(echo "$@" | grep \\--no-interaction)" ]]; then
                    read -p "Feature '$FEATURE_NAME' has been disabled. A system restart is required for changes to take effect. Restart now? (y/N): " response
                    if [[ "$response" == "y" || "$response" == "Y" ]]; then
                        sudo systemctl reboot
                    else
                        echo "Please remember to restart your system later."
                    fi
                else
                    echo "Please remember to restart your system later."
                fi
            fi

        else
            echo "Error: Disable script not found for feature '$FEATURE_NAME'."
            exit 1
        fi
        ;;

    list)
        blacklisted=",$(/opt/aqua/sys/sbin/reg.sh root read "HKEY_LOCAL_MACHINE/SYSTEM/Policies/Features/Blacklisted" 2>/dev/null),"
        for dir in "${FEATURES_DIR[@]}"; do
            if [[ -d "$dir" ]]; then
                for feature in "$dir"/*; do
                    if [[ -d "$feature" ]]; then
                        feature_name=$(basename "$feature")

                        # Check if feature name is in blacklisted list
                        if [[ "$blacklisted" == *",$feature_name,"* ]]; then
                            continue
                        fi

                        enabled=$(/opt/aqua/sys/sbin/reg.sh root read "HKEY_LOCAL_MACHINE/SYSTEM/Features/$feature_name/Enabled" 2>/dev/null)
                        if [[ "$enabled" == "1" || "$enabled" == "True" ]];
                        then
                            status="*"
                        else
                            status=""
                        fi
                        echo "${status}${feature_name}"
                    fi
                done
            fi
        done
        ;;
esac