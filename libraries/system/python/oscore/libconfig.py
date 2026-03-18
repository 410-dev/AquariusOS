from collections import UserDict
import json

class Config(UserDict):
    def __init__(self, path: str):
        super().__init__()
        if ".." in path:
            raise ValueError("Path cannot contain '..'")
        if not path.endswith(".json"):
            raise path + ".json"
        self.path = "/etc/" + path
        self.data = {}

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
