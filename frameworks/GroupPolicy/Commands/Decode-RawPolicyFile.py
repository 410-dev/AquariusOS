#!/usr/bin/env python3
# This is objective shell compatible command.

import importlib
import json
import sys
from types import ModuleType

_TYPE = "GroupPolicy.1"

def _read_file(file_name: str) -> dict:
    with open(file_name, "r", encoding="utf-8") as f:
        return json.load(f)

def _check_file_integrity(data: dict) -> bool:
    # 호환성 체크
    EXPECTED_KEYS: dict[str, type] = {
        "id": str,
        "name": str,
        "level": str,
        "data": dict#[str, dict[str, str | dict | list | int | float | bool]]
    }
    OPTIONAL_KEYS: dict[str, type] = {
        "user": str,
        "description": str,
        "modules": list,#[str]
        "module_exec": dict#[str, dict[str, str | dict]]
    }

    # 타입 체크
    if data["type"] != _TYPE:
        return False

    # Expected keys 타입 체크
    for key, expected_type in EXPECTED_KEYS.items():
        if key not in data:
            return False
        if not isinstance(data[key], expected_type):
            return False

    # Optional keys 타입 체크
    for key, expected_type in OPTIONAL_KEYS.items():
        if key in data and not isinstance(data[key], expected_type):
            return False

    return True

def _extract_and_strip_metadata(data: dict) -> tuple[str, str, str, str, str, list, dict, dict]:
    # Returns:
    # (id, name, level, user, description, modules, module_exec, data)
    pol_id: str = data["id"]
    name: str = data["name"]
    level: str = data["level"]
    user: str = data.get("user", "")
    description: str = data.get("description", "")
    modules: list = data.get("modules", [])
    module_exec: dict = data.get("module_exec", {})
    data: dict = data["data"]
    return pol_id, name, level, user, description, modules, module_exec, data

def _find_and_import_module(module_name: str) -> ModuleType | None :
    try:
        module_root = f"{{SYS_FRAMEWORKS}}/GroupPolicy/Resources/GPApplicatorModules".replace("/", ".")
        module = importlib.import_module(f"{module_root}.{module_name}")
        return module
    except ImportError:
        return None

def _run_module(module: ModuleType, module_name: str, params: dict) -> tuple[bool, str]:
    if not hasattr(module, "module_init") or not hasattr(module, "module_execute"):
        return False, f"Error: Module '{module_name}' does not have required functions."
    try:
        if not module.module_init():
            return False, f"Error: Module '{module_name}' failed to initialize."
        return True, module.module_execute(params)
    except Exception as ex:
        return False, f"Error: Module '{module_name}' execution failed with exception: {str(ex)}"


def _complete_variable_table(module_exec: dict, modules_imported: dict[str, ModuleType]) -> tuple[int, dict[str, str]] | None:
    module_results: dict[str, str] = {}
    for variable_name in module_exec.keys():
        module_name = module_exec[variable_name].get("module")
        params = module_exec[variable_name].get("params", {})
        if module_name not in modules_imported:
            return 1, {"error": f"Module '{module_name}' specified for variable '{variable_name}' is not imported."}
        success, result = _run_module(modules_imported[module_name], module_name, params)
        if not success:
            return 1, {"error": result}
        module_results[variable_name] = result
    return 0, module_results


def main(session, file_name: str) -> tuple[int, dict]:
    # 데이터 불러오기
    data: dict = _read_file(file_name)

    # 파일 무결성 체크
    if not _check_file_integrity(data):
        return 1, {"error": "Invalid policy file format."}

    # 언팩
    pol_id, name, level, user, description, modules, module_exec, data = _extract_and_strip_metadata(data)

    # 모듈 불러오기
    modules_imported: dict[str, ModuleType] = {}
    for module_name in modules:
        module = _find_and_import_module(module_name)
        if module is None:
            return 1, {"error": f"Module '{module_name}' not found."}
        modules_imported[module_name] = module

    # 모듈 실행
    exitc, var_table = _complete_variable_table(module_exec, modules_imported)
    if var_table is None:
        return 1, {"error": "Failed to execute modules for variable table completion."}

    var_table: dict[str, str] = var_table

    # 치환 가능한 타입
    replaceable_types: list[type] = [
        str, dict, list, set
    ]

    # 치환시, 하위 객체에도 모두 치환 적용하기 위한 헬퍼
    def substitution_recursive_helper(replace_from: str, replace_to: str, value):
        if isinstance(value, str):
            return value.replace(f"{{{replace_from}}}", str(replace_to))
        elif isinstance(value, dict):
            return {k: substitution_recursive_helper(replace_from, replace_to, v) for k, v in value.items()}
        elif isinstance(value, list):
            return [substitution_recursive_helper(replace_from, replace_to, v) for v in value]
        elif isinstance(value, set):
            return {substitution_recursive_helper(replace_from, replace_to, v) for v in value}
        else:
            return value

    # data 에서 각 항목의 dict 에 vars 라는 리스트가 있으면, 뽑아온 후, value 의 {varname} 에 치환 해넣기
    for key, item in data.items():
        if "vars" not in item:
            continue

        for t in replaceable_types:
            if not isinstance(item["vars"], t):
                return 1, {"error": f"'vars' field in item '{key}' must be one of the following types: {', '.join([t.__name__ for t in replaceable_types])}."}

        if not isinstance(item["vars"], list):
            continue

        for var_name in item["vars"]:
            if var_name not in var_table:
                return 1, {"error": f"Variable '{var_name}' specified in 'vars' of item '{key}' is not defined in module_exec."}

            var_value: str = var_table[var_name]
            item = substitution_recursive_helper(var_name, var_value, item)

    # 최종적으로, id, name, level, user, description, data 만 남긴 후 반환
    return 0, {
        "type": f"{_TYPE}.dec",
        "id": pol_id,
        "name": name,
        "level": level,
        "user": user,
        "description": description,
        "data": data
    }

if __name__ == '__main__':
    exit_code, output = main(None, sys.argv[1])
    if exit_code != 0:
        print(f"Error: {output.get('error', 'Unknown error occurred.')}", file=sys.stderr)
    else:
        print(json.dumps(output, indent=4, ensure_ascii=False))
    sys.exit(exit_code)
