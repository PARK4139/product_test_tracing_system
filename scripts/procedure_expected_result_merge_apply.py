"""Apply: merge procedure expected_result into acceptance_criteria, drop column."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "procedure_expected_result_merge_apply.json"

KEEP_COLUMNS = [
    "product_test_procedure_id",
    "product_test_case_id",
    "procedure_sequence",
    "procedure_action",
    "acceptance_criteria",
    "required_evidence_type",
    "product_test_procedure_status",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
    "remark",
    "project_id",
]

INDEXES = [
    "CREATE INDEX ix_product_test_procedure_case_id ON product_test_procedure (product_test_case_id)",
    "CREATE INDEX ix_product_test_procedure_project_id ON product_test_procedure (project_id)",
]


def _load_dryrun():
    spec = importlib.util.spec_from_file_location(
        "procedure_er_merge_dryrun",
        PROJECT_ROOT / "scripts" / "procedure_expected_result_merge_dryrun.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


dryrun = _load_dryrun()


def backup_database(src: Path) -> Path:
    backup_dir = PROJECT_ROOT / "data" / "backups" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    backup_path = backup_dir / f"{src.stem}.procedure_er_merge_{stamp}.db"
    with sqlite3.connect(str(src)) as source, sqlite3.connect(str(backup_path)) as dest:
        source.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        source.backup(dest)
    return backup_path


def _column_names(conn: sqlite3.Connection, table_name: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")]


def rebuild_procedure_table(conn: sqlite3.Connection) -> None:
    columns = _column_names(conn, "product_test_procedure")
    if "expected_result" not in columns:
        return

    select_cols = ", ".join(KEEP_COLUMNS)
    conn.execute(
        f"""
        CREATE TABLE product_test_procedure_new (
            product_test_procedure_id TEXT NOT NULL,
            product_test_case_id TEXT NOT NULL,
            procedure_sequence INTEGER NOT NULL,
            procedure_action TEXT NOT NULL,
            acceptance_criteria TEXT NOT NULL,
            required_evidence_type TEXT,
            product_test_procedure_status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by TEXT NOT NULL,
            remark TEXT,
            project_id TEXT,
            PRIMARY KEY (product_test_procedure_id),
            FOREIGN KEY(product_test_case_id) REFERENCES product_test_case (product_test_case_id),
            FOREIGN KEY(project_id) REFERENCES project (project_id)
        )
        """
    )
    conn.execute(
        f"""
        INSERT INTO product_test_procedure_new ({select_cols})
        SELECT {select_cols}
        FROM product_test_procedure
        """
    )
    conn.execute("DROP TABLE product_test_procedure")
    conn.execute("ALTER TABLE product_test_procedure_new RENAME TO product_test_procedure")
    for index_sql in INDEXES:
        conn.execute(index_sql)


def apply_merge_updates(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT product_test_procedure_id, expected_result, acceptance_criteria
        FROM product_test_procedure
        """
    ).fetchall()
    updated = 0
    for row in rows:
        new_acceptance, kind = dryrun.merge_acceptance_criteria(
            expected_result=row["expected_result"],
            acceptance_criteria=row["acceptance_criteria"],
        )
        if not kind.startswith("merged"):
            continue
        conn.execute(
            """
            UPDATE product_test_procedure
            SET acceptance_criteria = ?
            WHERE product_test_procedure_id = ?
            """,
            (new_acceptance, row["product_test_procedure_id"]),
        )
        updated += 1
    return updated


def validate_post_apply(conn: sqlite3.Connection) -> dict:
    procedure_cols = _column_names(conn, "product_test_procedure")
    case_cols = _column_names(conn, "product_test_case")
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    return {
        "procedure_count": conn.execute("SELECT COUNT(*) FROM product_test_procedure").fetchone()[0],
        "case_count": conn.execute("SELECT COUNT(*) FROM product_test_case").fetchone()[0],
        "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
        "foreign_key_violations": len(fk_violations),
        "procedure_has_expected_result": "expected_result" in procedure_cols,
        "case_has_expected_result": "expected_result" in case_cols,
        "procedure_columns": procedure_cols,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"[ERROR] DB not found: {DB_PATH}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    try:
        plan = dryrun.collect_merge_plan(conn)
        if plan["pre_migration"]["integrity_check"] != "ok":
            raise RuntimeError("pre-apply integrity_check failed")
        if plan["pre_migration"]["foreign_key_violations"]:
            raise RuntimeError("pre-apply foreign_key_check failed")

        if not args.apply:
            print(
                json.dumps(
                    {
                        "step": "procedure_er_merge",
                        "mode": "preflight",
                        "status": "READY",
                        "procedure_count": plan["statistics"]["total"],
                        "rows_requiring_acceptance_update": plan["rows_requiring_acceptance_update"],
                    },
                    ensure_ascii=False,
                )
            )
            return 0

        backup_path = backup_database(DB_PATH)
        conn.execute("BEGIN IMMEDIATE")
        merge_updates = apply_merge_updates(conn)
        rebuild_procedure_table(conn)
        report = validate_post_apply(conn)
        if report["integrity_check"] != "ok":
            raise RuntimeError(f"post-apply integrity_check: {report['integrity_check']}")
        if report["foreign_key_violations"]:
            raise RuntimeError("post-apply foreign_key_check failed")
        if report["procedure_has_expected_result"]:
            raise RuntimeError("expected_result column still present on product_test_procedure")
        if not report["case_has_expected_result"]:
            raise RuntimeError("product_test_case.expected_result missing")
        if report["procedure_count"] != plan["statistics"]["total"]:
            raise RuntimeError("procedure row count changed")
        conn.commit()

        payload = {
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "backup_path": str(backup_path),
            "merge_updates": merge_updates,
            "validation": report,
        }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
