import sys
import argparse
import subprocess
import os

def main(args: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Mount RAM based filesystem")

    parser.add_argument("--path", required=True, help="Path to mount")
    parser.add_argument("--size", required=True, help="Size to assign (ex. 100M or 3G)")
    parser.add_argument("--mkdir", action="store_true", help="Create directory if it does not exist")
    parser.add_argument("--template", help="Template to build initial files from")
    parser.add_argument("--permission", help="Permission to set on the directory (ex. 0755), default is 2777")
    parser.add_argument("--allow-everyone-write", action="store_true", help="Removes ownership control, allows everyone to write.")
    opts = parser.parse_args(args)
    return make(opts.path, opts.size, opts.mkdir, opts.template, opts.permission if opts.permission else "2777", opts.allow_everyone_write)

def make(path: str, size: str, mkdir: bool, template: str, permission: str, allow_everyone_write: bool) -> int:
    if mkdir:
        subprocess.call(["mkdir", "-p", path])
        subprocess.call(["chmod", permission, path])
    
    mount_opts = f"size={size},mode={permission}"
    if allow_everyone_write:
        mount_opts += ",gid=1321" # vfsusers group

    mount_operation = subprocess.run(["mount", "-t", "tmpfs", "-o", mount_opts, "tmpfs", path])
    subprocess.call(["chmod", permission, path])

    if template:
        if not os.path.exists(f"/opt/aqua/share/vfstemplates/{template}.vfstemplate"):
            print(f"Template does not exist: {template}")
            return mount_operation.returncode
        # Copy template files to path
        print(f"Copying template '{template}' to '{path}'")
        subprocess.call(["cp", "-a", f"/opt/aqua/share/vfstemplates/{template}.vfstemplate/.", path])

    return mount_operation.returncode

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
