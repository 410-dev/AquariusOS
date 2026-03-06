
def help(session) -> str:
    return "Usage: User-List <bool: include_system_users>\nLists all users on the system."

# Return input string as bool
def main(session, include_system_users: bool) -> tuple[int, list[str]]:
    """
    excluded_users=("daemon" "bin" "sys" "sync" "games" "man" "lp" "mail" "news" "uucp" "proxy" "www-data" "backup" "list" "irc" "gnats" "nobody" "_apt" "systemd-network" "systemd-resolve" "systemd-timesync")
    getent passwd | while IFS=: read -r username _ uid _ _ _ _; do
        if [[ $uid -ge 1000 && ! " ${excluded_users[*]} " =~ " $username " ]]; then
            echo "$username"
        fi
    done    
    """

    excluded_users = ["daemon", "bin", "sys", "sync", "games", "man", "lp", "mail", "news", "uucp", "proxy", "www-data", "backup", "list", "irc", "gnats", "nobody", "_apt", "systemd-network", "systemd-resolve", "systemd-timesync"]
    result = []
    with open("/etc/passwd", "r") as f:
        for line in f:
            parts = line.split(":")
            if len(parts) < 3:
                continue

            username = parts[0]
            uid = int(parts[2])

            if uid >= 1000 and (username not in excluded_users or include_system_users):
                result.append(username)
                
    return 0, result

