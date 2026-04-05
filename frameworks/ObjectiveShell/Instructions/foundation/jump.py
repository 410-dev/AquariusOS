def help(session) -> str:
    return (
        "Usage: jump <name> [if <condition> [and|or <condition> ...]]\n"
        "Jumps to a named codeblock if the condition is true.\n"
        "Conditions can be grouped with [] for precedence.\n"
        "Example: jump my_block if $(isNull ${var:result})\n"
        "Example: jump my_block if [$(isNull ${var:result}) and $(isNull ${var:x})] or $(some_condition)"
    )

def _is_truthy(value) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 0  # exit code 기준
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)

def _evaluate_conditions(tokens: list) -> bool:
    """
    tokens 예시:
    [<val>, "and", <val2>]
    ["[", <val>, "and", <val2>, "]", "or", <val3>]
    """
    # 1. [] 그룹 먼저 평가 (단일 depth)
    while "[" in tokens:
        start = tokens.index("[")
        end = tokens.index("]")
        group_result = _evaluate_flat(tokens[start + 1:end])
        tokens = tokens[:start] + [group_result] + tokens[end + 1:]

    # 2. 나머지 평가
    return _evaluate_flat(tokens)

def _evaluate_flat(tokens: list) -> bool:
    """
    괄호 없는 단순 and/or 평가. 왼쪽에서 오른쪽으로.
    """
    if not tokens:
        return True

    result = _is_truthy(tokens[0])
    i = 1
    while i < len(tokens):
        op = tokens[i]
        if i + 1 >= len(tokens):
            break
        next_val = _is_truthy(tokens[i + 1])
        if op == "and":
            result = result and next_val
        elif op == "or":
            result = result or next_val
        i += 2

    return result

def _run_block(session, name: str, block: list):
    from oscore import objectiveshell

    def _replace_loop_vars(s: str) -> str:
        return s \
            .replace("${loop:item}", "${var:__loop_item__}") \
            .replace("${loop:index}", "${var:__loop_index__}")

    last_result = objectiveshell.ExecResult(0, None)
    for line in block:
        tokens = session.parse_line(_replace_loop_vars(line))

        # <name> return <value> 감지
        if len(tokens) >= 2 and str(tokens[0]) == name and str(tokens[1]) == "return":
            value = tokens[2] if len(tokens) > 2 else None
            return objectiveshell.ExecResult(0, value)

        last_result = session.execute_line(tokens)

    return objectiveshell.ExecResult(last_result.exit_code, last_result.returns)

def main(session, name: str, *args) -> object:
    from oscore import objectiveshell

    # 코드블록 존재 확인
    codeblocks = session.variables.get("__codeblocks__", {})
    if name not in codeblocks:
        print(f"Error: codeblock '{name}' not found.")
        return objectiveshell.ExecResult(1, None)

    block = codeblocks[name]

    # 조건 없으면 무조건 실행
    if not args:
        return _run_block(session, name, block)

    # "if" 확인
    if args[0] != "if":
        print(f"Error: expected 'if' after block name, got '{args[0]}'")
        return objectiveshell.ExecResult(1, None)

    condition_tokens = list(args[1:])

    # 조건 평가
    if _evaluate_conditions(condition_tokens):
        return _run_block(session, name, block)

    return objectiveshell.ExecResult(0, None)
