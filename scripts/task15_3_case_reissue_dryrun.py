"""TASK 15-3 dry-run: CASE campaign×topology reissue preview."""
from __future__ import annotations

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

from app.services.topology_normalize import CANONICAL_TOPOLOGIES, normalize_combo

DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
COMBO_PATTERN = re.compile(r"\[연결구성\]\s*([^\n\]]+)")
SEQ_PATTERN = re.compile(r"^\d{3}$")
LEGACY_RUN_PREFIX = "RUN-TEST_REPORT"
CASE_PREFIXES = ("CASE-", "TEST_CASE-", "DEPRECATED_TEST_CASE-")
PLACEHOLDER_PREFIX = "PLACEHOLDER_EMPTY_CASE-"
TC_PR01_WHITELIST_OLD_CASE = "PLACEHOLDER_EMPTY_CASE-WIFI_CONNECTIVITY_TEST_2026"
TC_PR01_EXCEPTION_REMARK = "[TC-PR01 예외: legacy placeholder, 절차 미정의]"


def extract_combo(remark: str | None) -> str:
    match = COMBO_PATTERN.search(remark or "")
    return match.group(1).strip() if match else ""


def campaign_from_round(test_round_id: str | None) -> str:
    if not test_round_id:
        return "UNCLASSIFIED"
    return test_round_id.removeprefix("ROUND-")


def parse_case_shape(case_id: str | None) -> tuple[str, str]:
    if not case_id:
        return "UNCLASSIFIED", "001"
    if case_id.startswith(PLACEHOLDER_PREFIX):
        scenario = case_id.removeprefix(PLACEHOLDER_PREFIX) or "UNCLASSIFIED"
        return scenario, "001"
    for prefix in CASE_PREFIXES:
        if case_id.startswith(prefix):
            remainder = case_id[len(prefix) :]
            parts = remainder.split("-")
            if len(parts) < 3:
                return "UNCLASSIFIED", "001"
            seq = parts[-1] if SEQ_PATTERN.fullmatch(parts[-1]) else "001"
            body = parts[:-1] if SEQ_PATTERN.fullmatch(parts[-1]) else parts
            if len(body) < 2:
                return "UNCLASSIFIED", seq
            scenario_parts = body[2:] if len(body) >= 3 else body[1:]
            scenario = "_".join(scenario_parts) or "UNCLASSIFIED"
            return scenario, seq
    return "UNCLASSIFIED", "001"


def topology_for_result(raw_combo: str, is_legacy_run: bool) -> tuple[str, str]:
    if is_legacy_run:
        return "UNCLASSIFIED", "legacy_run_forced_unclassified"
    if not raw_combo:
        return "UNCLASSIFIED", "missing_combo"
    normalized = normalize_combo(raw_combo)
    if normalized in CANONICAL_TOPOLOGIES:
        return normalized, "canonical"
    if normalized == "UNCLASSIFIED":
        return "UNCLASSIFIED", "normalize_unclassified"
    return normalized, "raw_fallback"


def build_new_case_id(campaign: str, topology: str, scenario: str, seq: str) -> str:
    return f"CASE_{campaign}_{topology}_{scenario}_{seq}"


def build_new_procedure_id(new_case_id: str, sequence: int) -> str:
    return f"{new_case_id}_STEP_{sequence:03d}"


@contextmanager
def readonly_db(src: Path):
    live = sqlite3.connect(str(src))
    live.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    live.close()

    temp_dir = Path(tempfile.mkdtemp(prefix="task15_3_", dir=PROJECT_ROOT))
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


def collect_case_mapping(conn: sqlite3.Connection) -> dict:
    case_rows = conn.execute("SELECT product_test_case_id FROM product_test_case").fetchall()
    procedure_rows = conn.execute(
        "SELECT product_test_procedure_id, product_test_case_id, procedure_sequence FROM product_test_procedure"
    ).fetchall()
    result_rows = conn.execute(
        """
        SELECT res.product_test_result_id, res.product_test_case_id, res.remark,
               rel.test_round_id, run.product_test_run_id
        FROM product_test_result res
        JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
        JOIN product_test_release rel ON rel.product_test_release_id = run.product_test_release_id
        """
    ).fetchall()

    procedures_by_case: dict[str, list[dict]] = defaultdict(list)
    for row in procedure_rows:
        procedures_by_case[row["product_test_case_id"]].append(
            {"old_procedure_id": row["product_test_procedure_id"], "procedure_sequence": int(row["procedure_sequence"])}
        )

    result_mappings: list[dict] = []
    new_case_meta: dict[str, dict] = {}
    old_to_new_pairs: set[tuple[str, str]] = set()

    for row in result_rows:
        old_case_id = row["product_test_case_id"]
        campaign = campaign_from_round(row["test_round_id"])
        topology, _ = topology_for_result(extract_combo(row["remark"]), row["product_test_run_id"].startswith(LEGACY_RUN_PREFIX))
        scenario, case_seq = parse_case_shape(old_case_id)
        new_case_id = build_new_case_id(campaign, topology, scenario, case_seq)
        result_mappings.append({"old_result_id": row["product_test_result_id"], "old_case_id": old_case_id, "new_case_id": new_case_id})
        old_to_new_pairs.add((old_case_id, new_case_id))
        if new_case_id not in new_case_meta:
            new_case_meta[new_case_id] = {
                "new_case_id": new_case_id,
                "remark_append": TC_PR01_EXCEPTION_REMARK if old_case_id == TC_PR01_WHITELIST_OLD_CASE else "",
                "tc_pr01_whitelisted": old_case_id == TC_PR01_WHITELIST_OLD_CASE,
                "source_old_case_ids": set(),
            }
        new_case_meta[new_case_id]["source_old_case_ids"].add(old_case_id)

    for meta in new_case_meta.values():
        meta["source_old_case_ids"] = sorted(meta["source_old_case_ids"])

    new_to_old: dict[str, set[str]] = defaultdict(set)
    for old, new in old_to_new_pairs:
        new_to_old[new].add(old)
    case_pk_collisions = [{"new_case_id": k, "old_case_ids": sorted(v)} for k, v in new_to_old.items() if len(v) > 1]

    case_mappings = sorted(new_case_meta.values(), key=lambda x: x["new_case_id"])
    procedure_mappings = []
    for old_case_id, new_case_id in sorted(old_to_new_pairs):
        for proc in procedures_by_case.get(old_case_id, []):
            procedure_mappings.append({
                "old_procedure_id": proc["old_procedure_id"],
                "new_procedure_id": build_new_procedure_id(new_case_id, proc["procedure_sequence"]),
                "old_case_id": old_case_id,
                "new_case_id": new_case_id,
                "procedure_sequence": proc["procedure_sequence"],
            })

    whitelisted = {m["new_case_id"] for m in case_mappings if m.get("tc_pr01_whitelisted")}
    used = {e["new_case_id"] for e in result_mappings}
    with_proc = {e["new_case_id"] for e in procedure_mappings}
    tc_violations = sorted(used - with_proc)
    tc_unresolved = sorted(x for x in tc_violations if x not in whitelisted)

    return {
        "counts": {
            "current_cases": len(case_rows),
            "new_cases": len(case_mappings),
            "current_procedures": len(procedure_rows),
            "new_procedures": len(procedure_mappings),
            "mapped_results": len(result_mappings),
            "case_pk_collisions": len(case_pk_collisions),
            "tc_pr01_violations": len(tc_violations),
            "tc_pr01_violations_unresolved": len(tc_unresolved),
        },
        "case_pk_collisions": case_pk_collisions,
        "tc_pr01_whitelist": {"old_case_id": TC_PR01_WHITELIST_OLD_CASE, "new_case_ids": sorted(whitelisted), "remark_append": TC_PR01_EXCEPTION_REMARK},
        "case_mappings": case_mappings,
        "result_case_mappings": result_mappings,
        "procedure_mappings": procedure_mappings,
    }


def main() -> int:
    output_path = PROJECT_ROOT / "docs" / "task15_3_dryrun.json"
    with readonly_db(DB_PATH) as (conn, meta):
        plan = collect_case_mapping(conn)
        blocked = plan["counts"]["case_pk_collisions"] > 0 or plan["counts"]["tc_pr01_violations_unresolved"] > 0
        payload = {"step": "15-3", "mode": "dry-run", "status": "BLOCKED_COLLISION" if blocked else "READY", "meta": meta, "summary": plan["counts"],
                   "case_mappings": plan["case_mappings"], "result_mappings": plan["result_case_mappings"], "procedure_mappings": plan["procedure_mappings"]}
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"step": "15-3", "status": payload["status"], "summary": plan["counts"]}, ensure_ascii=False))
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
