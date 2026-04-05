import os

def help(session) -> str:
    return "Usage: foreach\nIterate through a list and execute a command for each item. Use ${loop:index} and ${loop:item} in the command to access the current index and item."

def main(session) -> int:
    return 0

def _replace_loop_vars(s: str) -> str:
    return s \
        .replace("${loop:item}", "${var:__loop_item__}") \
        .replace("${loop:index}", "${var:__loop_index__}")

def udef_main(session, list_object: list, command_components: list):
    result = {}

    if not (len(command_components) == 1 and isinstance(command_components[0], list)):
        print("Error: foreach requires a block. Usage: foreach <list> { ... }")
        return result

    for i, item in enumerate(list_object):
        session.variables["__loop_item__"] = item
        session.variables["__loop_index__"] = i

        last_result = None
        for block_line in command_components[0]:
            tokens = session.parse_line(_replace_loop_vars(block_line))
            last_result = session.execute_line(tokens)
        result[i] = {
            "index": i,
            "item": item,
            "return_code": last_result.exit_code if last_result else 0,
            "output": last_result.returns if last_result else None
        }

    session.variables.pop("__loop_item__", None)
    session.variables.pop("__loop_index__", None)

    return result