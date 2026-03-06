import sys
import importlib
import json

def main(args: list[str]) -> int:
    # Parameter expected:
    #   0: module_name
    #   1: JSON as string
    if len(args) < 2:
        print("Usage: python3 JBridge.py <module_name> <json_string>")
        return 1
    module_name = args[0]
    json_string = args[1]

    # Module is in /opt/aqua/share/DeveloperKit/AppBuilder/Plugins/
    try:
        sys.path.append("/opt/aqua")
        module = importlib.import_module(f"aqua.share.DeveloperKit.AppBuilder.Plugins.{module_name}")
    except ImportError as e:
        print(f"Error importing module {module_name}: {e}")
        return 1
    if not hasattr(module, "plugin"):
        print(f"Module {module_name} does not have a 'plugin' function.")
        return 1
    plugin_func = getattr(module, "plugin")

    # Parse
    data: dict = json.loads(json_string)

    try:
        result = plugin_func(data)
        print(json.dumps(result, indent=4)) # Capture output from Java app side
        return 0
    except Exception as e:
        print(f"Error executing plugin function: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
