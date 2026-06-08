from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
ACTOR = "migrate_merge_environment_v1"
UNIFIED_TABLE = "product_test_environment_unified"
UNIFIED_COLUMNS = [
    "product_test_environment_id",
    "product_test_environment_name",
    "product_test_environment_status",
    "test_country",
    "test_city",
    "test_company",
    "test_building",
    "test_floor",
    "test_room",
    "network_type",
    "test_computer_name",
    "operating_system_version",
    "test_tool_name",
    "test_tool_version",
    "power_voltage",
    "power_frequency",
    "power_connector_type",
    "power_condition",
    "captured_at",
    "remark",
    "project_id",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
]


@contextmanager
def db_copy(path: Path, writable: bool):
    temp_dir = Path(tempfile.mkdtemp(prefix="task11_env_merge_", dir=PROJECT_ROOT))
    try:
        copied = []
        for suffix in ("", "-wal", "-shm"):
            src = Path(f"{path}{suffix}")
            if src.exists():
                shutil.copy2(src, temp_dir / src.name)
                copied.append(src.name)
        copy_path = temp_dir / path.name
        if writable:
            conn = sqlite3.connect(str(copy_path))
        else:
            conn = sqlite3.connect(f"file:{copy_path.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn, {"copy_path": str(copy_path), "copied_sidecars": copied}
        finally:
            conn.close()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def backup_database(src: Path) -> Path:
    backup_dir = PROJECT_ROOT / "data" / "backups" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{src.stem}.task11_{datetime.now().strftime('%H%M%S')}.db"
    with sqlite3.connect(str(src)) as source, sqlite3.connect(str(backup_path)) as dest:
        source.backup(dest)
    return backup_path


def fetch_scalar(conn: sqlite3.Connection, query: str, params: tuple = ()) -> int:
    return int(conn.execute(query, params).fetchone()[0] or 0)


def build_merged_remark(env_row: sqlite3.Row, def_row: sqlite3.Row) -> str:
    parts = []
    if (def_row["remark"] or "").strip():
        parts.append(str(def_row["remark"]).strip())
    if (env_row["remark"] or "").strip():
        parts.append(f"[구 env 노트] {str(env_row['remark']).strip()}")
    parts.append(f"[구 env id] {env_row['product_test_environment_id']}")
    parts.append(f"[구 def id] {def_row['product_test_environment_definition_id']}")
    return "\n".join(parts)


def collect_scan(conn: sqlite3.Connection) -> dict:
    table_exists = {
        "environment": fetch_scalar(
            conn, "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='product_test_environment'"
        ),
        "environment_definition": fetch_scalar(
            conn, "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='product_test_environment_definition'"
        ),
        "environment_unified": fetch_scalar(
            conn, f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{UNIFIED_TABLE}'"
        ),
    }
    if not table_exists["environment"] or not table_exists["environment_definition"]:
        raise RuntimeError("TASK 11 대상 테이블이 없습니다.")
    return {
        "table_exists": table_exists,
        "environment_count": fetch_scalar(conn, "SELECT COUNT(*) FROM product_test_environment"),
        "environment_definition_count": fetch_scalar(conn, "SELECT COUNT(*) FROM product_test_environment_definition"),
        "run_environment_distinct_count": fetch_scalar(
            conn,
            "SELECT COUNT(DISTINCT product_test_environment_id) FROM product_test_run WHERE product_test_environment_id IS NOT NULL",
        ),
        "run_environment_fk_orphans": fetch_scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM product_test_run run
            LEFT JOIN product_test_environment env
              ON env.product_test_environment_id = run.product_test_environment_id
            WHERE run.product_test_environment_id IS NOT NULL
              AND env.product_test_environment_id IS NULL
            """,
        ),
        "missing_definition_rows": fetch_scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM product_test_environment env
            LEFT JOIN product_test_environment_definition def
              ON def.product_test_environment_definition_id = env.product_test_environment_definition_id
            WHERE env.product_test_environment_definition_id IS NOT NULL
              AND def.product_test_environment_definition_id IS NULL
            """,
        ),
        "duplicate_definition_links": fetch_scalar(
            conn,
            """
            SELECT COUNT(*) FROM (
                SELECT product_test_environment_definition_id
                FROM product_test_environment
                GROUP BY product_test_environment_definition_id
                HAVING COUNT(*) > 1
            )
            """,
        ),
    }


def load_pairs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            env.product_test_environment_id,
            env.product_test_environment_definition_id,
            env.product_test_environment_name,
            env.product_test_environment_status,
            env.network_type,
            env.test_computer_name,
            env.operating_system_version,
            env.test_tool_version,
            env.power_voltage,
            env.power_frequency,
            env.power_connector_type,
            env.captured_at,
            env.remark AS env_remark,
            env.project_id AS env_project_id,
            env.created_at AS env_created_at,
            env.created_by AS env_created_by,
            env.updated_at AS env_updated_at,
            env.updated_by AS env_updated_by,
            def.product_test_environment_definition_name,
            def.test_country,
            def.test_city,
            def.test_company,
            def.test_building,
            def.test_floor,
            def.test_room,
            def.network_type AS def_network_type,
            def.test_computer_name AS def_test_computer_name,
            def.operating_system_version AS def_operating_system_version,
            def.test_tool_name,
            def.test_tool_version AS def_test_tool_version,
            def.power_voltage AS def_power_voltage,
            def.power_frequency AS def_power_frequency,
            def.power_connector_type AS def_power_connector_type,
            def.power_condition,
            def.product_test_environment_definition_status,
            def.remark AS def_remark,
            def.project_id AS def_project_id,
            def.created_at AS def_created_at,
            def.created_by AS def_created_by,
            def.updated_at AS def_updated_at,
            def.updated_by AS def_updated_by
        FROM product_test_environment env
        JOIN product_test_environment_definition def
          ON def.product_test_environment_definition_id = env.product_test_environment_definition_id
        ORDER BY env.product_test_environment_id
        """
    ).fetchall()


def create_unified_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE {UNIFIED_TABLE} (
            product_test_environment_id TEXT PRIMARY KEY,
            product_test_environment_name TEXT NOT NULL,
            product_test_environment_status TEXT NOT NULL,
            test_country TEXT,
            test_city TEXT,
            test_company TEXT,
            test_building TEXT,
            test_floor TEXT,
            test_room TEXT,
            network_type TEXT,
            test_computer_name TEXT,
            operating_system_version TEXT,
            test_tool_name TEXT,
            test_tool_version TEXT,
            power_voltage TEXT,
            power_frequency TEXT,
            power_connector_type TEXT,
            power_condition TEXT,
            captured_at TEXT,
            remark TEXT,
            project_id TEXT,
            created_at TEXT,
            created_by TEXT,
            updated_at TEXT,
            updated_by TEXT
        )
        """
    )


def merge_rows(conn: sqlite3.Connection, now_text: str) -> list[dict]:
    samples: list[dict] = []
    for row in load_pairs(conn):
        merged_name = row["product_test_environment_name"] or row["product_test_environment_definition_name"] or row["product_test_environment_id"]
        merged_status = row["product_test_environment_status"] or row["product_test_environment_definition_status"] or "ACTIVE"
        merged_project_id = row["env_project_id"] or row["def_project_id"]
        merged_created_at = row["env_created_at"] or row["def_created_at"] or now_text
        merged_created_by = row["env_created_by"] or row["def_created_by"] or ACTOR
        merged_updated_at = now_text
        merged_updated_by = ACTOR
        merged_remark = build_merged_remark(
            {
                "product_test_environment_id": row["product_test_environment_id"],
                "remark": row["env_remark"],
            },
            {
                "product_test_environment_definition_id": row["product_test_environment_definition_id"],
                "remark": row["def_remark"],
            },
        )
        values = (
            row["product_test_environment_id"],
            merged_name,
            merged_status,
            row["test_country"],
            row["test_city"],
            row["test_company"],
            row["test_building"],
            row["test_floor"],
            row["test_room"],
            row["network_type"] or row["def_network_type"],
            row["test_computer_name"] or row["def_test_computer_name"],
            row["operating_system_version"] or row["def_operating_system_version"],
            row["test_tool_name"],
            row["test_tool_version"] or row["def_test_tool_version"],
            row["power_voltage"] or row["def_power_voltage"],
            row["power_frequency"] or row["def_power_frequency"],
            row["power_connector_type"] or row["def_power_connector_type"],
            row["power_condition"],
            row["captured_at"],
            merged_remark,
            merged_project_id,
            merged_created_at,
            merged_created_by,
            merged_updated_at,
            merged_updated_by,
        )
        placeholders = ",".join("?" for _ in UNIFIED_COLUMNS)
        conn.execute(
            f"INSERT INTO {UNIFIED_TABLE} ({','.join(UNIFIED_COLUMNS)}) VALUES ({placeholders})",
            values,
        )
        if len(samples) < 6:
            samples.append(
                {
                    "product_test_environment_id": row["product_test_environment_id"],
                    "product_test_environment_definition_id": row["product_test_environment_definition_id"],
                    "merged_name": merged_name,
                    "merged_status": merged_status,
                    "remark_preview": merged_remark[:300],
                }
            )
    return samples


def validate_unified(conn: sqlite3.Connection) -> dict:
    return {
        "unified_count": fetch_scalar(conn, f"SELECT COUNT(*) FROM {UNIFIED_TABLE}"),
        "run_fk_orphans_to_unified": fetch_scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM product_test_run run
            LEFT JOIN {UNIFIED_TABLE} env
              ON env.product_test_environment_id = run.product_test_environment_id
            WHERE run.product_test_environment_id IS NOT NULL
              AND env.product_test_environment_id IS NULL
            """,
        ),
        "rows_with_captured_at": fetch_scalar(
            conn,
            f"SELECT COUNT(*) FROM {UNIFIED_TABLE} WHERE captured_at IS NOT NULL AND TRIM(captured_at) != ''",
        ),
        "rows_with_env_note_marker": fetch_scalar(
            conn,
            f"SELECT COUNT(*) FROM {UNIFIED_TABLE} WHERE remark LIKE '%[구 env 노트]%'",
        ),
        "rows_with_env_id_marker": fetch_scalar(
            conn,
            f"SELECT COUNT(*) FROM {UNIFIED_TABLE} WHERE remark LIKE '%[구 env id]%'",
        ),
        "rows_with_def_id_marker": fetch_scalar(
            conn,
            f"SELECT COUNT(*) FROM {UNIFIED_TABLE} WHERE remark LIKE '%[구 def id]%'",
        ),
    }


def dry_run_payload(conn: sqlite3.Connection, meta: dict) -> dict:
    scan = collect_scan(conn)
    if scan["environment_count"] != scan["environment_definition_count"]:
        raise RuntimeError("Environment 1:1 전제 불일치")
    if scan["missing_definition_rows"] or scan["duplicate_definition_links"]:
        raise RuntimeError("Environment 병합 전제 불일치")
    now_text = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    create_unified_table(conn)
    samples = merge_rows(conn, now_text)
    validation = validate_unified(conn)
    return {
        "mode": "dry-run",
        "meta": meta,
        "scan": scan,
        "summary": {
            "unified_table": UNIFIED_TABLE,
            "rows_to_merge": scan["environment_count"],
            "run_environment_distinct_count": scan["run_environment_distinct_count"],
            "sample_rows": samples,
            "validation": validation,
        },
    }


def apply_changes(conn: sqlite3.Connection) -> dict:
    scan = collect_scan(conn)
    if scan["environment_count"] != scan["environment_definition_count"]:
        raise RuntimeError("Environment 1:1 전제 불일치")
    if scan["missing_definition_rows"] or scan["duplicate_definition_links"]:
        raise RuntimeError("Environment 병합 전제 불일치")
    now_text = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    create_unified_table(conn)
    samples = merge_rows(conn, now_text)
    conn.execute("DROP TABLE product_test_environment")
    conn.execute("DROP TABLE product_test_environment_definition")
    validation = validate_unified(conn)
    return {
        "rows_to_merge": scan["environment_count"],
        "run_environment_distinct_count": scan["run_environment_distinct_count"],
        "sample_rows": samples,
        "validation": validation,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        backup_path = backup_database(DB_PATH)
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            summary = apply_changes(conn)
            conn.commit()
            print(
                json.dumps(
                    {
                        "mode": "apply",
                        "backup_path": str(backup_path),
                        "summary": summary,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        finally:
            conn.close()
        return 0
    with db_copy(DB_PATH, writable=True) as (conn, meta):
        payload = dry_run_payload(conn, meta)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
