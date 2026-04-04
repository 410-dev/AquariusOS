import os

def help(session) -> str:
    return "Usage: foreach\nIterate through a list and execute a command for each item. Use ${loop:index} and ${loop:item} in the command to access the current index and item."

def main(session) -> int:
    return 0 # Not available.

# Return input string as bool
def udef_main(session, list_object: list, command_components: list):
    result = {}

    for i, item in enumerate(list_object):
        # command_components가 블록(list[str])인지 단일 명령(list[token])인지 구분
        if len(command_components) == 1 and isinstance(command_components[0], list):
            # 블록 모드
            block_lines = command_components[0]
            last_result = None
            for block_line in block_lines:
                current_line = block_line \
                    .replace("${loop:index}", str(i)) \
                    .replace("${loop:item}", str(item))
                cmd_result = session.execute_line(session.parse_line(current_line.strip()))
                last_result = cmd_result
            result[item] = {
                "return_code": last_result.exit_code if last_result else 0,
                "output": last_result.returns if last_result else None
            }
        else:
            # 기존 단일 명령 모드 (버그 1 수정 버전)
            cmd_tokens = [
                item if token == "${loop:item}" else
                i if token == "${loop:index}" else
                token
                for token in command_components
            ]
            cmd_result = session.execute_line(cmd_tokens)
            result[item] = {
                "index": i,
                "item": item,
                "return_code": cmd_result.exit_code,
                "output": cmd_result.returns
            }

    return result