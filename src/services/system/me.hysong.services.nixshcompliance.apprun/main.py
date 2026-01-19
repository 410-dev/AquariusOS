import os
import stat
import pyinotify
from oscore import libreg as reg

# Configuration
TARGET_BIN_DIR = '/usr/local/sbin'
APPRUN_LAUNCHER = '/usr/local/sbin/apprun.sh'
REGISTRY_KEY = "HKEY_LOCAL_MACHINE/SYSTEM/Services/me.hysong.aqua/nixshcompliance/Prober"


def load_watch_dirs():
    """
    Reads the registry to find directories to watch.
    """
    watch_dirs = []
    try:
        # Read the key content to get value names and types
        key_content = reg.read(REGISTRY_KEY, default={})

        for value_name, value_type in key_content.items():
            # The prompt specifies we only care about 'str' typed values
            if value_type == 'str':
                # Construct path to the specific value to read the actual data
                # Assuming standard registry path syntax (Key/ValueName)
                full_value_path = f"{REGISTRY_KEY}/{value_name}"
                dir_path = reg.read(full_value_path)

                if dir_path and isinstance(dir_path, str):
                    if os.path.exists(dir_path):
                        watch_dirs.append(dir_path)
                    else:
                        print(f"Warning: Registry path does not exist on disk: {dir_path}")

    except Exception as e:
        print(f"Error reading registry: {e}")

    return watch_dirs


def create_symlink(source, filename):
    """Creates a symlink in TARGET_BIN_DIR pointing to source."""
    destination = os.path.join(TARGET_BIN_DIR, filename)

    # drop if destination has .sh at the end
    if destination.endswith(".sh"):
        destination = destination[:-len(".sh")]

    elif destination.endswith(".py"):
        destination = destination[:-len(".py")]

    # If destination exists
    if os.path.lexists(destination):
        # If it's a broken link, remove it so we can re-link it
        if os.path.islink(destination) and not os.path.exists(destination):
            try:
                os.unlink(destination)
                print(f"Removed broken link: {destination}")
            except OSError as e:
                print(f"Failed to remove broken link {destination}: {e}")
                return
        else:
            # Valid file/link already exists, skip
            return

    try:
        os.symlink(source, destination)
        print(f"Symlink created: {destination} -> {source}")
    except OSError as e:
        print(f"Failed to create symlink for {source}: {e}")


def create_apprun_wrapper(source_dir, dirname):
    """Creates a wrapper script for .apprun directories."""
    executable_name = dirname.replace('.apprun', '')
    destination = os.path.join(TARGET_BIN_DIR, executable_name)

    if os.path.exists(destination):
        return

    script_content = f"""#!/bin/bash
{APPRUN_LAUNCHER} "{source_dir}" "$@"
"""
    try:
        with open(destination, 'w') as f:
            f.write(script_content)

        st = os.stat(destination)
        os.chmod(destination, st.st_mode | stat.S_IEXEC)
        print(f"Apprun wrapper created: {destination} pointing to {source_dir}")

    except OSError as e:
        print(f"Failed to create wrapper for {source_dir}: {e}")


def cleanup_broken_links():
    """
    Scans TARGET_BIN_DIR and removes symbolic links that point to non-existent files.
    """
    if not os.path.exists(TARGET_BIN_DIR):
        return

    print("Scanning for broken symlinks...")
    for filename in os.listdir(TARGET_BIN_DIR):
        filepath = os.path.join(TARGET_BIN_DIR, filename)

        # Check if it is a link and if the target exists
        if os.path.islink(filepath):
            if not os.path.exists(filepath):
                try:
                    os.unlink(filepath)
                    print(f"Cleaned up broken symlink: {filepath}")
                except OSError as e:
                    print(f"Failed to delete broken symlink {filepath}: {e}")


def initial_scan(watch_dirs):
    """
    Scans the watch directories at startup to register existing files.
    """
    print("Performing initial scan of directories...")
    for directory in watch_dirs:
        try:
            for item in os.listdir(directory):
                full_path = os.path.join(directory, item)

                # Case 1: .sh executable
                if not os.path.isdir(full_path) and item.endswith('.sh'):
                    if os.access(full_path, os.X_OK):
                        create_symlink(full_path, item)

                # Case 2: .apprun directory
                elif os.path.isdir(full_path) and item.endswith('.apprun'):
                    create_apprun_wrapper(full_path, item)

                # Case 3: .py executable
                elif not os.path.isdir(full_path) and item.endswith('.py'):
                    # Check if it starts with shebang
                    with open(full_path, 'r') as f:
                        first_line = f.readline()
                        if first_line.startswith('#!') and 'python' in first_line:
                            create_symlink(full_path, item)
                            # Set executable
                            os.chmod(full_path, os.stat(full_path).st_mode | stat.S_IEXEC)


        except OSError as e:
            print(f"Error scanning directory {directory}: {e}")


class ChangeHandler(pyinotify.ProcessEvent):
    def process_IN_MOVED_TO(self, event):
        self._process_event(event)

    def process_IN_CLOSE_WRITE(self, event):
        self._process_event(event)

    def process_IN_ATTRIB(self, event):
        self._process_event(event)

    def _process_event(self, event):
        filename = event.name
        filepath = event.pathname

        if not os.path.exists(filepath):
            return

        if not event.dir and filename.endswith('.sh'):
            if os.access(filepath, os.X_OK):
                create_symlink(filepath, filename)

        elif event.dir and filename.endswith('.apprun'):
            create_apprun_wrapper(filepath, filename)

        elif not event.dir and filename.endswith('.py'):
            with open(filepath, 'r') as f:
                first_line = f.readline()
                if first_line.startswith('#!') and 'python' in first_line:
                    create_symlink(filepath, filename)
                    os.chmod(filepath, os.stat(filepath).st_mode | stat.S_IEXEC)

def main():
    # 1. Load configuration from Registry
    watch_dirs = load_watch_dirs()

    if not watch_dirs:
        print("No valid directories found in registry. Exiting.")
        return

    # 2. Clean up broken links in the target directory
    cleanup_broken_links()

    # 3. Scan existing files in watch dirs and create links/wrappers if missing
    initial_scan(watch_dirs)

    # 4. Start the inotify monitor
    wm = pyinotify.WatchManager()
    mask = pyinotify.IN_MOVED_TO | pyinotify.IN_CLOSE_WRITE | pyinotify.IN_ATTRIB

    handler = ChangeHandler()
    notifier = pyinotify.Notifier(wm, handler)

    print("\nStarting AquariusOS Directory Monitor...")

    for directory in watch_dirs:
        wm.add_watch(directory, mask, rec=False)
        print(f"Watching: {directory}")

    try:
        notifier.loop()
    except KeyboardInterrupt:
        print("\nStopping monitor.")


if __name__ == '__main__':
    main()
