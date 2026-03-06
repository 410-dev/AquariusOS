
def help(session) -> str:
    return "Usage: bool <number_string>\nConverts the given string to a bool."

# Return input string as bool
def main(session, num: str) -> tuple[int, bool]:
    return 0, bool(num)

