#!/usr/bin/env python3
import os
import pwd
import subprocess
import tkinter as tk
from tkinter import messagebox

# ---------------------------
# CONFIGURATION SECTION
# ---------------------------

EXCLUDED_USERS = {
    "daemon", "bin", "sys", "sync", "games", "man", "lp", "mail", "news", "uucp",
    "proxy", "www-data", "backup", "list", "irc", "gnats", "nobody", "_apt",
    "systemd-network", "systemd-resolve", "systemd-timesync"
}

SCRIPT_PATH = "/usr/local/sbin/apprun.sh"
APP_PATH = "/opt/aqua/sys/applications/regedit.apprun/regedit-app.apprun"


# ---------------------------
# FUNCTIONAL IMPLEMENTATION
# ---------------------------

def get_system_users():
    """Return a list of conventional users (UID ≥ 1000) + root."""
    users = []
    for user in pwd.getpwall():
        if user.pw_uid >= 1000 and user.pw_name not in EXCLUDED_USERS:
            users.append(user.pw_name)
        elif user.pw_name == "root":
            users.append("root")
    return sorted(users)


def run_as_user(selected_user):
    """Run the apprun.sh script as selected user, preserving DISPLAY and XAUTHORITY."""
    display = os.environ.get("DISPLAY")
    xauthority = os.environ.get("XAUTHORITY", os.path.expanduser("~/.Xauthority"))

    if not display:
        messagebox.showerror("Error", "DISPLAY environment variable not set.")
        return
    
    # If current user, no need to use pkexec
    if selected_user == os.getlogin():
        command = [SCRIPT_PATH, APP_PATH]
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", f"Failed to run script as {selected_user}")
        except FileNotFoundError:
            messagebox.showerror("Error", f"Script not found at {SCRIPT_PATH}")
        exit(0)

    # Prepare the environment-preserving command
    command = [
        "pkexec", "--user", selected_user,
        "env",
        f"DISPLAY={display}",
        f"XAUTHORITY={xauthority}",
        SCRIPT_PATH, APP_PATH
    ]

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError:
        messagebox.showerror("Error", f"Failed to run script as {selected_user}")
    except FileNotFoundError:
        messagebox.showerror("Error", f"Script not found at {SCRIPT_PATH}")
    exit(0)


def main():
    root = tk.Tk()
    root.title("Run Registry Editor As User")
    root.geometry("400x400")
    root.resizable(False, False)

    tk.Label(root, text="Select User to Run As", font=("Arial", 14, "bold")).pack(pady=10)

    users = get_system_users()
    if not users:
        messagebox.showerror("Error", "No valid users found.")
        root.destroy()
        return

    for user in users:
        tk.Button(
            root, text=user, width=20, height=2,
            command=lambda u=user: run_as_user(u)
        ).pack(pady=5)

    root.mainloop()


if __name__ == "__main__":
    main()
