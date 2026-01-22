#!/bin/env python3

# Keys to read:
# HKLM(or CU)/SOFTWARE/Services/MoTD/NextOnly/*
# HKLM(or CU)/SOFTWARE/Services/MoTD/Persist/*

# Key structures
# <Hive (HKLM/HKCU)>/SOFTWARE/Services/MoTD/<Keeping type>/<Alert type (Noti/Popup)>/<Message type (Info/Warning/Error)>/<any> = <Message>
# Keeping type: NextOnly, Persist
# Alert type: Noti, Popup
# Message type: Info, Warning, Error

from oscore import libreg as reg

import os
import subprocess

def main():
    base_path = "SOFTWARE/Services/MoTD"
    hives = ["HKEY_LOCAL_MACHINE", "HKEY_CURRENT_USER"]
    keep_types = ["NextOnly", "Persist"]
    alert_types = ["Noti", "Popup"]
    message_types = ["Info", "Warning", "Error", "Message"]

    notifs: list[dict] = []
    popups: list[dict] = []

    # Load messages from registry
    for hive in hives:
        for keep_type in keep_types:
            for alert_type in alert_types:
                for message_type in message_types:
                    key_path = f"{hive}/{base_path}/{keep_type}/{alert_type}/{message_type}"
                    print(f"Reading messages from: {key_path}")
                    try:
                        messages: dict[str, str] = reg.read(key_path, None)
                        print(f"Messages found: {messages}")
                        if messages is None:
                            continue
                        for name, val_type in messages.items():
                            if val_type != "str":
                                continue
                            message: str = reg.read(f"{key_path}/{name}", "")
                            entry = {
                                "Location": f"{key_path}/{name}",
                                "KeepType": keep_type,
                                "MessageType": message_type,
                                "Message": message
                            }
                            if alert_type == "Noti":
                                notifs.append(entry)
                            elif alert_type == "Popup":
                                popups.append(entry)
                    except Exception:
                        continue

    # For each notification, display it
    # If zenity is available, use it for popups
    zenity_path = "/usr/bin/zenity"
    zenity_available = os.path.isfile(zenity_path) and os.access(zenity_path, os.X_OK)

    if zenity_available:
        for popup in popups:
            message = popup["Message"]
            message_type = popup["MessageType"]
            if message_type == "Info" or message_type == "Message":
                subprocess.run([zenity_path, "--info", "--text", message])
            elif message_type == "Warning":
                subprocess.run([zenity_path, "--warning", "--text", message])
            elif message_type == "Error":
                subprocess.run([zenity_path, "--error", "--text", message])
            if popup["KeepType"] == "NextOnly":
                # Remove the message from registry
                location = popup["Location"]
                try:
                    reg.delete(location)
                except Exception:
                    print(f"Failed to delete registry key: {location}")
                    pass

        for notif in notifs:
            message = notif["Message"]
            message_type = notif["MessageType"]
            if message_type == "Message":
                subprocess.run([zenity_path, "--notification", "--text", message])
            else:
                subprocess.run([zenity_path, "--notification", "--text", f"{message_type}: {message}"])
            if notif["KeepType"] == "NextOnly":
                # Remove the message from registry
                location = notif["Location"]
                try:
                    reg.delete(location)
                except Exception:
                    print(f"Failed to delete registry key: {location}")
                    pass

    else:
        def print_message(etr: dict):
            msg = etr["Message"]
            msgt = etr["MessageType"]
            print(f"{msgt}: {msg}")
            if etr["KeepType"] == "NextOnly":
                # Remove the message from registry
                l = etr["Location"]
                try:
                    reg.delete(l)
                except Exception:
                    print(f"Failed to delete registry key: {l}")
                    pass

        for popup in popups:
            print_message(popup)

        for notif in notifs:
            print_message(notif)

main()
