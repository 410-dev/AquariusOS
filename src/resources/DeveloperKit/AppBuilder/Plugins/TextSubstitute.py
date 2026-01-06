def plugin(data: dict) -> dict:

    original: str = data.get("text", "")
    to_replace: str = data.get("from", "")
    replacement: str = data.get("to", "")

    return {
        "result": original.replace(to_replace, replacement)
    }
