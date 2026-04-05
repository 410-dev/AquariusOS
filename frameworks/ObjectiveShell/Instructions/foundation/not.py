def help(session) -> str:
    return "Usage: not <value>\nReturns the boolean negation of the value."

def main(session, o=None) -> tuple[int, bool]:
    if isinstance(o, bool):
        return 0, not o
    if isinstance(o, str):
        return 0, o.lower() != "true"
    if isinstance(o, int):
        return 0, o != 0
    return 0, o is None
