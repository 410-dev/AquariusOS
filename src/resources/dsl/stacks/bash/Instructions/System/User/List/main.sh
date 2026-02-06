#!/bin/bash

excluded_users=("daemon" "bin" "sys" "sync" "games" "man" "lp" "mail" "news" "uucp" "proxy" "www-data" "backup" "list" "irc" "gnats" "nobody" "_apt" "systemd-network" "systemd-resolve" "systemd-timesync")
getent passwd | while IFS=: read -r username _ uid _ _ _ _; do
    if [[ $uid -ge 1000 && ! " ${excluded_users[*]} " =~ " $username " ]]; then
        echo "$username"
    fi
done
