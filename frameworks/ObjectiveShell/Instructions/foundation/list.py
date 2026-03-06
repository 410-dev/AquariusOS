
def help(session) -> str:
    return "Usage: list <delimiter> <list string>\nConverts the given string to a list using the specified delimiter."

# Return input string as bool
def main(session, deli: str, data: str) -> tuple[int, list[str]]:
    return 0, data.split(deli)

