import os

def help(session) -> str:
    return "Usage: fasthelp\nLists all available instructions in current session"

def main(session):
    path_var = session.environment.get("PATH", "")
    path_dir_list = path_var.split(":") if path_var else []
    for directory in path_dir_list:
        if os.path.isdir(directory):
            for filename in os.listdir(directory):
                if filename.endswith(".py"):
                    print(os.path.basename(filename).split(".", maxsplit=2)[0])

    return 0, None
