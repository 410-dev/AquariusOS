#!/bin/bash

# $1 = action [ EnablePreboot | DisablePreboot | QueueUpdate | DequeueUpdate | EnableBgrt | SetNextInstallmentScript ]
# $2 = (Optional) update file path / Preboot version
# $3 = (Optional) enable snapshot

PREBOOT_STORAGE="/opt/aqua/boot/preboot"
PERSIST_STORAGE="${PREBOOT_STORAGE}/var"

case "$1" in
    EnablePreboot)
        if [[ -z "$2" ]]; then
            echo "Preboot version not specified. Usage: $0 EnablePreboot <version>"
            exit 1
        fi
        echo "Enabling preboot..."
        set -e
        sudo systemctl enable "${PREBOOT_STORAGE}"/preboot.service
        echo "$2" | sudo tee "${PREBOOT_STORAGE}"/conf/version > /dev/null
        set +e
        echo "Preboot enabled with version $2."
        ;;
    DisablePreboot)
        echo "Disabling preboot..."
        set -e
        sudo systemctl disable "${PREBOOT_STORAGE}"/preboot.service
        set +e
        echo "Preboot disabled."
        ;;
    QueueUpdate)
        echo "Enabling update mode..."
        sudo echo "Privilege escalation successful."
        if [[ -f "$2" ]]; then
            echo "Update mode enabled. Update file: $2"
            sudo touch "$PERSIST_STORAGE"/osaqua-update-mode.enabled
            echo "$2" > "$PERSIST_STORAGE"/osaqua-update-mode.file
        else
            echo "Update file $2 does not exist. Cannot enable update mode."
            exit 1
        fi
        if [[ "$3" == "true" ]]; then
            echo "Snapshot mode enabled."
            sudo touch "$PERSIST_STORAGE"/osaqua-update-mode.snapshot
        fi
        echo "Please reboot the system to apply update mode."
        ;;
    DequeueUpdate)
        echo "Disabling update mode..."
        file "$PERSIST_STORAGE"/osaqua-update-mode.enabled && sudo rm -f "$PERSIST_STORAGE"/osaqua-update-mode.enabled
        file "$PERSIST_STORAGE"/osaqua-update-mode.file && sudo rm -f "$PERSIST_STORAGE"/osaqua-update-mode.file
        file "$PERSIST_STORAGE"/osaqua-update-mode.snapshot && sudo rm -f "$PERSIST_STORAGE"/osaqua-update-mode.snapshot
        echo "Update mode disabled."
        ;;
    EnableBgrt)
#        echo "If asked, select AquariusOS version."
        echo "Enabling BGRT..."
        set -e
        sudo update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth /usr/share/plymouth/themes/aqua/aqua.plymouth 100
#        sudo update-alternatives --config default.plymouth
        sudo update-alternatives --set default.plymouth /usr/share/plymouth/themes/aqua/aqua.plymouth
        sudo update-initramfs -u
        set +e
        echo "BGRT enabled."
        ;;
    SetNextInstallmentScript)

        # If current preboot version is less than 3, exit with error with compatibility error
        CURRENT_VERSION_FILE="$(cat "${PREBOOT_STORAGE}"/conf/version 2>/dev/null || echo "0")"
        if [[ "$CURRENT_VERSION_FILE" -lt 3 ]]; then
            echo "ERR@AquariusOS.Preboot=NO_SUCH_CAPABILITY_FOR_CURRENT_PREBOOT: Setting next installment script is only supported on preboot version 3 or higher. Current version: $CURRENT_VERSION_FILE"
            exit 1
        fi

        INSTALLMENT_SCRIPT="$2"
        COPY_TO="/opt/aqua/boot/preboot/var/install_update_next.sh"

        if [[ -z "$INSTALLMENT_SCRIPT" ]]; then
            echo "Usage: $0 SetNextInstallmentScript <installment_script_path>"
            exit 1
        fi

        if [[ ! -f "$INSTALLMENT_SCRIPT" ]]; then
            echo "ERR@AquariusOS.Preboot=NO_SUCH_FILE_OR_DIRECTORY: Installment script '$INSTALLMENT_SCRIPT' does not exist."
            exit 1
        fi

        if [[ -f "$COPY_TO" ]] && [[ "$3" != "--override-existing" ]]; then
            echo "ERR@AquariusOS.Preboot=CONFLICTING_PRIORITY: An installment script is already set to be executed next. Use --override-existing to replace it."
            exit 1
        fi

        # Security check
        # Check if file is owned by root and not writable by group/others
        FILE_OWNER=$(stat -c '%U' "$INSTALLMENT_SCRIPT")
        FILE_PERMS=$(stat -c '%a' "$INSTALLMENT_SCRIPT") # Required to have at most 755 permissions
        if [[ "$FILE_OWNER" != "root" ]]; then
            echo "ERR@AquariusOS.Preboot=INVALID_FILE_PERMISSIONS_OWNERSHIP: Installment script must be owned by root."
            exit 1
        fi
        if [[ $((FILE_PERMS % 10)) -ne 5 ]] || [[ $(((FILE_PERMS / 10) % 10)) -ne 5 ]]; then
            echo "ERR@AquariusOS.Preboot=INVALID_FILE_PERMISSIONS_W_PERMIT: Installment script must not be writable by group or others."
            exit 1
        fi

        mkdir -p "$(dirname "$COPY_TO")"
        ln -sf "$INSTALLMENT_SCRIPT" "$COPY_TO"
        ;;

    SetInstallmentScriptFailRollbackScript)
        # If current preboot version is less than 3, exit with error with compatibility error
        CURRENT_VERSION_FILE="$(cat "${PREBOOT_STORAGE}"/conf/version 2>/dev/null || echo "0")"
        if [[ "$CURRENT_VERSION_FILE" -lt 3 ]]; then
            echo "ERR@AquariusOS.Preboot=NO_SUCH_CAPABILITY_FOR_CURRENT_PREBOOT: Setting next installment script is only supported on preboot version 3 or higher. Current version: $CURRENT_VERSION_FILE"
            exit 1
        fi
        ROLLBACK_SCRIPT="$2"
        COPY_TO="/opt/aqua/boot/preboot/var/rollback.sh"

        if [[ -z "$ROLLBACK_SCRIPT" ]]; then
            echo "Usage: $0 SetInstallmentScriptFailRollbackScript <installment_script_path>"
            exit 1
        fi

        if [[ ! -f "$ROLLBACK_SCRIPT" ]]; then
            echo "ERR@AquariusOS.Preboot=NO_SUCH_FILE_OR_DIRECTORY: Rollback script '$ROLLBACK_SCRIPT' does not exist."
            exit 1
        fi

        if [[ -f "$COPY_TO" ]] && [[ "$3" != "--override-existing" ]]; then
            echo "ERR@AquariusOS.Preboot=CONFLICTING_PRIORITY: A rollback script is already set to be executed next. Use --override-existing to replace it."
            exit 1
        fi
        mkdir -p "$(dirname "$COPY_TO")"
        ln -sf "$ROLLBACK_SCRIPT" "$COPY_TO"

        ;;

    *)
        echo "Usage: $0 [ EnablePreboot | DisablePreboot | QueueUpdate | DequeueUpdate | EnableBgrt | SetNextInstallmentScript ] [update_file_path/preboot_version] [enable_snapshot]"
        exit 1
        ;;
esac