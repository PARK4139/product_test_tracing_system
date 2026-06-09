from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "product_test_tracking_system.db"
DEFAULT_DIAGNOSIS = ROOT_DIR / "docs" / "run_target_relink_diagnosis_20260609.md"


@dataclass
class MappingRow:
    run_id: str
    old_target_id: str
    new_target_id: str
    result_count: int
    changed: bool


def copy_wal_safe_database() -> Path:
    scratch_dir = Path(tempfile.mkdtemp(prefix="stepc_relink_", dir=str(ROOT_DIR)))
    copy_base = scratch_dir / DB_PATH.name
    for suffix in ("", "-wal", "-shm"):
        src = Path(str(DB_PATH) + suffix)
        if src.exists():
            shutil.copy2(src, Path(str(copy_base) + suffix))
    return copy_base


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def parse_diagnosis_table(path: Path) -> list[MappingRow]:
    text = path.read_text(encoding="utf-8")
    marker = "## 전체 run -> target 매핑표"
    if marker not in text:
        raise SystemExit(f"diagnosis table marker missing: {path}")
    section = text.split(marker, 1)[1]
    rows: list[MappingRow] = []
    for line in section.splitlines():
        if not line.startswith("|"):
            if rows:
                break
            continue
        if "| --- " in line or "changed | run_id | old_target_id" in line:
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) < 12:
            continue
        changed_mark, run_id, old_target_id, new_target_id = parts[0], parts[1], parts[2], parts[3]
        result_count_text = parts[10]
        run_id = run_id.strip("`")
        old_target_id = old_target_id.strip("`")
        new_target_id = new_target_id.strip("`")
        changed = changed_mark == "Y"
        if not run_id:
            continue
        rows.append(
            MappingRow(
                run_id=run_id,
                old_target_id=old_target_id,
                new_target_id=new_target_id,
                result_count=int(result_count_text),
                changed=changed,
            )
        )
    if not rows:
        raise SystemExit(f"no mapping rows parsed from {path}")
    return rows


def backup_database() -> Path:
    backup_dir = ROOT_DIR / "data" / "backups" / datetime.now().strftime("%Y-%m-%d")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{DB_PATH.stem}.stepc_{datetime.now().strftime('%H%M%S')}.db"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def compute_preview(conn: sqlite3.Connection, mappings: list[MappingRow]) -> dict:
    changed_rows = [row for row in mappings if row.changed]
    run_ids = [row.run_id for row in changed_rows]
    placeholders = ",".join("?" for _ in run_ids)
    existing = {
        row["product_test_run_id"]: row["product_test_target_id"]
        for row in conn.execute(
            f"SELECT product_test_run_id, product_test_target_id FROM product_test_run WHERE product_test_run_id IN ({placeholders})",
            run_ids,
        ).fetchall()
    }
    missing_runs = [run_id for run_id in run_ids if run_id not in existing]
    if missing_runs:
        raise SystemExit(f"missing run ids in DB: {missing_runs}")
    mismatched = [
        row.run_id
        for row in changed_rows
        if existing[row.run_id] != row.old_target_id
    ]
    if mismatched:
        raise SystemExit(f"diagnosis old_target mismatch for runs: {mismatched[:5]}")

    distinct_after = conn.execute(
        f"""
        WITH remap(run_id, new_target_id) AS (
            VALUES {",".join(["(?, ?)"] * len(changed_rows))}
        )
        SELECT COUNT(DISTINCT COALESCE(remap.new_target_id, run.product_test_target_id))
        FROM product_test_run run
        LEFT JOIN remap ON remap.run_id = run.product_test_run_id
        """,
        [item for row in changed_rows for item in (row.run_id, row.new_target_id)],
    ).fetchone()[0]
    fk_orphans_after = conn.execute(
        f"""
        WITH remap(run_id, new_target_id) AS (
            VALUES {",".join(["(?, ?)"] * len(changed_rows))}
        )
        SELECT COUNT(*)
        FROM product_test_run run
        LEFT JOIN remap ON remap.run_id = run.product_test_run_id
        LEFT JOIN product_test_target_unified target
          ON target.product_test_target_id = COALESCE(remap.new_target_id, run.product_test_target_id)
        WHERE target.product_test_target_id IS NULL
        """,
        [item for row in changed_rows for item in (row.run_id, row.new_target_id)],
    ).fetchone()[0]
    result_run_orphans = conn.execute(
        """
        SELECT COUNT(*)
        FROM product_test_result res
        LEFT JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
        WHERE run.product_test_run_id IS NULL
        """
    ).fetchone()[0]
    return {
        "changed_run_count": len(changed_rows),
        "changed_result_count": sum(row.result_count for row in changed_rows),
        "distinct_after": distinct_after,
        "fk_orphans_after": fk_orphans_after,
        "result_run_orphans": result_run_orphans,
        "sample_rows": changed_rows[:10],
    }


def apply_changes(conn: sqlite3.Connection, mappings: list[MappingRow]) -> int:
    changed_rows = [row for row in mappings if row.changed]
    conn.execute("BEGIN")
    try:
        for row in changed_rows:
            conn.execute(
                "UPDATE product_test_run SET product_test_target_id=? WHERE product_test_run_id=?",
                (row.new_target_id, row.run_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return len(changed_rows)


def print_preview(preview: dict) -> None:
    print("[STEP C] run -> target relink")
    print(f"- changed_run_count={preview['changed_run_count']}")
    print(f"- changed_result_count={preview['changed_result_count']}")
    print(f"- run_target_distinct_after={preview['distinct_after']}")
    print(f"- run_to_target_unified_fk_orphans_after={preview['fk_orphans_after']}")
    print(f"- result_to_run_orphans={preview['result_run_orphans']}")
    print("- sample_changes:")
    for row in preview["sample_rows"]:
        print(
            f"  - {row.run_id}: {row.old_target_id} -> {row.new_target_id}"
            f" (results={row.result_count})"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Relink run.product_test_target_id from approved diagnosis mapping.")
    parser.add_argument("--diagnosis", default=str(DEFAULT_DIAGNOSIS))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    diagnosis_path = Path(args.diagnosis)
    mappings = parse_diagnosis_table(diagnosis_path)
    preview_db = copy_wal_safe_database()
    with connect(preview_db) as preview_conn:
        preview = compute_preview(preview_conn, mappings)
    print_preview(preview)

    if not args.apply:
        print("- mode=dry-run")
        return

    backup_path = backup_database()
    with connect(DB_PATH) as conn:
        updated_count = apply_changes(conn, mappings)
        verification = compute_preview(conn, mappings)
    print("- mode=apply")
    print(f"- backup={backup_path}")
    print(f"- updated_run_count={updated_count}")
    print(f"- postcheck_changed_run_count={verification['changed_run_count']}")


if __name__ == "__main__":
    main()
