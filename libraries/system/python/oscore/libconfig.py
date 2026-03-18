from collections import UserDict
import json
import os

class Config(UserDict):

    def __init__(self, path: str, user_local: bool = False, cascade: bool = False, cascade_prioritize_global: bool = False, logging: bool = False):
        super().__init__()

        # 처음 설정시에 로깅 함수를 설정함으로서 읽기쓰기 오버헤드의 분기문을 줄임
        # (if logging is True 를 항상 체크하지 않아도 됨)
        if logging:
            self._log = lambda message: print(f"[Config] {message}")
        else:
            self._log = lambda message: None

        # Directory traversal 공격 방지
        if ".." in path:
            raise ValueError("Path cannot contain '..'")

        # JSON 강제 확장자 추가
        if not path.endswith(".json"):
            path += ".json"

        # cascade_prioritize_global과 cascade 설정 검증
        # cascade_prioritize_global은 cascade 가 반드시 True 일 때만 사용 가능
        if cascade_prioritize_global and not cascade:
            raise ValueError("cascade_prioritize_global cannot be True if cascade is False")
        
        # user_local은 cascade가 True일 수 없음
        if user_local and cascade:
            raise ValueError("user_local cannot be True if cascade is True")
        
        home_path = "~/.config/" + path
        global_path = "/etc/" + path

        # cascade 모드
        if cascade:
            self._log(f"Cascade mode enabled. Prioritizing {'global' if cascade_prioritize_global else 'user local'} settings.")

            # a 가 있으면 a, 없으면 b 를 반환하는 함수 정의
            def get_path(priority: str, fallback: str) -> str:
                if os.path.isfile(priority):
                    self._log(f"Found config at {priority}")
                    return priority
                else:
                    self._log(f"Priority not found, using default path: {priority}")
                    return priority  # 기본적으로 우선순위 경로를 반환 (존재하지 않더라도)
            
            # cascade_prioritize_global이 True이면 /etc/에서 먼저 설정을 찾고, 그렇지 않으면 사용자의 홈 디렉토리에서 먼저 설정을 찾음
            if cascade_prioritize_global:
                # /etc/ 우선, 없으면 home으로 폴백
                self.path = get_path(global_path, home_path)
            else:
                # home 우선, 없으면 /etc/로 폴백
                self.path = get_path(home_path, global_path)

        # Cascade 모드가 아님
        else:
            self._log("Cascade mode disabled.")

            # user_local이 True이면 홈 디렉토리를 사용하고, 그렇지 않으면 /etc/를 사용
            if user_local:
                self._log("Using user local settings.")
                self.path = os.path.expanduser(home_path)
            else:
                self._log("Using global settings.")
                self.path = global_path

        self._log(f"Config path set to: {self.path}")

        self.data = {}

    def _log(self, message: str):
        pass
    
    def fetch(self) -> "Config":
        try:
            with open(self.path, "r") as f:
                self.data = json.load(f)
        except Exception as e:
            self.data = {}
        return self

    def sync(self) -> bool:
        try:
            with open(self.path, "w") as f:
                json.dump(self.data, f)
                return True
        except Exception as e:
            return False

    def to_str(self):
        return json.dumps(self.data, indent=4)
