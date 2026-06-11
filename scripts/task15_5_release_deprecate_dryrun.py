"""TASK 15-5 dry-run: release table removal + FK drift fix preview."""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
CANONICAL_ROUNDS = {
    "ROUND-WIFI_1ST",
    "ROUND-WIFI_1ST_IMPROVE",
    "ROUND-WIFI_2ND",
    "ROUND-WIFI_2ND_IMPROVE",
    "ROUND-DOWNGRADE",
    "ROUND-WIFI_SMOKE",
    "ROUND-WBS",
}


def resolve_round_for_release(
    conn: sqlite3.Connection,
    release_id: str,
    cache: dict[str, str | None],
) -> str | None:
    if release_id in cache:
        return cache[release_id]
    seen: set[str] = set()
    current = release_id
    while current and current not in seen:
        seen.add(current)
        row = conn.execute(
            "SELECT test_round_id, upstream_release_id FROM product_test_release WHERE product_test_release_id=?",
            (current,),
        ).fetchone()
        if not row:
            cache[release_id] = None
            return None
        if row["test_round_id"]:
            cache[release_id] = row["test_round_id"]
            return row["test_round_id"]
        current = row["upstream_release_id"]
    cache[release_id] = None
    return None


@contextmanager
def readonly_db_copy(src: Path, prefix: str):
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
            yield conn, {"copy_path": str(copy_path), "mode": "dry-run"}
        finally:
            conn.close()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def fk_check_status(conn: sqlite3.Connection) -> dict:
    try:
        rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        return {"ok": len(rows) == 0, "violations": len(rows), "samples": [dict(r) for r in rows[:5]]}
    except sqlite3.OperationalError as exc:
        return {"ok": False, "violations": -1, "error": str(exc), "samples": []}


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        is not None
    )


def collect_plan(conn: sqlite3.Connection) -> dict:
    cache: dict[str, str | None] = {}
    run_rows = conn.execute(
        """
        SELECT product_test_run_id, product_test_release_id, product_test_environment_id, remark
        FROM product_test_run ORDER BY product_test_run_id
        """
    ).fetchall()

    run_mappings = []
    missing_round = []
    for row in run_rows:
        rnd = resolve_round_for_release(conn, row["product_test_release_id"], cache)
        entry = {
            "product_test_run_id": row["product_test_run_id"],
            "old_release_id": row["product_test_release_id"],
            "test_round_id": rnd,
            "env_id": row["product_test_environment_id"],
            "remark_has_legacy_release": "[구 release]" in (row["remark"] or ""),
        }
        run_mappings.append(entry)
        if not rnd or rnd not in CANONICAL_ROUNDS:
            missing_round.append(entry)

    report_mappings = []
    missing_report_round = []
    for row in conn.execute(
        "SELECT product_test_report_id, product_test_release_id, remark FROM product_test_report ORDER BY 1"
    ):
        rnd = resolve_round_for_release(conn, row["product_test_release_id"], cache)
        entry = {
            "product_test_report_id": row["product_test_report_id"],
            "old_release_id": row["product_test_release_id"],
            "test_round_id": rnd,
            "remark_has_legacy_report_release": "[구 report release]" in (row["remark"] or ""),
        }
        report_mappings.append(entry)
        if not rnd or rnd not in CANONICAL_ROUNDS:
            missing_report_round.append(entry)

    snapshot_mappings = []
    missing_snapshot_round = []
    for row in conn.execute(
        """
        SELECT product_test_report_snapshot_id, product_test_release_id
        FROM product_test_report_snapshot ORDER BY 1
        """
    ):
        rnd = resolve_round_for_release(conn, row["product_test_release_id"], cache)
        entry = {
            "product_test_report_snapshot_id": row["product_test_report_snapshot_id"],
            "old_release_id": row["product_test_release_id"],
            "test_round_id": rnd,
        }
        snapshot_mappings.append(entry)
        if not rnd or rnd not in CANONICAL_ROUNDS:
            missing_snapshot_round.append(entry)

    release_ref_tables = [
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE '%product_test_release%'"
        )
    ]

    return {
        "counts": {
            "runs": len(run_mappings),
            "reports": len(report_mappings),
            "report_snapshots": len(snapshot_mappings),
            "releases_to_drop": conn.execute("SELECT COUNT(*) FROM product_test_release").fetchone()[0],
            "legacy_environment_table_exists": table_exists(conn, "product_test_environment"),
            "unified_environment_rows": conn.execute(
                "SELECT COUNT(*) FROM product_test_environment_unified"
            ).fetchone()[0],
        },
        "fk_before": fk_check_status(conn),
        "run_mappings": run_mappings,
        "report_mappings": report_mappings,
        "snapshot_mappings": snapshot_mappings,
        "missing_run_round": missing_round,
        "missing_report_round": missing_report_round,
        "missing_snapshot_round": missing_snapshot_round,
        "env_orphan_runs": conn.execute(
            """
            SELECT COUNT(*) FROM product_test_run run
            LEFT JOIN product_test_environment_unified env
              ON env.product_test_environment_id = run.product_test_environment_id
            WHERE env.product_test_environment_id IS NULL
            """
        ).fetchone()[0],
        "release_ref_tables": release_ref_tables,
        "schema_plan": {
            "product_test_run": {
                "add": ["test_round_id TEXT NOT NULL REFERENCES product_test_round(test_round_id)"],
                "drop_columns": ["product_test_release_id"],
                "fk_fix": "product_test_environment_id -> product_test_environment_unified",
            },
            "product_test_report": {
                "add": ["test_round_id TEXT NOT NULL REFERENCES product_test_round(test_round_id)"],
                "drop_columns": ["product_test_release_id"],
            },
            "product_test_report_snapshot": {
                "add": ["test_round_id TEXT NOT NULL REFERENCES product_test_round(test_round_id)"],
                "drop_columns": ["product_test_release_id"],
            },
            "drop_tables": ["product_test_release"],
        },
    }


def simulate_apply_on_copy(conn: sqlite3.Connection, plan: dict) -> dict:
    round_by_run = {m["product_test_run_id"]: m["test_round_id"] for m in plan["run_mappings"]}
    round_by_report = {m["product_test_report_id"]: m["test_round_id"] for m in plan["report_mappings"]}
    round_by_snapshot = {
        m["product_test_report_snapshot_id"]: m["test_round_id"] for m in plan["snapshot_mappings"]
    }
    cache: dict[str, str | None] = {}

    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute(
            """
            CREATE TABLE product_test_run_new (
                product_test_run_id TEXT NOT NULL PRIMARY KEY,
                test_round_id TEXT NOT NULL,
                product_test_target_id TEXT NOT NULL,
                product_test_environment_id TEXT NOT NULL,
                product_test_run_status TEXT NOT NULL,
                started_at TEXT,
                started_by TEXT NOT NULL,
                finished_at TEXT,
                cancelled_at TEXT,
                cancelled_by TEXT,
                cancel_reason TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                remark TEXT,
                project_id TEXT,
                FOREIGN KEY (test_round_id) REFERENCES product_test_round(test_round_id),
                FOREIGN KEY (product_test_target_id) REFERENCES product_test_target_unified(product_test_target_id),
                FOREIGN KEY (product_test_environment_id) REFERENCES product_test_environment_unified(product_test_environment_id),
                FOREIGN KEY (project_id) REFERENCES project(project_id)
            )
            """
        )
        for row in conn.execute("SELECT * FROM product_test_run"):
            conn.execute(
                """
                INSERT INTO product_test_run_new (
                    product_test_run_id, test_round_id, product_test_target_id, product_test_environment_id,
                    product_test_run_status, started_at, started_by, finished_at, cancelled_at, cancelled_by,
                    cancel_reason, created_at, created_by, updated_at, updated_by, remark, project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["product_test_run_id"],
                    round_by_run[row["product_test_run_id"]],
                    row["product_test_target_id"],
                    row["product_test_environment_id"],
                    row["product_test_run_status"],
                    row["started_at"],
                    row["started_by"],
                    row["finished_at"],
                    row["cancelled_at"],
                    row["cancelled_by"],
                    row["cancel_reason"],
                    row["created_at"],
                    row["created_by"],
                    row["updated_at"],
                    row["updated_by"],
                    row["remark"],
                    row["project_id"],
                ),
            )
        conn.execute("DROP TABLE product_test_run")
        conn.execute("ALTER TABLE product_test_run_new RENAME TO product_test_run")

        conn.execute(
            """
            CREATE TABLE product_test_report_new (
                product_test_report_id TEXT NOT NULL PRIMARY KEY,
                test_round_id TEXT NOT NULL,
                product_test_report_type TEXT NOT NULL,
                product_test_report_status TEXT NOT NULL,
                product_test_report_title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                approved_at TEXT,
                approved_by TEXT,
                rejected_at TEXT,
                rejected_by TEXT,
                rejection_reason TEXT,
                remark TEXT,
                project_id TEXT,
                FOREIGN KEY (test_round_id) REFERENCES product_test_round(test_round_id),
                FOREIGN KEY (project_id) REFERENCES project(project_id)
            )
            """
        )
        for row in conn.execute("SELECT * FROM product_test_report"):
            remark = row["remark"] or ""
            if "[구 report release]" not in remark:
                remark = f"[구 report release] {row['product_test_release_id']}\n{remark}".strip()
            conn.execute(
                """
                INSERT INTO product_test_report_new (
                    product_test_report_id, test_round_id, product_test_report_type, product_test_report_status,
                    product_test_report_title, created_at, created_by, updated_at, updated_by,
                    approved_at, approved_by, rejected_at, rejected_by, rejection_reason, remark, project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["product_test_report_id"],
                    round_by_report[row["product_test_report_id"]],
                    row["product_test_report_type"],
                    row["product_test_report_status"],
                    row["product_test_report_title"],
                    row["created_at"],
                    row["created_by"],
                    row["updated_at"],
                    row["updated_by"],
                    row["approved_at"],
                    row["approved_by"],
                    row["rejected_at"],
                    row["rejected_by"],
                    row["rejection_reason"],
                    remark,
                    row["project_id"],
                ),
            )
        conn.execute("DROP TABLE product_test_report")
        conn.execute("ALTER TABLE product_test_report_new RENAME TO product_test_report")

        if table_exists(conn, "product_test_report_snapshot"):
            conn.execute(
                """
                CREATE TABLE product_test_report_snapshot_new (
                    product_test_report_snapshot_id TEXT NOT NULL PRIMARY KEY,
                    product_test_report_id TEXT NOT NULL,
                    test_round_id TEXT NOT NULL,
                    snapshot_type TEXT NOT NULL,
                    snapshot_format TEXT NOT NULL,
                    snapshot_payload TEXT NOT NULL,
                    snapshot_hash TEXT NOT NULL,
                    source_data_locked INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    remark TEXT,
                    project_id TEXT,
                    FOREIGN KEY (product_test_report_id) REFERENCES product_test_report(product_test_report_id),
                    FOREIGN KEY (test_round_id) REFERENCES product_test_round(test_round_id),
                    FOREIGN KEY (project_id) REFERENCES project(project_id)
                )
                """
            )
            for row in conn.execute("SELECT * FROM product_test_report_snapshot"):
                snap_id = row["product_test_report_snapshot_id"]
                rnd = round_by_snapshot.get(snap_id)
                if rnd is None:
                    rnd = resolve_round_for_release(conn, row["product_test_release_id"], cache)
                conn.execute(
                    """
                    INSERT INTO product_test_report_snapshot_new (
                        product_test_report_snapshot_id, product_test_report_id, test_round_id,
                        snapshot_type, snapshot_format, snapshot_payload, snapshot_hash,
                        source_data_locked, created_at, created_by, remark, project_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snap_id,
                        row["product_test_report_id"],
                        rnd,
                        row["snapshot_type"],
                        row["snapshot_format"],
                        row["snapshot_payload"],
                        row["snapshot_hash"],
                        row["source_data_locked"],
                        row["created_at"],
                        row["created_by"],
                        row["remark"],
                        row["project_id"],
                    ),
                )
            conn.execute("DROP TABLE product_test_report_snapshot")
            conn.execute("ALTER TABLE product_test_report_snapshot_new RENAME TO product_test_report_snapshot")

        conn.execute("DROP TABLE IF EXISTS product_test_release")
        if table_exists(conn, "product_test_environment"):
            conn.execute("DROP TABLE product_test_environment")
    finally:
        conn.execute("PRAGMA foreign_keys=ON")

    post_counts = {
        "runs": conn.execute("SELECT COUNT(*) FROM product_test_run").fetchone()[0],
        "results": conn.execute("SELECT COUNT(*) FROM product_test_result").fetchone()[0],
        "cases": conn.execute("SELECT COUNT(*) FROM product_test_case").fetchone()[0],
        "procedures": conn.execute("SELECT COUNT(*) FROM product_test_procedure").fetchone()[0],
        "defects": conn.execute("SELECT COUNT(*) FROM product_test_defect").fetchone()[0],
        "reports": conn.execute("SELECT COUNT(*) FROM product_test_report").fetchone()[0],
        "report_snapshots": conn.execute("SELECT COUNT(*) FROM product_test_report_snapshot").fetchone()[0],
        "release_table_exists": table_exists(conn, "product_test_release"),
    }
    run_cols = [r[1] for r in conn.execute("PRAGMA table_info(product_test_run)")]
    report_cols = [r[1] for r in conn.execute("PRAGMA table_info(product_test_report)")]
    snap_cols = [r[1] for r in conn.execute("PRAGMA table_info(product_test_report_snapshot)")]
    orphans = {
        "result_to_run": conn.execute(
            """
            SELECT COUNT(*) FROM product_test_result res
            LEFT JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
            WHERE run.product_test_run_id IS NULL
            """
        ).fetchone()[0],
        "run_to_round": conn.execute(
            """
            SELECT COUNT(*) FROM product_test_run run
            LEFT JOIN product_test_round rnd ON rnd.test_round_id = run.test_round_id
            WHERE rnd.test_round_id IS NULL
            """
        ).fetchone()[0],
        "report_to_round": conn.execute(
            """
            SELECT COUNT(*) FROM product_test_report rep
            LEFT JOIN product_test_round rnd ON rnd.test_round_id = rep.test_round_id
            WHERE rnd.test_round_id IS NULL
            """
        ).fetchone()[0],
        "snapshot_to_round": conn.execute(
            """
            SELECT COUNT(*) FROM product_test_report_snapshot snap
            LEFT JOIN product_test_round rnd ON rnd.test_round_id = snap.test_round_id
            WHERE rnd.test_round_id IS NULL
            """
        ).fetchone()[0],
        "run_to_env_unified": conn.execute(
            """
            SELECT COUNT(*) FROM product_test_run run
            LEFT JOIN product_test_environment_unified env
              ON env.product_test_environment_id = run.product_test_environment_id
            WHERE env.product_test_environment_id IS NULL
            """
        ).fetchone()[0],
        "run_to_target_unified": conn.execute(
            """
            SELECT COUNT(*) FROM product_test_run run
            LEFT JOIN product_test_target_unified tgt
              ON tgt.product_test_target_id = run.product_test_target_id
            WHERE tgt.product_test_target_id IS NULL
            """
        ).fetchone()[0],
    }

    return {
        "post_counts": post_counts,
        "orphans": orphans,
        "fk_after": fk_check_status(conn),
        "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
        "run_schema": {
            "test_round_id": "test_round_id" in run_cols,
            "product_test_release_id": "product_test_release_id" in run_cols,
        },
        "report_schema": {
            "test_round_id": "test_round_id" in report_cols,
            "product_test_release_id": "product_test_release_id" in report_cols,
        },
        "snapshot_schema": {
            "test_round_id": "test_round_id" in snap_cols,
            "product_test_release_id": "product_test_release_id" in snap_cols,
        },
    }


def grep_code_references() -> dict:
    app_root = PROJECT_ROOT / "app"
    pattern = re.compile(r"product_test_release")
    hits: list[dict] = []
    for path in sorted(app_root.rglob("*")):
        if path.suffix not in {".py", ".js", ".html"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        count = len(pattern.findall(text))
        if count:
            hits.append({"path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"), "count": count})
    return {"app_files_with_release_refs": len(hits), "hits": hits, "total_refs": sum(h["count"] for h in hits)}


def main() -> int:
    output_path = PROJECT_ROOT / "docs" / "task15_5_dryrun.json"
    with readonly_db_copy(DB_PATH, "task15_5_") as (conn, meta):
        plan = collect_plan(conn)
        blocked = bool(
            plan["missing_run_round"]
            or plan["missing_report_round"]
            or plan["missing_snapshot_round"]
            or plan["env_orphan_runs"]
        )

        sim_conn = sqlite3.connect(meta["copy_path"])
        sim_conn.row_factory = sqlite3.Row
        simulation = simulate_apply_on_copy(sim_conn, plan)
        sim_conn.close()

        code_grep = grep_code_references()
        expected_snapshots = plan["counts"]["report_snapshots"]
        validation = {
            "run_round_missing_zero": len(plan["missing_run_round"]) == 0,
            "report_round_missing_zero": len(plan["missing_report_round"]) == 0,
            "snapshot_round_missing_zero": len(plan["missing_snapshot_round"]) == 0,
            "env_orphan_runs_zero": plan["env_orphan_runs"] == 0,
            "fk_after_zero": simulation["fk_after"]["ok"],
            "release_table_dropped": not simulation["post_counts"]["release_table_exists"],
            "data_loss_zero": (
                simulation["post_counts"]["runs"] == 41
                and simulation["post_counts"]["results"] == 375
                and simulation["post_counts"]["cases"] == 134
                and simulation["post_counts"]["procedures"] == 339
                and simulation["post_counts"]["defects"] == 15
                and simulation["post_counts"]["reports"] == 8
                and simulation["post_counts"]["report_snapshots"] == expected_snapshots
            ),
            "run_has_test_round_id": simulation["run_schema"]["test_round_id"],
            "run_release_column_removed": not simulation["run_schema"]["product_test_release_id"],
            "report_release_column_removed": not simulation["report_schema"]["product_test_release_id"],
            "snapshot_release_column_removed": not simulation["snapshot_schema"]["product_test_release_id"],
            "sim_orphans_zero": sum(simulation["orphans"].values()) == 0,
        }
        status = "READY" if not blocked and all(validation.values()) else "BLOCKED"

        payload = {
            "step": "15-5",
            "mode": "dry-run",
            "status": status,
            "meta": meta,
            "summary": plan["counts"],
            "fk_before": plan["fk_before"],
            "fk_after_simulation": simulation["fk_after"],
            "validation": validation,
            "schema_plan": plan["schema_plan"],
            "run_round_mappings": plan["run_mappings"],
            "report_round_mappings": plan["report_mappings"],
            "snapshot_round_mappings": plan["snapshot_mappings"],
            "missing_run_round": plan["missing_run_round"],
            "missing_report_round": plan["missing_report_round"],
            "missing_snapshot_round": plan["missing_snapshot_round"],
            "release_ref_tables_before": plan["release_ref_tables"],
            "simulation": simulation,
            "code_grep_product_test_release": code_grep,
            "apply_notes": {
                "db_transaction": "single transaction on live DB after backup",
                "run_remark": "[구 release] already preserved by 15-4",
                "report_remark": "[구 report release] appended if missing",
                "code_sync": "separate step after DB apply — app/ grep hits must become 0",
            },
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        report = {
            "step": "15-5",
            "mode": "dry-run",
            "status": status,
            "output": str(output_path),
            "summary": plan["counts"],
            "fk_before": plan["fk_before"],
            "fk_after_simulation": simulation["fk_after"],
            "validation": validation,
            "simulation_counts": simulation["post_counts"],
            "code_grep_app_files": code_grep["app_files_with_release_refs"],
            "code_grep_total_refs": code_grep["total_refs"],
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if status != "READY" else 0


if __name__ == "__main__":
    raise SystemExit(main())
