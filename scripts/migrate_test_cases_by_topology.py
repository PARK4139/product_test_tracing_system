from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import tempfile
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.services.topology_normalize import CANONICAL_TOPOLOGIES, normalize_combo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
NOW = datetime.now(timezone.utc).isoformat()
ACTOR = "migrate_test_cases_by_topology_v1"
COMBO_PATTERN = re.compile(r"\[연결구성\]\s*([^\n\]]+)")
TEST_CASE_PATTERN = re.compile(r"^TEST_CASE-([^-]+)-(.+?)-(\d{3})$")
TOKEN_DUT_PATTERN = re.compile(r"(\d+)?([A-Z]+)$")


def backup_database(src: Path) -> Path:
    backup_dir = PROJECT_ROOT / "data" / "backups" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{src.stem}.task6_{datetime.now().strftime('%H%M%S')}.db"
    with sqlite3.connect(str(src)) as source, sqlite3.connect(str(backup_path)) as dest:
        source.backup(dest)
    return backup_path


@contextmanager
def readonly_copy(src: Path):
    temp_dir = Path(tempfile.mkdtemp(prefix="task6_cases_", dir=PROJECT_ROOT))
    try:
        copied = []
        for suffix in ("", "-wal", "-shm"):
            sidecar = Path(f"{src}{suffix}")
            if sidecar.exists():
                shutil.copy2(sidecar, temp_dir / sidecar.name)
                copied.append(sidecar.name)
        copy_path = temp_dir / src.name
        conn = sqlite3.connect(f"file:{copy_path.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn, {"copy_path": str(copy_path), "copied_sidecars": copied}
        finally:
            conn.close()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def extract_combo(remark: str | None) -> str:
    match = COMBO_PATTERN.search(remark or "")
    return match.group(1).strip() if match else ""


def topology_token_length(topology: str) -> int:
    if not topology or topology == "UNCLASSIFIED":
        return 0
    return len([token for token in topology.split("_") if token])


def topology_total_units(topology: str) -> int:
    if not topology or topology == "UNCLASSIFIED":
        return 0
    total = 0
    for token in topology.split("_"):
        match = re.match(r"(\d+)", token)
        total += int(match.group(1)) if match else 1
    return total


def derive_dut_from_legacy_topology(legacy_topology: str) -> str:
    if not legacy_topology:
        return "UNCLASSIFIED"
    for token in reversed([part for part in legacy_topology.split("_") if part]):
        match = TOKEN_DUT_PATTERN.match(token)
        if not match:
            continue
        dut = match.group(2)
        if dut not in {"AP", "ROUTER"}:
            return dut
    return "UNCLASSIFIED"


def parse_case_shape(case_id: str) -> dict:
    if not case_id.startswith("TEST_CASE-"):
        return {
            "is_regular": False,
            "legacy_topology": "",
            "dut": "UNCLASSIFIED",
            "scenario_slug": "UNCLASSIFIED",
            "seq": "001",
        }
    remainder = case_id[len("TEST_CASE-") :]
    parts = remainder.split("-")
    if len(parts) < 3:
        return {
            "is_regular": False,
            "legacy_topology": "",
            "dut": "UNCLASSIFIED",
            "scenario_slug": "UNCLASSIFIED",
            "seq": "001",
        }
    legacy_topology = parts[0]
    seq = parts[-1] if re.fullmatch(r"\d{3}", parts[-1]) else "001"
    middle = parts[1:-1] if re.fullmatch(r"\d{3}", parts[-1]) else parts[1:]
    scenario_slug = "_".join(segment.strip().replace("-", "_") for segment in middle if segment.strip()) or "UNCLASSIFIED"
    return {
        "is_regular": True,
        "legacy_topology": legacy_topology,
        "dut": derive_dut_from_legacy_topology(legacy_topology),
        "scenario_slug": scenario_slug,
        "seq": seq,
    }


def choose_topology(combo_counter: Counter[str]) -> tuple[str, list[dict]]:
    candidates = []
    for combo, count in combo_counter.items():
        candidates.append(
            {
                "combo": combo,
                "count": count,
                "token_length": topology_token_length(combo),
                "total_units": topology_total_units(combo),
            }
        )
    candidates.sort(
        key=lambda item: (-item["token_length"], -item["total_units"], -item["count"], item["combo"])
    )
    selected = candidates[0]["combo"] if candidates else "UNCLASSIFIED"
    return selected, candidates


def collect_proposals(conn: sqlite3.Connection) -> dict:
    existing_case_ids = {
        row[0] for row in conn.execute("SELECT product_test_case_id FROM product_test_case").fetchall()
    }
    proposals = []
    for case_row in conn.execute(
        """
        SELECT product_test_case_id, product_test_case_status, remark
        FROM product_test_case
        ORDER BY product_test_case_id
        """
    ).fetchall():
        case_id = case_row["product_test_case_id"]
        shape = parse_case_shape(case_id)
        result_rows = conn.execute(
            """
            SELECT product_test_result_id, remark
            FROM product_test_result
            WHERE product_test_case_id=?
            ORDER BY product_test_result_id
            """,
            (case_id,),
        ).fetchall()
        combo_counter: Counter[str] = Counter()
        for result_row in result_rows:
            combo_counter[normalize_combo(extract_combo(result_row["remark"]))] += 1
        selected_topology, candidates = choose_topology(combo_counter)
        target_case_id = case_id
        reason = "unchanged"
        warnings: list[str] = []
        if not shape["is_regular"]:
            warnings.append("non_regular_case_id")
        if selected_topology == "UNCLASSIFIED":
            warnings.append("selected_topology_unclassified")
        if selected_topology not in CANONICAL_TOPOLOGIES and selected_topology != "UNCLASSIFIED":
            warnings.append("selected_topology_not_canonical")
        if shape["dut"] == "UNCLASSIFIED":
            warnings.append("dut_unclassified")
        if shape["is_regular"] and selected_topology != "UNCLASSIFIED" and shape["dut"] != "UNCLASSIFIED":
            target_case_id = (
                f"TEST_CASE-{selected_topology}-{shape['dut']}-{shape['scenario_slug']}-{shape['seq']}"
            )
            if target_case_id != case_id:
                reason = "topology_changed"
        elif selected_topology == "UNCLASSIFIED" or shape["dut"] == "UNCLASSIFIED":
            reason = "unchanged"
        if target_case_id in existing_case_ids and target_case_id != case_id:
            warnings.append("target_case_id_conflict")
        proposals.append(
            {
                "case_id": case_id,
                "product_test_case_status": case_row["product_test_case_status"],
                "legacy_topology": shape["legacy_topology"],
                "dut": shape["dut"],
                "scenario_slug": shape["scenario_slug"],
                "seq": shape["seq"],
                "selected_topology": selected_topology,
                "candidate_topologies": candidates,
                "result_count": len(result_rows),
                "target_case_id": target_case_id,
                "reason": reason,
                "warnings": warnings,
                "is_regular": shape["is_regular"],
            }
        )
    changed = [proposal for proposal in proposals if proposal["target_case_id"] != proposal["case_id"]]
    multi_topology_cases = [
        proposal for proposal in proposals if len(proposal["candidate_topologies"]) > 1
    ]
    return {
        "proposals": proposals,
        "changed": changed,
        "multi_topology_cases": multi_topology_cases,
    }


def apply_changes(conn: sqlite3.Connection, proposal_bundle: dict) -> None:
    for proposal in proposal_bundle["changed"]:
        if not proposal["is_regular"]:
            continue
        if "target_case_id_conflict" in proposal["warnings"]:
            continue
        old_id = proposal["case_id"]
        new_id = proposal["target_case_id"]
        case_row = conn.execute(
            """
            SELECT product_test_case_title, test_category, test_objective, precondition,
                   expected_result, product_test_case_status, created_at, created_by,
                   updated_at, updated_by, remark, project_id
            FROM product_test_case
            WHERE product_test_case_id=?
            """,
            (old_id,),
        ).fetchone()
        candidate_list = ", ".join(
            f"{item['combo']}:{item['count']}" for item in proposal["candidate_topologies"]
        )
        new_remark = "\n".join(
            [
                f"[구 Case ID] {old_id}",
                f"[선택 연결구성] {proposal['selected_topology']}",
                f"[후보 연결구성 목록] {candidate_list}",
                "[추론 출처] TASK6 longest combo selection from result remarks",
                (case_row["remark"] or "").strip(),
            ]
        ).strip()
        conn.execute(
            """
            INSERT INTO product_test_case (
                product_test_case_id, product_test_case_title, test_category, test_objective,
                precondition, expected_result, product_test_case_status, created_at, created_by,
                updated_at, updated_by, remark, project_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                case_row["product_test_case_title"],
                case_row["test_category"],
                case_row["test_objective"],
                case_row["precondition"],
                case_row["expected_result"],
                case_row["product_test_case_status"],
                case_row["created_at"],
                case_row["created_by"],
                NOW,
                ACTOR,
                new_remark,
                case_row["project_id"],
            ),
        )
        conn.execute(
            "UPDATE product_test_result SET product_test_case_id=? WHERE product_test_case_id=?",
            (new_id, old_id),
        )
        conn.execute(
            "UPDATE product_test_procedure SET product_test_case_id=? WHERE product_test_case_id=?",
            (new_id, old_id),
        )
        conn.execute("DELETE FROM product_test_case WHERE product_test_case_id=?", (old_id,))


def summarize(bundle: dict) -> dict:
    unresolved = [
        proposal for proposal in bundle["proposals"]
        if (not proposal["is_regular"]) or proposal["warnings"]
    ]
    return {
        "total_cases": len(bundle["proposals"]),
        "changed_case_count": len(bundle["changed"]),
        "multi_topology_case_count": len(bundle["multi_topology_cases"]),
        "unresolved_case_count": len(unresolved),
        "sample_changed_cases": bundle["changed"][:20],
        "sample_unresolved_cases": unresolved[:20],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        backup_path = backup_database(DB_PATH)
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        meta = {"backup_path": str(backup_path)}
    else:
        backup_path = None
        ctx = readonly_copy(DB_PATH)
        conn, copy_meta = ctx.__enter__()
        meta = copy_meta
    try:
        bundle = collect_proposals(conn)
        if args.apply:
            apply_changes(conn, bundle)
            conn.commit()
        payload = {
            "mode": "apply" if args.apply else "dry-run",
            "backup_path": str(backup_path) if backup_path else "",
            "meta": meta,
            "summary": summarize(bundle),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        conn.close()
        if not args.apply:
            ctx.__exit__(None, None, None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
