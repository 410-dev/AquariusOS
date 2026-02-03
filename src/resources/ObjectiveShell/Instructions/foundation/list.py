
def help(session) -> str:
    return "Usage: list <delimiter> <list string>\nConverts the given string to a list using the specified delimiter."

# Return input string as bool
def main(session, deli: str, data: str) -> list:
    return data.split(deli)

