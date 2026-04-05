#!/usr/bin/env python3
# Apply-Policy — 디코딩된 정책 데이터를 machinepol DB 에 적용합니다.

import sqlite3
import json
import sys
import os
import hashlib
import subprocess
import time
import argparse
import logging
import importlib.util
from pathlib import Path
from types import ModuleType

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DB_PATH = "{{SYS_FRAMEWORKS}}/GroupPolicy/policy.db"

# ── 허용 타입 및 직렬화 ───────────────────────────────────────────────────────

# value_type 문자열 매핑
_TYPE_MAP: dict[type, str] = {
    str:   "string",
    int:   "number",
    float: "number",
    bool:  "boolean",
    list:  "list",
    set:   "list",      # set → list 로 취급
    dict:  "json",
}

_SERIALIZABLE_TYPES = (str, int, float, bool, list, set, dict)


def _serialize_value(key: str, value) -> tuple[str, str]:
    """
    value 를 DB 저장용 문자열과 value_type 으로 변환합니다.

    Returns:
        (serialized_str, value_type_str)

    Raises:
        TypeError: 직렬화 불가능한 타입이거나 str 캐스트 실패 시
    """
    # bool 은 int 의 서브클래스이므로 먼저 체크
    if isinstance(value, bool):
        return str(value).lower(), "boolean"  # "true" / "false"

    if isinstance(value, (int, float)):
        return str(value), "number"

    if isinstance(value, str):
        return value, "string"

    if isinstance(value, (list, set)):
        try:
            serialized = json.dumps(list(value), ensure_ascii=False)
        except (TypeError, ValueError) as e:
            raise TypeError(f"'{key}': list/set 직렬화 실패 — {e}")
        return serialized, "list"

    if isinstance(value, dict):
        try:
            serialized = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            raise TypeError(f"'{key}': dict 직렬화 실패 — {e}")
        return serialized, "json"

    # 허용 타입이 아닌 경우 — str 캐스트 시도
    try:
        return str(value), "string"
    except Exception:
        raise TypeError(
            f"'{key}': 허용되지 않는 타입 '{type(value).__name__}' 이며 str 변환도 실패했습니다."
        )


# ── 정책 키 분리 ──────────────────────────────────────────────────────────────

def _split_policy_id(policy_id: str) -> tuple[str, str]:
    """
    "Machine/Hostname"              → ("Machine",         "Hostname")
    "MachineOverride/Timezone"      → ("MachineOverride", "Timezone")
    "MachineOverride/PackagerControl/Enable" → ("MachineOverride", "PackagerControl/Enable")
    """
    parts = policy_id.split("/", 1)
    if len(parts) != 2:
        raise ValueError(
            f"정책 키 형식이 올바르지 않습니다: '{policy_id}' "
            f"(최소 'Table/Key' 형식이어야 합니다)"
        )
    return parts[0], parts[1]


# ── 레벨 검증 ─────────────────────────────────────────────────────────────────
#
# # 정책 레벨별로 허용되는 테이블 접두사
# _LEVEL_ALLOWED_TABLES: dict[str, set[str]] = {
#     "Domain":          {"Domain"},
#     "Site":            {"Site"},
#     "Group":           {"Group"},
#     "Machine":         {"Machine"},
#     "MachineOverride": {"MachineOverride"},
#     "User":            {"<username>"},   # 실제 검증 시 username 으로 대체
# }
#
# def _validate_table_for_level(table: str, level: str, username: str) -> bool:
#     """
#     정책 파일의 level 과 data 키의 테이블명이 일치하는지 검증합니다.
#     User 레벨은 username 테이블만 허용합니다.
#     """
#     if level == "User":
#         return table == username
#     allowed = _LEVEL_ALLOWED_TABLES.get(level, set())
#     return table in allowed

def _load_decoder() -> ModuleType:
    decoder_path = os.path.join(os.path.dirname(__file__), "Decode-RawPolicyFile.py")
    spec = importlib.util.spec_from_file_location("decoder", decoder_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── applicator 실행 ───────────────────────────────────────────────────────────

def _run_applicator(applicator_json: str | None, polkey: str, value: str):
    """
    applicator 커맨드를 실행합니다.
    applicator 가 없거나 빈 리스트이면 건너뜁니다.
    {polkey}, {value} 플레이스홀더를 치환합니다.
    """
    if not applicator_json:
        return

    try:
        cmd = json.loads(applicator_json)
    except json.JSONDecodeError:
        log.warning(f"  applicator 파싱 실패, 건너뜀: {applicator_json}")
        return

    if not cmd:  # 빈 리스트
        return

    # 만약 {value.asIterable} 이 있다면, 해당 값 위치에 value 를 리스트로 변환하여 치환
    if "{value.asIterable}" in cmd:
        try:
            value_list = json.loads(value) if value else []
            if not isinstance(value_list, list) and not isinstance(value_list, set):
                raise ValueError("value.asIterable 플레이스홀더는 리스트 / 세트 타입이어야 합니다.")
            begin_idx = cmd.index("{value.asIterable}")
            cmd = cmd[:begin_idx] + [str(v) for v in value_list] + cmd[begin_idx + 1:]
        except json.JSONDecodeError:
            log.warning(f"  value.asIterable 플레이스홀더 치환 실패, value 가 리스트가 아님: {value}")
            return
        except ValueError as e:
            log.warning(f"  value.asIterable 플레이스홀더 치환 실패: {e}")
            return

    # 플레이스홀더 치환
    cmd = [
        arg.replace("{polkey}", polkey).replace("{value}", value)
        for arg in cmd
    ]

    log.info(f"  applicator 실행: {cmd}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            log.warning(
                f"  applicator 비정상 종료 (code={result.returncode}): "
                f"{result.stderr.strip()}"
            )
    except subprocess.TimeoutExpired:
        log.warning(f"  applicator 타임아웃 (30s): {cmd}")
    except FileNotFoundError:
        log.warning(f"  applicator 실행 파일 없음: {cmd[0]}")


# ── 레시피 키 유효성 확인 ─────────────────────────────────────────────────────

def _get_recipe_valid_keys(recipe_cur: sqlite3.Cursor, table: str) -> set[str] | None:
    """
    레시피 DB 에서 해당 테이블의 유효한 polkey 목록을 반환합니다.
    테이블이 없으면 None 반환 → 알 수 없는 테이블로 처리.
    """
    recipe_cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    if recipe_cur.fetchone() is None:
        return None

    recipe_cur.execute(f'SELECT polkey FROM "{table}"')
    return {row[0] for row in recipe_cur.fetchall()}


# ── 메인 upsert 로직 ──────────────────────────────────────────────────────────

def _apply_to_db(
    decoded: dict,
    db_path: str,
    recipe_db_path: str,
    source_file: str,
    source_digest: str,
    run_applicator: bool,
    dry_run: bool,
):
    pol_id    = decoded["id"]
    pol_name  = decoded["name"]
    level     = decoded["level"]
    username  = decoded.get("user", "")
    data      = decoded["data"]
    now_unix  = int(time.time())

    # 레시피 DB (읽기 전용 — 유효 키 확인용)
    recipe_conn = sqlite3.connect(f"file:{recipe_db_path}?mode=ro", uri=True)
    recipe_cur  = recipe_conn.cursor()

    target_conn = sqlite3.connect(db_path if not dry_run else ":memory:")
    target_conn.execute("PRAGMA journal_mode=WAL")
    target_conn.execute("PRAGMA busy_timeout=5000")
    target_cur  = target_conn.cursor()

    errors: list[str] = []

    try:
        for policy_id, item in data.items():

            # 1. 키 분리
            try:
                table, polkey = _split_policy_id(policy_id)
            except ValueError as e:
                errors.append(str(e))
                continue

            # 2. 레벨 검증
            # if not _validate_table_for_level(table, level, username):
            #     errors.append(
            #         f"'{policy_id}': 레벨 '{level}' 에서 테이블 '{table}' 은 허용되지 않습니다."
            #     )
            #     continue

            # 3. 레시피 DB 에서 유효 키 확인
            valid_keys = _get_recipe_valid_keys(recipe_cur, table)
            if valid_keys is None:
                errors.append(f"'{policy_id}': 레시피 DB 에 테이블 '{table}' 이 없습니다.")
                continue
            if polkey not in valid_keys:
                errors.append(
                    f"'{policy_id}': 키 '{polkey}' 는 레시피에 정의되지 않은 유효하지 않은 정책입니다."
                )
                continue

            # 4. value 추출 및 직렬화
            raw_value = item.get("value")
            if raw_value is None:
                errors.append(f"'{policy_id}': 'value' 필드가 없습니다.")
                continue

            # selections 확인 (레시피 DB 에서 조회)
            recipe_cur.execute(
                f'SELECT selections FROM "{table}" WHERE polkey = ?', (polkey,)
            )
            row = recipe_cur.fetchone()
            if row and row[0]:
                try:
                    selections = json.loads(row[0])
                    if selections and raw_value not in selections:
                        errors.append(
                            f"'{policy_id}': 값 '{raw_value}' 는 허용된 값이 아닙니다. "
                            f"허용값: {selections}"
                        )
                        continue
                except json.JSONDecodeError:
                    log.warning(f"  '{policy_id}': selections 파싱 실패, 검증 건너뜀")

            try:
                serialized_value, value_type = _serialize_value(policy_id, raw_value)
            except TypeError as e:
                errors.append(str(e))
                continue

            log.info(f"  UPSERT [{table}] {polkey} = {serialized_value!r} ({value_type})")

            if not dry_run:
                # 5. 기존 applicator 조회 (실행용)
                target_cur.execute(
                    f'SELECT applicator FROM "{table}" WHERE polkey = ?', (polkey,)
                )
                row = target_cur.fetchone()
                applicator_json = row[0] if row else None

                # 6. DB upsert
                target_cur.execute(f"""
                    INSERT INTO "{table}"
                        (polkey, value, value_type, applied_at,
                         applied_by_pol_id, applied_by_pol_name, applied_by_pol_level,
                         applied_by_pol_user, source, pol_file_digest)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(polkey) DO UPDATE SET
                        value                = excluded.value,
                        value_type           = excluded.value_type,
                        applied_at           = excluded.applied_at,
                        applied_by_pol_id    = excluded.applied_by_pol_id,
                        applied_by_pol_name  = excluded.applied_by_pol_name,
                        applied_by_pol_level = excluded.applied_by_pol_level,
                        applied_by_pol_user  = excluded.applied_by_pol_user,
                        source               = excluded.source,
                        pol_file_digest      = excluded.pol_file_digest
                """, (
                    polkey, serialized_value, value_type, now_unix,
                    pol_id, pol_name, level,
                    username if level == "User" else None,
                    source_file, source_digest,
                ))

                # 7. applicator 실행
                if run_applicator:
                    _run_applicator(applicator_json, polkey, serialized_value)

        # 오류가 하나라도 있으면 전체 롤백
        if errors:
            target_conn.rollback()
            return 1, {"error": "일부 정책 적용 실패", "details": errors}

        target_conn.commit()
        return 0, {"applied": list(data.keys()), "count": len(data)}

    except Exception as e:
        target_conn.rollback()
        log.error(f"예외 발생, 롤백: {e}")
        return 1, {"error": str(e)}

    finally:
        recipe_conn.close()
        target_conn.close()


# ── 파일 digest 계산 ─────────────────────────────────────────────────────────

def _digest_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ── public API ───────────────────────────────────────────────────────────────

def main(
    session,
    file_name: str,
    db_path: str | None = None,
    recipe_db_path: str | None = None,
    run_applicator: bool = True,
    dry_run: bool = False,
) -> tuple[int, dict]:

    db_path        = db_path        or DB_PATH
    recipe_db_path = recipe_db_path or DB_PATH

    # 1. 디코더로 정책 파일 파싱 + 변수 치환
    decoder = _load_decoder()
    exit_code, decoded = decoder.main(session, file_name)
    if exit_code != 0:
        return 1, decoded  # 디코더 오류를 그대로 전달

    # 2. 소스 파일 digest
    source_digest = _digest_file(file_name)
    source_file   = os.path.basename(file_name)

    # 3. DB 적용
    return _apply_to_db(
        decoded       = decoded,
        db_path       = db_path,
        recipe_db_path= recipe_db_path,
        source_file   = source_file,
        source_digest = source_digest,
        run_applicator= run_applicator,
        dry_run       = dry_run,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="정책 파일을 디코딩하여 machinepol DB 에 적용합니다."
    )
    parser.add_argument("file",            help="정책 JSON 파일 경로")
    parser.add_argument("--db",            help="대상 DB 경로")
    parser.add_argument("--recipe-db",     help="레시피 DB 경로 (유효 키 확인용)")
    parser.add_argument("--no-applicator", action="store_true", help="applicator 실행 생략")
    parser.add_argument("--dry-run",       action="store_true", help="DB 변경 없이 검증만")
    parser.add_argument("--verbose",       action="store_true")
    args = parser.parse_args()

    if args.verbose:
        log.setLevel(logging.DEBUG)

    exit_code, output = main(
        session        = None,
        file_name      = args.file,
        db_path        = args.db,
        recipe_db_path = args.recipe_db,
        run_applicator = not args.no_applicator,
        dry_run        = args.dry_run,
    )

    if exit_code != 0:
        print(json.dumps(output, indent=4, ensure_ascii=False), file=sys.stderr)
    else:
        print(json.dumps(output, indent=4, ensure_ascii=False))

    sys.exit(exit_code)
