#!/usr/bin/env python3
import os
import sys
import json
import importlib
from termui.browser import run_browser

def type_convert(value: str, dtype: str):
    if dtype == "int":
        input_value = int(value)
    elif dtype == "float":
        input_value = float(value)
    elif dtype == "str":
        input_value = str(value)
    elif dtype == "bool":
        input_value = value.lower() in ("true", "1", "yes")
    elif dtype == "list":
        input_value = [item.strip() for item in value.split(",")]
    elif dtype == "dict":
        input_value = json.loads(value)
    elif dtype == "multiline":
        input_value = value.strip().replace(", ", "\n").replace(",", "\n")
    else:
        raise ValueError(f"Unsupported data type: {dtype}")
    return input_value

def mem_substitute(obj: dict, memory: dict) -> str:
    value = obj.get("value", "")

    if value == "@PluginCall":
        plugin_name = obj.get("plugin", {}).get("name", "")
        if not plugin_name:
            raise ValueError("Plugin call requires a plugin name.")
        plugin_params = obj.get("plugin", {}).get("parameters", {})
        for param_key, param_value in plugin_params.items():
            plugin_params[param_key] = mem_substitute({"value": param_value}, memory)
        try:
            plugin_module = importlib.import_module(f"share.DeveloperKit.AppBuilder.Plugins.{plugin_name}")
            if not hasattr(plugin_module, "plugin"):
                raise ImportError(f"Plugin module {plugin_name} does not have a 'plugin' function.")
            plugin_func = getattr(plugin_module, "plugin")
            result = plugin_func(plugin_params).get("result", "")
            return result
        except ImportError as e:
            raise ImportError(f"Error importing plugin {plugin_name}: {e}")

    for mem_key, mem_value in memory.items():
        placeholder = "$" + mem_key + "$"
        if placeholder in value:
            value = value.replace(placeholder, str(mem_value))
    return value

def execute_routine(routine_data: dict) -> dict:
    routine_obj: dict = routine_data["InputRequirements"]
    memory: dict = {}

    sys.path.insert(0, "/opt/aqua")


    for key in routine_obj.keys():
        # Check for required fields: display, value, type
        display = routine_obj[key].get("display", None)
        value = routine_obj[key].get("value", None)
        dtype = routine_obj[key].get("type", None)
        if value is None or dtype is None:
            raise ValueError(f"Invalid routine input requirement for key: {key}")

        if display is None:
            memory[key] = type_convert(mem_substitute(routine_obj[key], memory), dtype)
            continue

        # If "selections" type, prepare and launch browser
        if dtype == "selections":
            if "selections" not in routine_obj[key]:
                raise ValueError(f"Selections type requires 'selections' field for key: {key}")
            selections = routine_obj[key]["selections"]
            if selections["dynamic"]:
                # Launch plugin
                plugin_name = selections["source"]["plugin"]
                plugin_params = selections["source"].get("parameters", {})
                try:
                    plugin_module = importlib.import_module(f"share.DeveloperKit.AppBuilder.Plugins.{plugin_name}")
                    if not hasattr(plugin_module, "plugin"):
                        raise ImportError(f"Plugin module {plugin_name} does not have a 'plugin' function.")
                    plugin_func = getattr(plugin_module, "plugin")
                    options = plugin_func(plugin_params)
                except ImportError as e:
                    raise ImportError(f"Error importing plugin {plugin_name}: {e}")
            else:
                options = selections.get("source", {})
            # Run browser
            selected_option = run_browser(options, title=display)
            memory[key] = json.dumps(selected_option)
            continue

        input_value = input(f"{display} (type: {dtype}, default: {value}): ")
        if input_value == "":
            input_value = value
        # Type conversion
        input_value = type_convert(input_value, dtype)
        memory[key] = input_value

    return memory

def get_templates() -> dict[str, str]:
    templates_dir = "/opt/aqua/share/DeveloperKit/AppBuilder/Templates"
    templates: dict[str, str] = {}
    if not os.path.exists(templates_dir):
        return templates

    for entry in os.listdir(templates_dir):
        full_path = os.path.join(templates_dir, entry)
        if not full_path.endswith(".template.json"):
            continue
        try:
            with open(full_path, "r") as f:
                data = json.load(f)
                name = data.get("TemplateName", None)
                version = data.get("TemplateVersion", None)
                if name is None or version is None:
                    continue
                templates[name] = full_path
        except json.JSONDecodeError:
            continue

    return templates

def main():
    # Ask for project location
    name_of_project = input("Name of project: ")
    if not name_of_project:
        print("Project name is required.")
        return
    project_dir_path = input("Enter the directory path for the new project (default: ./): ")
    if not project_dir_path:
        project_dir_path = "./"
    project_dir_path = os.path.abspath(project_dir_path)
    print(f"Project will be created at: {os.path.join(project_dir_path, name_of_project)}")

    # Create directory first
    project_full_path = os.path.join(project_dir_path, name_of_project)
    if not os.path.exists(project_full_path):
        os.makedirs(project_full_path)

    templates: dict[str, str] = get_templates()
    if not templates:
        print("No templates found.")
        return

    template_names = list(templates.keys())
    for i, name in enumerate(template_names):
        print(f"{i + 1}: {name}")

    selected_item = input("Type the number of the template to select and press Enter: ")
    selected_item = int(selected_item)
    selected_item -= 1
    if selected_item < 0 or selected_item >= len(template_names):
        print("Invalid selection.")
        return

    selected_template_name = template_names[selected_item]
    # Load
    template = templates[selected_template_name]
    try:
        with open(template, "r") as f:
            data: dict = json.load(f)
    except json.JSONDecodeError:
        print("Failed to load template.")

    # Execute routine
    memory = execute_routine(data)

    print(f"Generating project at: {project_full_path} ...")
    output_path = project_full_path

    # Load structure
    structure = data.get("Structure", {})

    # If object, process it as directory - recurse
    # If string, treat as file - and write value as file content
    # Replace key and value with memory substitutions
    def directory_processing(current_path: str, structure_obj: dict):
        for key, value in structure_obj.items():
            # Substitute key
            substituted_key = mem_substitute({"value": key}, memory)
            new_path = os.path.join(current_path, substituted_key)

            if isinstance(value, dict):
                # Directory
                if not os.path.exists(new_path):
                    os.makedirs(new_path)
                directory_processing(new_path, value)
            elif isinstance(value, str):
                # File
                file_content = mem_substitute({"value": value}, memory)
                with open(new_path, "w") as f:
                    f.write(file_content)
            else:
                raise ValueError(f"Invalid structure value type for key: {key}")

    directory_processing(output_path, structure)
    print("Done.")

if __name__ == "__main__":
    main()