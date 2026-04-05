def help(session) -> str:
    return "Usage: isNull <value>\nReturns true if the value is None."

def main(session, o=None) -> tuple[int, bool]:
    return 0, o is None