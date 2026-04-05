from typing import Any

def help(session) -> str:
    return "Usage: item <key: str,int> <object: iterable,dictionary>\nGets item from an iterable or dictionary"

# Return input string as int
def main(session, key: str|int, o) -> tuple[int, Any]:

    if isinstance(o, dict):
        return 0, o.get(key)
    elif isinstance(o, (list, tuple)):
        try:
            index = int(key)
            return 0, o[index]
        except (ValueError, IndexError):
            return 1, None
    else:
        return 1, None


