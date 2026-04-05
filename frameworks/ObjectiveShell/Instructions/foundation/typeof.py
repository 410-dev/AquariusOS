def help(session) -> str:
    return "Usage: typeof <object>\nGets the type of the given object as a string."

# Return input string as int
def main(session, o) -> tuple[int, str]:
    return 0, type(o).__name__
