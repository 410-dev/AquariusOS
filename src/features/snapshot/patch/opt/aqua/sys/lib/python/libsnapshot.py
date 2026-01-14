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
    "HKEY_LOCAL_MACHINE/SYSTEM/Features/snapshot/Enabled"
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
        try:
            if os.path.exists(REGISTRY_CHECK_CMD[0]):
                res = subprocess.check_output(REGISTRY_CHECK_CMD).decode().strip()
                if res != "True":
                    raise SnapshotError("Feature 'snapshot' is not enabled.")
        except subprocess.CalledProcessError:
            pass
        if os.geteuid() != 0:
            raise SnapshotError("Must be run as root.")

    def _run(self, cmd, check=True):
        return subprocess.run(cmd, shell=True, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def _get_mount_info(self, path):
        cmd = f"findmnt -J -n -o SOURCE,FSTYPE,UUID {path}"
        res = self._run(cmd)
        data = json.loads(res.stdout)
        return data['filesystems'][0]

    @contextmanager
    def _mount_btrfs_root(self):
        root_info = self._get_mount_info("/")
        if root_info['fstype'] == 'overlay':
            if os.path.exists("/media/root-ro"):
                root_info = self._get_mount_info("/media/root-ro")
            else:
                raise SnapshotError("Detected OverlayFS but cannot find physical Btrfs root.")

        device_path = root_info['source'].split('[')[0]
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
        boot_info = self._get_mount_info("/boot")
        root_info = self._get_mount_info("/")
        is_separate = (boot_info.get('uuid') != root_info.get('uuid'))

        if is_separate:
            print(f"[-] Detected separate /boot partition. Syncing kernel assets to {snapshot_path}/boot...")
            target_boot = os.path.join(snapshot_path, "boot")
            os.makedirs(target_boot, exist_ok=True)
            cmd = f"rsync -a --exclude 'efi' /boot/ {target_boot}/"
            self._run(cmd)

    def _scan_snapshots_internal(self, mnt):
        """Scans for snapshots and pairs kernels/initrds accurately."""
        snapshots = []
        paths = glob.glob(os.path.join(mnt, "@snapshot*"))
        sys_snaps = [p for p in paths if "@home_snapshot" not in p]

        for path in sys_snaps:
            snap_name = os.path.basename(path)
            meta_file = os.path.join(path, "etc/btrfs-snap.info")

            snap_type = "bootable"
            if os.path.exists(meta_file):
                with open(meta_file, 'r') as f:
                    for line in f:
                        if line.startswith("TYPE="):
                            snap_type = line.split("=")[1].strip()

            boot_dir = os.path.join(path, "boot")

            # 1. Find Kernel
            # Prioritize 'vmlinuz-*' (real files) to avoid bare 'vmlinuz' symlink issues
            k_files = glob.glob(os.path.join(boot_dir, "vmlinuz-*"))
            # Fallback to bare vmlinuz if no versioned file exists
            if not k_files:
                k_files = glob.glob(os.path.join(boot_dir, "vmlinuz"))

            if not k_files:
                # No kernel found, skip this snapshot
                continue

            # Pick the first valid kernel found
            kernel_path = k_files[0]
            kernel_filename = os.path.basename(kernel_path)

            # Extract version to find matching initrd
            # If filename is 'vmlinuz-6.8.0-generic', version is '6.8.0-generic'
            if kernel_filename.startswith("vmlinuz-"):
                version = kernel_filename[8:]
            else:
                version = ""  # Handle bare 'vmlinuz' case

            # 2. Find matching Initrd
            initrd_filename = None
            if version:
                # Look for initrd.img-VERSION
                i_candidates = glob.glob(os.path.join(boot_dir, f"initrd.img-{version}"))
                if i_candidates:
                    initrd_filename = os.path.basename(i_candidates[0])

            # Fallback: try generic initrd.img or initrd
            if not initrd_filename:
                fallback_i = glob.glob(os.path.join(boot_dir, "initrd*"))
                # Filter out the kernel we just found if names overlap (unlikely)
                fallback_i = [f for f in fallback_i if "vmlinuz" not in f]
                if fallback_i:
                    initrd_filename = os.path.basename(fallback_i[0])

            if kernel_filename and initrd_filename:
                snapshots.append({
                    "name": snap_name,
                    "type": snap_type,
                    "kernel_file": kernel_filename,  # Store EXACT filename
                    "initrd_file": initrd_filename,  # Store EXACT filename
                    "path": path
                })

        return snapshots

    def create_snapshot(self, mode="bootable", name=None):
        valid_modes = ["bootable", "integrity", "sandbox"]
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode. Must be one of {valid_modes}")

        ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        clean_name = f"-{name.replace(' ', '_')}" if name else ""
        snap_suffix = f"{clean_name}-{ts}"

        snap_sys_name = f"@snapshot{snap_suffix}"
        snap_home_name = f"@home_snapshot{snap_suffix}"

        with self._mount_btrfs_root() as mnt:
            if not os.path.exists(os.path.join(mnt, "@")):
                raise SnapshotError("Source subvolume @ not found.")

            print(f"[-] Creating snapshot: {snap_sys_name} ({mode})")

            self._run(f"btrfs subvolume snapshot {mnt}/@ {mnt}/{snap_sys_name}")
            self._run(f"btrfs subvolume snapshot {mnt}/@home {mnt}/{snap_home_name}")

            sys_path = os.path.join(mnt, snap_sys_name)
            self._sync_boot_if_needed(sys_path)

            fstab_path = os.path.join(sys_path, "etc/fstab")
            if os.path.exists(fstab_path):
                with open(fstab_path, 'r') as f: content = f.read()
                content = re.sub(r'subvol=@home([\s,])', f'subvol={snap_home_name}\\1', content)
                with open(fstab_path, 'w') as f: f.write(content)

            meta_path = os.path.join(sys_path, "etc/btrfs-snap.info")
            with open(meta_path, 'w') as f:
                f.write(f"TYPE={mode}\nCREATED={ts}\nNAME={name or 'N/A'}\n")

            if mode in ["integrity", "sandbox"]:
                self._run(f"btrfs property set {mnt}/{snap_sys_name} ro true")
                self._run(f"btrfs property set {mnt}/{snap_home_name} ro true")

            with open(REGISTRY_LOG, "a") as log:
                log.write(f"{ts} | {name or 'N/A'} | {mode} | {snap_sys_name} | {snap_home_name}\n")

            if mode != "integrity":
                # Pass existing mount context to prevent double-mount error
                self.enumerate_snapshots(update_grub=True, mount_context=mnt)

        return snap_sys_name

    def enumerate_snapshots(self, update_grub=False, mount_context=None):
        if mount_context:
            snapshots = self._scan_snapshots_internal(mount_context)
            if update_grub: self._reconstruct_grub(mount_context, snapshots)
            return snapshots
        else:
            with self._mount_btrfs_root() as mnt:
                snapshots = self._scan_snapshots_internal(mnt)
                if update_grub: self._reconstruct_grub(mnt, snapshots)
                return snapshots

    def _reconstruct_grub(self, mnt_point, snapshots):
        print("[-] Regenerating GRUB entries...")

        root_dev = self._get_mount_info(mnt_point)['source'].split('[')[0]
        uuid_cmd = f"blkid -s UUID -o value {root_dev}"
        root_uuid = subprocess.check_output(uuid_cmd, shell=True).decode().strip()

        with open("/proc/cmdline", "r") as f:
            cmdline = f.read().strip()

        ignore_args = [r"root=UUID=\S+", r"rootflags=\S+", r"overlayroot=\S+", r"\bro\b", r"\brw\b"]
        clean_args = cmdline
        for pattern in ignore_args:
            clean_args = re.sub(pattern, "", clean_args)
        clean_args = re.sub(r"\s+", " ", clean_args).strip()

        lines = [
            "#!/bin/sh",
            "exec tail -n +3 $0",
            "# Auto-generated by libsnapshot.py",
            ""
        ]

        for snap in snapshots:
            if snap['type'] == 'integrity': continue

            title_prefix = "Sandbox" if snap['type'] == 'sandbox' else "Snapshot"
            args = f"{clean_args} overlayroot=tmpfs" if snap['type'] == 'sandbox' else clean_args
            rw_mode = "ro" if snap['type'] == 'sandbox' else "rw"
            pretty_name = snap['name'].replace("@snapshot-", "")

            # FIX: Use the exact filenames found by the scanner
            k_path = f"/{snap['name']}/boot/{snap['kernel_file']}"
            i_path = f"/{snap['name']}/boot/{snap['initrd_file']}"

            entry = f"""
menuentry '{title_prefix}: {pretty_name}' --class ubuntu --class gnu-linux --class os {{
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
        with self._mount_btrfs_root() as mnt:
            if not target_name.startswith("@snapshot"):
                candidates = glob.glob(os.path.join(mnt, f"@snapshot*{target_name}*"))
                if not candidates: raise SnapshotError(f"Snapshot '{target_name}' not found.")
                snap_sys_name = os.path.basename(candidates[0])
            else:
                snap_sys_name = target_name

            snap_home_name = snap_sys_name.replace("@snapshot", "@home_snapshot")

            print(f"[-] Deleting {snap_sys_name}...")
            sys_path = os.path.join(mnt, snap_sys_name)
            home_path = os.path.join(mnt, snap_home_name)

            if os.path.exists(sys_path): self._run(f"btrfs subvolume delete {sys_path}")
            if os.path.exists(home_path):
                print(f"[-] Deleting {snap_home_name}...")
                self._run(f"btrfs subvolume delete {home_path}")

            self.enumerate_snapshots(update_grub=True, mount_context=mnt)

    def restore_snapshot(self, snapshot_name):
        current_root_info = self._get_mount_info("/")
        if current_root_info['source'].endswith("[/@]"):
            raise SnapshotError("Cannot restore while booted into main volume (@). Boot into a snapshot first.")

        with self._mount_btrfs_root() as mnt:
            target_path = os.path.join(mnt, snapshot_name)
            if not os.path.exists(target_path): raise SnapshotError(f"Snapshot {snapshot_name} not found.")

            # ... (Rest of restore logic identical to previous version) ...
            home_name = snapshot_name.replace("@snapshot", "@home_snapshot")
            target_home_path = os.path.join(mnt, home_name)

            ts = int(time.time())
            print(f"[-] Backing up current system to @_backup_{ts}...")
            if os.path.exists(os.path.join(mnt, "@")): self._run(f"mv {mnt}/@ {mnt}/@_backup_{ts}")
            if os.path.exists(os.path.join(mnt, "@home")): self._run(f"mv {mnt}/@home {mnt}/@home_backup_{ts}")

            print("[-] Restoring snapshots to @ and @home...")
            self._run(f"btrfs subvolume snapshot {target_path} {mnt}/@")
            self._run(f"btrfs subvolume snapshot {target_home_path} {mnt}/@home")

            new_fstab = os.path.join(mnt, "@", "etc/fstab")
            with open(new_fstab, 'r') as f:
                content = f.read()
            content = re.sub(r'subvol=@home_snapshot[^,\s]*', 'subvol=@home', content)
            with open(new_fstab, 'w') as f:
                f.write(content)

            print("[+] Restore complete. Please reboot.")
