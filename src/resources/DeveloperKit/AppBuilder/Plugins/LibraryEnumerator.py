import os
import importlib
import sys
import ast
import json
from pathlib import Path

def plugin(data: dict) -> dict:

    search_paths = [
        "/opt/aqua/lib/python/",
        "/usr/share/lib/python/me.hysong/apprunutils/"
    ]

    # Scan under /opt/aqua/lib/python
    # -> Then, ask which components to import

    components = []
    search_filter = data.get("filter", "")
    exclude_init = data.get("exclude_init", True)
    for p in search_paths:
        for root, dirs, files in os.walk(p):
            for file in files:
                if file.endswith(".py"):
                    if exclude_init and file == "__init__.py":
                        continue
                    if search_filter and search_filter not in file:
                        continue
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, p)
                    module_path = rel_path[:-3].replace(os.path.sep, ".")  # Remove .py and convert to module path
                    components.append(module_path)

    # Enumerate public functions and classes in each component
    sys.path.insert(0, "/opt/aqua/lib/python/aqua")
    for p in search_paths:
        if p not in sys.path:
            sys.path.insert(0, p)
    component_details = {}

    for component in components:
        try:
            file_path = Path(component).with_suffix(".py")

            if not file_path.exists():
                component_details[component] = {"error": "Python file not found"}
                continue

            tree = ast.parse(file_path.read_text())

            functions = [
                node.name
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
            ]

            classes = [
                node.name
                for node in tree.body
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
            ]

            component_details[component] = {
                "functions": functions,
                "classes": classes,
            }

        except Exception as e:
            component_details[component] = {"error": str(e)}

    return component_details
