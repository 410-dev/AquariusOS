#!/bin/bash

# Symbolic link all .py files from /opt/aqua/sys/lib/python/ to /usr/lib/python3/dist-packages/aqua/
SOURCE_DIR="/opt/aqua/sys/lib/python/"
TARGET_DIR="/usr/lib/python3/dist-packages/"

mkdir -p "$TARGET_DIR"
find "$SOURCE_DIR" -name *.py | while read -r file; do
    relative_path="${file#$SOURCE_DIR}"
    target_path="$TARGET_DIR$relative_path"
    target_dir="$(dirname "$target_path")"
    mkdir -p "$target_dir"
    ln -sf "$file" "$target_path"
    echo "Created symlink: $target_path -> $file"
done
echo "Symbolic links for .py files created from $SOURCE_DIR to $TARGET_DIR"

unset SOURCE_DIR
unset TARGET_DIR
unset file
unset relative_path
unset target_path
unset target_dir

