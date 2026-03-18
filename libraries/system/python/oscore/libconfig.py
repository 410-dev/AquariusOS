from collections import UserDict
import json
import os

class Config(UserDict):

    def __init__(self, path: str, user_local: bool = False, cascade_merge_mode: bool = False, cascade: bool = False, cascade_priorities: list[str] = None, cascade_priority_write_index: int = 0, logging: bool = False):
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

        # 기본 경로 설정
        home_path: str = os.path.expanduser("~/.config/" + path)
        global_path: str = "/etc/" + path

        # cascade 설정 검증
        # cascade_merge_mode 가 True 이면 cascade 도 True 여야 함
        if cascade_merge_mode and not cascade:
            self._log("cascade_merge_mode is True but cascade is False. Enabling cascade mode.")
            cascade = True
        
        # user_local은 cascade가 True일 수 없음
        if user_local and cascade:
            raise ValueError("user_local cannot be True if cascade (or cascade_merge_mode) is True")

        # 전역변수 초기화
        self.path: str = None
        self.cascade_merge_priorities: list[str] = None
        self.cascade_merge_index: int = cascade_priority_write_index
        self.data: dict = {}

        # cascade 모드
        if cascade:

            # cascade_priorities 검증
            self._log("Validating cascade related settings...")
            if (cascade_merge_mode or cascade) and (cascade_priorities is None or len(cascade_priorities) == 0):
                cascade_priorities = [home_path, global_path] # 기본 우선순위 설정
            if len(cascade_priorities) != len(set(cascade_priorities)): # 중복 경로 검증
                raise ValueError("cascade_priorities cannot contain duplicate paths")
            if len(cascade_priorities) <= cascade_priority_write_index: # cascade_priority_write_index 의 범위 유효성 검증
                raise ValueError("cascade_priority_write_index must be less than the number of cascade_priorities")

            self._log(f"Cascade mode enabled. Prioritizing in order: {cascade_priorities}")

            # Cascade Merge 모드
            if cascade_merge_mode:
                self._log("Cascade merge mode enabled. Will merge configurations from all existing files in cascade_priorities.")
                self.cascade_merge_priorities = cascade_priorities

                # 실제 Implementation 치환
                self.fetch = lambda: _fetch_cascade_merge(self)
                self.sync = lambda: _sync_cascade_merge(self)
            
            # 일반 Cascade 모드
            else:
                self._log("Cascade mode enabled without merge. Will use the first existing config file found in cascade_priorities.")
                # cascade_priorities 에서 첫 번째로 존재하는 파일을 사용하도록 설정
                for priority in cascade_priorities:
                    if os.path.isfile(priority):
                        self._log(f"Config file found at {priority}. Using this path.")
                        self.path = priority
                        break

                # 만약 지정된 path 가 존재하지 않으면 (둘 다 파일이 없으면) priority 로 설정
                if self.path is None:
                    default = cascade_priorities[cascade_priority_write_index]
                    self._log(f"No config file found. Falling back to write index path: {default}")
                    self.path = default
                
                # 실제 Implementation 치환
                # cascade 모드에서는 fetch() 와 sync() 가 일반 모드와 동일하게 동작하지만, path 가 cascade_priorities 에서 결정된다는 점이 다름
                self.fetch = lambda: _fetch_general(self)
                self.sync = lambda: _sync_general(self)
            

        # Cascade 모드가 아님
        else:
            self._log("Cascade mode disabled.")

            # user_local이 True이면 홈 디렉토리를 사용하고, 그렇지 않으면 /etc/를 사용
            if user_local:
                self._log("Using user local settings.")
                self.path = home_path
            else:
                self._log("Using global settings.")
                self.path = global_path

            # 실제 Implementation 치환
            self.fetch = lambda: _fetch_general(self)
            self.sync = lambda: _sync_general(self)

        self._log(f"Config path set to: {self.path}")


    def _log(self, message: str):
        pass
    
    # Fallback 용으로 노출
    def fetch(self) -> "Config":
        try:
            with open(self.path, "r") as f:
                self.data = json.load(f)
        except Exception as e:
            self.data = {}
        return self

    # Fallback 용으로 노출
    def sync(self) -> bool:
        try:
            with open(self.path, "w") as f:
                json.dump(self.data, f)
                return True
        except Exception as e:
            return False

    def to_str(self):
        return json.dumps(self.data, indent=4)\
        
# ====
# 실제 fetch 구현
# ====
def _fetch_general(self) -> "Config":
    try:
        with open(self.path, "r") as f:
            self.data = json.load(f)
    except Exception as e:
        self.data = {}
    return self


# 사실상 path 가 정해지기 때문에 일반 fetch 와 동일
# 실제 클래스에서는 _fetch_general 을 fetch 로 노출
# def _fetch_cascade(self) -> "Config":
#     pass

def _fetch_cascade_merge(self) -> "Config":
    merged_data = {}
    for priority in self.cascade_merge_priorities[::-1]: # 우선순위가 높은 파일이 나중에 덮어쓰도록 역순으로 처리
        if os.path.isfile(priority):
            try:
                with open(priority, "r") as f:
                    data = json.load(f)
                    merged_data.update(data)
            except Exception as e:
                continue
    self.data = merged_data
    return self

# ====
# 실제 sync 구현
# ====
def _sync_general(self) -> bool:
    try:
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=4) # JSON 파일을 사람이 읽기 좋게 들여쓰기
            return True
    except Exception as e:
        return False
    
# 사실상 path 가 정해지기 때문에 일반 sync 와 동일
# 실제 클래스에서는 _sync_general 을 sync 로 노출
# def _sync_cascade(self) -> bool:
#     pass

def _sync_cascade_merge(self) -> bool:
    # cascade_merge 모드에서는 사용자가 정한 우선순위에 모두 쓰는 방식으로 구현
    target_path = self.cascade_merge_priorities[self.cascade_merge_index]
    try:
        with open(target_path, "w") as f:
            json.dump(self.data, f, indent=4) # JSON 파일을 사람이 읽기 좋게 들여쓰기
            return True
    except Exception as e:
        return False
