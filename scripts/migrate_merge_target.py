from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "product_test_tracking_system.db"
UNIFIED_TABLE = "product_test_target_unified"


@dataclass
class MergePreview:
    product_test_target_id: str
    product_test_target_definition_id: str
    product_code: str | None
    manufacturer: str | None
    model_name: str | None
    hardware_revision: str | None
    default_software_version: str | None
    default_firmware_version: str | None
    serial_number: str | None
    software_version: str | None
    firmware_version: str | None
    manufacture_lot: str | None
    product_test_target_status: str | None
    remark: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge target + target_definition into unified table.")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the real database.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    return parser.parse_args()


def fetch_scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return 0 if row is None or row[0] is None else int(row[0])


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(
        fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        )
    )


def build_backup_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%H%M%S")
    backup_dir = ROOT_DIR / "data" / "backups" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir / f"{DB_PATH.stem}.task12_{timestamp}{DB_PATH.suffix}"


def backup_database() -> Path:
    backup_path = build_backup_path()
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def copy_wal_bundle(src_db: Path, temp_dir: Path) -> Path:
    db_copy = temp_dir / src_db.name
    shutil.copy2(src_db, db_copy)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(src_db) + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, temp_dir / sidecar.name)
    return db_copy


def merged_remark(
    *,
    def_id: str,
    def_remark: str | None,
    target_id: str,
    target_remark: str | None,
) -> str:
    parts: list[str] = []
    def_remark = (def_remark or "").strip()
    target_remark = (target_remark or "").strip()
    if def_remark:
        parts.append(def_remark)
    parts.append(f"[구 target 노트] {target_remark}" if target_remark else "[구 target 노트]")
    parts.append(f"[구 target id] {target_id}")
    parts.append(f"[구 def id] {def_id}")
    return "\n".join(parts)


def scan_database(conn: sqlite3.Connection) -> dict:
    return {
        "target_count": fetch_scalar(conn, "SELECT COUNT(*) FROM product_test_target"),
        "target_definition_count": fetch_scalar(conn, "SELECT COUNT(*) FROM product_test_target_definition"),
        "run_target_distinct_count": fetch_scalar(
            conn,
            "SELECT COUNT(DISTINCT product_test_target_id) FROM product_test_run WHERE product_test_target_id IS NOT NULL",
        ),
        "run_target_fk_orphans": fetch_scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM product_test_run run
            LEFT JOIN product_test_target target
              ON target.product_test_target_id = run.product_test_target_id
            WHERE run.product_test_target_id IS NOT NULL
              AND target.product_test_target_id IS NULL
            """,
        ),
        "missing_definition_rows": fetch_scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM product_test_target target
            LEFT JOIN product_test_target_definition def
              ON def.product_test_target_definition_id = target.product_test_target_definition_id
            WHERE target.product_test_target_definition_id IS NOT NULL
              AND def.product_test_target_definition_id IS NULL
            """,
        ),
        "duplicate_definition_links": fetch_scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM (
                SELECT product_test_target_definition_id
                FROM product_test_target
                GROUP BY product_test_target_definition_id
                HAVING COUNT(*) > 1
            )
            """,
        ),
    }


def create_unified_table(conn: sqlite3.Connection) -> None:
    conn.execute(f"DROP TABLE IF EXISTS {UNIFIED_TABLE}")
    conn.execute(
        f"""
        CREATE TABLE {UNIFIED_TABLE} (
            product_test_target_id TEXT PRIMARY KEY,
            project_id TEXT,
            product_code TEXT,
            manufacturer TEXT,
            model_name TEXT,
            hardware_revision TEXT,
            default_software_version TEXT,
            default_firmware_version TEXT,
            serial_number TEXT,
            software_version TEXT,
            firmware_version TEXT,
            manufacture_lot TEXT,
            product_test_target_status TEXT NOT NULL,
            created_at TEXT,
            created_by TEXT,
            updated_at TEXT,
            updated_by TEXT,
            remark TEXT
        )
        """
    )


def insert_unified_rows(conn: sqlite3.Connection) -> list[MergePreview]:
    conn.row_factory = sqlite3.Row
    source_rows = conn.execute(
        """
        SELECT
            target.product_test_target_id,
            target.product_test_target_definition_id,
            target.project_id,
            target.serial_number,
            target.software_version,
            target.firmware_version,
            target.manufacture_lot,
            target.product_test_target_status,
            target.created_at,
            target.created_by,
            target.updated_at,
            target.updated_by,
            target.remark AS target_remark,
            def.product_code,
            def.manufacturer,
            def.model_name,
            def.hardware_revision,
            def.default_software_version,
            def.default_firmware_version,
            def.remark AS def_remark
        FROM product_test_target target
        JOIN product_test_target_definition def
          ON def.product_test_target_definition_id = target.product_test_target_definition_id
        ORDER BY target.product_test_target_id
        """
    ).fetchall()
    previews: list[MergePreview] = []
    for row in source_rows:
        remark = merged_remark(
            def_id=row["product_test_target_definition_id"],
            def_remark=row["def_remark"],
            target_id=row["product_test_target_id"],
            target_remark=row["target_remark"],
        )
        conn.execute(
            f"""
            INSERT INTO {UNIFIED_TABLE} (
                product_test_target_id,
                project_id,
                product_code,
                manufacturer,
                model_name,
                hardware_revision,
                default_software_version,
                default_firmware_version,
                serial_number,
                software_version,
                firmware_version,
                manufacture_lot,
                product_test_target_status,
                created_at,
                created_by,
                updated_at,
                updated_by,
                remark
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["product_test_target_id"],
                row["project_id"],
                row["product_code"],
                row["manufacturer"],
                row["model_name"],
                row["hardware_revision"],
                row["default_software_version"],
                row["default_firmware_version"],
                row["serial_number"],
                row["software_version"],
                row["firmware_version"],
                row["manufacture_lot"],
                row["product_test_target_status"],
                row["created_at"],
                row["created_by"],
                row["updated_at"],
                row["updated_by"],
                remark,
            ),
        )
        previews.append(
            MergePreview(
                product_test_target_id=row["product_test_target_id"],
                product_test_target_definition_id=row["product_test_target_definition_id"],
                product_code=row["product_code"],
                manufacturer=row["manufacturer"],
                model_name=row["model_name"],
                hardware_revision=row["hardware_revision"],
                default_software_version=row["default_software_version"],
                default_firmware_version=row["default_firmware_version"],
                serial_number=row["serial_number"],
                software_version=row["software_version"],
                firmware_version=row["firmware_version"],
                manufacture_lot=row["manufacture_lot"],
                product_test_target_status=row["product_test_target_status"],
                remark=remark,
            )
        )
    return previews


def simulate_merge(conn: sqlite3.Connection) -> dict:
    create_unified_table(conn)
    previews = insert_unified_rows(conn)
    return {
        "unified_table": UNIFIED_TABLE,
        "merged_row_count": fetch_scalar(conn, f"SELECT COUNT(*) FROM {UNIFIED_TABLE}"),
        "run_fk_orphans_to_unified": fetch_scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM product_test_run run
            LEFT JOIN {UNIFIED_TABLE} target
              ON target.product_test_target_id = run.product_test_target_id
            WHERE run.product_test_target_id IS NOT NULL
              AND target.product_test_target_id IS NULL
            """,
        ),
        "remark_target_note_count": fetch_scalar(
            conn,
            f"SELECT COUNT(*) FROM {UNIFIED_TABLE} WHERE remark LIKE '%[구 target 노트]%'",
        ),
        "remark_target_id_count": fetch_scalar(
            conn,
            f"SELECT COUNT(*) FROM {UNIFIED_TABLE} WHERE remark LIKE '%[구 target id]%'",
        ),
        "remark_def_id_count": fetch_scalar(
            conn,
            f"SELECT COUNT(*) FROM {UNIFIED_TABLE} WHERE remark LIKE '%[구 def id]%'",
        ),
        "sample_rows": [preview.__dict__ for preview in previews[:3]],
    }


def validate_scan(scan: dict) -> None:
    if scan["target_count"] != scan["target_definition_count"]:
        raise SystemExit("target / target_definition row counts diverged; stop and inspect.")
    if scan["missing_definition_rows"] != 0:
        raise SystemExit("target rows without definition found; stop and inspect.")
    if scan["duplicate_definition_links"] != 0:
        raise SystemExit("definition linked to multiple targets; stop and inspect.")
    if scan["run_target_fk_orphans"] != 0:
        raise SystemExit("run -> target FK orphan found; stop and inspect.")


def run_dry_run(json_mode: bool) -> None:
    with TemporaryDirectory() as tmp:
        db_copy = copy_wal_bundle(DB_PATH, Path(tmp))
        conn = sqlite3.connect(db_copy)
        try:
            scan = scan_database(conn)
            validate_scan(scan)
            simulation = simulate_merge(conn)
        finally:
            conn.close()
    payload = {"scan": scan, "simulation": simulation}
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print("[TASK 12 dry-run] target merge")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_apply(json_mode: bool) -> None:
    backup_path = backup_database()
    conn = sqlite3.connect(DB_PATH)
    try:
        scan = scan_database(conn)
        validate_scan(scan)
        simulation = simulate_merge(conn)
        conn.execute("DROP TABLE product_test_target")
        conn.execute("DROP TABLE product_test_target_definition")
        conn.commit()
    finally:
        conn.close()
    payload = {"backup_path": str(backup_path), "scan": scan, "simulation": simulation}
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print("[TASK 12 apply] target merge")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    args = parse_args()
    if args.apply:
        run_apply(args.json)
        return
    run_dry_run(args.json)


if __name__ == "__main__":
    main()
