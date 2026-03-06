import json

def plugin(data: dict) -> dict:
    # Get imports
    imports = data.get("imports", "[]")
    if isinstance(imports, str):
        imports = json.loads(imports)

    # For each element, split by >. The first part is the module, second is either class or function, third is method or class name
    batch_import_statements: dict[str, list[str]] = {} # Key: module name, Value: list of member for that module

    for item in imports:
        parts = item.split(">")
        if len(parts) < 2:
            continue
        module_name = parts[0]
        member_name = parts[2] if len(parts) > 2 else None

        if module_name not in batch_import_statements:
            batch_import_statements[module_name] = []

        if member_name:
            batch_import_statements[module_name].append(member_name)

    # Generate import statements
    import_statements: list[str] = []
    for module_name, members in batch_import_statements.items():
        if members:
            members_str = ", ".join(members)
            import_statements.append(f"from {module_name} import {members_str}")
        else:
            import_statements.append(f"import {module_name}")

    return {
        "result": "\n".join(import_statements)
    }
