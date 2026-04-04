from oscore import objectiveshell
# from oscore import libreg
from oscore.libconfig2 import Config
from AppContext import AppContext

import datetime
import os
import subprocess
import readline
import sys

context: AppContext = AppContext()

# AVBL Keys for env vars
# OBJSHELL_HISTORY_ENABLE (0/1) - Enable/Disable command history
# OBJSHELL_HISTORY_FILE (str) - Path to history file
# OBJSHELL_PROMPT (str) - Custom prompt string
# OBJSHELL_PRINT_RETURNS (0/1) - Enable/Disable printing return values


# Custom prompt variables
#   {ExitCode}: Last command exit code
#   {ExecTime}: Last command execution time in seconds (0.1 precision)
#   {User}: Current user name
#   {Cwd}: Current working directory
#   {Time}: Current time in HH:MM:SS format
#   {Date}: Current date in YYYY-MM-DD format
#   {Datetime}: Current date and time in YYYY-MM-DD HH:MM:SS format
#   {Hostname}: System hostname
#   {ShellVersion}: ObjectiveShell version
#   {Exec:xxx}: Output of executing command xxx (Not stored in history unless "OBJSHELL_HISTORY_EVAL_EXEC" is set to 1)

def parse_exec_variables(prompt: str, session: objectiveshell.ObjectiveShellSession, exit_code, elapsed) -> str:
    if prompt is None:
        return ""

    variables = {
        "ExitCode": exit_code,
        "ExecTime": elapsed,
        "User": os.getenv("USER") or os.getenv("USERNAME") or "unknown",
        "Cwd": session.pwd,
        "Time": datetime.datetime.now().strftime("%I:%M %p"),
        "Date": datetime.datetime.now().strftime("%d/%m/%y"),
        "Datetime": datetime.datetime.now().strftime("%I:%M:%S %p"),
        "Hostname": os.uname().nodename if hasattr(os, 'uname') else os.getenv("COMPUTERNAME") or "unknown",
        "ShellVersion": "1.0"
    }
    for key, value in variables.items():
        prompt = prompt.replace(f"{{{key}}}", str(value))

    while "{Exec:" in prompt:
        start_idx = prompt.index("{Exec:")
        end_idx = prompt.index("}", start_idx)
        command = prompt[start_idx + 6:end_idx]
        try:
            exec_result = session.execute_line(session.parse_line(command))
            exec_output = str(exec_result.returns) if exec_result.returns is not None else ""
        except Exception as e:
            exec_output = f"Error: {e}"
        prompt = prompt[:start_idx] + exec_output + prompt[end_idx + 1:]

    return prompt


def main():

    # Get configuration
    config: Config = Config("me.hysong.osaqua.applications.ObjectiveShell").fetch()
    env: dict[str, str] = config.get("Environment", {})
    paths: str = config.get("Paths", "{{SYS_FRAMEWORKS}}/ObjectiveShell/Instructions/foundation:{{SYS_FRAMEWORKS}}/GroupPolicy/Commands")
    dev_on: bool = config.get("Developer", False)
    allow_fallback_to_bash: bool = config.get("AllowFallbackToBash", False)

    # Set if not exist
    if not config.exists():
        config["Environment"] = {
            "OBJSHELL_HISTORY_ENABLE": "0",
            "OBJSHELL_HISTORY_FILE": context.file_in_box("history.txt"),
            "OBJSHELL_PROMPT": "ObjectiveShell > ",
            "OBJSHELL_PRINT_RETURNS": "1"
        }
        config["Paths"] = "{{SYS_FRAMEWORKS}}/ObjectiveShell/Instructions/foundation:{{SYS_FRAMEWORKS}}/GroupPolicy/Commands"
        config["Developer"] = False
        config["AllowFallbackToBash"] = False
        config.sync()

    if dev_on:
        paths = f"{paths}:{{SYS_FRAMEWORKS}}/ObjectiveShell/Instructions/developers"

    env["PATH"] = paths

    session = objectiveshell.ObjectiveShellSession(env)
    elapsed_time = 0.0
    exit_code = 0

    history: list[str] = []

    history_path = session.environment.get("OBJSHELL_HISTORY_FILE", "")
    if history_path and os.path.isfile(history_path):
        try:
            # This loads the file content directly into the input() history buffer
            readline.read_history_file(history_path)

            # Keep your original list logic if you need the variable 'history' for other logic
            with open(history_path, "r") as history_file:
                history = history_file.read().splitlines()
        except IOError:
            pass

    # Get parameters
    cmdline_input: list = sys.argv[1:]
    if cmdline_input:
        # Check if the first argument is a file
        if os.path.isfile(cmdline_input[0]):
            with open(cmdline_input[0], "r") as script_file:
                for line in script_file:
                    parsed_line = session.parse_line(line.strip())
                    result = session.execute_line(parsed_line)
                    if result.returns is not None and session.environment.get("OBJSHELL_PRINT_RETURNS", "1"):
                        print(result.returns)
            return result.exit_code
        else:
            # Otherwise, treat the arguments as a single command
            result = session.execute_line(cmdline_input)
            if result.returns is not None and session.environment.get("OBJSHELL_PRINT_RETURNS", "1"):
                print(result.returns)
            return result.exit_code

    while True:
        try:

            prompt_template = session.environment.get("OBJSHELL_PROMPT", "ObjectiveShell > ")
            prompt = parse_exec_variables(prompt_template, session, exit_code, elapsed_time)

            raw_input = input(prompt)

            history.append(raw_input)
            readline.add_history(raw_input)
            if session.environment.get("OBJSHELL_HISTORY_ENABLE", "0") == "1":
                history_file_path = session.environment.get("OBJSHELL_HISTORY_FILE", "")
                if history_file_path:
                    with open(history_file_path, "a") as history_file:
                        history_file.write(raw_input + "\n")

            parsed_line = session.parse_line(raw_input)

            # Start timing execution
            start_time = datetime.datetime.now()
            result = session.execute_line(parsed_line)
            end_time = datetime.datetime.now()

            elapsed_time = (end_time - start_time).total_seconds()
            exit_code: int = result.exit_code

            if exit_code == -32768:
                if not allow_fallback_to_bash:
                    print(f"Command not found.")
                    continue

                # Fallback to bash
                try:
                    bash_process = subprocess.Popen(
                        ["bash", "-c", raw_input],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    stdout, stderr = bash_process.communicate()

                    if stdout:
                        print(stdout, end="")
                    if stderr:
                        print(stderr, end="")

                    exit_code = bash_process.returncode
                except Exception as e:
                    print(f"Error executing command in bash: {e}")
                    exit_code = -1

            if result.returns is not None and session.environment.get("OBJSHELL_PRINT_RETURNS", "1"):

                # Only if command is not echo.
                if parsed_line[0] != "echo":
                    print(result.returns)

        except (EOFError, KeyboardInterrupt):
            print("\nExiting ObjectiveShell.")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
