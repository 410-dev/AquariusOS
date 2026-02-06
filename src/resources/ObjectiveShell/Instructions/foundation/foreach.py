import os

def help(session) -> str:
    return "Usage: about\nShows about this system"

def main(session) -> int:
    return 0 # Not available.

# Return input string as bool
def udef_main(session, list_object: list, command_components: list) -> dict:
    result: dict = {}

    # Merge command components back to a single string
    command_line = ""
    for index, i in enumerate(command_components):
        if index == 0:
            command_line = i + " "
        else:
            command_line += f"\"{i}\" "
        # print(f"cmdc[{index}] = {i}")

    for i, item in enumerate(list_object):
        # print(f"i={i} , it = {item}")
        current_command_line = command_line.replace("${loop:index}", str(i)).replace("${loop:item}", str(item))
        # print(f"cmdl: {current_command_line}")
        cmd_result = session.execute_line(session.parse_line(current_command_line.strip()))
        result[item] = {
            "return_code": cmd_result.exit_code,
            "output": cmd_result.returns
        }

    return result
