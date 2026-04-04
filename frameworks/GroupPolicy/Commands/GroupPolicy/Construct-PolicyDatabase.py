#!/usr/bin/env python3
"""
machinepol DB 생성/업데이트 엔진
레시피 파일(JSON5)을 읽어 SQLite DB를 구성합니다.
"""

import sqlite3
import json
import re
import sys
import os
import hashlib
import argparse
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)
DB_PATH="{{SYS_FRAMEWORKS}}/GroupPolicy/policy.db"

# ── JSON5 주석 제거 ──────────────────────────────────────────────────────────

def strip_json5_comments(text: str) -> str:
    """// 한 줄 주석과 trailing comma 를 제거해 표준 JSON 으로 변환합니다."""
    # // 주석 제거 (문자열 내부 제외)
    result = re.sub(r'//[^\n]*', '', text)
    # trailing comma 제거  ,  } 또는 ,  ]
    result = re.sub(r',\s*([}\]])', r'\1', result)
    return result


def load_recipe(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    cleaned = strip_json5_comments(raw)
    return json.loads(cleaned)


# ── 메타 정보 검증 ────────────────────────────────────────────────────────────

def validate_meta(meta: dict):
    assert "file" in meta, "__meta.file 이 없습니다."
    assert "format" in meta, "__meta.format 이 없습니다."
    if meta["format"] != 1:
        raise ValueError(f"지원하지 않는 format 버전: {meta['format']}")


# ── 테이블 스키마 생성 ────────────────────────────────────────────────────────

def build_create_sql(table_name: str, schema: dict) -> str:
    """__table 스키마 정의로부터 CREATE TABLE SQL 을 생성합니다."""
    cols = []
    for col, props in schema.items():
        col_type = props.get("type", "TEXT")
        parts = [f'"{col}" {col_type}']
        if props.get("primary_key"):
            parts.append("PRIMARY KEY")
        if props.get("auto_increment"):
            # SQLite 에서는 INTEGER PRIMARY KEY 가 자동으로 rowid alias 가 됨
            # AUTOINCREMENT 키워드는 gap 없는 증가가 필요할 때만 사용
            pass
        if props.get("unique"):
            parts.append("UNIQUE")
        cols.append(" ".join(parts))
    cols_sql = ",\n    ".join(cols)
    return f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n    {cols_sql}\n);'


# ── 정책 행 upsert ────────────────────────────────────────────────────────────

POLICY_COLUMNS = [
    "polkey", "value_type", "uuid", "applicator", "selections",
    "default_value", "source", "pol_file_digest"
]

def upsert_policies(cur: sqlite3.Cursor, table_name: str,
                    policies: dict, source: str, digest: str):
    """정책 딕셔너리를 테이블에 INSERT OR REPLACE 합니다."""
    for polkey, props in policies.items():
        if not isinstance(props, dict):
            log.warning(f"  '{polkey}' 값이 dict 가 아니므로 건너뜁니다.")
            continue

        applicator = props.get("applicator")
        applicator_str = json.dumps(applicator) if applicator is not None else None

        selections = props.get("selections")
        selections_str = json.dumps(selections) if selections is not None else None

        default_value = props.get("default_value")
        default_str = (
            json.dumps(default_value)
            if not isinstance(default_value, str)
            else default_value
        ) if default_value is not None else None

        cur.execute(f"""
            INSERT INTO "{table_name}"
                (polkey, value_type, uuid, applicator, selections, default_value, source, pol_file_digest)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(polkey) DO UPDATE SET
                value_type      = excluded.value_type,
                uuid            = excluded.uuid,
                applicator      = excluded.applicator,
                selections      = excluded.selections,
                default_value   = excluded.default_value,
                source          = excluded.source,
                pol_file_digest = excluded.pol_file_digest
        """, (
            polkey,
            props.get("type"),
            props.get("uuid"),
            applicator_str,
            selections_str,
            default_str,
            source,
            digest,
        ))
        log.info(f"  UPSERT [{table_name}] {polkey}")


# ── 고아 행 제거 (업데이트 시) ────────────────────────────────────────────────

def remove_orphans(cur: sqlite3.Cursor, table_name: str,
                   valid_keys: set, source: str):
    """레시피에 더 이상 존재하지 않는 키를 같은 source 에서 제거합니다."""
    cur.execute(f'SELECT polkey FROM "{table_name}" WHERE source = ?', (source,))
    existing = {row[0] for row in cur.fetchall()}
    orphans = existing - valid_keys
    for key in orphans:
        cur.execute(f'DELETE FROM "{table_name}" WHERE polkey = ? AND source = ?',
                    (key, source))
        log.warning(f"  REMOVE orphan [{table_name}] {key}")


# ── Current 테이블 기록 ───────────────────────────────────────────────────────

def update_current_table(cur: sqlite3.Cursor, recipe_path: str,
                         digest: str, meta: dict):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS "Current" (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    info = {
        "recipe_file":   os.path.basename(recipe_path),
        "recipe_digest": digest,
        "format":        str(meta.get("format")),
        "updated_at":    str(int(datetime.now().timestamp())),
        "db_file":       meta.get("file", DB_PATH),
    }
    for k, v in info.items():
        cur.execute("""
            INSERT INTO "Current" (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (k, v))


# ── 메인 엔진 ─────────────────────────────────────────────────────────────────

RESERVED_KEYS = {"__meta", "__table", "Current"}

def run(recipe_path: str, db_path: str | None = None, dry_run: bool = False):
    # 1. 레시피 로드
    log.info(f"레시피 로드: {recipe_path}")
    recipe = load_recipe(recipe_path)

    meta  = recipe.get("__meta", {})
    validate_meta(meta)

    schema = recipe.get("__table", {})
    if meta["file"] == "SYS":
        meta["file"] = DB_PATH
    db_path = db_path or meta["file"]

    # 2. 레시피 파일 digest 계산
    with open(recipe_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()

    source = os.path.basename(recipe_path)

    log.info(f"대상 DB   : {db_path}")
    log.info(f"레시피 해시: {digest[:16]}...")

    if dry_run:
        log.info("[dry-run] DB 변경 없이 파싱만 수행합니다.")

    conn = sqlite3.connect(db_path if not dry_run else ":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()

    try:
        # 3. 정책 테이블들 생성 + 데이터 upsert
        policy_tables = {
            k: v for k, v in recipe.items()
            if k not in RESERVED_KEYS and not k.startswith("__")
        }

        for table_name, policies in policy_tables.items():
            log.info(f"테이블 처리: {table_name}")
            create_sql = build_create_sql(table_name, schema)
            cur.execute(create_sql)

            if isinstance(policies, dict) and policies:
                upsert_policies(cur, table_name, policies, source, digest)
                remove_orphans(cur, table_name, set(policies.keys()), source)
            else:
                log.info(f"  (정책 없음 — 테이블만 생성)")

        # 4. Current 테이블 업데이트
        update_current_table(cur, recipe_path, digest, meta)

        conn.commit()
        log.info("완료.")

    except Exception as e:
        conn.rollback()
        log.error(f"오류 발생, 롤백: {e}")
        raise
    finally:
        conn.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(session, recipe_path: str, db_path: str | None = None, dry_run: bool = False) -> tuple[int, str]:
    run(recipe_path, db_path, dry_run)
    return 0, ""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="machinepol 레시피 → SQLite DB 생성/업데이트 엔진"
    )
    parser.add_argument("recipe", help="레시피 JSON5 파일 경로")
    parser.add_argument("--db", help="출력 DB 경로 (기본: 레시피의 __meta.file)")
    parser.add_argument("--dry-run", action="store_true",
                        help="실제 DB 변경 없이 파싱/검증만 수행")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        log.setLevel(logging.DEBUG)

    main(None, args.recipe, db_path=args.db, dry_run=args.dry_run)
