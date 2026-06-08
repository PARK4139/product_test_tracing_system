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
PREFIX_RULES = [
    ("TEST_CONFIG_DEF-", "CONFIG_DEF-"),
    ("TEST_CONFIG-", "CONFIG-"),
    ("TEST_RELEASE-", "RELEASE-"),
    ("TEST_ROUND-", "ROUND-"),
    ("TEST_CASE-", "CASE-"),
]
TARGETS = [
    ("product_test_case", "product_test_case_id", True),
    ("product_test_procedure", "product_test_procedure_id", True),
    ("product_test_procedure", "product_test_case_id", False),
    ("product_test_result", "product_test_case_id", False),
    ("product_test_release", "product_test_release_id", True),
    ("product_test_release", "upstream_release_id", False),
    ("product_test_report", "product_test_release_id", False),
    ("product_test_run", "product_test_release_id", False),
    ("product_test_round", "test_round_id", True),
    ("product_test_release", "test_round_id", False),
    ("product_test_environment", "product_test_environment_id", True),
    ("product_test_run", "product_test_environment_id", False),
    ("product_test_environment_definition", "product_test_environment_definition_id", True),
    ("product_test_environment", "product_test_environment_definition_id", False),
]
FK_QUERIES = {
    "result_to_run": """
        SELECT COUNT(*) FROM product_test_result child
        LEFT JOIN product_test_run parent ON parent.product_test_run_id = child.product_test_run_id
        WHERE child.product_test_run_id IS NOT NULL AND parent.product_test_run_id IS NULL
    """,
    "result_to_case": """
        SELECT COUNT(*) FROM product_test_result child
        LEFT JOIN product_test_case parent ON parent.product_test_case_id = child.product_test_case_id
        WHERE child.product_test_case_id IS NOT NULL AND parent.product_test_case_id IS NULL
    """,
    "procedure_to_case": """
        SELECT COUNT(*) FROM product_test_procedure child
        LEFT JOIN product_test_case parent ON parent.product_test_case_id = child.product_test_case_id
        WHERE child.product_test_case_id IS NOT NULL AND parent.product_test_case_id IS NULL
    """,
    "run_to_release": """
        SELECT COUNT(*) FROM product_test_run child
        LEFT JOIN product_test_release parent ON parent.product_test_release_id = child.product_test_release_id
        WHERE child.product_test_release_id IS NOT NULL AND parent.product_test_release_id IS NULL
    """,
    "run_to_environment": """
        SELECT COUNT(*) FROM product_test_run child
        LEFT JOIN product_test_environment parent ON parent.product_test_environment_id = child.product_test_environment_id
        WHERE child.product_test_environment_id IS NOT NULL AND parent.product_test_environment_id IS NULL
    """,
    "release_to_round": """
        SELECT COUNT(*) FROM product_test_release child
        LEFT JOIN product_test_round parent ON parent.test_round_id = child.test_round_id
        WHERE child.test_round_id IS NOT NULL AND parent.test_round_id IS NULL
    """,
    "environment_to_definition": """
        SELECT COUNT(*) FROM product_test_environment child
        LEFT JOIN product_test_environment_definition parent
          ON parent.product_test_environment_definition_id = child.product_test_environment_definition_id
        WHERE child.product_test_environment_definition_id IS NOT NULL
          AND parent.product_test_environment_definition_id IS NULL
    """,
}
TRAPS = {
    "result_test_report": "SELECT COUNT(*) FROM product_test_result WHERE product_test_result_id LIKE 'RESULT-TEST_REPORT_%'",
    "deprecated_test_case": "SELECT COUNT(*) FROM product_test_case WHERE product_test_case_id LIKE 'DEPRECATED_TEST_CASE-%'",
    "placeholder_test_case": "SELECT COUNT(*) FROM product_test_case WHERE product_test_case_id LIKE 'PLACEHOLDER_EMPTY_CASE-%'",
    "test_target_midword": "SELECT COUNT(*) FROM product_test_case WHERE product_test_case_id LIKE '%_TEST_TARGET%'",
    "wifi_test_word": "SELECT COUNT(*) FROM product_test_release WHERE product_test_release_id LIKE '%WIFI_TEST_%'",
}


def transform(value: str | None) -> str | None:
    if value is None:
        return None
    for old, new in PREFIX_RULES:
        if value.startswith(old):
            return new + value[len(old) :]
    return value


@contextmanager
def db_copy(path: Path, writable: bool):
    temp_dir = Path(tempfile.mkdtemp(prefix="task10_strip_", dir=PROJECT_ROOT))
    try:
        copied = []
        for suffix in ("", "-wal", "-shm"):
            src = Path(f"{path}{suffix}")
            if src.exists():
                shutil.copy2(src, temp_dir / src.name)
                copied.append(src.name)
        copy_path = temp_dir / path.name
        conn = sqlite3.connect(str(copy_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn, {"copy_path": str(copy_path), "copied_sidecars": copied}
        finally:
            conn.close()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def count(conn: sqlite3.Connection, query: str) -> int:
    return int(conn.execute(query).fetchone()[0] or 0)


def collect_plan(conn: sqlite3.Connection) -> dict:
    changes, collisions = [], []
    for table, column, is_pk in TARGETS:
        rows = conn.execute(f"SELECT rowid, {column} AS value FROM {table} WHERE {column} IS NOT NULL ORDER BY rowid").fetchall()
        table_changes = []
        for row in rows:
            new_value = transform(row["value"])
            if new_value == row["value"]:
                continue
            table_changes.append({"rowid": row["rowid"], "old": row["value"], "new": new_value})
        if is_pk:
            for item in table_changes:
                if conn.execute(f"SELECT 1 FROM {table} WHERE {column}=? AND rowid != ?", (item["new"], item["rowid"])).fetchone():
                    collisions.append({"table": table, "column": column, "old": item["old"], "new": item["new"]})
        changes.append({"table": table, "column": column, "is_pk": is_pk, "count": len(table_changes), "samples": table_changes[:10]})
    return {"changes": changes, "collisions": collisions}


def simulate(conn: sqlite3.Connection, plan: dict) -> None:
    conn.execute("PRAGMA foreign_keys=OFF")
    for entry in plan["changes"]:
        table, column = entry["table"], entry["column"]
        for item in entry["samples"] if False else []:
            pass
        for item in conn.execute(f"SELECT rowid, {column} AS value FROM {table} WHERE {column} IS NOT NULL").fetchall():
            new_value = transform(item["value"])
            if new_value != item["value"]:
                conn.execute(f"UPDATE {table} SET {column}=? WHERE rowid=?", (new_value, item["rowid"]))


def summarize(conn: sqlite3.Connection, plan: dict, meta: dict, mode: str, backup_path: str = "") -> dict:
    before_targets = {
        f"{table}.{column}": count(conn, f"SELECT COUNT(*) FROM {table} WHERE {column} LIKE 'TEST_%-%'")
        for table, column, _ in TARGETS
    }
    trap_counts = {name: count(conn, query) for name, query in TRAPS.items()}
    if mode == "dry-run":
        simulate(conn, plan)
    fk_orphans = {name: count(conn, query) for name, query in FK_QUERIES.items()}
    after_targets = {
        f"{table}.{column}": count(conn, f"SELECT COUNT(*) FROM {table} WHERE {column} LIKE 'TEST_%-%'")
        for table, column, _ in TARGETS
    }
    trap_after = {name: count(conn, query) for name, query in TRAPS.items()}
    return {
        "mode": mode,
        "backup_path": backup_path,
        "meta": meta,
        "summary": {
            "column_change_counts": {f"{c['table']}.{c['column']}": c["count"] for c in plan["changes"]},
            "pk_collision_count": len(plan["collisions"]),
            "pk_collisions": plan["collisions"][:20],
            "sample_changes": [sample for c in plan["changes"] for sample in ({**s, "table": c["table"], "column": c["column"]} for s in c["samples"])][:25],
            "target_prefix_counts_before": before_targets,
            "target_prefix_counts_after": after_targets,
            "trap_counts_before": trap_counts,
            "trap_counts_after": trap_after,
            "fk_orphans_after": fk_orphans,
        },
    }


def backup_database(src: Path) -> Path:
    backup_dir = PROJECT_ROOT / "data" / "backups" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{src.stem}.task10_{datetime.now().strftime('%H%M%S')}.db"
    with sqlite3.connect(str(src)) as source, sqlite3.connect(str(backup_path)) as dest:
        source.backup(dest)
    return backup_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        backup_path = backup_database(DB_PATH)
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        meta = {"copy_path": str(DB_PATH), "copied_sidecars": []}
    else:
        backup_path = None
        ctx = db_copy(DB_PATH, writable=True)
        conn, meta = ctx.__enter__()
    try:
        plan = collect_plan(conn)
        if args.apply and plan["collisions"]:
            raise RuntimeError("PK collisions detected. Resolve dry-run first.")
        if args.apply:
            simulate(conn, plan)
            conn.commit()
        payload = summarize(conn, plan, meta, "apply" if args.apply else "dry-run", str(backup_path or ""))
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        conn.close()
        if not args.apply:
            ctx.__exit__(None, None, None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
