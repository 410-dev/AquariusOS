
def help(session) -> str:
    return "Usage: float <number_string>\nConverts the given string to a float."

# Return input string as float
def main(session, num: str) -> tuple[int, float]:
    return 0, float(num)

