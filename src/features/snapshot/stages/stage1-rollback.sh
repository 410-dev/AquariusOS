#!/bin/bash

set -e
STEP 1 10 "Restoring home content"
mv /@home/* /@/home/

STEP 2 10 "Deleting btrfs subvolumes /@ and /@home"
btrfs subvolume delete /@
btrfs subvolume delete /@home

STEP 3 10 "Reconstructing fstab for original layout"
python3 "/opt/aqua/features/me.hysong.SnapshotSupport/fstab_editor.py" "$(findmnt --output=UUID --noheadings --target=/)" --rollback

STEP 4 10 "Restoring GRUB configuration"
python3 "/opt/aqua/features/me.hysong.SnapshotSupport/grub_editor_stg1.py" --rollback
update-grub

STEP 5 10 "Restoring original GRUB configuration backups"
if [[ -f /etc/default/grub.bak ]]; then
    mv /etc/default/grub.bak /etc/default/grub
else
    echo "Warning: Backup file /etc/default/grub.bak not found. Skipping restoration."
fi
if [[ -f /boot/grub/grub.cfg.bak ]]; then
    mv /boot/grub/grub.cfg.bak /boot/grub/grub.cfg
else
    echo "Warning: Backup file /boot/grub/grub.cfg.bak not found. Skipping restoration."
fi

STEP 6 10 "Restoring /etc/default/grub if modified"
if grep -q "rootflags=subvol=@" /etc/default/grub; then
    echo "Removing rootflags=subvol=@ from /etc/default/grub..."
    sed -i 's/rootflags=subvol=@ //g' /etc/default/grub
else
    echo "rootflags=subvol=@ not found in /etc/default/grub. No changes made."
fi

STEP 7 10 "Regenerating GRUB configuration"
if command -v update-grub &> /dev/null; then
    update-grub
else
    echo "WARNING: update-grub command not found. Using grub-mkconfig instead."
    grub-mkconfig -o /boot/grub/grub.cfg
fi

STEP 8 10 "Reverting GRUB path adjustments"
# Replace "linux /@/boot/" with "linux /boot/"
sed -i 's|linux[[:space:]]*/@/boot/|linux/boot/|g' /boot/grub/grub.cfg
sed -i 's|linux[[:space:]]*/@/vmlinuz|linux /vmlinuz|g' /boot/grub/grub.cfg

# Replace "initrd /@/boot/" with "initrd /boot/"
sed -i 's|initrd[[:space:]]*/@/boot/|initrd /boot/|g' /boot/grub/grub.cfg
sed -i 's|initrd[[:space:]]*/@/initrd|initrd /initrd|g' /boot/grub/grub.cfg

STEP 9 10 "Cleanup complete. System rollback to original layout finished."
exit 0
