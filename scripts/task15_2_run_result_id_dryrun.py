"""TASK 15-2 dry-run: RUN/RESULT new ID mapping preview."""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.topology_normalize import CANONICAL_TOPOLOGIES, normalize_combo

DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
COMBO_PATTERN = re.compile(r"\[연결구성\]\s*([^\n\]]+)")
RC_TAIL_PATTERN = re.compile(r"-RC(\d+(?:-\d+)?)$")
RESULT_SUFFIX_PATTERN = re.compile(r"(-NO\d+)$")
DEVICE_SHELL_SUFFIX = re.compile(r"-(?:HDC|HDR|HLM|HRK|HTR|HIIS)$")
LEGACY_TEST_REPORT_PREFIX = "RUN-TEST_REPORT"
LEGACY_ROUND_VERSION = {
    "ROUND-WIFI_SMOKE": "1_1_1D",
    "ROUND-DOWNGRADE": "1_1_0A",
    "ROUND-WIFI_2ND": "1_1_1A",
}
COLLISION_PAIR_OLD_IDS = {
    "RUN-WIFI_2ND-25AP_1HDR_1HDC-RC1",
    "RUN-WIFI_2ND-25AP_1HDR_1HDC-RC1-2",
    "RUN-WIFI_2ND-25AP_1HLM_1HDR-RC1",
    "RUN-WIFI_2ND-25AP_1HLM_1HDR-RC1-2",
    "RUN-WIFI_2ND-25AP_1HRK_1HDR-RC1",
    "RUN-WIFI_2ND-25AP_1HRK_1HDR-RC1-2",
    "RUN-WIFI_2ND-25AP_1HTR_1HDR-RC1",
    "RUN-WIFI_2ND-25AP_1HTR_1HDR-RC1-2",
}


def extract_combo(remark: str | None) -> str:
    match = COMBO_PATTERN.search(remark or "")
    return match.group(1).strip() if match else ""


def slug_product(model_name: str | None) -> str | None:
    if not model_name:
        return None
    return model_name.strip().replace("-", "_")


def slug_sw_fullname(version: str | None, rc_token: str | None) -> str | None:
    if not version or not rc_token:
        return None
    version_slug = version.strip().replace(".", "_")
    return f"{version_slug}_{rc_token}"


def strip_device_suffix(run_id: str) -> str:
    match = DEVICE_SHELL_SUFFIX.search(run_id)
    if match:
        return run_id[: match.start()]
    return run_id


def extract_rc_token(run_id: str) -> str | None:
    """RC tail after topology: RC1, RC1_2 (from RC1-2), RC2, ..."""
    base = strip_device_suffix(run_id)
    match = RC_TAIL_PATTERN.search(base)
    if not match:
        return None
    return "RC" + match.group(1).replace("-", "_")


def is_legacy_test_report_run(run_id: str) -> bool:
    return run_id.startswith(LEGACY_TEST_REPORT_PREFIX)


def legacy_version_from_round(test_round_id: str | None) -> str | None:
    if not test_round_id:
        return None
    return LEGACY_ROUND_VERSION.get(test_round_id)


def topology_for_run(conn: sqlite3.Connection, run_id: str) -> tuple[str, list[str]]:
    combos: list[str] = []
    for row in conn.execute(
        "SELECT remark FROM product_test_result WHERE product_test_run_id=?",
        (run_id,),
    ):
        combo = extract_combo(row["remark"])
        if combo:
            combos.append(combo)
    if not combos:
        return "", []
    counter = Counter(combos)
    canonical = counter.most_common(1)[0][0]
    return canonical, sorted(counter.keys())


def classify_topology(raw_combo: str) -> str:
    if not raw_combo:
        return "MISSING"
    normalized = normalize_combo(raw_combo)
    if normalized == "UNCLASSIFIED":
        return "UNCLASSIFIED"
    if normalized in CANONICAL_TOPOLOGIES:
        return "CANONICAL"
    return "UNCLASSIFIED"


def build_new_run_id(product: str, sw_fullname: str, topology: str) -> str:
    return f"RUN_{product}_{sw_fullname}_{topology}"


def build_new_result_id(new_run_id: str, old_result_id: str) -> str:
    suffix_match = RESULT_SUFFIX_PATTERN.search(old_result_id)
    suffix = suffix_match.group(1) if suffix_match else f"-{old_result_id.split('-')[-1]}"
    return new_run_id.replace("RUN_", "RESULT_", 1) + suffix


@contextmanager
def readonly_db(src: Path):
    live = sqlite3.connect(str(src))
    live.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    live.close()

    temp_dir = Path(tempfile.mkdtemp(prefix="task15_2_", dir=PROJECT_ROOT))
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
    runs = conn.execute(
        """
        SELECT
            run.product_test_run_id,
            run.product_test_target_id,
            rel.test_round_id,
            target.model_name,
            target.software_version,
            (
                SELECT COUNT(*)
                FROM product_test_result res
                WHERE res.product_test_run_id = run.product_test_run_id
            ) AS result_count
        FROM product_test_run run
        LEFT JOIN product_test_release rel
            ON rel.product_test_release_id = run.product_test_release_id
        LEFT JOIN product_test_target_unified target
            ON target.product_test_target_id = run.product_test_target_id
        ORDER BY run.product_test_run_id
        """
    ).fetchall()

    migrate_drop: list[dict] = []
    incomplete_runs: list[dict] = []
    unclassified_runs: list[dict] = []
    run_mappings: list[dict] = []
    result_mappings: list[dict] = []

    for row in runs:
        old_run_id = row["product_test_run_id"]
        result_count = int(row["result_count"])

        if result_count == 0:
            migrate_drop.append(
                {
                    "old_run_id": old_run_id,
                    "classification": "MIGRATE_DROP",
                    "reason": "empty_base_run_no_results",
                }
            )
            continue

        legacy = is_legacy_test_report_run(old_run_id)
        raw_topology, combo_variants = topology_for_run(conn, old_run_id)
        topology_class = classify_topology(raw_topology)

        if legacy:
            version_source = legacy_version_from_round(row["test_round_id"])
            rc_token = "RC1"
            topology_token = "UNCLASSIFIED"
            topology_class = "UNCLASSIFIED"
            unclassified_runs.append(
                {
                    "old_run_id": old_run_id,
                    "raw_topology": raw_topology or "UNCLASSIFIED",
                    "combo_variants": combo_variants,
                    "result_count": result_count,
                    "legacy": True,
                    "test_round_id": row["test_round_id"],
                    "version_source": version_source,
                }
            )
        else:
            topology_token = normalize_combo(raw_topology) if raw_topology else "MISSING"
            if topology_class == "UNCLASSIFIED" or topology_token in {"", "UNCLASSIFIED", "MISSING"}:
                topology_token = raw_topology.replace(" ", "") if raw_topology else "UNCLASSIFIED"
                unclassified_runs.append(
                    {
                        "old_run_id": old_run_id,
                        "raw_topology": raw_topology,
                        "combo_variants": combo_variants,
                        "result_count": result_count,
                        "legacy": False,
                    }
                )
            version_source = row["software_version"]
            rc_token = extract_rc_token(old_run_id)

        product = slug_product(row["model_name"])
        sw_fullname = slug_sw_fullname(version_source, rc_token)

        missing_fields = []
        if not row["product_test_target_id"]:
            missing_fields.append("target_id")
        if not product:
            missing_fields.append("product")
        if not sw_fullname:
            if legacy and not version_source:
                missing_fields.append("round_version")
            else:
                missing_fields.append("sw_fullname")
        if missing_fields:
            incomplete_runs.append(
                {
                    "old_run_id": old_run_id,
                    "target_id": row["product_test_target_id"],
                    "test_round_id": row["test_round_id"],
                    "model_name": row["model_name"],
                    "software_version": row["software_version"],
                    "version_source": version_source,
                    "rc_token": rc_token,
                    "missing_fields": missing_fields,
                    "result_count": result_count,
                    "legacy": legacy,
                }
            )
            new_run_id = None
        else:
            new_run_id = build_new_run_id(product, sw_fullname, topology_token)

        run_entry = {
            "old_run_id": old_run_id,
            "new_run_id": new_run_id,
            "legacy": legacy,
            "product": product,
            "sw_fullname": sw_fullname,
            "rc_token": rc_token,
            "version_source": version_source,
            "test_round_id": row["test_round_id"],
            "topology_raw": raw_topology,
            "topology_token": topology_token,
            "topology_class": topology_class,
            "combo_variants": combo_variants,
            "result_count": result_count,
            "target_id": row["product_test_target_id"],
            "model_name": row["model_name"],
            "software_version": row["software_version"],
        }
        run_mappings.append(run_entry)

        if not new_run_id:
            continue

        for res in conn.execute(
            """
            SELECT product_test_result_id, remark
            FROM product_test_result
            WHERE product_test_run_id=?
            ORDER BY product_test_result_id
            """,
            (old_run_id,),
        ):
            combo = extract_combo(res["remark"])
            result_mappings.append(
                {
                    "old_result_id": res["product_test_result_id"],
                    "new_result_id": build_new_result_id(new_run_id, res["product_test_result_id"]),
                    "old_run_id": old_run_id,
                    "new_run_id": new_run_id,
                    "topology_raw": combo,
                }
            )

    new_run_id_to_old: dict[str, list[str]] = {}
    for entry in run_mappings:
        if not entry["new_run_id"]:
            continue
        new_run_id_to_old.setdefault(entry["new_run_id"], []).append(entry["old_run_id"])

    run_pk_collisions = [
        {
            "new_run_id": new_run_id,
            "old_run_ids": old_ids,
            "collision_count": len(old_ids),
        }
        for new_run_id, old_ids in sorted(new_run_id_to_old.items())
        if len(old_ids) > 1
    ]

    new_result_ids = [entry["new_result_id"] for entry in result_mappings]
    result_pk_collisions = [
        {"new_result_id": rid, "count": cnt}
        for rid, cnt in Counter(new_result_ids).items()
        if cnt > 1
    ]

    samples = []
    for entry in run_mappings:
        if not entry["new_run_id"]:
            continue
        sample_result = next(
            (r for r in result_mappings if r["old_run_id"] == entry["old_run_id"]),
            None,
        )
        samples.append(
            {
                "old_run_id": entry["old_run_id"],
                "new_run_id": entry["new_run_id"],
                "old_result_id": sample_result["old_result_id"] if sample_result else None,
                "new_result_id": sample_result["new_result_id"] if sample_result else None,
            }
        )
        if len(samples) >= 10:
            break

    collision_resolution_samples = [
        {
            "old_run_id": entry["old_run_id"],
            "new_run_id": entry["new_run_id"],
            "rc_token": entry["rc_token"],
            "result_count": entry["result_count"],
        }
        for entry in run_mappings
        if entry["old_run_id"] in COLLISION_PAIR_OLD_IDS and entry["new_run_id"]
    ]

    legacy_samples = [
        {
            "old_run_id": entry["old_run_id"],
            "new_run_id": entry["new_run_id"],
            "test_round_id": entry["test_round_id"],
            "version_source": entry["version_source"],
            "result_count": entry["result_count"],
        }
        for entry in run_mappings
        if entry.get("legacy") and entry["new_run_id"]
    ]

    return {
        "counts": {
            "total_runs": len(runs),
            "mapped_runs": sum(1 for entry in run_mappings if entry["new_run_id"]),
            "mapped_results": len(result_mappings),
            "migrate_drop_runs": len(migrate_drop),
            "incomplete_runs": len(incomplete_runs),
            "unclassified_topology_runs": len(unclassified_runs),
            "run_pk_collisions": len(run_pk_collisions),
            "result_pk_collisions": len(result_pk_collisions),
        },
        "migrate_drop": migrate_drop,
        "incomplete_runs": incomplete_runs,
        "unclassified_topology_runs": unclassified_runs,
        "run_pk_collisions": run_pk_collisions,
        "result_pk_collisions": result_pk_collisions,
        "run_mappings": run_mappings,
        "result_mappings": result_mappings,
        "samples": samples,
        "collision_resolution_samples": collision_resolution_samples,
        "legacy_samples": legacy_samples,
    }


def main() -> int:
    output_path = PROJECT_ROOT / "docs" / "task15_2_dryrun.json"
    with readonly_db(DB_PATH) as (conn, meta):
        plan = collect_mapping(conn)
        payload = {
            "step": "15-2",
            "mode": "dry-run",
            "meta": meta,
            "summary": plan["counts"],
            "migrate_drop": plan["migrate_drop"],
            "incomplete_runs": plan["incomplete_runs"],
            "unclassified_topology_runs": plan["unclassified_topology_runs"],
            "run_pk_collisions": plan["run_pk_collisions"],
            "result_pk_collisions": plan["result_pk_collisions"],
            "samples": plan["samples"],
            "collision_resolution_samples": plan["collision_resolution_samples"],
            "legacy_samples": plan["legacy_samples"],
            "run_mappings": plan["run_mappings"],
            "result_mappings": plan["result_mappings"],
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(
            {
                "step": "15-2",
                "mode": "dry-run",
                "output": str(output_path),
                "summary": plan["counts"],
                "run_pk_collisions": plan["run_pk_collisions"],
                "unclassified_topology_runs": plan["unclassified_topology_runs"],
                "incomplete_runs": plan["incomplete_runs"],
                "collision_resolution_samples": plan["collision_resolution_samples"],
                "legacy_samples": plan["legacy_samples"],
                "samples": plan["samples"],
            },
            ensure_ascii=False,
            indent=2,
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
