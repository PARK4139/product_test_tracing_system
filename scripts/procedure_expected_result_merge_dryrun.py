"""Procedure expected_result -> acceptance_criteria merge dry-run (read-only)."""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "procedure_expected_result_merge_dryrun.json"

MERGE_SEPARATOR = "\n[기대결과] "


def _normalize_text(value: str | None) -> str:
    return str(value or "").strip()


def _expected_already_in_acceptance(expected_result: str, acceptance_criteria: str) -> bool:
    expected = _normalize_text(expected_result)
    acceptance = _normalize_text(acceptance_criteria)
    if not expected:
        return True
    if expected == acceptance:
        return True
    if expected in acceptance:
        return True
    expected_compact = re.sub(r"\s+", "", expected).casefold()
    acceptance_compact = re.sub(r"\s+", "", acceptance).casefold()
    return expected_compact in acceptance_compact


def merge_acceptance_criteria(
    *,
    expected_result: str | None,
    acceptance_criteria: str | None,
) -> tuple[str, str]:
    acceptance = _normalize_text(acceptance_criteria)
    expected = _normalize_text(expected_result)
    if not expected:
        return acceptance, "unchanged_empty_expected"
    if _expected_already_in_acceptance(expected, acceptance):
        return acceptance, "unchanged_already_included"
    if acceptance:
        return f"{acceptance}{MERGE_SEPARATOR}{expected}", "merged_append"
    return expected, "merged_replace_empty_acceptance"


@contextmanager
def readonly_db_copy(src: Path, prefix: str = "proc_er_merge_"):
    live = sqlite3.connect(str(src))
    live.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    live.close()
    temp_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=PROJECT_ROOT))
    try:
        for suffix in ("", "-wal", "-shm"):
            sidecar = Path(f"{src}{suffix}")
            if sidecar.exists():
                shutil.copy2(sidecar, temp_dir / sidecar.name)
        copy_path = temp_dir / src.name
        conn = sqlite3.connect(str(copy_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn, str(copy_path)
        finally:
            conn.close()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def table_sql(conn: sqlite3.Connection, table_name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row["sql"] if row else ""


def simulate_schema_after_drop(conn: sqlite3.Connection) -> dict:
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='product_test_procedure'"
    ).fetchone():
        return {"error": "product_test_procedure table missing"}

    pragma_rows = conn.execute("PRAGMA table_info(product_test_procedure)").fetchall()
    columns = [row["name"] for row in pragma_rows]
    if "expected_result" not in columns:
        return {"already_dropped": True, "columns": columns}

    keep_columns = [c for c in columns if c != "expected_result"]
    create_sql = table_sql(conn, "product_test_procedure")

    return {
        "current_columns": columns,
        "planned_columns": keep_columns,
        "drop_column": "expected_result",
        "rebuild_method": (
            "1) UPDATE acceptance_criteria where merge needed "
            "2) CREATE product_test_procedure_new without expected_result "
            "3) INSERT SELECT 4) DROP old 5) RENAME 6) recreate indexes"
        ),
        "current_create_sql_excerpt": create_sql[:500] if create_sql else "",
        "indexes_preserved": [
            {"name": r["name"], "sql": r["sql"]}
            for r in conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='product_test_procedure'"
            ).fetchall()
        ],
        "fk_notes": "PK product_test_procedure_id unchanged; child FKs preserved",
    }


def collect_merge_plan(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT product_test_procedure_id, product_test_case_id, procedure_sequence,
               procedure_action, expected_result, acceptance_criteria
        FROM product_test_procedure
        ORDER BY product_test_procedure_id
        """
    ).fetchall()

    stats = {
        "total": len(rows),
        "unchanged_empty_expected": 0,
        "unchanged_already_included": 0,
        "merged_append": 0,
        "merged_replace_empty_acceptance": 0,
    }
    samples: list[dict] = []
    updates: list[dict] = []

    for row in rows:
        new_acceptance, kind = merge_acceptance_criteria(
            expected_result=row["expected_result"],
            acceptance_criteria=row["acceptance_criteria"],
        )
        stats[kind] = stats.get(kind, 0) + 1
        if kind.startswith("merged"):
            item = {
                "product_test_procedure_id": row["product_test_procedure_id"],
                "change_kind": kind,
                "before": {
                    "expected_result": row["expected_result"],
                    "acceptance_criteria": row["acceptance_criteria"],
                },
                "after": {"acceptance_criteria": new_acceptance},
            }
            updates.append(item)
            if len(samples) < 10:
                samples.append(item)

    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(DB_PATH),
        "merge_format": {
            "separator": MERGE_SEPARATOR,
            "description": (
                "expected_result empty -> keep acceptance_criteria; "
                "already included -> keep; "
                "else acceptance_criteria + separator + expected_result"
            ),
        },
        "statistics": stats,
        "rows_requiring_acceptance_update": len(updates),
        "rows_unchanged": stats["unchanged_empty_expected"] + stats["unchanged_already_included"],
        "samples": samples,
        "pre_migration": {
            "procedure_count": len(rows),
            "integrity_check": integrity,
            "foreign_key_violations": len(fk),
        },
        "schema_plan": simulate_schema_after_drop(conn),
        "case_table_untouched": {
            "note": "product_test_case.expected_result is NOT modified",
            "case_count": conn.execute("SELECT COUNT(*) FROM product_test_case").fetchone()[0],
            "case_has_expected_result_column": "expected_result"
            in [r["name"] for r in conn.execute("PRAGMA table_info(product_test_case)").fetchall()],
        },
    }


def main() -> int:
    if not DB_PATH.exists():
        print(f"[ERROR] DB not found: {DB_PATH}", file=sys.stderr)
        return 2

    with readonly_db_copy(DB_PATH) as (conn, copy_path):
        plan = collect_merge_plan(conn)
        plan["dry_run_copy"] = copy_path

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    stats = plan["statistics"]
    print("=" * 65)
    print("  Procedure expected_result merge DRY-RUN")
    print(f"  DB: {DB_PATH}")
    print(f"  Output: {OUTPUT_PATH}")
    print("=" * 65)
    print(f"  Total procedures: {stats['total']}")
    print(f"  Unchanged (empty expected_result): {stats['unchanged_empty_expected']}")
    print(f"  Unchanged (already in acceptance): {stats['unchanged_already_included']}")
    print(f"  Merged (append): {stats['merged_append']}")
    print(f"  Merged (replace empty acceptance): {stats['merged_replace_empty_acceptance']}")
    print(f"  Rows requiring UPDATE: {plan['rows_requiring_acceptance_update']}")
    print()
    print("  Merge separator:", json.dumps(MERGE_SEPARATOR, ensure_ascii=False))
    print()
    for idx, sample in enumerate(plan["samples"], 1):
        print(f"  --- Sample {idx}: {sample['product_test_procedure_id']} ({sample['change_kind']}) ---")
        print(f"  BEFORE expected_result: {sample['before']['expected_result']!r}")
        print(f"  BEFORE acceptance_criteria: {sample['before']['acceptance_criteria']!r}")
        print(f"  AFTER acceptance_criteria: {sample['after']['acceptance_criteria']!r}")
        print()
    print("  Schema: DROP column product_test_procedure.expected_result (table rebuild)")
    print("  [DRY-RUN ONLY] apply forbidden until user approval")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
