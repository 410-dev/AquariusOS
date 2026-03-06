#!/bin/bash

FLAG_FILES="/opt/aqua/boot/preboot/var"

echo "Preboot Version 3"

if [[ ! -f "${FLAG_FILES}/install_update.sh" ]]; then
    if [[ -f "${FLAG_FILES}/install_update_next.sh" ]]; then
        mv -f "${FLAG_FILES}/install_update_next.sh" "${FLAG_FILES}/install_update.sh"
        echo "No current installment script found. Moved next installment script to current."
    else
        echo "Installment script not found. Exiting."
        exit 0
    fi
else
    echo "Installment script found. Proceeding with update."
fi

plymouth change-mode --updates

STEP() {
    local n="$1"    # current step number
    local of="$2"   # total steps
    local label="$3"
    local percent

    # Integer 0–100
    percent=$(( 100 * n / of ))
    echo "Step $n of $of: $label"
    plymouth message --text="$label"
    plymouth system-update --progress="${percent}"
}

VALIDATE() {
    EXIT_CODE=$1
    STEP_NAME="$2"
    if [[ $EXIT_CODE -ne 0 ]]; then
        plymouth message --text="$STEP_NAME failed. Aborting update."
        plymouth system-update --progress=100
        mv -f "${FLAG_FILES}/install_update.sh" "${FLAG_FILES}/install_update.sh.failed@${this_time}"
        if [[ -f "${FLAG_FILES}/rollback.sh" ]]; then
            plymouth message --text="Executing rollback script..."
            "${FLAG_FILES}/rollback.sh"
            if [[ $? -ne 0 ]]; then
                plymouth message --text="Rollback script failed."
                mv -f "${FLAG_FILES}/rollback.sh" "${FLAG_FILES}/rollback.sh.failed@${this_time}"
            else
                plymouth message --text="Rollback script completed successfully."
                mv -f "${FLAG_FILES}/rollback.sh" "${FLAG_FILES}/rollback.sh.completed@${this_time}"
            fi
        fi
        sleep 2
        systemctl reboot
        exit 1
    fi
}

export -f STEP
export -f VALIDATE

sleep 2

STEP 0 100 "Executing update script..."
function execute_script() {
    "${FLAG_FILES}/install_update.sh"
    return $?
}
execute_script
VALIDATE $? "Script Run"


STEP 100 100 "Cleaning up..."
function cleanup() {
    this_time=$(date +%s)
    mv -f "${FLAG_FILES}/install_update.sh" "${FLAG_FILES}/install_update.sh.complete@${this_time}"
    if [[ -f "${FLAG_FILES}/rollback.sh" ]]; then
        mv -f "${FLAG_FILES}/rollback.sh" "${FLAG_FILES}/rollback.sh.no-invoke@${this_time}"
    fi
    return 0
}
cleanup

plymouth message --text="Update complete."
plymouth system-update --progress=100
sleep 2

sync
systemctl reboot --force --force

