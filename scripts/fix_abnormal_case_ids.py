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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
NOW = datetime.now(timezone.utc).isoformat()
ACTOR = "fix_abnormal_case_ids_v1"
COMBO_PATTERN = re.compile(r"\[연결구성\]\s*([^\n\]]+)")
DEVICE_ORDER = ["HRK", "HTR", "HLM", "HDR", "HDC", "HIIS"]
SCENARIO_SLUGS = {
    "Wi-Fi 재ON 후 복구": "WIFI_REON_RECOVERY",
    "라우터 재부팅 후 복구": "ROUTER_REBOOT_RECOVERY",
    "시험대상장비 재부팅 후 복구": "DUT_REBOOT_RECOVERY",
}
CANONICAL_TOPOLOGIES = {
    "1HDC", "1HDC_1ROUTER", "1HDR_1CABLE_1HIIS", "1HDR_1ROUTER", "1HDR_1ROUTER_1HDC",
    "1HDR_25ROUTER", "1HDR_25ROUTER_1HDC", "1HLM_1ROUTER", "1HLM_1ROUTER_1HDR",
    "1HLM_1ROUTER_4HDR", "1HLM_25ROUTER", "1HLM_25ROUTER_1HDR", "1HRK_1ROUTER",
    "1HRK_1ROUTER_1HDR", "1HRK_1ROUTER_1HTR_1HLM_4HDR", "1HRK_1ROUTER_3HDR",
    "1HRK_1ROUTER_4HDR", "1HRK_25ROUTER", "1HRK_25ROUTER_1HDR", "1HTR_1ROUTER",
    "1HTR_1ROUTER_1HDR", "1HTR_1ROUTER_2HDR", "1HTR_25ROUTER", "1HTR_25ROUTER_1HDR",
    "2HDR_1ROUTER", "4HDR_1ROUTER", "4HDR_1ROUTER_1HDC", "4HDR_1ROUTER_1HIIS",
}


def extract_combo(remark: str | None) -> str:
    match = COMBO_PATTERN.search(remark or "")
    return match.group(1).strip() if match else ""


def normalize_topology(raw: str) -> str:
    if not raw or raw.strip() in {"", "TBD", "VARIOUS_CONNECTIONS"}:
        return "UNCLASSIFIED"
    parts = re.findall(r"(\d*)(AP|ROUTER|HRK|HTR|HLM|HDR|HDC|HIIS|CABLE)", raw.replace(" ", ""))
    if not parts:
        return "UNCLASSIFIED"
    router_count = 0
    device_counts: dict[str, int] = {}
    for count_str, token in parts:
        count = int(count_str) if count_str else 1
        if token == "AP":
            router_count += count
        elif token == "ROUTER":
            router_count += count
        else:
            device_counts[token] = device_counts.get(token, 0) + count
    ordered_devices = []
    if "CABLE" in device_counts:
        ordered_devices.append(f"{device_counts.pop('CABLE')}CABLE")
    for token in DEVICE_ORDER:
        if token in device_counts:
            ordered_devices.append(f"{device_counts[token]}{token}")
    if router_count and ordered_devices:
        ordered = [ordered_devices[0], f"{router_count}ROUTER", *ordered_devices[1:]]
    elif router_count:
        ordered = [f"{router_count}ROUTER"]
    else:
        ordered = ordered_devices
    topology = "_".join(ordered)
    return topology if topology in CANONICAL_TOPOLOGIES else topology or "UNCLASSIFIED"


def backup_database(src: Path) -> Path:
    backup_dir = PROJECT_ROOT / "data" / "backups" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{src.stem}.task4_{datetime.now().strftime('%H%M%S')}.db"
    with sqlite3.connect(str(src)) as source, sqlite3.connect(str(backup_path)) as dest:
        source.backup(dest)
    return backup_path


@contextmanager
def readonly_copy(src: Path):
    temp_dir = Path(tempfile.mkdtemp(prefix="task4_case_fix_", dir=PROJECT_ROOT))
    try:
        for suffix in ("", "-wal", "-shm"):
            sidecar = Path(f"{src}{suffix}")
            if sidecar.exists():
                shutil.copy2(sidecar, temp_dir / sidecar.name)
        copy_path = temp_dir / src.name
        conn = sqlite3.connect(f"file:{copy_path.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def load_abnormal_cases(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT c.product_test_case_id, c.product_test_case_status, c.remark,
               COUNT(DISTINCT p.product_test_procedure_id) AS procedure_count,
               COUNT(DISTINCT r.product_test_result_id) AS result_count
        FROM product_test_case c
        LEFT JOIN product_test_procedure p ON p.product_test_case_id = c.product_test_case_id
        LEFT JOIN product_test_result r ON r.product_test_case_id = c.product_test_case_id
        WHERE c.product_test_case_id NOT LIKE 'TEST_CASE-%'
        GROUP BY c.product_test_case_id, c.product_test_case_status, c.remark
        ORDER BY c.product_test_case_id
        """
    ).fetchall()


def propose(conn: sqlite3.Connection, deprecated_action: str) -> list[dict]:
    existing_ids = {row[0] for row in conn.execute("SELECT product_test_case_id FROM product_test_case").fetchall()}
    proposals = []
    for row in load_abnormal_cases(conn):
        case_id = row["product_test_case_id"]
        result_rows = conn.execute("SELECT product_test_result_id, remark FROM product_test_result WHERE product_test_case_id=?", (case_id,)).fetchall()
        topology_counts = Counter(normalize_topology(extract_combo(r["remark"])) for r in result_rows)
        topology = topology_counts.most_common(1)[0][0] if topology_counts else "UNCLASSIFIED"
        proposal = {"case_id": case_id, "status": row["product_test_case_status"], "procedure_count": row["procedure_count"], "result_count": row["result_count"], "topology": topology}
        if case_id.startswith("PLACEHOLDER_EMPTY_CASE-"):
            proposal["action"] = "needs_decision"
            proposal["reason"] = "placeholder case is used by results but has zero procedures"
        elif case_id.startswith("DEPRECATED_TEST_CASE-") and deprecated_action == "mark_deprecated":
            proposal["action"] = "mark_status_only"
            proposal["new_status"] = "DEPRECATED"
        else:
            if case_id.startswith("DEPRECATED_TEST_CASE-"):
                dut, scenario_slug, seq = "HDC", "DR_CONNECT_ON_DHCP", "002"
            else:
                dut, scenario_slug, seq = "HRK", SCENARIO_SLUGS[case_id], "001"
            candidate = f"TEST_CASE-{topology}-{dut}-{scenario_slug}-{seq}"
            suffix = 1
            base = candidate
            while candidate in existing_ids and candidate != case_id:
                suffix += 1
                candidate = re.sub(r"-\d{3}$", f"-{suffix:03d}", base)
            proposal["action"] = "rename_case_id"
            proposal["new_case_id"] = candidate
            proposal["new_status"] = "DEPRECATED" if case_id.startswith("DEPRECATED_TEST_CASE-") else row["product_test_case_status"]
            proposal["warning"] = "topology not in canonical list" if topology not in CANONICAL_TOPOLOGIES else ""
            existing_ids.add(candidate)
        proposals.append(proposal)
    return proposals


def apply_changes(conn: sqlite3.Connection, proposals: list[dict]) -> None:
    for proposal in proposals:
        old_id = proposal["case_id"]
        if proposal["action"] == "needs_decision":
            continue
        if proposal["action"] == "mark_status_only":
            conn.execute("UPDATE product_test_case SET product_test_case_status=?, updated_at=?, updated_by=? WHERE product_test_case_id=?", ("DEPRECATED", NOW, ACTOR, old_id))
            continue
        new_id = proposal["new_case_id"]
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
        new_remark = f"[구 Case ID] {old_id}\n{case_row['remark'] or ''}".strip()
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
                proposal["new_status"],
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


def validate(conn: sqlite3.Connection) -> dict:
    unresolved_placeholder_case_ids = [
        row[0]
        for row in conn.execute(
            """
            SELECT product_test_case_id
            FROM product_test_case
            WHERE product_test_case_id LIKE 'PLACEHOLDER_EMPTY_CASE-%'
            ORDER BY product_test_case_id
            """
        ).fetchall()
    ]
    return {
        "abnormal_case_count": conn.execute("SELECT COUNT(*) FROM product_test_case WHERE product_test_case_id NOT LIKE 'TEST_CASE-%'").fetchone()[0],
        "cases_without_procedure_used_by_result": conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT c.product_test_case_id
                FROM product_test_case c
                JOIN product_test_result r ON r.product_test_case_id = c.product_test_case_id
                LEFT JOIN product_test_procedure p ON p.product_test_case_id = c.product_test_case_id
                GROUP BY c.product_test_case_id
                HAVING COUNT(p.product_test_procedure_id) = 0
            )
            """
        ).fetchone()[0],
        "unresolved_placeholder_case_ids": unresolved_placeholder_case_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--deprecated-action", choices=["mark_deprecated", "rename"], default="mark_deprecated")
    args = parser.parse_args()
    connector = sqlite3.connect if args.apply else None
    if args.apply:
        backup_path = backup_database(DB_PATH)
        conn = connector(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
    else:
        backup_path = None
        ctx = readonly_copy(DB_PATH)
        conn = ctx.__enter__()
    try:
        proposals = propose(conn, args.deprecated_action)
        if args.apply:
            apply_changes(conn, proposals)
            conn.commit()
        payload = {"mode": "apply" if args.apply else "dry-run", "backup_path": str(backup_path) if backup_path else "", "proposals": proposals, "validation": validate(conn)}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        conn.close()
        if not args.apply:
            ctx.__exit__(None, None, None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
