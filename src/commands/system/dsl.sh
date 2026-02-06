#!/bin/bash

# If parameter "-s" is provided, launch "/opt/aqua/sbin/dsl-shell.sh"
if [[ "$1" == "-s" ]]; then
    /opt/aqua/sbin/dsl-shell.sh
    exit $?
fi

# Otherwise, it is a one line dsl command

# Look through: /opt/aqua/share/dsl/stacks/bash/Instructions to find the command
# Until it reaches a directory with main.sh file, iterate through the tree directory structure
current_path="/opt/aqua/share/dsl/stacks/bash/Instructions"
command_path=""
for cmd in "$@"; do
    if [[ -d "$current_path/$cmd" ]]; then
        current_path="$current_path/$cmd"
        if [[ -f "$current_path/main.sh" ]]; then
            command_path="$current_path/main.sh"
        fi
    else
        break
    fi
done

# If command_path is found, execute it with remaining parameters
if [[ -n "$command_path" ]]; then
    remaining_params=("${@:$(($# - $(echo "$@" | tr ' ' '\n' | grep -n -m1 "$(basename "$command_path" .sh)" | cut -d: -f1) + 1))}")
    bash "$command_path" "$command_path" "${remaining_params[@]}"
    exit $?
else
    echo "Command not found."
    exit 1
fi
