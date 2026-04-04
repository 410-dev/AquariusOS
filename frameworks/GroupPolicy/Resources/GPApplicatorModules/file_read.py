import os

def module_init():
    return True

def module_execute(params: dict) -> str: # Doesn't have to be a string, but recommended
    path: str = params.get("path", None)
    if path is None:
        raise ValueError("Error: 'path' parameter is required.")

    if not os.path.isfile(path):
        raise FileNotFoundError(f"Error: File '{path}' does not exist.")

    with open(path, "r") as f:
        content = f.read()

    return content

