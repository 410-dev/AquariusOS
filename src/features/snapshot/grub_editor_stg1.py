import sys

# First argument is the uuid of current disk
grub_cfg_path = "/etc/default/grub"

with open(grub_cfg_path, "r") as grub_cfg:
    content = grub_cfg.read()

if "--rollback" in sys.argv:
    # On rollback, we need to revert the changes
    content = content.replace("GRUB_TIMEOUT_STYLE=menu", "GRUB_TIMEOUT_STYLE=hidden")
    content = content.replace("GRUB_TIMEOUT=3", "GRUB_TIMEOUT=0")
else:
    content.replace("GRUB_TIMEOUT_STYLE=hidden", "GRUB_TIMEOUT_STYLE=menu")
    content.replace("GRUB_TIMEOUT=0", "GRUB_TIMEOUT=3")

with open(grub_cfg_path, "w") as fstab:
    fstab.writelines(content)

sys.exit(0)
