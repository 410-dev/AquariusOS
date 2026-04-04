import os

def help(session) -> str:
    return "Usage: foreach\nIterate through a list and execute a command for each item. Use ${loop:index} and ${loop:item} in the command to access the current index and item."

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

    for i, item in enumerate(list_object):
        # This is old code
        # current_command_line = command_line.replace("${loop:index}", str(i)).replace("${loop:item}", str(item))
        # cmd_result = session.execute_line(session.parse_line(current_command_line.strip()))

        # Code below is patched by Claude
        cmd_tokens = [
            item if token == "${loop:item}" else token
            for token in command_components
        ]
        cmd_result = session.execute_line(cmd_tokens)

        # This is universal
        result[item] = {
            "return_code": cmd_result.exit_code,
            "output": cmd_result.returns
        }

    return result
