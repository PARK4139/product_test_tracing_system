from __future__ import annotations

import argparse
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "product_test_tracking_system.db"
TABLES = ("product_test_target", "product_test_target_definition")


@dataclass
class TableScan:
    name: str
    object_type: str | None
    row_count: int | None


def copy_wal_safe_database() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scratch_dir = ROOT_DIR / f"task12b_drop_preview_{stamp}"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    copy_base = scratch_dir / DB_PATH.name
    for suffix in ("", "-wal", "-shm"):
        source = Path(str(DB_PATH) + suffix)
        if source.exists():
            shutil.copy2(source, Path(str(copy_base) + suffix))
    return copy_base


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def scan_tables(conn: sqlite3.Connection) -> list[TableScan]:
    scans: list[TableScan] = []
    for table_name in TABLES:
        row = conn.execute(
            "SELECT type, name FROM sqlite_master WHERE name=? LIMIT 1",
            (table_name,),
        ).fetchone()
        object_type = row["type"] if row else None
        row_count = None
        if object_type == "table":
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        scans.append(TableScan(name=table_name, object_type=object_type, row_count=row_count))
    return scans


def backup_database() -> Path:
    backup_dir = ROOT_DIR / "data" / "backups" / datetime.now().strftime("%Y-%m-%d")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{DB_PATH.stem}.task12b_{datetime.now().strftime('%H%M%S')}.db"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Drop empty legacy target tables after unified migration.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    preview_db = copy_wal_safe_database()
    with connect(preview_db) as conn:
        scans = scan_tables(conn)

    print("[TASK 12-B] drop old target tables")
    for scan in scans:
        print(f"- {scan.name}: type={scan.object_type!r} rows={scan.row_count}")

    missing_or_empty = all(scan.object_type in {None, "table"} and (scan.row_count or 0) == 0 for scan in scans)
    print(f"- droppable={missing_or_empty}")

    if not args.apply:
        print("- mode=dry-run")
        return

    if not missing_or_empty:
        raise SystemExit("legacy target tables are not empty; refusing apply.")

    backup_path = backup_database()
    with connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            for table_name in TABLES:
                conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()
        finally:
            conn.execute("PRAGMA foreign_keys=ON")

    print(f"- mode=apply")
    print(f"- backup={backup_path}")


if __name__ == "__main__":
    main()
