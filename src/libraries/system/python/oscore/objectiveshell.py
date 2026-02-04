import shlex
import importlib
import importlib.util
from importlib.machinery import SourceFileLoader
import sys
import os
import types
import re
import copy


from typing import Any, List, Union


class ExecResult:
    def __init__(self, exit_code: int, returns: Any):
        self.exit_code = exit_code
        self.returns = returns

    def __repr__(self):
        return f"<ExecResult code={self.exit_code} returns={self.returns}>"



class _INTERNAL_CMDS:

    @staticmethod
    # set var x = y
    # set env x = y
    def set(session: 'ObjectiveShellSession', set_type: str, varname: str, var_type: str = None, value: Any = None) -> ExecResult:
        if set_type == "var":
            session.variables[varname] = value
        elif set_type == "env":
            session.environment[varname] = value
        else:
            print(f"Unknown set type: {set_type} (Must be 'var' or 'env')")
            return ExecResult(1, None)
        return ExecResult(0, value)


    @staticmethod
    # unset var x
    # unset env x
    def unset(session: 'ObjectiveShellSession', set_type: str, varname: str) -> ExecResult:
        if set_type == "var":
            session.variables.pop(varname)
        elif set_type == "env":
            session.environment.pop(varname)
        else:
            print(f"Unknown unset type: {set_type} (Must be 'var' or 'env')")
            return ExecResult(1, None)
        return ExecResult(0, varname)

    @staticmethod
    def add(session: 'ObjectiveShellSession', a: int, b: int) -> ExecResult:
        return ExecResult(0, int(a) + int(b))

    @staticmethod
    def exit(session: 'ObjectiveShellSession', code: int):
        sys.exit(int(code))

    @staticmethod
    def cd(session: 'ObjectiveShellSession', directory: str):
        if os.path.isdir(os.path.join(os.path.abspath(session.pwd), directory)):
            session.pwd = os.path.join(os.path.abspath(session.pwd), directory)
            return ExecResult(0, session.pwd)
        else:
            print(f"No such file or directory: {directory}")
            return ExecResult(1, None)

class ObjectiveShellSession:

    def __init__(self, environment: dict[str, str] = None):
        self.environment: dict[str, str] = environment if environment else {}
        self.variables: dict = {}
        # Default PWD to current working directory if not set
        self.pwd: str = os.getcwd()

        # Internal commands map
        self.internal_cmds = {
            "set": _INTERNAL_CMDS.set,
            "unset": _INTERNAL_CMDS.unset,
            "exit": _INTERNAL_CMDS.exit,
            "add": _INTERNAL_CMDS.add,
            "cd": _INTERNAL_CMDS.cd,
            "pwd": lambda s, *args: ExecResult(0, s.pwd),
            # Simple echo for testing
            "echo": lambda s, *args: ExecResult(0, " ".join([str(a) for a in args]))
        }

    def copy(self) -> 'ObjectiveShellSession':
        """
        Creates a copy of the session for external command execution.
        We perform a deep copy of environment and variables so the child
        command cannot mutate the parent shell's state unexpectedly.
        """
        new_session = ObjectiveShellSession()
        new_session.environment = copy.deepcopy(self.environment)
        new_session.variables = copy.deepcopy(self.variables)
        new_session.pwd = self.pwd
        new_session.internal_cmds = self.internal_cmds  # Shared reference is fine for functions
        return new_session

    def parse_line(self, line: str) -> List[Any]:
        """
        Parses a raw command string into a list of arguments (tokens).
        Handles quotes, nested $() execution, and ${} variable expansion.
        """
        tokens = []
        current_token = []
        quote_char = None  # None, ', or "
        i = 0
        n = len(line)

        while i < n:
            char = line[i]

            # 1. Handle Quotes
            if char in ('"', "'"):
                if quote_char is None:
                    quote_char = char  # Start quote
                elif quote_char == char:
                    quote_char = None  # End quote
                else:
                    current_token.append(char)  # Inside a different quote style
                i += 1
                continue

            # 2. Handle Space (Delimiters)
            if char.isspace() and quote_char is None:
                if current_token:
                    # Token complete, expand it
                    raw_token = "".join(current_token)
                    expanded = self._expand_token(raw_token)
                    tokens.append(expanded)
                    current_token = []
                i += 1
                continue

            # 3. Handle Command Substitution $()
            if char == '$' and i + 1 < n and line[i + 1] == '(':
                # Find matching closing parenthesis handling nesting
                start = i + 2
                depth = 1
                end = start
                while end < n and depth > 0:
                    if line[end] == '(':
                        depth += 1
                    elif line[end] == ')':
                        depth -= 1
                    end += 1

                if depth == 0:
                    # Extract command string inside $()
                    cmd_str = line[start: end - 1]

                    # Recursively execute
                    exec_res = self.execute_line(self.parse_line(cmd_str))

                    # Check for .exit_code property access after the closing ')'
                    # e.g. $(cmd).exit_code
                    pointer = end
                    use_exit_code = False
                    if pointer + 9 < n and line[pointer:pointer + 10] == ".exit_code":
                        use_exit_code = True
                        pointer += 10  # skip .exit_code
                        i = pointer  # Advance main loop
                    else:
                        i = end  # Advance main loop

                    val = exec_res.exit_code if use_exit_code else exec_res.returns

                    # If we are inside quotes or attached to text, force string conversion
                    # If this is the ONLY thing in the token and not quoted, keep type
                    current_token.append(val)
                    continue

            # 4. Normal character
            current_token.append(char)
            i += 1

        # Flush last token
        if current_token:
            raw_token = current_token
            # If current_token is a list containing non-strings (objects from $()),
            # we need to be careful how we join it.

            # Check if token is a single object instance (preserves type)
            if len(raw_token) == 1 and not isinstance(raw_token[0], str):
                tokens.append(raw_token[0])
            else:
                # Mixed content (strings and objects) -> Convert all to string
                # This handles cases like: "Result: $(calc_obj)"
                final_str = "".join([str(p) for p in raw_token])
                tokens.append(self._expand_token(final_str))

        return tokens

    def _resolve_paths(self) -> List[str]:
        """
        Generates search paths in priority order:
        1. Current Directory (self.pwd)
        2. ENV:PATH (colon separated)
        3. VAR:PATH (list of strings)
        """
        paths = [self.pwd]

        # ENV PATH
        env_path = self.environment.get("PATH", "")
        if env_path:
            paths.extend(env_path.split(":"))

        # VAR PATH
        var_path = self.variables.get("PATH", [])
        if isinstance(var_path, list):
            paths.extend(var_path)

        return paths

    def _expand_token(self, token: Union[str, Any]) -> Any:
        """
        Handles ${env:x} and ${var:x} expansion.
        If the token is exactly ${var:x}, returns the object.
        If embedded ("a${var:x}"), returns string.
        """
        if not isinstance(token, str):
            return token

        # Regex for ${type:name}
        pattern = re.compile(r'\$\{(env|var):([a-zA-Z0-9_]+)\}')

        # Check if it's a "perfect match" (the whole token is one variable)
        # This allows returning actual Objects instead of strings
        match = pattern.fullmatch(token)
        if match:
            v_type, v_name = match.groups()
            if v_type == 'env':
                return self.environment.get(v_name, "")
            elif v_type == 'var':
                return self.variables.get(v_name, None)

        # Otherwise, perform string substitution
        def replace_match(m):
            v_type, v_name = m.groups()
            if v_type == 'env':
                return str(self.environment.get(v_name, ""))
            elif v_type == 'var':
                val = self.variables.get(v_name, "")
                return str(val)
            return m.group(0)

        return pattern.sub(replace_match, token)

    def _load_and_run_external(self, filepath: str, args: list) -> ExecResult:
        # 1. Ensure absolute path to prevent importlib confusion
        filepath = os.path.abspath(filepath)
        module_name = os.path.splitext(os.path.basename(filepath))[0]

        try:
            # 2. Use SourceFileLoader directly.
            # This bypasses 'spec' heuristics and forces loading the file as source.
            loader = SourceFileLoader(module_name, filepath)
            module = types.ModuleType(loader.name)

            # Register module to sys.modules to support reloading/imports
            sys.modules[module_name] = module

            # Initialize the module (executes the code)
            try:
                loader.exec_module(module)
            except Exception as e:
                return ExecResult(1, f"Failed to load module code: {e}")

            # 3. Look for main
            if not hasattr(module, "main"):
                return ExecResult(1, f"Error: '{filepath}' does not have a main() function.")

            # 4. Prepare Session Copy
            session_copy = self.copy()

            # 5. Execute main with Error Handling
            try:
                # Pass session_copy as first arg, then the rest of args
                result =  module.main(session_copy, *args)

                # If tuple:
                if isinstance(result, tuple) and len(result) == 2:
                    exit_code, returns = result
                    return ExecResult(int(exit_code), returns)
                # If string, assume exit code 0
                elif isinstance(result, str):
                    return ExecResult(0, result)
                # If ExecResult, return directly
                elif isinstance(result, ExecResult):
                    return result
                # If int, assume exit code with no return
                elif isinstance(result, int):
                    return ExecResult(result, None)
                else:
                    return ExecResult(0, result)


            except TypeError as e:
                # Parameter mismatch handling
                if "positional argument" in str(e) or "argument" in str(e):
                    if hasattr(module, "help"):
                        try:
                            help_msg = module.help(session_copy)
                            print(f"Command usage error. Help:\n{help_msg}")
                            return ExecResult(1, None)
                        except Exception as help_err:
                            print(f"Error executing help(): {help_err}")
                    else:
                        print(f"Error executing {module_name}: {e}")
                else:
                    raise e

        except FileNotFoundError:
            return ExecResult(1, f"File not found during load: {filepath}")
        except PermissionError:
            return ExecResult(1, f"Permission denied reading: {filepath}")
        except Exception as e:
            return ExecResult(1, f"Execution failed: {e}")

        return ExecResult(0, None)

    def execute_line(self, line: list) -> ExecResult:
        if not line:
            return ExecResult(0, None)

        cmd_name = str(line[0])  # Command name is the first token
        args = line[1:]

        # 1. Internal Commands Check
        if cmd_name in self.internal_cmds:
            return self.internal_cmds[cmd_name](self, *args)

        # 2. External Command Path Resolution
        search_paths = self._resolve_paths()
        target_file = f"{cmd_name}.py"
        found_path = None

        for path in search_paths:
            # Clean path and join
            possible_path = os.path.join(path, target_file)
            if os.path.isfile(possible_path):
                found_path = possible_path
                break

        if found_path:
            return self._load_and_run_external(found_path, args)

        print(f"Command not found: {cmd_name}")
        return ExecResult(127, None)

