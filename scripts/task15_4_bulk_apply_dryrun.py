"""TASK 15-4 dry-run: unified RUN/RESULT/CASE/PROCEDURE ID apply preview."""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sqlite3
import sys
import tempfile
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
AP_TOKEN_PATTERN = re.compile(r"(?<!\w)(?:\d+AP|AP_\d+|\bAP\b)(?!\w)", re.IGNORECASE)
CANONICAL_ROUNDS = {
    "ROUND-WIFI_1ST", "ROUND-WIFI_1ST_IMPROVE", "ROUND-WIFI_2ND", "ROUND-WIFI_2ND_IMPROVE",
    "ROUND-DOWNGRADE", "ROUND-WIFI_SMOKE", "ROUND-WBS",
}
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


task15_2 = _load_module("task15_2", PROJECT_ROOT / "scripts" / "task15_2_run_result_id_dryrun.py")
task15_3 = _load_module("task15_3", PROJECT_ROOT / "scripts" / "task15_3_case_reissue_dryrun.py")


@contextmanager
def readonly_db(src: Path, prefix: str):
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
        conn = sqlite3.connect(f"file:{copy_path.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn, {"copy_path": str(copy_path), "mode": "dry-run"}
        finally:
            conn.close()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def resolve_round_for_release(conn: sqlite3.Connection, release_id: str, cache: dict[str, str | None]) -> str | None:
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


def collect_report_mappings(conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    mappings, blocked = [], []
    cache: dict[str, str | None] = {}
    for row in conn.execute("SELECT product_test_report_id, product_test_release_id FROM product_test_report"):
        old = row["product_test_release_id"]
        new = REPORT_RELEASE_REMAP.get(old, old)
        exists = conn.execute("SELECT 1 FROM product_test_release WHERE product_test_release_id=?", (new,)).fetchone()
        rnd = resolve_round_for_release(conn, new, cache) if exists else None
        entry = {"product_test_report_id": row["product_test_report_id"], "old_release_id": old, "new_release_id": new,
                 "release_changed": old != new, "resolved_test_round_id": rnd}
        mappings.append(entry)
        if not exists or not rnd or rnd not in CANONICAL_ROUNDS:
            blocked.append(entry)
    return mappings, blocked


def collect_defect_mappings(conn: sqlite3.Connection, result_id_map: dict[str, str]) -> list[dict]:
    out = []
    for row in conn.execute("SELECT product_test_defect_id, product_test_result_id, retest_product_test_result_id FROM product_test_defect"):
        old_r, old_rt = row["product_test_result_id"], row["retest_product_test_result_id"]
        out.append({"product_test_defect_id": row["product_test_defect_id"], "old_result_id": old_r,
                    "new_result_id": result_id_map.get(old_r), "old_retest_result_id": old_rt,
                    "new_retest_result_id": result_id_map.get(old_rt) if old_rt else None})
    return out


def has_ap_token(value: str | None) -> bool:
    return bool(value and AP_TOKEN_PATTERN.search(value))


def simulate_post_apply(conn: sqlite3.Connection) -> dict:
    run_plan = task15_2.collect_mapping(conn)
    case_plan = task15_3.collect_case_mapping(conn)
    report_mappings, report_blocked = collect_report_mappings(conn)

    if run_plan["counts"]["run_pk_collisions"] or run_plan["counts"]["result_pk_collisions"]:
        return {"blocked": True, "reason": "run_result_pk_collision"}
    if case_plan["counts"]["case_pk_collisions"] or case_plan["counts"]["tc_pr01_violations_unresolved"]:
        return {"blocked": True, "reason": "case_pk_collision"}
    if report_blocked:
        return {"blocked": True, "reason": "report_remap_blocked", "report_blocked": report_blocked}

    run_id_map = {e["old_run_id"]: e["new_run_id"] for e in run_plan["run_mappings"] if e["new_run_id"]}
    result_id_map = {e["old_result_id"]: e["new_result_id"] for e in run_plan["result_mappings"]}
    case_id_map = {e["old_case_id"]: e["new_case_id"] for e in case_plan["result_case_mappings"]}
    drop_ids = {e["old_run_id"] for e in run_plan["migrate_drop"]}
    defect_mappings = collect_defect_mappings(conn, result_id_map)

    post_runs, post_results = set(run_id_map.values()), set(result_id_map.values())
    post_cases = {e["new_case_id"] for e in case_plan["case_mappings"]}
    post_procs = {e["new_procedure_id"] for e in case_plan["procedure_mappings"]}

    sim = []
    for row in conn.execute("SELECT product_test_result_id, product_test_run_id, product_test_case_id FROM product_test_result"):
        sim.append({"product_test_result_id": result_id_map[row["product_test_result_id"]],
                    "product_test_run_id": run_id_map[row["product_test_run_id"]],
                    "product_test_case_id": case_id_map[row["product_test_case_id"]]})

    round_to_runs: dict[str, set[str]] = defaultdict(set)
    for e in run_plan["run_mappings"]:
        if e["new_run_id"]:
            round_to_runs[e["test_round_id"]].add(e["new_run_id"])

    rel_ids = {r[0] for r in conn.execute("SELECT product_test_release_id FROM product_test_release")}
    tbd = "RPT-TBD_"
    orphan_report_run = [r for r in report_mappings if not r["product_test_report_id"].startswith(tbd)
                         and r["resolved_test_round_id"] and not round_to_runs.get(r["resolved_test_round_id"])]

    orphans = {
        "result_to_run": sum(1 for r in sim if r["product_test_run_id"] not in post_runs),
        "result_to_case": sum(1 for r in sim if r["product_test_case_id"] not in post_cases),
        "procedure_to_case": sum(1 for e in case_plan["procedure_mappings"] if e["new_case_id"] not in post_cases),
        "defect_to_result": sum(1 for d in defect_mappings if not d["new_result_id"] or d["new_result_id"] not in post_results),
        "defect_retest_to_result": sum(1 for d in defect_mappings if d["old_retest_result_id"] and (not d["new_retest_result_id"] or d["new_retest_result_id"] not in post_results)),
        "report_to_release": sum(1 for r in report_mappings if r["new_release_id"] not in rel_ids),
        "report_to_round": sum(1 for r in report_mappings if not r["resolved_test_round_id"] or r["resolved_test_round_id"] not in CANONICAL_ROUNDS),
        "report_to_run": len(orphan_report_run),
    }

    ap_hits = [{"field": lbl, "value": v} for lbl, vals in [("run_id", post_runs), ("result_id", post_results), ("case_id", post_cases)]
               for v in sorted(vals) if has_ap_token(v)]

    return {
        "blocked": False,
        "counts": {
            "runs_before": run_plan["counts"]["total_runs"], "runs_after": len(post_runs), "runs_updated": len(run_id_map),
            "runs_migrate_drop": len(drop_ids), "results_before": len(result_id_map), "results_after": len(post_results),
            "results_updated": len(result_id_map), "cases_before": case_plan["counts"]["current_cases"],
            "cases_after": len(post_cases), "procedures_before": case_plan["counts"]["current_procedures"],
            "procedures_after": len(post_procs), "defects_total": len(defect_mappings), "reports_total": len(report_mappings),
            "reports_release_remapped": sum(1 for r in report_mappings if r["release_changed"]),
            "evidence_rows": conn.execute("SELECT COUNT(*) FROM product_test_evidence").fetchone()[0],
            "procedure_result_rows": conn.execute("SELECT COUNT(*) FROM product_test_procedure_result").fetchone()[0],
        },
        "orphans": orphans,
        "ap_token_hits": ap_hits,
        "pk_collision_checks": {"run": len(post_runs) != len(run_id_map), "result": len(post_results) != len(result_id_map),
                              "case": len(post_cases) != len(case_plan["case_mappings"]),
                              "procedure": len(post_procs) != len(case_plan["procedure_mappings"])},
        "report_mappings": report_mappings,
        "defect_mappings": defect_mappings,
        "samples": {"run": run_plan["samples"][:5], "defect": defect_mappings[:5],
                    "report": [r for r in report_mappings if r["release_changed"]] or report_mappings[:3]},
        "apply_notes": {"transaction": "single transaction", "release_table": "retained in 15-4; removed in 15-5"},
    }


def main() -> int:
    output_path = PROJECT_ROOT / "docs" / "task15_4_dryrun.json"
    with readonly_db(DB_PATH, "task15_4_") as (conn, meta):
        plan = simulate_post_apply(conn)
        blocked = plan.get("blocked", False)
        if not blocked:
            blocked = sum(plan["orphans"].values()) > 0 or any(plan["pk_collision_checks"].values()) or bool(plan["ap_token_hits"])
        validation = {
            "result_loss_zero": plan.get("counts", {}).get("results_after") == 375,
            "defects_all_15": plan.get("counts", {}).get("defects_total") == 15,
            "cases_after_134": plan.get("counts", {}).get("cases_after") == 134,
            "procedures_after_339": plan.get("counts", {}).get("procedures_after") == 339,
            "migrate_drop_21": plan.get("counts", {}).get("runs_migrate_drop") == 21,
            "all_orphans_zero": sum(plan.get("orphans", {}).values()) == 0,
            "pk_collisions_zero": not any(plan.get("pk_collision_checks", {}).values()),
            "ap_tokens_zero": len(plan.get("ap_token_hits") or []) == 0,
        }
        payload = {"step": "15-4", "mode": "dry-run", "status": "BLOCKED" if blocked else "READY", "meta": meta,
                   "summary": plan.get("counts"), "orphans": plan.get("orphans"), "validation": validation,
                   "report_release_remap": REPORT_RELEASE_REMAP, "report_mappings": plan.get("report_mappings"),
                   "defect_mappings": plan.get("defect_mappings"), "apply_notes": plan.get("apply_notes"),
                   "samples": plan.get("samples"), "blocked_reason": plan.get("reason")}
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"step": "15-4", "status": payload["status"], "output": str(output_path),
                          "summary": payload["summary"], "validation": validation, "orphans": payload["orphans"],
                          "report_release_remap": REPORT_RELEASE_REMAP}, ensure_ascii=False, indent=2))
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
