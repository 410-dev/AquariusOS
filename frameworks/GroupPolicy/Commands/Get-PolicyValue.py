#!/usr/bin/env python3
# This is objective shell compatible command.

import sys
import json
import sqlite3
import os
from datetime import datetime, timezone

# Usage:
# Get-PolicyValue <user> <Policy key name>
# Get-PolicyValue john MachineOverride/Timezone

# Returns
# {
#     "Id": "MachineOverride/Timezone"
#     "User": "john"
#     "Name": "시간대",
#     "Description": "장치의 로컬 시간대를 설정합니다."
#     "Type": "string",
#     "Value": "UTC+9",
#     "AppliedBy": {
#         "Name": "Policy ABC",
#         "Id":   "policy-abc",
#         "Time": "2024-01-01T00:00:00Z",
#         "PolicyFileDigest": "sha256:9q4h98dosdikjfasdf984ijasdf",
#         "ByUser": "agent",
#         ..other elements...
#     }
# }

# Note: Localization is in "{{SYS_FRAMEWORKS}}/Localization/Policies/<locale>-title.json" and "{{SYS_FRAMEWORKS}}/Localization/Policies/<locale>-description.json"
# Note: Localization setting cascades to: Machine/LanguageAndRegion/PreferredLocale or <user>/LanguageAndRegion/PreferredLocale
# Note: Policy reader is not implemented yet - leave get_locale as-is for now

# 정책 키에서 테이블명과 polkey 를 분리
# "Machine/Hostname"         → ("Machine", "Hostname")
# "MachineOverride/Timezone" → ("MachineOverride", "Timezone")
# "<username>/SomeKey"       → ("<username>", "SomeKey")

def _split_policy_id(policy_id: str) -> tuple[str, str]:
    parts = policy_id.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"정책 키 형식이 올바르지 않습니다: '{policy_id}' (예: 'Machine/Hostname')")
    return parts[0], parts[1]


def get_locale(cur: sqlite3.Cursor, username: str) -> str:
    """
    로케일 캐스케이드 순서:
      1. <username>/LanguageAndRegion/PreferredLocale  (유저 설정)
      2. Machine/LanguageAndRegion/PreferredLocale     (머신 설정)
      3. 시스템 환경변수 LANG                           (OS 폴백)
      4. "en_us"                                       (최종 폴백)
    """

    def _query(table: str, polkey: str) -> str | None:
        # 테이블 존재 여부 먼저 확인
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        if cur.fetchone() is None:
            return None
        cur.execute(
            f'SELECT value FROM "{table}" WHERE polkey = ?',
            (polkey,)
        )
        row = cur.fetchone()
        return row[0] if row and row[0] else None

    # 1. 유저별 로케일
    locale = _query(username, "LanguageAndRegion/PreferredLocale")
    if locale:
        return locale.lower().replace("-", "_")  # "ko-KR" → "ko_kr" 정규화

    # 2. 머신 로케일
    locale = _query("Machine", "LanguageAndRegion/PreferredLocale")
    if locale:
        return locale.lower().replace("-", "_")

    # 3. OS 환경변수 (예: "ko_KR.UTF-8" → "ko_kr")
    lang = os.environ.get("LANG") or os.environ.get("LANGUAGE")
    if lang:
        return lang.split(".")[0].lower().replace("-", "_")

    # 4. 최종 폴백
    return "en_us"


def _load_localization(locale: str, kind: str) -> dict:
    """
    로케일 파일 로드. 없으면 en_us 로 폴백.
    둘 다 없으면 빈 dict 반환.
    """
    def _try_load(loc: str) -> dict | None:
        path = "{{SYS_FRAMEWORKS}}/Localization/Policies/{}-{}.json".format(loc, kind)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as e:
            print(f"[WARN] 로컬라이제이션 파일 파싱 오류 ({path}): {e}", file=sys.stderr)
            return None

    result = _try_load(locale)
    if result is not None:
        return result

    # 폴백: en_us
    if locale != "en_us":
        print(f"[WARN] 로컬라이제이션 파일 없음 ({locale}-{kind}.json), en_us 로 폴백", file=sys.stderr)
        result = _try_load("en_us")
        if result is not None:
            return result

    # 둘 다 없으면 빈 dict
    print(f"[WARN] 로컬라이제이션 파일 없음 (en_us-{kind}.json), 로컬라이제이션 없이 진행", file=sys.stderr)
    return {}


def _unix_to_iso8601(unix_time) -> str | None:
    """Unix timestamp → ISO 8601 UTC 문자열. None/0 이면 None 반환."""
    if not unix_time:
        return None
    try:
        return datetime.fromtimestamp(int(unix_time), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OSError):
        return None


def _fetch_policy_row(cur: sqlite3.Cursor, table: str, polkey: str) -> dict | None:
    """
    지정한 테이블에서 polkey 로 행을 조회합니다.
    테이블이 존재하지 않거나 키가 없으면 None 반환.
    """
    # 테이블 존재 여부 확인 (SQL injection 방지를 위해 sqlite_master 로 검증)
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    if cur.fetchone() is None:
        return None

    cur.execute(
        f'SELECT * FROM "{table}" WHERE polkey = ?',
        (polkey,)
    )
    row = cur.fetchone()
    if row is None:
        return None

    columns = [desc[0] for desc in cur.description]
    return dict(zip(columns, row))


def _build_policy_result(
    policy_id: str,
    username: str,
    row: dict,
    titles: dict,
    descriptions: dict,
) -> dict:
    """DB 행 + 로컬라이제이션으로 최종 응답 dict 를 구성합니다."""

    # AppliedBy — 적용 이력 관련 필드만 묶음
    applied_at_iso = _unix_to_iso8601(row.get("applied_at"))

    digest_raw = row.get("pol_file_digest")
    digest = f"sha256:{digest_raw}" if digest_raw and not digest_raw.startswith("sha256:") else digest_raw

    applied_by: dict | None = None
    if any([
        row.get("applied_by_pol_name"),
        row.get("applied_by_pol_id"),
        applied_at_iso,
    ]):
        applied_by = {
            "Name":              row.get("applied_by_pol_name"),
            "Id":                row.get("applied_by_pol_id"),
            "Time":              applied_at_iso,
            "PolicyFileDigest":  digest,
            "ByUser":            row.get("by_user"),
            "ByProcess":         row.get("by_process"),
            "Source":            row.get("source"),
            "Level":             row.get("applied_by_pol_level"),
            "PolicyUser":        row.get("applied_by_pol_user"),
        }
        # None 값인 키는 제거 (응답을 깔끔하게 유지)
        applied_by = {k: v for k, v in applied_by.items() if v is not None}

    return {
        "Id":          policy_id,
        "User":        username,
        "Name":        titles.get(policy_id, policy_id),           # 로컬라이제이션 없으면 키 자체를 이름으로 사용
        "Description": descriptions.get(policy_id, policy_id),     # 로컬라이제이션 없으면 키 자체를 설명으로 사용 (없느니만 못한 설명보다는 낫다고 판단)
        "Type":        row.get("value_type"),
        "Value":       row.get("value"),
        "AppliedBy":   applied_by,
    }


def main(session, username: str, policies_to_read: list[str]) -> tuple[int, list[dict] | str]:

    DB_PATH = "{{SYS_FRAMEWORKS}}/GroupPolicy/policy.db"

    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.execute("PRAGMA journal_mode=WAL")  # 추가
        conn.execute("PRAGMA busy_timeout=5000")  # 추가: 최대 3초 대기 후 실패
    except sqlite3.OperationalError as e:
        return 1, f"DB Connection failed ({DB_PATH}): {e}"

    results: list[dict] = []
    errors:  list[str]  = []

    with conn:
        cur = conn.cursor()

        locale = get_locale(cur, username)
        titles = _load_localization(locale, "title")
        descriptions = _load_localization(locale, "description")

        for policy_id in policies_to_read:
            # 1. 키 파싱
            try:
                raw_table, polkey = _split_policy_id(policy_id)
            except ValueError as e:
                errors.append(str(e))
                continue

            # 2. 테이블명 결정
            # "<username>" 플레이스홀더가 레시피에 있지만,
            # 실제 DB 에는 실제 유저명 테이블로 저장되어야 함.
            # Machine/MachineOverride 등 고정 테이블은 그대로 사용.
            table = raw_table

            # 3. DB 조회
            row = _fetch_policy_row(cur, table, polkey)
            if row is None:
                errors.append(f"정책을 찾을 수 없습니다: '{policy_id}' (table={table}, key={polkey})")
                continue

            # 4. 결과 구성
            results.append(
                _build_policy_result(policy_id, username, row, titles, descriptions)
            )

    conn.close()

    if errors and not results:
        # 요청한 정책이 전부 실패한 경우에만 에러 코드 반환
        return 1, "\n".join(errors)

    if errors:
        # 일부 실패 — stderr 에 경고만 출력하고 성공한 결과는 반환
        for err in errors:
            print(f"[WARN] {err}", file=sys.stderr)

    return 0, results


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: Get-PolicyValue <user> <PolicyKey> [PolicyKey2 ...]", file=sys.stderr)
        sys.exit(1)

    exit_code, output = main(None, sys.argv[1], sys.argv[2:])

    if exit_code != 0:
        print(f"Failed to load policy value: {output}", file=sys.stderr)
    else:
        print(json.dumps(output, indent=4, ensure_ascii=False))

    sys.exit(exit_code)
