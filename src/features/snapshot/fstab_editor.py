import os
import sys

# First argument is the uuid of current disk
disk_uuid = sys.argv[1]

fstab_path = "/etc/fstab"

with open(fstab_path, "r") as fstab:
    content = fstab.readlines()

new_content = []
if "--rollback" in sys.argv:
    # On rollback, we need to revert the changes
    for line in content:
        # Check if ends with subvolumes and contains uuid
        if line.strip().endswith("subvol=@,defaults 0 0") and f"{disk_uuid}" in line:
            # revert
            components = line.split(" ")
            line_reverted = f"{components[0]} {components[1]} {components[2]} btrfs defaults 0 1\n"
            new_content.append(line_reverted)
        elif line.strip().endswith("subvol=@home,defaults 0 0") and f"{disk_uuid}" in line:
            # skip home subvolume line
            continue
        else:
            new_content.append(line)
    with open(fstab_path, "w") as fstab:
        fstab.writelines(new_content)
    sys.exit(0)
else:
    for line in content:
        # Check if ends with btrfs defaults 0 1 and contains uuid
        if line.strip().endswith("btrfs defaults 0 1") and f"{disk_uuid}" in line:
            # substitute
            # Assuming the line is /dev/disk/by-uuid/<uuid> / btrfs defaults 0 1
            components = line.split(" ")
            line1 = f"{components[0]} {components[1]} {components[2]} subvol=@,defaults 0 0\n"
            line2 = f"{components[0]} /home {components[2]} subvol=@home,defaults 0 0\n"
            new_content.append(line1)
            new_content.append(line2)
        else:
            new_content.append(line)

    with open(fstab_path, "w") as fstab:
        fstab.writelines(new_content)

    sys.exit(0)