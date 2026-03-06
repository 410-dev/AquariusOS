import os

def plugin(data: dict) -> dict:

    file: str = data.get("file", "")
    if not file:
        raise ValueError("No file specified.")

    if not os.path.exists(file):
        raise FileNotFoundError(f"File not found: {file}")

    with open(file, "r") as f:
        content = f.read()

    return {
        "result": content
    }
