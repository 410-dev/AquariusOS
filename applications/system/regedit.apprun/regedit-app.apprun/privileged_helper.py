#!/usr/bin/env python3
import sys
import json
import os
import shutil
from pathlib import Path

def main():
    """
    Listens for JSON commands on stdin and executes them with root privileges.
    Communicates results back via stdout.
    """
    for line in sys.stdin:
        try:
            command = json.loads(line)
            action = command.get("action")
            
            if action == "exit":
                break

            # A simple router for filesystem commands
            if action == "mkdir":
                Path(command["path"]).mkdir(parents=False, exist_ok=False)
            elif action == "rmtree":
                shutil.rmtree(command["path"])
            elif action == "rename":
                Path(command["src"]).rename(command["dst"])
            elif action == "unlink":
                Path(command["path"]).unlink(missing_ok=True)
            elif action == "write_text":
                Path(command["path"]).write_text(command["content"], encoding="utf-8")
            else:
                raise ValueError(f"Unknown action: {action}")

            # Send success response
            print(json.dumps({"status": "ok"}), flush=True)

        except Exception as e:
            # Send error response
            print(json.dumps({"status": "error", "message": str(e)}), flush=True)

if __name__ == "__main__":
    # Ensure this script is run with euid 0 (as root)
    if os.geteuid() != 0:
        print(json.dumps({"status": "error", "message": "Helper must be run as root."}), flush=True)
        sys.exit(1)
    main()
    