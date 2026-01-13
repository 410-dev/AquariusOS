import os
import sys
import shutil
import subprocess
import json
import time
import glob
import re
from contextlib import contextmanager
from datetime import datetime

# ==============================================================================
# Configuration & Constants
# ==============================================================================
REGISTRY_CHECK_CMD = [
    "/opt/aqua/sys/sbin/reg.sh", "root", "read",
    "HKEY_LOCAL_MACHINE/SYSTEM/Features/me.hysong.snapshot/Enabled"
]
MOUNT_POINT = "/mnt/btrfs_lib_root"
GRUB_CFG_PATH = "/etc/grub.d/42_btrfs_snapshots"
REGISTRY_LOG = "/var/log/btrfs_snapshot_registry.log"


class SnapshotError(Exception):
    pass


class BtrfsSnapshotManager:
    def __init__(self):
        self._check_compatibility()

    def _check_compatibility(self):
        """Checks specific feature flags requested by the user."""
        try:
            # Skip check if the tool doesn't exist (for portability), but if it exists, respect it.
            if os.path.exists(REGISTRY_CHECK_CMD[0]):
                res = subprocess.check_output(REGISTRY_CHECK_CMD).decode().strip()
                if res != "True":
                    raise SnapshotError("Feature 'me.hysong.snapshot' is not enabled.")
        except subprocess.CalledProcessError:
            pass  # Fail safely if registry tool is broken, or raise strict error if preferred.

        if os.geteuid() != 0:
            raise SnapshotError("Must be run as root.")

    def _run(self, cmd, check=True):
        """Helper to run shell commands."""
        return subprocess.run(cmd, shell=True, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def _get_mount_info(self, path):
        """Returns source device and fs type for a given path using findmnt."""
        cmd = f"findmnt -J -n -o SOURCE,FSTYPE,UUID {path}"
        res = self._run(cmd)
        data = json.loads(res.stdout)
        # findmnt -J returns a dict with 'filesystems': [ ... ]
        return data['filesystems'][0]

    @contextmanager
    def _mount_btrfs_root(self):
        """
        Context manager to mount the raw Btrfs root (subvolid=5).
        Yields the mount path.
        """
        # 1. Detect root device
        root_info = self._get_mount_info("/")

        # Handle OverlayFS (Sandbox mode)
        if root_info['fstype'] == 'overlay':
            # In sandbox, real root is usually at /media/root-ro or similar.
            # We try to find the lowerdir source.
            if os.path.exists("/media/root-ro"):
                root_info = self._get_mount_info("/media/root-ro")
            else:
                raise SnapshotError("Detected OverlayFS but cannot find physical Btrfs root (/media/root-ro missing).")

        device_path = root_info['source'].split('[')[0]  # Strip [subvol] info

        os.makedirs(MOUNT_POINT, exist_ok=True)
        try:
            self._run(f"mount -o subvolid=5 {device_path} {MOUNT_POINT}")
            yield MOUNT_POINT
        finally:
            if os.path.ismount(MOUNT_POINT):
                self._run(f"umount {MOUNT_POINT}", check=False)
            try:
                os.rmdir(MOUNT_POINT)
            except:
                pass

    def _sync_boot_if_needed(self, snapshot_path):
        """
        If /boot is a separate partition, the snapshot will have an empty /boot folder.
        We must copy the current kernels into the snapshot so it acts as a self-contained root.
        """
        boot_info = self._get_mount_info("/boot")
        root_info = self._get_mount_info("/")

        # If UUIDs differ, or sources differ significantly, it's a separate partition
        is_separate = (boot_info.get('uuid') != root_info.get('uuid'))

        if is_separate:
            print(f"[-] Detected separate /boot partition. Syncing kernel assets to {snapshot_path}/boot...")
            # We use rsync to copy contents of /boot (live) to the snapshot's /boot folder
            # The snapshot is mounted at MOUNT_POINT/snapshot_name
            # snapshot_path is the full path to the snapshot root

            target_boot = os.path.join(snapshot_path, "boot")
            # Ensure target exists
            os.makedirs(target_boot, exist_ok=True)

            # Copy everything except efi (if present) to save space/time, usually we just need vmlinuz/initrd/config
            # But simplest is to copy valid kernel files.
            cmd = f"rsync -a --exclude 'efi' /boot/ {target_boot}/"
            self._run(cmd)

    # ==========================================================================
    # Public API
    # ==========================================================================

    def create_snapshot(self, mode="bootable", name=None):
        """
        Creates a snapshot trio (@snapshot, @home_snapshot).
        mode: 'bootable' (RW), 'integrity' (RO), 'sandbox' (RO+Overlay)
        """
        valid_modes = ["bootable", "integrity", "sandbox"]
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode. Must be one of {valid_modes}")

        ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        clean_name = f"-{name.replace(' ', '_')}" if name else ""
        snap_suffix = f"{clean_name}-{ts}"

        snap_sys_name = f"@snapshot{snap_suffix}"
        snap_home_name = f"@home_snapshot{snap_suffix}"

        with self._mount_btrfs_root() as mnt:
            # Validate source exists
            if not os.path.exists(os.path.join(mnt, "@")):
                raise SnapshotError("Source subvolume @ not found in root (id=5).")

            print(f"[-] Creating snapshot: {snap_sys_name} ({mode})")

            # 1. Create Snapshots
            self._run(f"btrfs subvolume snapshot {mnt}/@ {mnt}/{snap_sys_name}")
            self._run(f"btrfs subvolume snapshot {mnt}/@home {mnt}/{snap_home_name}")

            sys_path = os.path.join(mnt, snap_sys_name)

            # 2. Handle Separate /boot
            self._sync_boot_if_needed(sys_path)

            # 3. Update Fstab in Snapshot
            fstab_path = os.path.join(sys_path, "etc/fstab")
            if os.path.exists(fstab_path):
                with open(fstab_path, 'r') as f:
                    content = f.read()

                # Replace subvol=@home with subvol=@home_snapshot...
                # Regex handles spaces, tabs, and potential commas in options
                content = re.sub(r'subvol=@home([\s,])', f'subvol={snap_home_name}\\1', content)

                with open(fstab_path, 'w') as f:
                    f.write(content)

            # 4. Write Metadata
            meta_path = os.path.join(sys_path, "etc/btrfs-snap.info")
            with open(meta_path, 'w') as f:
                f.write(f"TYPE={mode}\nCREATED={ts}\nNAME={name or 'N/A'}\n")

            # 5. Lock RO if needed
            if mode in ["integrity", "sandbox"]:
                self._run(f"btrfs property set {mnt}/{snap_sys_name} ro true")
                self._run(f"btrfs property set {mnt}/{snap_home_name} ro true")

            # 6. Log
            with open(REGISTRY_LOG, "a") as log:
                log.write(f"{ts} | {name or 'N/A'} | {mode} | {snap_sys_name} | {snap_home_name}\n")

            # 7. Update GRUB (unless integrity mode)
            if mode != "integrity":
                self.enumerate_snapshots(update_grub=True)

        return snap_sys_name

    def enumerate_snapshots(self, update_grub=False):
        """
        Lists snapshots found on disk.
        If update_grub is True, it regenerates the grub configuration file.
        Returns a list of dicts.
        """
        snapshots = []

        with self._mount_btrfs_root() as mnt:
            # Find all dirs starting with @snapshot
            paths = glob.glob(os.path.join(mnt, "@snapshot*"))

            # Filter out @home_snapshot
            sys_snaps = [p for p in paths if "@home_snapshot" not in p]

            for path in sys_snaps:
                snap_name = os.path.basename(path)
                meta_file = os.path.join(path, "etc/btrfs-snap.info")

                # Read Metadata
                snap_type = "bootable"  # Default
                if os.path.exists(meta_file):
                    with open(meta_file, 'r') as f:
                        for line in f:
                            if line.startswith("TYPE="):
                                snap_type = line.split("=")[1].strip()

                # Find Kernel Version
                boot_dir = os.path.join(path, "boot")
                kernel_ver = "Unknown"
                # Look for vmlinuz symlink or file
                vmlinuz = glob.glob(os.path.join(boot_dir, "vmlinuz*"))
                if vmlinuz:
                    # simplistic parse
                    kernel_ver = os.path.basename(vmlinuz[0]).replace("vmlinuz-", "")

                snapshots.append({
                    "name": snap_name,
                    "type": snap_type,
                    "kernel": kernel_ver,
                    "path": path
                })

            if update_grub:
                self._reconstruct_grub(mnt, snapshots)

        return snapshots

    def _reconstruct_grub(self, mnt_point, snapshots):
        """Internal method to generate 42_btrfs_snapshots."""
        print("[-] Regenerating GRUB entries...")

        root_dev = self._get_mount_info(mnt_point)['source'].split('[')[0]
        # Get UUID of the ROOT partition (not boot partition)
        # We rely on blkid for specific UUID extraction
        uuid_cmd = f"blkid -s UUID -o value {root_dev}"
        root_uuid = subprocess.check_output(uuid_cmd, shell=True).decode().strip()

        # Get base boot args
        with open("/proc/cmdline", "r") as f:
            cmdline = f.read().strip()

        # Strip existing root specific args
        ignore_args = [r"root=UUID=\S+", r"rootflags=\S+", r"overlayroot=\S+", r"\bro\b", r"\brw\b"]
        clean_args = cmdline
        for pattern in ignore_args:
            clean_args = re.sub(pattern, "", clean_args)
        clean_args = re.sub(r"\s+", " ", clean_args).strip()

        # Generate File Content
        lines = [
            "#!/bin/sh",
            "exec tail -n +3 $0",
            "# Auto-generated by libsnapshotutil.py",
            ""
        ]

        for snap in snapshots:
            if snap['type'] == 'integrity':
                continue  # Skip integrity snaps in GRUB

            # Determine Title and Args
            title_prefix = "Sandbox" if snap['type'] == 'sandbox' else "Snapshot"
            args = f"{clean_args} overlayroot=tmpfs" if snap['type'] == 'sandbox' else clean_args
            rw_mode = "ro" if snap['type'] == 'sandbox' else "rw"

            pretty_name = snap['name'].replace("@snapshot-", "")

            # Kernel Paths (relative to subvolume)
            # Since we synced /boot into the snapshot, the files are at /boot/vmlinuz-...
            k_path = f"/{snap['name']}/boot/vmlinuz-{snap['kernel']}"
            i_path = f"/{snap['name']}/boot/initrd.img-{snap['kernel']}"

            entry = f"""
menuentry '{title_prefix}: {pretty_name} ({snap['kernel']})' --class ubuntu --class gnu-linux --class os {{
    recordfail
    load_video
    insmod gzio
    insmod part_gpt
    insmod btrfs
    search --no-floppy --fs-uuid --set=root {root_uuid}
    echo 'Loading Kernel from Snapshot...'
    linux {k_path} root=UUID={root_uuid} rootflags=subvol={snap['name']} {rw_mode} {args}
    echo 'Loading Initrd...'
    initrd {i_path}
}}
"""
            lines.append(entry)

        with open(GRUB_CFG_PATH, "w") as f:
            f.write("\n".join(lines))

        os.chmod(GRUB_CFG_PATH, 0o755)
        self._run("update-grub")

    def delete_snapshot(self, target_name):
        """
        Deletes a snapshot and its paired home snapshot.
        target_name: The full directory name (e.g., @snapshot-2023...) or just the suffix
        """
        with self._mount_btrfs_root() as mnt:
            # Resolve name
            if not target_name.startswith("@snapshot"):
                # Try to find it loosely
                candidates = glob.glob(os.path.join(mnt, f"@snapshot*{target_name}*"))
                if not candidates:
                    raise SnapshotError(f"Snapshot matching '{target_name}' not found.")
                snap_sys_name = os.path.basename(candidates[0])
            else:
                snap_sys_name = target_name

            # Deduce Home Name
            # Standard naming: @snapshot-X -> @home_snapshot-X
            snap_home_name = snap_sys_name.replace("@snapshot", "@home_snapshot")

            print(f"[-] Deleting {snap_sys_name}...")
            sys_path = os.path.join(mnt, snap_sys_name)
            home_path = os.path.join(mnt, snap_home_name)

            if os.path.exists(sys_path):
                self._run(f"btrfs subvolume delete {sys_path}")

            if os.path.exists(home_path):
                print(f"[-] Deleting {snap_home_name}...")
                self._run(f"btrfs subvolume delete {home_path}")

            # Update GRUB
            self.enumerate_snapshots(update_grub=True)

    def restore_snapshot(self, snapshot_name):
        """
        Restores the system to a specific snapshot.
        1. Renames current @ -> @_backup_TS
        2. Snapshots target -> @
        3. Reconstructs GRUB
        """
        # Safety Check
        current_root_info = self._get_mount_info("/")
        if current_root_info['source'].endswith("[/@]"):
            raise SnapshotError("Cannot restore while booted into main volume (@). Boot into a snapshot first.")

        with self._mount_btrfs_root() as mnt:
            target_path = os.path.join(mnt, snapshot_name)
            if not os.path.exists(target_path):
                raise SnapshotError(f"Snapshot {snapshot_name} not found.")

            # Identify paired home
            home_name = snapshot_name.replace("@snapshot", "@home_snapshot")
            target_home_path = os.path.join(mnt, home_name)

            ts = int(time.time())
            print(f"[-] Backing up current system to @_backup_{ts}...")

            # Move current @
            if os.path.exists(os.path.join(mnt, "@")):
                self._run(f"mv {mnt}/@ {mnt}/@_backup_{ts}")
            if os.path.exists(os.path.join(mnt, "@home")):
                self._run(f"mv {mnt}/@home {mnt}/@home_backup_{ts}")

            print("[-] Restoring snapshots to @ and @home...")
            self._run(f"btrfs subvolume snapshot {target_path} {mnt}/@")
            self._run(f"btrfs subvolume snapshot {target_home_path} {mnt}/@home")

            # Fix fstab in the new @
            new_fstab = os.path.join(mnt, "@", "etc/fstab")
            with open(new_fstab, 'r') as f:
                content = f.read()
            # Revert any snapshot references back to @home
            content = re.sub(r'subvol=@home_snapshot[^,\s]*', 'subvol=@home', content)
            with open(new_fstab, 'w') as f:
                f.write(content)

            print("[+] Restore complete. Please reboot.")