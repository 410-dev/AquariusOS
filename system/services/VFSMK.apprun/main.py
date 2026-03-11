
import subprocess

from oscore import libapplog as log
from oscore import libreg as reg

from AppContext import AppContext

def main():
    log.info("VFSMK service started.")
    log.info(f"AppContext: id={AppContext().id()}, bundle_id={AppContext().id()}, box={AppContext().box()}")
    
    exec_py = "{{SYS_CMDS}}/mkvfs.py"
    mnt_pty = "{{AQUA_VFS_ROOT}}"
    sz = reg.read("/SYSTEM/Services/Aqua/VFSMK/SizeMB", 2048)
    try:
        sz = int(sz)
    except Exception as e:
        log.error(f"Invalid size value in registry: {sz}, using default 2048MB")
        sz = 2048

    cmd = f"/usr/bin/python3 {exec_py} --path={mnt_pty} --size={sz}M --mkdir --template=SYS1 --permission=2777"
    
    log.info("Using shell, calling '{{SYS_CMDS}}/mkvfs.py' to create VFS mount point at {{AQUA_VFS_ROOT}}.")
    log.info(f"-> Command: {cmd}")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        log.error(f"Failed to create VFS mount point at {mnt_pty} with size {sz}MB. Return code: {ret}")
        return
    log.info(f"VFS mount point created at {mnt_pty} with size {sz}MB.")


if __name__ == "__main__":
    main()
