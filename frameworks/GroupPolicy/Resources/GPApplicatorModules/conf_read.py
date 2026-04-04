from oscore.libconfig2 import Config, ConfigView

def module_init():
    return True

def module_execute(params: dict) -> str: # Doesn't have to be a string, but recommended
    key: list = params.get("key", None)
    path: str = params.get("path", None)
    path_is_abs: bool = params.get("path_is_abs", False)
    enforce_global: bool = params.get("enforce_global", False)
    cascade_merge_mode: bool = params.get("cascade_merge_mode", False)
    cascade: bool = params.get("cascade", False)
    cascade_priorities: list[str] = params.get("cascade_priorities", None)
    cascade_priority_write_index: int = params.get("cascade_priority_write_index", 0)
    logging: bool = params.get("logging", False)
    resolve_pattern: bool = params.get("resolve_pattern", True)

    if path is None:
        raise ValueError("Error: 'path' parameter is required.")
    if key is None:
        raise ValueError("Error: 'key' parameter is required.")
    if not isinstance(key, list):
        raise TypeError("Error: 'key' parameter must be a list of strings.")

    config: Config = Config(path, path_is_abs, enforce_global, cascade_merge_mode, cascade, cascade_priorities, cascade_priority_write_index, logging, resolve_pattern)
    config.fetch()

    # Reads each element as key name.
    view: ConfigView = config.to_view()
    for i, e in enumerate(key):
        if i == len(key) - 1:
            break
        view = view.view(e)

    return view.get(key[-1])
