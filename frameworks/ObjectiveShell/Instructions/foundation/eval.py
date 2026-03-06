
def help(session) -> str:
    return "Usage: eval <python expression>\nExecutes python expression."

def main(session, expr: str) -> tuple:
    try:
        result = eval(expr)
        return 0, result
    except Exception as err:
        return 1, str(err)