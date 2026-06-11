"""TASK 15-4 apply: unified RUN/RESULT/CASE/PROCEDURE ID migration."""
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
ACTOR = "task15_4_bulk_apply_v1"
NOW = datetime.now(timezone.utc).isoformat()
REPORT_RELEASE_REMAP = {
    "RELEASE-HRK_9000A_1_1_1A-RC1": "RELEASE-HRK_9000A_1_1_1A-WIFI_1ST-RUN_RC1",
    "RELEASE-HRK_9000A_1_1_1A-RC2": "RELEASE-HRK_9000A_1_1_1A-WIFI_1ST-RUN_RC2",
}


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


dryrun = _load_module("task15_4_dryrun", PROJECT_ROOT / "scripts" / "task15_4_bulk_apply_dryrun.py")
task15_2 = dryrun.task15_2
task15_3 = dryrun.task15_3


def backup_database(src: Path) -> Path:
    backup_dir = PROJECT_ROOT / "data" / "backups" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{src.stem}.task15_4_{datetime.now().strftime('%H%M%S')}.db"
    with sqlite3.connect(str(src)) as source, sqlite3.connect(str(backup_path)) as dest:
        source.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        source.backup(dest)
    return backup_path


def append_remark(existing: str | None, line: str) -> str:
    base = (existing or "").strip()
    return f"{line}\n{base}".strip() if base else line


def collect_plan(conn: sqlite3.Connection) -> dict:
    preview = dryrun.simulate_post_apply(conn)
    if preview.get("blocked"):
        raise RuntimeError(f"dry-run blocked: {preview.get('reason')}")
    if sum(preview["orphans"].values()) > 0 or any(preview["pk_collision_checks"].values()) or preview["ap_token_hits"]:
        raise RuntimeError("pre-apply validation failed")
    run_plan = task15_2.collect_mapping(conn)
    case_plan = task15_3.collect_case_mapping(conn)
    return {
        "run_plan": run_plan,
        "case_plan": case_plan,
        "report_mappings": preview["report_mappings"],
        "defect_mappings": preview["defect_mappings"],
        "drop_run_ids": [e["old_run_id"] for e in run_plan["migrate_drop"]],
        "counts": preview["counts"],
    }


def apply_migration(conn: sqlite3.Connection, plan: dict) -> None:
    run_plan = plan["run_plan"]
    case_plan = plan["case_plan"]

    run_id_map = {e["old_run_id"]: e["new_run_id"] for e in run_plan["run_mappings"] if e["new_run_id"]}
    result_id_map = {e["old_result_id"]: e["new_result_id"] for e in run_plan["result_mappings"]}
    result_run_map = {e["old_result_id"]: run_id_map[e["old_run_id"]] for e in run_plan["result_mappings"]}
    result_case_map = {e["old_result_id"]: e["new_case_id"] for e in case_plan["result_case_mappings"]}

    conn.execute("PRAGMA foreign_keys=OFF")

    for old_run_id, new_run_id in run_id_map.items():
        row = conn.execute("SELECT * FROM product_test_run WHERE product_test_run_id=?", (old_run_id,)).fetchone()
        if not row:
            raise RuntimeError(f"missing run {old_run_id}")
        remark = append_remark(row["remark"], f"[구 run id] {old_run_id}")
        remark = append_remark(remark, f"[구 release] {row['product_test_release_id']}")
        conn.execute(
            """
            INSERT INTO product_test_run (
                product_test_run_id, product_test_release_id, product_test_target_id,
                product_test_environment_id, product_test_run_status, started_at, started_by,
                finished_at, cancelled_at, cancelled_by, cancel_reason, created_at, created_by,
                updated_at, updated_by, remark, project_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_run_id,
                row["product_test_release_id"],
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
                NOW,
                ACTOR,
                remark,
                row["project_id"],
            ),
        )

    for meta in case_plan["case_mappings"]:
        new_case_id = meta["new_case_id"]
        source_old = meta["source_old_case_ids"][0]
        row = conn.execute("SELECT * FROM product_test_case WHERE product_test_case_id=?", (source_old,)).fetchone()
        if not row:
            raise RuntimeError(f"missing source case {source_old} for {new_case_id}")
        remark = append_remark(row["remark"], f"[구 case id] {source_old}")
        if meta.get("remark_append"):
            remark = append_remark(remark, meta["remark_append"])
        conn.execute(
            """
            INSERT INTO product_test_case (
                product_test_case_id, product_test_case_title, test_category, test_objective,
                precondition, expected_result, product_test_case_status, created_at, created_by,
                updated_at, updated_by, remark, project_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_case_id,
                row["product_test_case_title"],
                row["test_category"],
                row["test_objective"],
                row["precondition"],
                row["expected_result"],
                row["product_test_case_status"],
                row["created_at"],
                row["created_by"],
                NOW,
                ACTOR,
                remark,
                row["project_id"],
            ),
        )

    for entry in case_plan["procedure_mappings"]:
        old_proc_id = entry["old_procedure_id"]
        new_proc_id = entry["new_procedure_id"]
        new_case_id = entry["new_case_id"]
        row = conn.execute(
            "SELECT * FROM product_test_procedure WHERE product_test_procedure_id=?", (old_proc_id,)
        ).fetchone()
        if not row:
            raise RuntimeError(f"missing procedure {old_proc_id}")
        remark = append_remark(row["remark"], f"[구 procedure id] {old_proc_id}")
        conn.execute(
            """
            INSERT INTO product_test_procedure (
                product_test_procedure_id, product_test_case_id, procedure_sequence,
                procedure_action, expected_result, acceptance_criteria, required_evidence_type,
                product_test_procedure_status, created_at, created_by, updated_at, updated_by,
                remark, project_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_proc_id,
                new_case_id,
                row["procedure_sequence"],
                row["procedure_action"],
                row["expected_result"],
                row["acceptance_criteria"],
                row["required_evidence_type"],
                row["product_test_procedure_status"],
                row["created_at"],
                row["created_by"],
                NOW,
                ACTOR,
                remark,
                row["project_id"],
            ),
        )

    for old_result_id, new_result_id in result_id_map.items():
        row = conn.execute(
            "SELECT * FROM product_test_result WHERE product_test_result_id=?", (old_result_id,)
        ).fetchone()
        if not row:
            raise RuntimeError(f"missing result {old_result_id}")
        remark = append_remark(row["remark"], f"[구 result id] {old_result_id}")
        conn.execute(
            """
            INSERT INTO product_test_result (
                product_test_result_id, product_test_run_id, product_test_case_id,
                product_test_result_status, actual_result, judgement_reason, result_judged_at,
                result_judged_by, created_at, created_by, updated_at, updated_by, remark, project_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_result_id,
                result_run_map[old_result_id],
                result_case_map[old_result_id],
                row["product_test_result_status"],
                row["actual_result"],
                row["judgement_reason"],
                row["result_judged_at"],
                row["result_judged_by"],
                row["created_at"],
                row["created_by"],
                NOW,
                ACTOR,
                remark,
                row["project_id"],
            ),
        )

    for entry in plan["defect_mappings"]:
        conn.execute(
            """
            UPDATE product_test_defect
            SET product_test_result_id=?, retest_product_test_result_id=?, updated_at=?, updated_by=?
            WHERE product_test_defect_id=?
            """,
            (
                entry["new_result_id"],
                entry["new_retest_result_id"],
                NOW,
                ACTOR,
                entry["product_test_defect_id"],
            ),
        )

    for old_result_id, new_result_id in result_id_map.items():
        conn.execute(
            "UPDATE product_test_evidence SET product_test_result_id=? WHERE product_test_result_id=?",
            (new_result_id, old_result_id),
        )
        conn.execute(
            "UPDATE product_test_procedure_result SET product_test_result_id=? WHERE product_test_result_id=?",
            (new_result_id, old_result_id),
        )

    for proc in case_plan["procedure_mappings"]:
        conn.execute(
            "UPDATE product_test_procedure_result SET product_test_procedure_id=? WHERE product_test_procedure_id=?",
            (proc["new_procedure_id"], proc["old_procedure_id"]),
        )

    for rep in plan["report_mappings"]:
        if rep["release_changed"]:
            row = conn.execute(
                "SELECT remark FROM product_test_report WHERE product_test_report_id=?",
                (rep["product_test_report_id"],),
            ).fetchone()
            remark = append_remark(
                row["remark"] if row else None,
                f"[구 report release] {rep['old_release_id']}",
            )
            conn.execute(
                """
                UPDATE product_test_report
                SET product_test_release_id=?, remark=?, updated_at=?, updated_by=?
                WHERE product_test_report_id=?
                """,
                (rep["new_release_id"], remark, NOW, ACTOR, rep["product_test_report_id"]),
            )
        conn.execute(
            "UPDATE product_test_report_snapshot SET product_test_release_id=? WHERE product_test_release_id=?",
            (rep["new_release_id"], rep["old_release_id"]),
        )

    old_result_ids = list(result_id_map.keys())
    old_proc_ids = [e["old_procedure_id"] for e in case_plan["procedure_mappings"]]
    old_case_ids = sorted({cid for meta in case_plan["case_mappings"] for cid in meta["source_old_case_ids"]})
    old_run_ids = sorted(set(run_id_map.keys()) | set(plan["drop_run_ids"]))

    for rid in old_result_ids:
        conn.execute("DELETE FROM product_test_result WHERE product_test_result_id=?", (rid,))
    for pid in old_proc_ids:
        conn.execute("DELETE FROM product_test_procedure WHERE product_test_procedure_id=?", (pid,))
    for cid in old_case_ids:
        conn.execute("DELETE FROM product_test_case WHERE product_test_case_id=?", (cid,))
    for rid in old_run_ids:
        conn.execute("DELETE FROM product_test_run WHERE product_test_run_id=?", (rid,))

    conn.execute("PRAGMA foreign_keys=ON")


def validate_post_apply(conn: sqlite3.Connection) -> dict:
    counts = {
        "runs": conn.execute("SELECT COUNT(*) FROM product_test_run").fetchone()[0],
        "results": conn.execute("SELECT COUNT(*) FROM product_test_result").fetchone()[0],
        "cases": conn.execute("SELECT COUNT(*) FROM product_test_case").fetchone()[0],
        "procedures": conn.execute("SELECT COUNT(*) FROM product_test_procedure").fetchone()[0],
        "defects": conn.execute("SELECT COUNT(*) FROM product_test_defect").fetchone()[0],
        "reports": conn.execute("SELECT COUNT(*) FROM product_test_report").fetchone()[0],
    }
    orphans = {
        "result_to_run": conn.execute(
            """
            SELECT COUNT(*) FROM product_test_result res
            LEFT JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
            WHERE run.product_test_run_id IS NULL
            """
        ).fetchone()[0],
        "result_to_case": conn.execute(
            """
            SELECT COUNT(*) FROM product_test_result res
            LEFT JOIN product_test_case c ON c.product_test_case_id = res.product_test_case_id
            WHERE c.product_test_case_id IS NULL
            """
        ).fetchone()[0],
        "procedure_to_case": conn.execute(
            """
            SELECT COUNT(*) FROM product_test_procedure p
            LEFT JOIN product_test_case c ON c.product_test_case_id = p.product_test_case_id
            WHERE c.product_test_case_id IS NULL
            """
        ).fetchone()[0],
        "defect_to_result": conn.execute(
            """
            SELECT COUNT(*) FROM product_test_defect d
            LEFT JOIN product_test_result r ON r.product_test_result_id = d.product_test_result_id
            WHERE r.product_test_result_id IS NULL
            """
        ).fetchone()[0],
        "report_to_release": conn.execute(
            """
            SELECT COUNT(*) FROM product_test_report rep
            LEFT JOIN product_test_release rel ON rel.product_test_release_id = rep.product_test_release_id
            WHERE rel.product_test_release_id IS NULL
            """
        ).fetchone()[0],
    }
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    return {"counts": counts, "orphans": orphans, "integrity_check": integrity}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Run apply (default: dry-run preflight only)")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    try:
        plan = collect_plan(conn)
        if not args.apply:
            print(json.dumps({"step": "15-4", "mode": "preflight", "status": "READY", "counts": plan["counts"]}, ensure_ascii=False, indent=2))
            return 0

        backup_path = backup_database(DB_PATH)
        apply_migration(conn, plan)
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        validation = validate_post_apply(conn)
        payload = {
            "step": "15-4",
            "mode": "apply",
            "status": "APPLIED",
            "backup_path": str(backup_path),
            "expected": plan["counts"],
            "validation": validation,
        }
        out = PROJECT_ROOT / "docs" / "task15_4_apply_result.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if validation["integrity_check"] != "ok" or any(validation["orphans"].values()):
            return 1
        if validation["counts"]["results"] != 375 or validation["counts"]["cases"] != 134:
            return 1
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
