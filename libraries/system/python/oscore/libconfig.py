from collections import UserDict
import json
import os

class Config(UserDict):

    def __init__(self, path: str, user_local: bool = False, cascade: bool = False, cascade_prioritize_global: bool = False, logging: bool = False):
        super().__init__()

        # Assign logging function if logging is enabled, otherwise assign a no-op function
        if logging:
            self._log = lambda message: print(f"[Config] {message}")

        # Validate the path to prevent directory traversal attacks
        if ".." in path:
            raise ValueError("Path cannot contain '..'")

        # Ensure the path ends with .json
        if not path.endswith(".json"):
            path += ".json"

        # Validate cascade_prioritize_global and cascade settings
        if cascade_prioritize_global and not cascade:
            raise ValueError("cascade_prioritize_global cannot be True if cascade is False")
        
        # user_local cannot be true if cascade is True
        if user_local and cascade:
            raise ValueError("user_local cannot be True if cascade is True")
        
        home_path = "~/.config/" + path
        global_path = "/etc/" + path

        # Load the config file based on the cascade and user_local settings
        if cascade:
            # Try to look up the config in the user's home directory first
            
            if os.path.isfile(os.path.expanduser(home_path)):
                self.path = os.path.expanduser(home_path)

            # If cascade_prioritize_global is True, look up the config in /etc/ first
            elif os.path.isfile(global_path):
                self.path = global_path

            # If not exists in either location, default to the user's home directory if cascade_prioritize_global is False, otherwise default to /etc/
            else:
                if cascade_prioritize_global:
                    self.path = global_path
                else:
                    self.path = os.path.expanduser(home_path)

        # Not cascade mode
        else:

            # If user_local is True, look up the config in the user's home directory, otherwise look up the config in /etc/
            if user_local:
                self.path = os.path.expanduser(home_path)
            else:
                self.path = global_path

        self.data = {}

    def _log(self, message: str):
        pass
    
    def read(self) -> "Config":
        try:
            with open(self.path, "r") as f:
                self.data = json.load(f)
        except Exception as e:
            self.data = {}
        return self

    def write(self) -> bool:
        try:
            with open(self.path, "w") as f:
                json.dump(self.data, f)
                return True
        except Exception as e:
            return False

    def to_str(self):
        return json.dumps(self.data, indent=4)
