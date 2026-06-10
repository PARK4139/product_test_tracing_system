"""TASK 15-3 dry-run: CASE campaign×topology reissue preview."""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter, defaultdict
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


def extract_combo(remark: str | None) -> str:
    match = COMBO_PATTERN.search(remark or "")
    return match.group(1).strip() if match else ""


def campaign_from_round(test_round_id: str | None) -> str:
    if not test_round_id:
        return "UNCLASSIFIED"
    return test_round_id.removeprefix("ROUND-")


def parse_scenario_slug(case_id: str | None) -> str:
    if not case_id:
        return "UNCLASSIFIED"
    if case_id.startswith("PLACEHOLDER_EMPTY_CASE-"):
        return case_id.removeprefix("PLACEHOLDER_EMPTY_CASE-") or "UNCLASSIFIED"
    for prefix in CASE_PREFIXES:
        if case_id.startswith(prefix):
            remainder = case_id[len(prefix) :]
            parts = remainder.split("-")
            if len(parts) < 3:
                return "UNCLASSIFIED"
            seq = parts[-1] if SEQ_PATTERN.fullmatch(parts[-1]) else None
            body = parts[:-1] if seq else parts
            if len(body) < 2:
                return "UNCLASSIFIED"
            scenario_parts = body[2:] if len(body) >= 3 else body[1:]
            return "_".join(scenario_parts) or "UNCLASSIFIED"
    return "UNCLASSIFIED"


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


def build_new_case_id(campaign: str, topology: str, scenario: str) -> str:
    return f"CASE_{campaign}_{topology}_{scenario}"


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


def collect_mapping(conn: sqlite3.Connection) -> dict:
    case_rows = conn.execute(
        """
        SELECT product_test_case_id, product_test_case_status, remark
        FROM product_test_case
        ORDER BY product_test_case_id
        """
    ).fetchall()
    procedure_rows = conn.execute(
        """
        SELECT product_test_procedure_id, product_test_case_id, procedure_sequence
        FROM product_test_procedure
        ORDER BY product_test_case_id, procedure_sequence
        """
    ).fetchall()
    result_rows = conn.execute(
        """
        SELECT
            res.product_test_result_id,
            res.product_test_case_id,
            res.remark,
            rel.test_round_id,
            run.product_test_run_id
        FROM product_test_result res
        JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
        JOIN product_test_release rel ON rel.product_test_release_id = run.product_test_release_id
        ORDER BY res.product_test_result_id
        """
    ).fetchall()

    procedures_by_case: dict[str, list[dict]] = defaultdict(list)
    for row in procedure_rows:
        procedures_by_case[row["product_test_case_id"]].append(
            {
                "old_procedure_id": row["product_test_procedure_id"],
                "procedure_sequence": int(row["procedure_sequence"]),
            }
        )

    result_mappings: list[dict] = []
    new_case_meta: dict[str, dict] = {}
    old_to_new_pairs: set[tuple[str, str]] = set()

    for row in result_rows:
        old_case_id = row["product_test_case_id"]
        campaign = campaign_from_round(row["test_round_id"])
        raw_combo = extract_combo(row["remark"])
        is_legacy = row["product_test_run_id"].startswith(LEGACY_RUN_PREFIX)
        topology, topology_source = topology_for_result(raw_combo, is_legacy)
        scenario = parse_scenario_slug(old_case_id)
        new_case_id = build_new_case_id(campaign, topology, scenario)

        result_mappings.append(
            {
                "old_result_id": row["product_test_result_id"],
                "old_case_id": old_case_id,
                "new_case_id": new_case_id,
                "campaign": campaign,
                "topology": topology,
                "topology_raw": raw_combo,
                "topology_source": topology_source,
                "scenario": scenario,
                "test_round_id": row["test_round_id"],
                "old_run_id": row["product_test_run_id"],
                "legacy_run": is_legacy,
            }
        )
        old_to_new_pairs.add((old_case_id, new_case_id))
        if new_case_id not in new_case_meta:
            new_case_meta[new_case_id] = {
                "new_case_id": new_case_id,
                "campaign": campaign,
                "topology": topology,
                "scenario": scenario,
                "source_old_case_ids": set(),
            }
        new_case_meta[new_case_id]["source_old_case_ids"].add(old_case_id)

    for meta in new_case_meta.values():
        meta["source_old_case_ids"] = sorted(meta["source_old_case_ids"])

    new_to_old_cases: dict[str, set[str]] = defaultdict(set)
    for old_case_id, new_case_id in old_to_new_pairs:
        new_to_old_cases[new_case_id].add(old_case_id)

    case_pk_collisions = [
        {
            "new_case_id": new_case_id,
            "old_case_ids": sorted(old_ids),
            "collision_count": len(old_ids),
        }
        for new_case_id, old_ids in sorted(new_to_old_cases.items())
        if len(old_ids) > 1
    ]

    case_mappings = sorted(new_case_meta.values(), key=lambda item: item["new_case_id"])

    procedure_mappings: list[dict] = []
    for old_case_id, new_case_id in sorted(old_to_new_pairs):
        for proc in procedures_by_case.get(old_case_id, []):
            seq = proc["procedure_sequence"]
            procedure_mappings.append(
                {
                    "old_procedure_id": proc["old_procedure_id"],
                    "new_procedure_id": build_new_procedure_id(new_case_id, seq),
                    "old_case_id": old_case_id,
                    "new_case_id": new_case_id,
                    "procedure_sequence": seq,
                }
            )

    new_procedure_ids = [entry["new_procedure_id"] for entry in procedure_mappings]
    procedure_pk_collisions = [
        {"new_procedure_id": pid, "count": cnt}
        for pid, cnt in Counter(new_procedure_ids).items()
        if cnt > 1
    ]

    used_new_case_ids = {entry["new_case_id"] for entry in result_mappings}
    new_cases_with_procedure = {entry["new_case_id"] for entry in procedure_mappings}
    tc_pr01_violations = sorted(used_new_case_ids - new_cases_with_procedure)

    result_orphans = [
        entry["old_result_id"]
        for entry in result_mappings
        if not entry["new_case_id"]
    ]
    procedure_orphans = [
        entry["new_procedure_id"]
        for entry in procedure_mappings
        if entry["new_case_id"] not in new_case_meta
    ]

    unclassified_case_entries = [
        entry
        for entry in case_mappings
        if entry["topology"] == "UNCLASSIFIED"
    ]
    unclassified_result_entries = [
        entry
        for entry in result_mappings
        if entry["topology"] == "UNCLASSIFIED"
    ]

    samples = []
    seen_old: set[str] = set()
    for entry in result_mappings:
        old_case_id = entry["old_case_id"]
        if old_case_id in seen_old:
            continue
        seen_old.add(old_case_id)
        samples.append(
            {
                "old_case_id": old_case_id,
                "new_case_id": entry["new_case_id"],
                "campaign": entry["campaign"],
                "topology": entry["topology"],
                "scenario": entry["scenario"],
            }
        )
        if len(samples) >= 10:
            break

    return {
        "counts": {
            "current_cases": len(case_rows),
            "new_cases": len(case_mappings),
            "current_procedures": len(procedure_rows),
            "new_procedures": len(procedure_mappings),
            "mapped_results": len(result_mappings),
            "case_pk_collisions": len(case_pk_collisions),
            "procedure_pk_collisions": len(procedure_pk_collisions),
            "result_case_orphans": len(result_orphans),
            "procedure_case_orphans": len(procedure_orphans),
            "tc_pr01_violations": len(tc_pr01_violations),
            "unclassified_new_cases": len(unclassified_case_entries),
            "unclassified_results": len(unclassified_result_entries),
        },
        "case_pk_collisions": case_pk_collisions,
        "procedure_pk_collisions": procedure_pk_collisions,
        "tc_pr01_violations": tc_pr01_violations,
        "unclassified_topology_policy": {
            "rule": "legacy RUN-TEST_REPORT result: topology=UNCLASSIFIED (15-2 정렬). remark [연결구성] raw는 UNCLASSIFIED/TBD/VARIOUS이며 normalize_combo도 UNCLASSIFIED.",
            "new_case_id_pattern": "CASE_{campaign}_UNCLASSIFIED_{scenario}",
            "legacy_result_count": sum(1 for entry in result_mappings if entry["legacy_run"]),
            "distinct_unclassified_new_cases": sorted({entry["new_case_id"] for entry in unclassified_result_entries}),
            "samples": unclassified_result_entries[:4],
        },
        "case_mappings": case_mappings,
        "result_mappings": result_mappings,
        "procedure_mappings": procedure_mappings,
        "samples": samples,
    }


def main() -> int:
    output_path = PROJECT_ROOT / "docs" / "task15_3_dryrun.json"
    with readonly_db(DB_PATH) as (conn, meta):
        plan = collect_mapping(conn)
        blocked = plan["counts"]["case_pk_collisions"] > 0
        payload = {
            "step": "15-3",
            "mode": "dry-run",
            "status": "BLOCKED_COLLISION" if blocked else "READY",
            "meta": meta,
            "summary": plan["counts"],
            "validation": {
                "case_pk_collisions_zero": plan["counts"]["case_pk_collisions"] == 0,
                "result_case_orphans_zero": plan["counts"]["result_case_orphans"] == 0,
                "procedure_case_orphans_zero": plan["counts"]["procedure_case_orphans"] == 0,
                "tc_pr01_all_used_cases_have_procedure": plan["counts"]["tc_pr01_violations"] == 0,
            },
            "case_pk_collisions": plan["case_pk_collisions"],
            "procedure_pk_collisions": plan["procedure_pk_collisions"],
            "tc_pr01_violations": plan["tc_pr01_violations"],
            "unclassified_topology_policy": plan["unclassified_topology_policy"],
            "samples": plan["samples"],
            "case_mappings": plan["case_mappings"],
            "result_mappings": plan["result_mappings"],
            "procedure_mappings": plan["procedure_mappings"],
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        report = {
            "step": "15-3",
            "mode": "dry-run",
            "status": payload["status"],
            "output": str(output_path),
            "summary": plan["counts"],
            "validation": payload["validation"],
            "case_pk_collisions": plan["case_pk_collisions"],
            "tc_pr01_violations": plan["tc_pr01_violations"],
            "unclassified_topology_policy": {
                "rule": plan["unclassified_topology_policy"]["rule"],
                "legacy_result_count": plan["unclassified_topology_policy"]["legacy_result_count"],
                "distinct_unclassified_new_cases": plan["unclassified_topology_policy"]["distinct_unclassified_new_cases"],
            },
            "samples": plan["samples"],
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
