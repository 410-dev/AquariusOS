import os
import ast

from oscore import libreg as reg

def help(session) -> str:
    return "Usage: fasthelp\nLists all available instructions in current session"


def main(session, quick_scan=True):
    max_depth = reg.read("SOFTWARE/Aqua/ObjectiveShell/Settings/FastHelpMaxDepth", default=3)
    # 1. Normalize Arguments (handle string inputs from CLI)
    if isinstance(quick_scan, str):
        quick_scan = quick_scan.lower() not in ("false", "0", "no", "off")
    if isinstance(max_depth, str):
        try:
            max_depth = int(max_depth)
        except ValueError:
            max_depth = 3

    path_var = session.environment.get("PATH", "")
    path_dir_list = path_var.split(":") if path_var else []

    # Helper to check for function definitions using AST
    def has_target_functions(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        if node.name in ("main", "udef_main"):
                            return True
            return False
        except (SyntaxError, UnicodeDecodeError, OSError):
            # If we can't parse it (binary, permission, bad encoding), skip it
            return False

    for directory in path_dir_list:
        if os.path.isdir(directory):
            # Calculate base depth to enforce relative depth limit
            base_depth = directory.rstrip(os.sep).count(os.sep)

            for root, dirs, files in os.walk(directory):
                # 2. Enforce Depth Limit
                current_depth = root.rstrip(os.sep).count(os.sep)
                if current_depth - base_depth >= max_depth:
                    dirs[:] = []  # Clear dirs to stop recursing deeper

                for filename in files:
                    if filename.endswith(".py"):
                        filepath = os.path.join(root, filename)
                        name_no_ext = filename.split(".", maxsplit=1)[0]
                        name_no_ext = f"{root}/{name_no_ext}".replace(directory + os.sep, "")

                        # 3. Logic: Inspect unless quick_scan is False
                        if quick_scan:
                            if has_target_functions(filepath):
                                print(name_no_ext)
                        else:
                            # If quick_scan is False, we just print everything found
                            print(name_no_ext)

    return 0, None