#!/usr/bin/env python3
"""
AquariusOS Build Tool
Builds an edition of AquariusOS from a common + edition recipe.
"""

import fnmatch
import json
import sys
import shutil
import os
import subprocess
import argparse
from typing import Any

# ─────────────────────────────────────────────
# ANSI 컬러 출력
# ─────────────────────────────────────────────

class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    DIM     = "\033[2m"

def log_info(msg: str, indent: int = 0):
    print(" " * indent + f"{C.CYAN}→{C.RESET} {msg}")

def log_ok(msg: str, indent: int = 0):
    print(" " * indent + f"{C.GREEN}✓{C.RESET} {msg}")

def log_warn(msg: str, indent: int = 0):
    print(" " * indent + f"{C.YELLOW}⚠{C.RESET}  {msg}")

def log_error(msg: str, indent: int = 0):
    print(" " * indent + f"{C.RED}✗{C.RESET} {msg}", file=sys.stderr)

def log_step(step: int, total: int, msg: str):
    print(f"\n{C.BOLD}{C.BLUE}[{step}/{total}]{C.RESET} {C.BOLD}{msg}{C.RESET}")

def log_verbose(msg: str, indent: int = 0, verbose: bool = False):
    if verbose:
        print(" " * indent + f"{C.DIM}  {msg}{C.RESET}")

def die(msg: str):
    log_error(msg)
    sys.exit(1)


# ─────────────────────────────────────────────
# JSON5 로더 (주석 제거 후 json 파싱)
# ─────────────────────────────────────────────

def load_json5(path: str) -> dict:
    """주석을 제거하고 JSON5 파일을 파싱합니다."""
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read()

    # 한 줄 주석 제거 (//)
    lines = []
    for line in raw.splitlines():
        # 문자열 안의 // 는 건드리지 않도록 간단히 처리
        in_string = False
        result = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"' and (i == 0 or line[i-1] != '\\'):
                in_string = not in_string
            if not in_string and ch == '/' and i + 1 < len(line) and line[i+1] == '/':
                break
            result.append(ch)
            i += 1
        lines.append(''.join(result))

    cleaned = '\n'.join(lines)

    # 후행 쉼표 제거 (JSON5 허용, 표준 JSON 불허)
    import re
    cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        die(f"JSON5 파싱 실패: {path}\n  {e}")


# ─────────────────────────────────────────────
# 레시피 로딩 및 병합
# ─────────────────────────────────────────────

def deep_merge(base: dict, override: dict, path: str = "") -> dict:
    """
    두 딕셔너리를 딥 머지합니다.
    허용된 키(Mapping, Output.Filename) 외 충돌 시 빌드 실패.
    """
    ALLOWED_OVERRIDE_KEYS = {"Mapping", "Output", "Variables", "Output", "NimCompilerFlags*", "NimCompilerFlags"}
    # log_info(f"딥 머지: {path or 'root'} (허용 키값: {ALLOWED_OVERRIDE_KEYS}", indent=2)
    # log_info(f"머지 중: {path or 'root'}", indent=2)

    result = dict(base)
    for key, value in override.items():
        full_path = f"{path}.{key}"
        if full_path.startswith("."):
            full_path = full_path[1:]
        if key in result:
            # 1. 키가 정확히 일치하거나
            # 2. X.* 패턴에 해당하는 하위 키인지 검사합니다.
            is_allowed = False
            for ak in ALLOWED_OVERRIDE_KEYS:
                if key.startswith(ak[:-1]) or key == ak or full_path.startswith(ak[:-1]): # KEY* or KEY detection
                    is_allowed = True
                    break

            if is_allowed:
                # 허용된 키는 재귀 머지
                if isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value, path + f".{key}")
                else:
                    result[key] = value
            else:
                die(
                    f"레시피 충돌: '{full_path}' 키가 common 과 edition 양쪽에 존재합니다.\n"
                    f"  공통과 에디션의 키셋은 반드시 분리되어야 합니다."
                )
        else:
            result[key] = value
    return result


def evaluate_variables(variables: dict, config: dict) -> dict[str, str]:
    """$run, $ref 를 평가하여 최종 변수 딕셔너리를 반환합니다."""
    resolved: dict[str, str] = {}

    for key, value in variables.items():
        if isinstance(value, dict):
            if "$run" in value:
                cmd = value["$run"]
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    die(f"변수 '{key}' 평가 실패 ($run: {cmd})\n  {result.stderr.strip()}")
                resolved[key] = result.stdout.strip()

            elif "$ref" in value:
                ref_key = value["$ref"]
                if ref_key not in resolved:
                    die(f"변수 '{key}' 에서 참조한 '{ref_key}' 가 아직 정의되지 않았습니다.")
                resolved[key] = resolved[ref_key]

            else:
                die(f"변수 '{key}' 에 알 수 없는 지시자가 있습니다: {value}")

        elif isinstance(value, str):
            resolved[key] = value

        else:
            resolved[key] = str(value)

    return resolved


def substitute(text: str, variables: dict[str, str]) -> str:
    """{{VARIABLE}} 을 변수값으로 치환합니다."""
    for key, value in variables.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def substitute_postbuild(commands: list, variables: dict[str, str]) -> list:
    """PostBuild 커맨드 리스트의 변수를 치환합니다."""
    result = []
    for cmd in commands:
        result.append([substitute(arg, variables) for arg in cmd])
    return result


def load_recipe(common_path: str, edition_path: str, verbose: bool) -> dict:
    """common + edition 레시피를 로드하고 병합합니다."""
    log_info(f"공통 레시피 로드: {common_path}")
    common = load_json5(common_path)

    log_info(f"에디션 레시피 로드: {edition_path}")
    edition = load_json5(edition_path)

    # StructType 검증
    if common.get("StructType") != "BuildRecipe":
        die(f"common.json5 의 StructType 이 'BuildRecipe' 가 아닙니다.")
    if edition.get("StructType") != "BuildRecipeEdition":
        die(f"edition.json5 의 StructType 이 'BuildRecipeEdition' 가 아닙니다.")

    log_info("레시피 딥 머지 중...")
    # StructType, StructVersion 은 머지 전 제거
    for key in ["StructType", "StructVersion"]:
        edition.pop(key, None)

    merged = deep_merge(common, edition)

    # Output.Filename 검증
    if merged.get("Output", {}).get("Filename") is None:
        die("에디션 레시피에 Output.Filename 이 선언되지 않았습니다.")

    # 변수 평가
    log_info("변수 평가 중...")
    raw_variables = merged.get("Variables", {})
    resolved_vars = evaluate_variables(raw_variables, merged)
    resolved_vars["Temporary"] = merged.get("Temporary", "tmp")
    resolved_vars["Output"]    = merged.get("OutputDir", "build")
    resolved_vars["Source"]    = merged.get("Source", ".")
    merged["_resolved_vars"] = resolved_vars

    log_verbose(f"평가된 변수: {resolved_vars}", verbose=verbose)

    # PostBuild 변수 치환
    if "PostBuild" in merged:
        merged["PostBuild"] = substitute_postbuild(merged["PostBuild"], resolved_vars)

    return merged


# ─────────────────────────────────────────────
# 컴포넌트 필터링
# ─────────────────────────────────────────────

def resolve_components(mapping: dict[str, str], components: dict, verbose: bool) -> dict[str, str]:
    """
    Components 설정에 따라 최종 Mapping 을 필터링합니다.
    - Whitelist: Include 에 있는 것만
    - Blacklist: Exclude 에 있는 것만 제외
    Include 된 항목이 Mapping 에 없으면 빌드 실패.
    Exclude 된 항목이 Mapping 에 있으면 경고.
    """
    mode = components.get("Mode", "blacklist").lower()
    final_mapping: dict[str, str] = {}

    if mode == "whitelist":
        includes = components.get("Include", [])
        for pattern in includes:
            matched = False
            for src, dest in mapping.items():
                if fnmatch.fnmatch(src, pattern):
                    final_mapping[src] = dest
                    matched = True
            if not matched:
                die(
                    f"Whitelist Include 항목 '{pattern}' 이 Mapping 에 존재하지 않습니다.\n"
                    f"  Mapping 에 해당 경로를 추가하거나 Include 에서 제거하세요."
                )

    elif mode == "blacklist":
        excludes = components.get("Exclude", [])
        excluded_keys = set()

        for pattern in excludes:
            matched = False
            for src in mapping.keys():
                if fnmatch.fnmatch(src, pattern):
                    matched = True
                    excluded_keys.add(src)
            if matched:
                log_warn(f"Exclude '{pattern}' → Mapping 에서 무시됩니다.", indent=4)
            else:
                log_verbose(f"Exclude '{pattern}' 는 Mapping 에 없습니다 (무해).", verbose=verbose, indent=4)

        for src, dest in mapping.items():
            if src not in excluded_keys:
                final_mapping[src] = dest

    else:
        die(f"알 수 없는 Components.Mode: '{mode}' (whitelist 또는 blacklist 만 허용)")

    return final_mapping


# ─────────────────────────────────────────────
# 파일 유틸
# ─────────────────────────────────────────────

def is_binary_file(filepath: str) -> bool:
    try:
        with open(filepath, 'rb') as f:
            return b'\x00' in f.read(8192)
    except Exception:
        return True


def should_skip_extension(filename: str, skip_extensions: list[str]) -> bool:
    return any(filename.lower().endswith("." + ext) for ext in skip_extensions)


def set_executable(filepath: str, patterns: list[str], verbose: bool):
    filename = os.path.basename(filepath)
    for pattern in patterns:
        if fnmatch.fnmatch(filename, pattern):
            os.chmod(filepath, 0o755)
            log_verbose(f"실행 권한 설정: {filepath}", verbose=verbose, indent=4)
            return


# ─────────────────────────────────────────────
# 전처리기
# ─────────────────────────────────────────────


def run_preprocessor(cswd: str, config: dict, verbose: bool):
    preprocessor = config.get("Preprocessor", {})
    variables    = config.get("_resolved_vars", {})
    substitutions = config.get("Substitutions", {})

    apply_patterns = substitutions.get("Apply", [])
    skip_patterns  = substitutions.get("Skip", [])
    delimiter      = substitutions.get("Delimiter", ["{{", "}}"])
    open_delim, close_delim = delimiter[0], delimiter[1]

    blacklist        = preprocessor.get("Blacklist", [])
    path_replacements = preprocessor.get("PathReplacements", {})
    set_executables  = preprocessor.get("SetExecutables", [])

    # [1/4] 블랙리스트 파일 제거
    log_step(1, 4, "블랙리스트 파일 제거")
    for root, dirs, files in os.walk(cswd):
        for file in files:
            if file in blacklist:
                fp = os.path.join(root, file)
                os.remove(fp)
                log_verbose(f"제거됨: {fp}", verbose=verbose, indent=4)

    # [2/4] 소스코드 변수 치환
    log_step(2, 4, "소스코드 변수 치환")
    apply_to_all = substitutions.get("ApplyToAllNonBinary", False)
    for root, dirs, files in os.walk(cswd):
        for file in files:
            fp = os.path.join(root, file)

            # Skip 패턴은 항상 적용
            if any(fnmatch.fnmatch(file, p) for p in skip_patterns):
                log_verbose(f"스킵 (패턴): {fp}", verbose=verbose, indent=4)
                continue

            # 바이너리는 항상 스킵
            if is_binary_file(fp):
                log_verbose(f"스킵 (바이너리): {fp}", verbose=verbose, indent=4)
                continue

            # ApplyToAllNonBinary 가 False 면 Apply 패턴 체크
            if not apply_to_all and not any(fnmatch.fnmatch(file, p) for p in apply_patterns):
                log_verbose(f"스킵 (Apply 미해당): {fp}", verbose=verbose, indent=4)
                continue

            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            new_content = content
            for key, value in variables.items():
                new_content = new_content.replace(open_delim + key + close_delim, value)

            if new_content != content:
                with open(fp, 'w', encoding='utf-8', errors='ignore') as f:
                    f.write(new_content)
                log_verbose(f"치환됨: {fp}", verbose=verbose, indent=4)

    # [3/4] 경로 치환
    log_step(3, 4, "경로 및 파일명 치환")
    for root, dirs, files in os.walk(cswd, topdown=False):
        for name in dirs + files:
            item_path = os.path.join(root, name)
            new_name = name
            for old, new in path_replacements.items():
                new_name = new_name.replace(old, new)
            if new_name != name:
                new_path = os.path.join(root, new_name)
                shutil.move(item_path, new_path)
                log_verbose(f"이름 변경: {item_path} → {new_path}", verbose=verbose, indent=4)

        # 파일 내용도 치환
        for file in files:
            fp = os.path.join(root, file)
            if not os.path.exists(fp):
                continue
            if is_binary_file(fp):
                continue
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            new_content = content
            for old, new in path_replacements.items():
                new_content = new_content.replace(old, new)
            if new_content != content:
                with open(fp, 'w', encoding='utf-8', errors='ignore') as f:
                    f.write(new_content)

    # [4/4] 실행 권한 설정
    log_step(4, 4, "실행 권한 설정")
    for root, dirs, files in os.walk(cswd):
        for file in files:
            fp = os.path.join(root, file)
            set_executable(fp, set_executables, verbose)


# ─────────────────────────────────────────────
# 서브모듈 빌드
# ─────────────────────────────────────────────

def build_nim_submodule(submodule_path: str, verbose: bool, cmd: list[str]):
    """main.nim 이 있고 build.sh 가 없는 경우 nim 프로덕션 빌드를 수행합니다."""
    main_nim = os.path.join(submodule_path, "main.nim")
    if not os.path.exists(main_nim):
        die(f"Nim 서브모듈 '{submodule_path}' 에 main.nim 이 없습니다.")

    # 출력 바이너리 이름: my-command.bin → my-command
    dir_name = os.path.basename(submodule_path)
    if dir_name.endswith(".bin"):
        output_name = dir_name[:-4]
    else:
        output_name = dir_name

    output_bin = os.path.join(submodule_path, output_name)

    log_info(f"Nim 빌드: {main_nim} → {output_name}", indent=4)
    cmd.extend([f"--out:{output_bin}", main_nim])
    log_verbose(f"빌드 명령: {' '.join(cmd)}", indent=6)
    result = subprocess.run(
        cmd,
        cwd=submodule_path,
        capture_output=not verbose
    )
    if result.returncode != 0:
        if not verbose and result.stderr:
            print(result.stderr.decode() if isinstance(result.stderr, bytes) else result.stderr)
        die(f"Nim 빌드 실패: {submodule_path}")

    # 바이너리를 부모 디렉토리로 이동
    parent_dir = os.path.dirname(submodule_path)
    final_path = os.path.join(parent_dir, output_name)
    shutil.move(output_bin, final_path)
    log_ok(f"Nim 빌드 완료: {final_path}", indent=4)

    # .bin 디렉토리 삭제
    shutil.rmtree(submodule_path)
    log_verbose(f"서브모듈 디렉토리 삭제: {submodule_path}", verbose=verbose, indent=4)


def build_submodules(cswd: str, config: dict, verbose: bool):
    """서브모듈을 우선순위에 따라 빌드합니다."""
    ignore_config  = config.get("IgnoreErrors", {})
    priority_list  = config.get("BuildPriority", [])
    target_distro  = config.get("Upstream", "Ubuntu")

    # 서브모듈 탐색: build.sh + build.json 또는 .bin 디렉토리 (main.nim)
    discovered: list[str] = []
    for root, dirs, files in os.walk(cswd):
        has_build_sh   = "build.sh"   in files
        has_build_json = "build.json" in files
        has_main_nim   = "main.nim"   in files
        dir_name       = os.path.basename(root)

        if has_build_sh and has_build_json:
            discovered.append(os.path.abspath(root))
        elif has_main_nim and not has_build_sh and dir_name.endswith(".bin"):
            discovered.append(os.path.abspath(root))

    # 우선순위 정렬
    build_queue: list[str] = []
    processed: set[str]    = set()

    for entry in priority_list:
        target = os.path.abspath(os.path.join(cswd, entry))
        matches = sorted([
            s for s in discovered
            if s not in processed and (
                    s == target or s.startswith(target + os.sep)
            )
        ])
        build_queue.extend(matches)
        processed.update(matches)

    remaining = sorted([s for s in discovered if s not in processed])
    build_queue.extend(remaining)

    # 빌드 실행
    nim_submodule_compiler_flag: list[str] = ["nim", "compile"]
    nim_submodule_compiler_flag.extend(config.get("NimCompilerFlags", {}).get("Submodule", []))
    for submodule_path in build_queue:
        dir_name    = os.path.basename(submodule_path)
        has_main_nim = os.path.exists(os.path.join(submodule_path, "main.nim"))
        has_build_sh = os.path.exists(os.path.join(submodule_path, "build.sh"))

        log_info(f"서브모듈 빌드: {submodule_path}", indent=2)

        try:
            # Nim 서브모듈
            if has_main_nim and not has_build_sh and dir_name.endswith(".bin"):
                build_nim_submodule(submodule_path, verbose, nim_submodule_compiler_flag)
                continue

            # 일반 서브모듈 (build.sh + build.json)
            result = subprocess.run(
                ["bash", "build.sh", "build.json", target_distro],
                cwd=submodule_path,
                capture_output=not verbose
            )
            if result.returncode != 0:
                die(f"서브모듈 빌드 실패: {submodule_path}")

            with open(os.path.join(submodule_path, "build.json"), 'r') as f:
                sub_config = json.load(f)

            output_file = sub_config.get("Output", "build")
            built_output = os.path.join(submodule_path, output_file)

            if not os.path.exists(built_output):
                die(f"서브모듈 빌드 결과물이 없습니다: {built_output}")

            build_map: dict | None = sub_config.get("AsSubmoduleBuildMap", {}).get(
                target_distro.lower(), None
            )

            if build_map is not None:
                for src, dest in build_map.items():
                    lsrc  = os.path.join(built_output, src)
                    ldest = os.path.join(cswd, dest)
                    os.makedirs(os.path.dirname(ldest), exist_ok=True)
                    if os.path.isdir(lsrc):
                        shutil.copytree(lsrc, ldest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(lsrc, ldest)
                    log_verbose(f"매핑: {lsrc} → {ldest}", verbose=verbose, indent=6)

                shutil.rmtree(built_output, ignore_errors=True)
                shutil.rmtree(submodule_path, ignore_errors=True)

            else:
                parent         = os.path.dirname(submodule_path)
                temp_out       = os.path.join(parent, os.path.basename(built_output) + ".out")
                final_name     = sub_config.get("AsOutput", None)
                final_path     = os.path.join(parent, final_name) if final_name else submodule_path

                os.rename(built_output, temp_out)
                shutil.rmtree(submodule_path, ignore_errors=True)
                os.rename(temp_out, final_path)
                log_verbose(f"결과물 이동: {final_path}", verbose=verbose, indent=6)

            log_ok(f"완료: {submodule_path}", indent=4)

        except Exception as e:
            exception_name = type(e).__name__
            log_error(f"{exception_name}: {e}", indent=4)

            # IgnoreErrors 검사
            if exception_name in ignore_config:
                normalized = os.path.normpath(submodule_path) \
                    .replace(os.path.abspath(cswd), "").lstrip(os.sep)
                for path_entry in ignore_config[exception_name]:
                    if os.path.normpath(path_entry) == normalized:
                        log_warn(f"무시됨 (IgnoreErrors): {submodule_path}", indent=4)
                        break
                else:
                    die(f"서브모듈 빌드 실패 (무시 불가): {submodule_path}")
            else:
                die(f"서브모듈 빌드 실패: {submodule_path}")

    log_info("잔여 .nim 파일 검사 중...", indent=2)
    build_remaining_nim_files(cswd, verbose, config.get("NimCompilerFlags", {}))


def build_remaining_nim_files(cswd: str, verbose: bool, compiler_flags: dict[str, list[str]]):
    """
    서브모듈 빌드 후 cswd 에 남아있는 .nim 파일을
    같은 이름의 바이너리로 컴파일합니다.
    """
    lib_flags: list[str] = ["nim", "compile"]
    lib_flags.extend(compiler_flags.get("Library", []))
    single_bin_flags: list[str] = ["nim", "compile"]
    single_bin_flags.extend(compiler_flags.get("SingleBinary", []))

    for root, dirs, files in os.walk(cswd):
        for file in files:
            if not file.endswith(".nim"):
                continue

            nim_path    = os.path.join(root, file)
            output_name = file[:-4]  # .nim 확장자 제거
            output_bin  = os.path.join(root, output_name)

            log_info(f"잔여 Nim 파일 빌드: {nim_path} → {output_name}", indent=4)

            # .so.nim 이였다면 라이브러리로 컴파일
            if output_name.endswith(".so"):
                new_nim_name = output_name[:-3] + ".nim"  # crypto.so → crypto.nim
                new_path = os.path.join(root, new_nim_name)
                os.rename(nim_path, new_path)
                build_arg = lib_flags + [
                             "--out:" + output_name,  # 파일명만
                             "--app:lib", new_nim_name]  # 파일명만
            else:
                build_arg = single_bin_flags + [
                             "--out:" + output_name,  # 파일명만
                             file]  # 파일명만
                new_path = nim_path

            log_verbose(f"빌드 명령: {' '.join(build_arg)}", verbose=verbose, indent=6)

            result = subprocess.run(
                build_arg,
                cwd=root,
                capture_output=not verbose
            )

            if result.returncode != 0:
                if not verbose and result.stderr:
                    print(result.stderr.decode() if isinstance(result.stderr, bytes) else result.stderr)
                die(f"잔여 Nim 파일 빌드 실패: {nim_path}")

            os.remove(new_path)  # 소스 파일 제거
            os.chmod(output_bin, 0o755)
            log_ok(f"완료: {output_bin}", indent=4)

def install_nimbles(nimbles: list[str]):
    # Run "nimble install xxx"
    # for nimble in nimbles:
    #     log_info(f"Nimble 설치: {nimble}", indent=4)
    #     result = subprocess.run(
    #         ["nimble", "install", nimble],
    #         capture_output=True,
    #         text=True
    #     )
    #     if result.returncode != 0:
    #         die(f"Nimble 설치 실패: {nimble}\n  {result.stderr.strip()}")
    #     log_ok(f"Nimble 설치 완료: {nimble}", indent=4)

    log_info(f"Nimble 설치: {nimbles}", indent=4)
    if not nimbles:
        log_ok("Nimble 설치할 패키지가 없습니다.", indent=4)
        return


    result = subprocess.run(
        ["nimble", "install"] + nimbles,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        die(f"Nimble 설치 실패: {nimbles}\n  {result.stderr.strip()}")
    log_ok(f"Nimble 설치 완료: {nimbles}", indent=4)


# ─────────────────────────────────────────────
# 메인테이너 스크립트 조합
# ─────────────────────────────────────────────

def compose_maintainer_script(scope: str, distro: str, pswd: str, output: str, blacklist: list[str], verbose: bool):
    distro = distro.lower()
    if distro not in ["debian", "ubuntu"]:
        log_verbose(f"{distro} 는 메인테이너 스크립트 미지원, 건너뜀", verbose=verbose, indent=4)
        return

    script_dir = os.path.join(pswd, "package-meta", distro, scope + ".d")
    if not os.path.isdir(script_dir):
        log_verbose(f"메인테이너 스크립트 디렉토리 없음: {script_dir}", verbose=verbose, indent=4)
        return

    scripts = sorted([
        s for s in os.listdir(script_dir)
        if s.endswith(".sh") and s not in blacklist
    ])
    if not scripts:
        log_verbose(f"메인테이너 스크립트 없음: {script_dir}", verbose=verbose, indent=4)
        return

    out_path = os.path.join(output, "DEBIAN", scope)
    log_info(f"{distro} {scope} 메인테이너 스크립트 조합 → {out_path}", indent=4)

    with open(out_path, 'w') as outfile:
        outfile.write("#!/bin/bash\n\n")
        for script in scripts:
            sfp = os.path.join(script_dir, script)
            log_verbose(f"추가: {sfp}", verbose=verbose, indent=6)
            with open(sfp, 'r') as infile:
                content = infile.read()
            outfile.write(f"\n# Begin: {script}\n")
            outfile.write(f"\necho Running {script}\n")
            lines = content.splitlines()
            for line in lines:
                if line.startswith("#!"):
                    continue
                outfile.write(line + "\n")
            outfile.write(f"\n# End: {script}\n\n")

    os.chmod(out_path, 0o755)
    shutil.rmtree(out_path + ".d", ignore_errors=True)

# ─────────────────────────────────────────────
# 빌드 메인
# ─────────────────────────────────────────────

def delete_tests(cswd: str):
    # Recursively delete *_test.py
    for root, dirs, files in os.walk(cswd):
        for file in files:
            if file.endswith("_test.py"):
                fp = os.path.join(root, file)
                os.remove(fp)
                log_verbose(f"테스트 파일 삭제: {fp}", verbose=True, indent=4)

def make_ignore_func(exclude_list: list[str]):
    """점(.)으로 시작하는 파일/디렉토리와 exclude_list 를 모두 무시합니다."""
    def ignore_func(dir_path, contents):
        ignored = set()
        for item in contents:
            # . 으로 시작하는 모든 항목 제외
            if item.startswith("."):
                ignored.add(item)
                continue
            # SourceExclude 목록 제외 (최상위에서만 적용)
            if os.path.abspath(dir_path) == os.path.abspath("."):
                if item in exclude_list:
                    ignored.add(item)
        return ignored
    return ignore_func

TOTAL_STEPS = 7

def build(config: dict, verbose: bool, dry_run: bool):
    name    = config.get("Name", "Unknown")
    version = config.get("_resolved_vars", {}).get("VERSION", "?")
    edition = config.get("Edition", "unknown")
    tmp     = config.get("Temporary", "tmp")
    # out     = config.get("Output", {})         # ← dict
    out_dir = config.get("OutputDir", "build") # ← 실제 출력 디렉토리 경로
    source  = config.get("Source", "src")

    print(f"\n{C.BOLD}{C.WHITE}{'─' * 50}{C.RESET}")
    print(f"{C.BOLD}  {name} — {edition.upper()} 에디션{C.RESET}")
    print(f"{C.DIM}  버전: {version}{C.RESET}")
    print(f"{C.BOLD}{C.WHITE}{'─' * 50}{C.RESET}\n")

    if dry_run:
        log_warn("DRY RUN 모드: 실제 파일 작업을 수행하지 않습니다.")
        # 검증만 수행
        _validate_only(config, verbose)
        log_ok("검증 완료 (dry-run)")
        return

    # ── Step 1: 준비
    log_step(1, TOTAL_STEPS, "빌드 환경 준비")
    for d in [out_dir, tmp]:
        if os.path.isdir(d):
            log_info(f"기존 디렉토리 정리: {d}", indent=2)
            shutil.rmtree(d)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(tmp, exist_ok=True)

    cswd = os.path.join(tmp, "step_0")

    source_exclude = config.get("SourceExclude", [])

    log_info(f"소스 복사: {source} → {cswd}", indent=2)
    shutil.copytree(
        source,
        cswd,
        ignore=make_ignore_func(source_exclude),
        dirs_exist_ok=True
    )
    log_info(f"Nimble 준비", indent=2)
    install_nimbles(config.get("Nimbles", []))
    log_ok("준비 완료", indent=2)
    log_info(f"테스트 파일 삭제", indent=2)
    delete_tests(cswd)
    log_ok("테스트 파일 삭제 완료", indent=2)

    # ── Step 2: 전처리기
    log_step(2, TOTAL_STEPS, "전처리기 실행")
    run_preprocessor(cswd, config, verbose)
    log_ok("전처리 완료", indent=2)

    # ── Step 3: 서브모듈 빌드
    log_step(3, TOTAL_STEPS, "서브모듈 빌드")
    build_submodules(cswd, config, verbose)
    log_ok("서브모듈 빌드 완료", indent=2)

    # ── Step 4: 오버레이 적용
    log_step(4, TOTAL_STEPS, "오버레이 적용")
    step1 = os.path.join(tmp, "step_1")
    os.makedirs(step1, exist_ok=True)
    for root, dirs, files in os.walk(cswd):
        if "_overlay" in dirs:
            overlay = os.path.join(root, "_overlay")
            log_info(f"오버레이 적용: {overlay}", indent=2)
            for item in os.listdir(overlay):
                src = os.path.join(overlay, item)
                dst = os.path.join(step1, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
            shutil.rmtree(overlay)
    log_ok("오버레이 적용 완료", indent=2)

    # ── Step 5: 컴포넌트 필터링 + 파일 매핑
    log_step(5, TOTAL_STEPS, "컴포넌트 필터링 및 파일 매핑")
    raw_mapping = config.get("Mapping", {})
    components  = config.get("Components", {})

    if components:
        log_info(f"Components 모드: {components.get('Mode', 'blacklist').upper()}", indent=2)
        final_mapping = resolve_components(raw_mapping, components, verbose)
    else:
        log_warn("Components 미선언, 전체 Mapping 사용", indent=2)
        final_mapping = raw_mapping

    for src, dest in final_mapping.items():
        lsrc  = os.path.join(cswd, src)
        ldest = step1 + "/" + dest.lstrip("/")
        log_info(f"{src} → {dest}", indent=2)
        if not os.path.isdir(lsrc):
            log_warn(f"소스 없음, 건너뜀: {lsrc}", indent=4)
            continue
        os.makedirs(ldest, exist_ok=True)
        shutil.copytree(lsrc, ldest, dirs_exist_ok=True)
    log_ok("파일 매핑 완료", indent=2)

    # ── Step 6: 패치 + 메인테이너 스크립트
    log_step(6, TOTAL_STEPS, "패치 및 메인테이너 스크립트")

    patches = config.get("Patches", {})
    for patch_name, enabled in patches.items():
        patch_path = os.path.join("patches", patch_name)
        if enabled:
            log_info(f"패치 적용: {patch_path}", indent=2)
            if os.path.isdir(patch_path):
                shutil.copytree(patch_path, step1, dirs_exist_ok=True)
            elif os.path.isfile(patch_path):
                shutil.copy2(patch_path, step1)
            else:
                die(f"패치 파일을 찾을 수 없습니다: {patch_path}")
        else:
            log_verbose(f"패치 건너뜀: {patch_path}", verbose=verbose, indent=2)

    distro    = config.get("Upstream", "ubuntu")
    bl        = config.get("MaintainerScriptBlacklist", [])
    for scope in ["preinst", "postinst", "prerm", "postrm"]:
        compose_maintainer_script(scope, distro, cswd, step1, bl, verbose)
    log_ok("패치 및 메인테이너 스크립트 완료", indent=2)

    # ── Step 7: PostBuild 실행
    log_step(7, TOTAL_STEPS, "PostBuild 실행")
    post_build = config.get("PostBuild", [])
    for cmd in post_build:
        log_info(f"실행: {' '.join(cmd)}", indent=2)
        result = subprocess.run(cmd, cwd=os.getcwd())
        if result.returncode != 0:
            die(f"PostBuild 커맨드 실패: {' '.join(cmd)}")

    # 출력 파일 수집
    output_patterns = config.get("Output", {}).get("Patterns", [])
    for pattern in output_patterns:
        for root, dirs, files in os.walk(step1):
            for file in files:
                if fnmatch.fnmatch(file, pattern):
                    src_path  = os.path.join(root, file)
                    dest_path = os.path.join(out_dir, file)
                    os.rename(src_path, dest_path)
                    log_ok(f"출력 파일 수집: {dest_path}", indent=2)

    print(f"\n{C.BOLD}{C.GREEN}{'─' * 50}{C.RESET}")
    print(f"{C.BOLD}{C.GREEN}  빌드 성공!{C.RESET}")
    print(f"{C.DIM}  출력: {out_dir}/{config['Output'].get('Filename', 'output')}.deb{C.RESET}")
    print(f"{C.BOLD}{C.GREEN}{'─' * 50}{C.RESET}\n")


def _validate_only(config: dict, verbose: bool):
    raw_mapping = config.get("Mapping", {})
    components  = config.get("Components", {})
    if components:
        resolve_components(raw_mapping, components, verbose)
        log_ok("Mapping/Components 검증 통과", indent=2)
    output_filename = config.get("Output", {}).get("Filename")
    if output_filename is None:
        die("Output.Filename 미선언")


# ─────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────

def select_edition(recipes_dir: str) -> str:
    """에디션 목록을 보여주고 선택받습니다."""
    editions_dir = os.path.join(recipes_dir, "editions")
    if not os.path.isdir(editions_dir):
        die(f"에디션 디렉토리를 찾을 수 없습니다: {editions_dir}")

    editions = sorted([
        f[:-6] for f in os.listdir(editions_dir)
        if f.endswith(".json5")
    ])
    if not editions:
        die("빌드 가능한 에디션이 없습니다.")

    print(f"\n{C.BOLD}빌드할 에디션을 선택하세요:{C.RESET}\n")
    for i, name in enumerate(editions, 1):
        print(f"  {C.CYAN}{i}{C.RESET}. {name}")
    print()

    while True:
        try:
            choice = input(f"{C.BOLD}선택 (1-{len(editions)}): {C.RESET}").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(editions):
                return os.path.join(editions_dir, editions[idx] + ".json5")
        except (ValueError, KeyboardInterrupt):
            pass
        log_warn("올바른 번호를 입력하세요.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AquariusOS Build Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "edition",
        nargs="?",
        help="에디션 이름 또는 레시피 경로 (생략 시 대화형 선택)"
    )
    parser.add_argument(
        "--recipes", "-r",
        default=".build/recipes",
        help="레시피 디렉토리 (기본: .build/recipes)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="상세 로그 출력"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="실제 빌드 없이 검증만 수행"
    )
    args = parser.parse_args()

    recipes_dir  = args.recipes
    common_path  = os.path.join(recipes_dir, "common.json5")

    if not os.path.exists(common_path):
        die(f"common.json5 를 찾을 수 없습니다: {common_path}")

    # 에디션 결정
    if args.edition:
        # 경로로 직접 지정된 경우
        if args.edition.endswith(".json5") and os.path.exists(args.edition):
            edition_path = args.edition
        else:
            edition_path = os.path.join(recipes_dir, "editions", args.edition + ".json5")
            if not os.path.exists(edition_path):
                die(f"에디션 레시피를 찾을 수 없습니다: {edition_path}")
    else:
        edition_path = select_edition(recipes_dir)

    log_ok(f"에디션: {edition_path}")

    config = load_recipe(common_path, edition_path, args.verbose)
    build(config, verbose=args.verbose, dry_run=args.dry_run)
