# test_btrfs_snapshot_manager.py

import pytest
import os
import json
import subprocess
from unittest.mock import patch, MagicMock, mock_open, call
from datetime import datetime

from libsnapshot import BtrfsSnapshotManager, SnapshotError, REGISTRY_LOG, GRUB_CFG_PATH, MOUNT_POINT


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def manager():
    """
    BtrfsSnapshotManager 인스턴스를 생성합니다.
    _check_compatibility는 항상 패스하도록 패치합니다.
    """
    with patch.object(BtrfsSnapshotManager, "_check_compatibility"):
        return BtrfsSnapshotManager()


@pytest.fixture
def mock_mount_info_root():
    return {"source": "/dev/sda1[/@]", "fstype": "btrfs", "uuid": "1234-abcd"}


@pytest.fixture
def mock_mount_info_overlay():
    return {"source": "overlay", "fstype": "overlay", "uuid": ""}


@pytest.fixture
def mock_mount_info_boot_same():
    return {"source": "/dev/sda1[/@]", "fstype": "btrfs", "uuid": "1234-abcd"}


@pytest.fixture
def mock_mount_info_boot_separate():
    return {"source": "/dev/sda2", "fstype": "ext4", "uuid": "9999-ffff"}


@pytest.fixture
def sample_snapshots():
    return [
        {
            "name": "@snapshot-2025-01-01-120000",
            "type": "bootable",
            "kernel_file": "vmlinuz-6.8.0-generic",
            "initrd_file": "initrd.img-6.8.0-generic",
            "path": f"{MOUNT_POINT}/@snapshot-2025-01-01-120000",
        },
        {
            "name": "@snapshot-sandbox-2025-01-02-120000",
            "type": "sandbox",
            "kernel_file": "vmlinuz-6.8.0-generic",
            "initrd_file": "initrd.img-6.8.0-generic",
            "path": f"{MOUNT_POINT}/@snapshot-sandbox-2025-01-02-120000",
        },
        {
            "name": "@snapshot-integrity-2025-01-03-120000",
            "type": "integrity",
            "kernel_file": "vmlinuz-6.8.0-generic",
            "initrd_file": "initrd.img-6.8.0-generic",
            "path": f"{MOUNT_POINT}/@snapshot-integrity-2025-01-03-120000",
        },
    ]


# ==============================================================================
# _check_compatibility
# ==============================================================================

class TestCheckCompatibility:

    def test_raises_if_not_root(self):
        with patch("os.geteuid", return_value=1000), \
             patch("os.path.exists", return_value=False):
            with pytest.raises(SnapshotError, match="root"):
                BtrfsSnapshotManager()

    def test_passes_when_root(self):
        with patch("os.geteuid", return_value=0), \
             patch("os.path.exists", return_value=False):
            manager = BtrfsSnapshotManager()
            assert manager is not None

    def test_raises_if_registry_disabled(self):
        with patch("os.geteuid", return_value=0), \
             patch("os.path.exists", return_value=True), \
             patch("subprocess.check_output", return_value=b"False"):
            with pytest.raises(SnapshotError, match="not enabled"):
                BtrfsSnapshotManager()

    def test_passes_if_registry_enabled(self):
        with patch("os.geteuid", return_value=0), \
             patch("os.path.exists", return_value=True), \
             patch("subprocess.check_output", return_value=b"True"):
            manager = BtrfsSnapshotManager()
            assert manager is not None

    def test_ignores_registry_check_error(self):
        """CalledProcessError 발생 시 예외 없이 통과되어야 합니다."""
        with patch("os.geteuid", return_value=0), \
             patch("os.path.exists", return_value=True), \
             patch("subprocess.check_output",
                   side_effect=subprocess.CalledProcessError(1, "reg.sh")):
            manager = BtrfsSnapshotManager()
            assert manager is not None


# ==============================================================================
# _get_mount_info
# ==============================================================================

class TestGetMountInfo:

    def test_returns_parsed_json(self, manager):
        fake_data = {"filesystems": [{"source": "/dev/sda1", "fstype": "btrfs", "uuid": "abc"}]}
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(fake_data).encode()

        with patch.object(manager, "_run", return_value=mock_result):
            info = manager._get_mount_info("/")
        assert info["source"] == "/dev/sda1"
        assert info["fstype"] == "btrfs"


# ==============================================================================
# _mount_btrfs_root (context manager)
# ==============================================================================

class TestMountBtrfsRoot:

    def test_mounts_and_unmounts_btrfs(self, manager, mock_mount_info_root):
        with patch.object(manager, "_get_mount_info", return_value=mock_mount_info_root), \
             patch("os.makedirs"), \
             patch.object(manager, "_run") as mock_run, \
             patch("os.path.ismount", return_value=True), \
             patch("os.rmdir"):
            with manager._mount_btrfs_root() as mnt:
                assert mnt == MOUNT_POINT
            # mount 호출 확인
            assert any("mount" in str(c) for c in mock_run.call_args_list)
            # umount 호출 확인
            assert any("umount" in str(c) for c in mock_run.call_args_list)

    def test_overlay_with_media_root_ro(self, manager, mock_mount_info_overlay, mock_mount_info_root):
        """OverlayFS 감지 시 /media/root-ro 에서 마운트 정보를 가져와야 합니다."""
        def side_effect(path):
            if path == "/":
                return mock_mount_info_overlay
            return mock_mount_info_root

        with patch.object(manager, "_get_mount_info", side_effect=side_effect), \
             patch("os.path.exists", return_value=True), \
             patch("os.makedirs"), \
             patch.object(manager, "_run"), \
             patch("os.path.ismount", return_value=False), \
             patch("os.rmdir"):
            with manager._mount_btrfs_root() as mnt:
                assert mnt == MOUNT_POINT

    def test_overlay_without_media_root_raises(self, manager, mock_mount_info_overlay):
        with patch.object(manager, "_get_mount_info", return_value=mock_mount_info_overlay), \
             patch("os.path.exists", return_value=False):
            with pytest.raises(SnapshotError, match="OverlayFS"):
                with manager._mount_btrfs_root():
                    pass

    def test_unmount_called_even_on_exception(self, manager, mock_mount_info_root):
        with patch.object(manager, "_get_mount_info", return_value=mock_mount_info_root), \
             patch("os.makedirs"), \
             patch.object(manager, "_run") as mock_run, \
             patch("os.path.ismount", return_value=True), \
             patch("os.rmdir"):
            with pytest.raises(RuntimeError):
                with manager._mount_btrfs_root():
                    raise RuntimeError("boom")
            assert any("umount" in str(c) for c in mock_run.call_args_list)


# ==============================================================================
# _sync_boot_if_needed
# ==============================================================================

class TestSyncBootIfNeeded:

    def test_syncs_when_separate_boot(self, manager, mock_mount_info_root, mock_mount_info_boot_separate):
        def side_effect(path):
            if path == "/boot":
                return mock_mount_info_boot_separate
            return mock_mount_info_root

        with patch.object(manager, "_get_mount_info", side_effect=side_effect), \
             patch("os.makedirs"), \
             patch.object(manager, "_run") as mock_run:
            manager._sync_boot_if_needed("/mnt/snap")
            assert any("rsync" in str(c) for c in mock_run.call_args_list)

    def test_no_sync_when_same_boot(self, manager, mock_mount_info_root):
        with patch.object(manager, "_get_mount_info", return_value=mock_mount_info_root), \
             patch.object(manager, "_run") as mock_run:
            manager._sync_boot_if_needed("/mnt/snap")
            assert not any("rsync" in str(c) for c in mock_run.call_args_list)


# ==============================================================================
# _scan_snapshots_internal
# ==============================================================================

class TestScanSnapshotsInternal:

    def _make_snap_dir(self, tmp_path, snap_name, kernel="vmlinuz-6.8.0-generic",
                       initrd="initrd.img-6.8.0-generic", snap_type=None):
        snap_dir = tmp_path / snap_name
        boot_dir = snap_dir / "boot"
        boot_dir.mkdir(parents=True)
        (boot_dir / kernel).write_text("kernel")
        (boot_dir / initrd).write_text("initrd")
        if snap_type:
            etc_dir = snap_dir / "etc"
            etc_dir.mkdir(exist_ok=True)
            (etc_dir / "btrfs-snap.info").write_text(f"TYPE={snap_type}\n")
        return snap_dir

    def test_finds_versioned_kernel_and_initrd(self, manager, tmp_path):
        self._make_snap_dir(tmp_path, "@snapshot-test")
        result = manager._scan_snapshots_internal(str(tmp_path))
        assert len(result) == 1
        assert result[0]["kernel_file"] == "vmlinuz-6.8.0-generic"
        assert result[0]["initrd_file"] == "initrd.img-6.8.0-generic"

    def test_falls_back_to_bare_vmlinuz(self, manager, tmp_path):
        self._make_snap_dir(tmp_path, "@snapshot-bare", kernel="vmlinuz", initrd="initrd.img")
        result = manager._scan_snapshots_internal(str(tmp_path))
        assert len(result) == 1
        assert result[0]["kernel_file"] == "vmlinuz"

    def test_skips_snapshot_without_kernel(self, manager, tmp_path):
        snap_dir = tmp_path / "@snapshot-nokernel" / "boot"
        snap_dir.mkdir(parents=True)
        (snap_dir / "initrd.img").write_text("initrd")
        result = manager._scan_snapshots_internal(str(tmp_path))
        assert len(result) == 0

    def test_reads_type_from_meta_file(self, manager, tmp_path):
        self._make_snap_dir(tmp_path, "@snapshot-sb", snap_type="sandbox")
        result = manager._scan_snapshots_internal(str(tmp_path))
        assert result[0]["type"] == "sandbox"

    def test_excludes_home_snapshots(self, manager, tmp_path):
        self._make_snap_dir(tmp_path, "@home_snapshot-test")
        result = manager._scan_snapshots_internal(str(tmp_path))
        assert len(result) == 0

    def test_multiple_snapshots(self, manager, tmp_path):
        self._make_snap_dir(tmp_path, "@snapshot-a")
        self._make_snap_dir(tmp_path, "@snapshot-b")
        result = manager._scan_snapshots_internal(str(tmp_path))
        assert len(result) == 2


# ==============================================================================
# create_snapshot
# ==============================================================================

class TestCreateSnapshot:

    def test_raises_on_invalid_mode(self, manager):
        with pytest.raises(ValueError, match="Invalid mode"):
            manager.create_snapshot(mode="invalid")

    def test_raises_if_at_subvol_missing(self, manager, mock_mount_info_root):
        with patch.object(manager, "_mount_btrfs_root") as mock_ctx, \
             patch("os.path.exists", return_value=False):
            mock_ctx.return_value.__enter__ = MagicMock(return_value="/mnt/btrfs_lib_root")
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            with pytest.raises(SnapshotError, match="Source subvolume"):
                manager.create_snapshot(mode="bootable")

    def test_bootable_snapshot_creates_subvols(self, manager):
        mnt = "/mnt/btrfs_lib_root"
        with patch.object(manager, "_mount_btrfs_root") as mock_ctx, \
             patch("os.path.exists", side_effect=lambda p: "@" in p or "fstab" not in p), \
             patch.object(manager, "_run") as mock_run, \
             patch.object(manager, "_sync_boot_if_needed"), \
             patch.object(manager, "enumerate_snapshots"), \
             patch("builtins.open", mock_open(read_data="subvol=@home ")), \
             patch("os.makedirs"):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mnt)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            manager.create_snapshot(mode="bootable", name="test")

            calls_str = [str(c) for c in mock_run.call_args_list]
            assert any("btrfs subvolume snapshot" in s and "@snapshot" in s for s in calls_str)
            assert any("btrfs subvolume snapshot" in s and "@home_snapshot" in s for s in calls_str)

    @pytest.mark.parametrize("mode", ["integrity", "sandbox"])
    def test_read_only_set_for_integrity_and_sandbox(self, manager, mode):
        mnt = "/mnt/btrfs_lib_root"
        with patch.object(manager, "_mount_btrfs_root") as mock_ctx, \
             patch("os.path.exists", side_effect=lambda p: "@" in p or "fstab" not in p), \
             patch.object(manager, "_run") as mock_run, \
             patch.object(manager, "_sync_boot_if_needed"), \
             patch.object(manager, "enumerate_snapshots"), \
             patch("builtins.open", mock_open(read_data="subvol=@home ")), \
             patch("os.makedirs"):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mnt)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            manager.create_snapshot(mode=mode)
            calls_str = [str(c) for c in mock_run.call_args_list]
            assert any("property set" in s and "ro true" in s for s in calls_str)

    def test_bootable_does_not_set_readonly(self, manager):
        mnt = "/mnt/btrfs_lib_root"
        with patch.object(manager, "_mount_btrfs_root") as mock_ctx, \
             patch("os.path.exists", side_effect=lambda p: "@" in p or "fstab" not in p), \
             patch.object(manager, "_run") as mock_run, \
             patch.object(manager, "_sync_boot_if_needed"), \
             patch.object(manager, "enumerate_snapshots"), \
             patch("builtins.open", mock_open(read_data="subvol=@home ")), \
             patch("os.makedirs"):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mnt)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            manager.create_snapshot(mode="bootable")
            calls_str = [str(c) for c in mock_run.call_args_list]
            assert not any("ro true" in s for s in calls_str)

    def test_fstab_updated_with_home_snapshot_name(self, manager):
        mnt = "/mnt/btrfs_lib_root"
        fstab_content = "UUID=xxx / btrfs defaults 0 0\nUUID=xxx /home btrfs subvol=@home 0 0\n"
        written = []

        m = mock_open(read_data=fstab_content)
        # write() 호출 내용을 캡처
        m.return_value.__enter__.return_value.write = lambda data: written.append(data)

        with patch.object(manager, "_mount_btrfs_root") as mock_ctx, \
                patch("os.path.exists", return_value=True), \
                patch.object(manager, "_run"), \
                patch.object(manager, "_sync_boot_if_needed"), \
                patch.object(manager, "enumerate_snapshots"), \
                patch("builtins.open", m), \
                patch("os.makedirs"):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mnt)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            snap_sys_name = manager.create_snapshot(mode="bootable", name="mysnap")

            # 반환값은 @snapshot-... 이어야 함
            assert snap_sys_name.startswith("@snapshot-mysnap-")

            # fstab에 기록된 내용에 @home_snapshot이 포함되어야 함
            fstab_written = "".join(written)
            expected_home_snap = snap_sys_name.replace("@snapshot", "@home_snapshot")
            assert expected_home_snap in fstab_written


# ==============================================================================
# delete_snapshot
# ==============================================================================

class TestDeleteSnapshot:

    def test_deletes_by_exact_name(self, manager):
        mnt = MOUNT_POINT
        snap_name = "@snapshot-2025-01-01-120000"

        with patch.object(manager, "_mount_btrfs_root") as mock_ctx, \
             patch("os.path.exists", return_value=True), \
             patch.object(manager, "_run") as mock_run, \
             patch.object(manager, "enumerate_snapshots"):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mnt)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            manager.delete_snapshot(snap_name)
            calls_str = [str(c) for c in mock_run.call_args_list]
            assert any("subvolume delete" in s and snap_name in s for s in calls_str)

    def test_raises_if_not_found(self, manager):
        mnt = MOUNT_POINT
        with patch.object(manager, "_mount_btrfs_root") as mock_ctx, \
             patch("glob.glob", return_value=[]):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mnt)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(SnapshotError, match="not found"):
                manager.delete_snapshot("nonexistent")

    def test_also_deletes_home_snapshot(self, manager):
        mnt = MOUNT_POINT
        snap_name = "@snapshot-2025-01-01-120000"
        home_name = "@home_snapshot-2025-01-01-120000"

        with patch.object(manager, "_mount_btrfs_root") as mock_ctx, \
             patch("os.path.exists", return_value=True), \
             patch.object(manager, "_run") as mock_run, \
             patch.object(manager, "enumerate_snapshots"):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mnt)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            manager.delete_snapshot(snap_name)
            calls_str = [str(c) for c in mock_run.call_args_list]
            assert any("subvolume delete" in s and home_name in s for s in calls_str)


# ==============================================================================
# restore_snapshot
# ==============================================================================

class TestRestoreSnapshot:

    def test_raises_if_booted_into_main_volume(self, manager):
        with patch.object(manager, "_get_mount_info",
                          return_value={"source": "/dev/sda1[/@]", "fstype": "btrfs", "uuid": "abc"}):
            with pytest.raises(SnapshotError, match="Cannot restore"):
                manager.restore_snapshot("@snapshot-test")

    def test_raises_if_snapshot_not_found(self, manager):
        mnt = MOUNT_POINT
        with patch.object(manager, "_get_mount_info",
                          return_value={"source": "/dev/sda1[/@snapshot-x]"}), \
             patch.object(manager, "_mount_btrfs_root") as mock_ctx, \
             patch("os.path.exists", return_value=False):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mnt)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(SnapshotError, match="not found"):
                manager.restore_snapshot("@snapshot-missing")

    def test_restores_sys_and_home(self, manager):
        mnt = MOUNT_POINT
        snap_name = "@snapshot-2025-01-01-120000"
        fstab_content = "subvol=@home_snapshot-2025-01-01-120000\n"

        with patch.object(manager, "_get_mount_info",
                          return_value={"source": "/dev/sda1[/@snapshot-x]"}), \
             patch.object(manager, "_mount_btrfs_root") as mock_ctx, \
             patch("os.path.exists", return_value=True), \
             patch.object(manager, "_run") as mock_run, \
             patch("builtins.open", mock_open(read_data=fstab_content)):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mnt)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            manager.restore_snapshot(snap_name)
            calls_str = [str(c) for c in mock_run.call_args_list]
            assert any("snapshot" in s and f"{mnt}/@" in s for s in calls_str)

    def test_fstab_subvol_restored_to_home(self, manager):
        mnt = MOUNT_POINT
        snap_name = "@snapshot-2025-01-01-120000"
        fstab_content = "subvol=@home_snapshot-2025-01-01-120000\n"
        written = []

        m = mock_open(read_data=fstab_content)
        m.return_value.write = lambda d: written.append(d)

        with patch.object(manager, "_get_mount_info",
                          return_value={"source": "/dev/sda1[/@snapshot-x]"}), \
             patch.object(manager, "_mount_btrfs_root") as mock_ctx, \
             patch("os.path.exists", return_value=True), \
             patch.object(manager, "_run"), \
             patch("builtins.open", m):
            mock_ctx.return_value.__enter__ = MagicMock(return_value=mnt)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            manager.restore_snapshot(snap_name)
            restored = "".join(written)
            assert "subvol=@home" in restored
            assert "subvol=@home_snapshot" not in restored


# ==============================================================================
# _reconstruct_grub
# ==============================================================================

class TestReconstructGrub:

    def test_integrity_snapshots_excluded(self, manager, sample_snapshots):
        root_dev = "/dev/sda1"

        with patch.object(manager, "_get_mount_info",
                          return_value={"source": f"{root_dev}[/@]"}), \
             patch("subprocess.check_output", return_value=b"1234-abcd"), \
             patch("builtins.open", mock_open(read_data="quiet splash")), \
             patch("os.chmod"), \
             patch.object(manager, "_run"):

            written = []
            m = mock_open()
            m.return_value.write = lambda d: written.append(d)

            with patch("builtins.open", m):
                manager._reconstruct_grub(MOUNT_POINT, sample_snapshots)

            content = "".join(written)
            assert "integrity" not in content.lower() or "Snapshot" not in content

    def test_sandbox_gets_overlayroot_arg(self, manager, sample_snapshots):
        with patch.object(manager, "_get_mount_info",
                          return_value={"source": "/dev/sda1[/@]"}), \
             patch("subprocess.check_output", return_value=b"1234-abcd"), \
             patch("os.chmod"), \
             patch.object(manager, "_run"):

            written_lines = []
            real_open = open

            def patched_open(path, mode='r', *args, **kwargs):
                if path == "/proc/cmdline":
                    return mock_open(read_data="quiet splash")()
                m = MagicMock()
                m.__enter__ = lambda s: s
                m.__exit__ = MagicMock(return_value=False)
                m.write = lambda d: written_lines.append(d)
                return m

            with patch("builtins.open", patched_open):
                manager._reconstruct_grub(MOUNT_POINT, sample_snapshots)

            content = "".join(written_lines)
            assert "overlayroot=tmpfs" in content

    def test_kernel_and_initrd_paths_in_grub(self, manager, sample_snapshots):
        bootable = [s for s in sample_snapshots if s["type"] == "bootable"]

        with patch.object(manager, "_get_mount_info",
                          return_value={"source": "/dev/sda1[/@]"}), \
             patch("subprocess.check_output", return_value=b"1234-abcd"), \
             patch("os.chmod"), \
             patch.object(manager, "_run"):

            written_lines = []

            def patched_open(path, mode='r', *args, **kwargs):
                if path == "/proc/cmdline":
                    return mock_open(read_data="quiet splash")()
                m = MagicMock()
                m.__enter__ = lambda s: s
                m.__exit__ = MagicMock(return_value=False)
                m.write = lambda d: written_lines.append(d)
                return m

            with patch("builtins.open", patched_open):
                manager._reconstruct_grub(MOUNT_POINT, sample_snapshots)

            content = "".join(written_lines)
            for snap in bootable:
                assert snap["kernel_file"] in content
                assert snap["initrd_file"] in content
