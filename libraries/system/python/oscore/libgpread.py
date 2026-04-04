import sys
import sqlite3
sys.path.append("{{SYS_FRAMEWORKS}}/GroupPolicy/Resources/Libraries")
import getpolvalcommon

def read_policies(username: str, policies_to_read: list[str]) -> list[dict]:
    exit_code, result = getpolvalcommon.fetch_policy_data(username, policies_to_read)
    if exit_code != 0:
        raise Exception(result)
    return result

def get_locale(username: str = "") -> str | None:
    exit_code, conn_or_error = getpolvalcommon.init()
    if exit_code != 0:
        raise Exception(conn_or_error)
    conn: sqlite3.Connection = conn_or_error  # 타입 힌트 명확히 하기 위해 별도 변수에 할당
    with conn:
        cur = conn.cursor()
        locale = getpolvalcommon._get_locale(cur, username)
    conn.close()
    return locale
