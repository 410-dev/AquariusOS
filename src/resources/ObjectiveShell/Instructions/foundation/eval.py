
def help(session) -> str:
    return "Usage: eval <python expression>\nExecutes python expression."

def main(session, expr: str):
    return eval(expr)
