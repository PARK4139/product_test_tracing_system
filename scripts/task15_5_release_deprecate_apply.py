"""TASK 15-5 apply: release table removal + FK drift fix."""
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


def _load_dryrun():
    spec = importlib.util.spec_from_file_location(
        "task15_5_dryrun",
        PROJECT_ROOT / "scripts" / "task15_5_release_deprecate_dryrun.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


dryrun = _load_dryrun()


def backup_database(src: Path) -> Path:
    backup_dir = PROJECT_ROOT / "data" / "backups" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{src.stem}.task15_5_{datetime.now().strftime('%H%M%S')}.db"
    with sqlite3.connect(str(src)) as source, sqlite3.connect(str(backup_path)) as dest:
        source.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        source.backup(dest)
    return backup_path


def validate_post_apply(conn: sqlite3.Connection) -> dict:
    counts = {
        "runs": conn.execute("SELECT COUNT(*) FROM product_test_run").fetchone()[0],
        "results": conn.execute("SELECT COUNT(*) FROM product_test_result").fetchone()[0],
        "cases": conn.execute("SELECT COUNT(*) FROM product_test_case").fetchone()[0],
        "procedures": conn.execute("SELECT COUNT(*) FROM product_test_procedure").fetchone()[0],
        "defects": conn.execute("SELECT COUNT(*) FROM product_test_defect").fetchone()[0],
        "reports": conn.execute("SELECT COUNT(*) FROM product_test_report").fetchone()[0],
        "report_snapshots": conn.execute("SELECT COUNT(*) FROM product_test_report_snapshot").fetchone()[0],
        "release_table_exists": dryrun.table_exists(conn, "product_test_release"),
    }
    run_cols = [r[1] for r in conn.execute("PRAGMA table_info(product_test_run)")]
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
        "run_to_env_unified": conn.execute(
            """
            SELECT COUNT(*) FROM product_test_run run
            LEFT JOIN product_test_environment_unified env
              ON env.product_test_environment_id = run.product_test_environment_id
            WHERE env.product_test_environment_id IS NULL
            """
        ).fetchone()[0],
    }
    return {
        "counts": counts,
        "orphans": orphans,
        "fk_check": dryrun.fk_check_status(conn),
        "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
        "run_schema": {
            "test_round_id": "test_round_id" in run_cols,
            "product_test_release_id": "product_test_release_id" in run_cols,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    try:
        plan = dryrun.collect_plan(conn)
        blocked = bool(
            plan["missing_run_round"]
            or plan["missing_report_round"]
            or plan["missing_snapshot_round"]
            or plan["env_orphan_runs"]
        )
        if blocked:
            raise RuntimeError("pre-apply plan blocked")

        if not args.apply:
            print(
                json.dumps(
                    {"step": "15-5", "mode": "preflight", "status": "READY", "summary": plan["counts"]},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        backup_path = backup_database(DB_PATH)
        dryrun.simulate_apply_on_copy(conn, plan)
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        validation = validate_post_apply(conn)
        payload = {
            "step": "15-5",
            "mode": "apply",
            "status": "APPLIED",
            "backup_path": str(backup_path),
            "summary": plan["counts"],
            "validation": validation,
        }
        out = PROJECT_ROOT / "docs" / "task15_5_apply_result.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if validation["integrity_check"] != "ok":
            return 1
        if not validation["fk_check"]["ok"]:
            return 1
        if any(validation["orphans"].values()):
            return 1
        if validation["counts"]["release_table_exists"]:
            return 1
        if validation["counts"]["runs"] != 41 or validation["counts"]["results"] != 375:
            return 1
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
