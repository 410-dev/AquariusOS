def help(session) -> str:
    return "Usage: codeblock <name> <block>\nRegisters a named codeblock in the session."


def main(session, name: str, block: list) -> int:
    if not isinstance(block, list):
        print(f"Error: codeblock requires a block.")
        return 1

    if "__codeblocks__" not in session.variables:
        session.variables["__codeblocks__"] = {}

    session.variables["__codeblocks__"][name] = block
    return 0