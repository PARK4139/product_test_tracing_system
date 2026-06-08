from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import tempfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REMARK_COMBO_PATTERN = re.compile(r"\[연결구성\]\s*([^\n\]]+)")
CASE_ID_PREFIX_PATTERN = re.compile(r"^(TEST_)?CASE-")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
RELEVANT_TABLES = [
    "product_test_release",
    "product_test_run",
    "product_test_result",
    "product_test_case",
    "product_test_procedure",
    "product_test_defect",
    "product_test_round",
    "product_test_target",
    "product_test_target_definition",
    "product_test_environment",
    "product_test_environment_definition",
    "product_test_evidence",
    "product_test_procedure_result",
    "product_test_status_transition",
    "product_test_report",
    "product_test_report_snapshot",
]
FK_CHECKS = [
    (
        "result_to_run",
        """
        SELECT COUNT(*)
        FROM product_test_result child
        LEFT JOIN product_test_run parent
          ON parent.product_test_run_id = child.product_test_run_id
        WHERE child.product_test_run_id IS NOT NULL
          AND parent.product_test_run_id IS NULL
        """,
    ),
    (
        "result_to_case",
        """
        SELECT COUNT(*)
        FROM product_test_result child
        LEFT JOIN product_test_case parent
          ON parent.product_test_case_id = child.product_test_case_id
        WHERE child.product_test_case_id IS NOT NULL
          AND parent.product_test_case_id IS NULL
        """,
    ),
    (
        "procedure_to_case",
        """
        SELECT COUNT(*)
        FROM product_test_procedure child
        LEFT JOIN product_test_case parent
          ON parent.product_test_case_id = child.product_test_case_id
        WHERE child.product_test_case_id IS NOT NULL
          AND parent.product_test_case_id IS NULL
        """,
    ),
    (
        "run_to_release",
        """
        SELECT COUNT(*)
        FROM product_test_run child
        LEFT JOIN product_test_release parent
          ON parent.product_test_release_id = child.product_test_release_id
        WHERE child.product_test_release_id IS NOT NULL
          AND parent.product_test_release_id IS NULL
        """,
    ),
    (
        "run_to_target",
        """
        SELECT COUNT(*)
        FROM product_test_run child
        LEFT JOIN product_test_target parent
          ON parent.product_test_target_id = child.product_test_target_id
        WHERE child.product_test_target_id IS NOT NULL
          AND parent.product_test_target_id IS NULL
        """,
    ),
    (
        "run_to_environment",
        """
        SELECT COUNT(*)
        FROM product_test_run child
        LEFT JOIN product_test_environment parent
          ON parent.product_test_environment_id = child.product_test_environment_id
        WHERE child.product_test_environment_id IS NOT NULL
          AND parent.product_test_environment_id IS NULL
        """,
    ),
    (
        "defect_to_result",
        """
        SELECT COUNT(*)
        FROM product_test_defect child
        LEFT JOIN product_test_result parent
          ON parent.product_test_result_id = child.product_test_result_id
        WHERE child.product_test_result_id IS NOT NULL
          AND parent.product_test_result_id IS NULL
        """,
        ),
    (
        "release_to_round",
        """
        SELECT COUNT(*)
        FROM product_test_release child
        LEFT JOIN product_test_round parent
          ON parent.test_round_id = child.test_round_id
        WHERE child.test_round_id IS NOT NULL
          AND parent.test_round_id IS NULL
        """,
    ),
    (
        "target_to_definition",
        """
        SELECT COUNT(*)
        FROM product_test_target child
        LEFT JOIN product_test_target_definition parent
          ON parent.product_test_target_definition_id = child.product_test_target_definition_id
        WHERE child.product_test_target_definition_id IS NOT NULL
          AND parent.product_test_target_definition_id IS NULL
        """,
    ),
    (
        "environment_to_definition",
        """
        SELECT COUNT(*)
        FROM product_test_environment child
        LEFT JOIN product_test_environment_definition parent
          ON parent.product_test_environment_definition_id = child.product_test_environment_definition_id
        WHERE child.product_test_environment_definition_id IS NOT NULL
          AND parent.product_test_environment_definition_id IS NULL
        """,
    ),
]


@dataclass
class CopyMetadata:
    source_db_path: str
    copy_db_path: str
    copied_sidecars: list[str]


def _extract_combo(remark: str | None) -> str:
    if not remark:
        return ""
    match = REMARK_COMBO_PATTERN.search(remark)
    if match is None:
        return ""
    return match.group(1).strip()


def _extract_case_prefix(case_id: str | None) -> str:
    if not case_id:
        return ""
    if CASE_ID_PREFIX_PATTERN.match(case_id):
        parts = case_id.split("-", 3)
        if len(parts) >= 2:
            return parts[1].strip()
    return case_id.strip()


def _is_comparable_case_prefix(case_id: str | None, case_prefix: str) -> bool:
    return bool(case_id and CASE_ID_PREFIX_PATTERN.match(case_id) and "_" in case_prefix)


@contextmanager
def readonly_db_copy(db_path: Path):
    temp_dir = Path(tempfile.mkdtemp(prefix="diagnose_integrity_", dir=PROJECT_ROOT))
    copied_sidecars: list[str] = []
    try:
        for suffix in ("", "-wal", "-shm"):
            source = Path(f"{db_path}{suffix}")
            if source.exists():
                target = temp_dir / source.name
                shutil.copy2(source, target)
                if suffix:
                    copied_sidecars.append(source.name)
        copy_db_path = temp_dir / db_path.name
        connection = sqlite3.connect(f"file:{copy_db_path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            yield connection, CopyMetadata(
                source_db_path=str(db_path),
                copy_db_path=str(copy_db_path),
                copied_sidecars=copied_sidecars,
            )
        finally:
            connection.close()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _fetch_scalar(connection: sqlite3.Connection, query: str) -> int:
    row = connection.execute(query).fetchone()
    if row is None:
        return 0
    return int(row[0] or 0)


def collect_integrity_report(db_path: Path) -> dict[str, Any]:
    with readonly_db_copy(db_path) as (connection, copy_metadata):
        table_counts = {
            table_name: _fetch_scalar(connection, f"SELECT COUNT(*) FROM {table_name}")
            for table_name in RELEVANT_TABLES
        }

        fk_orphans = {
            name: _fetch_scalar(connection, query)
            for name, query in FK_CHECKS
        }

        procedure_sequence_duplicates = [
            {
                "product_test_case_id": row["product_test_case_id"],
                "procedure_sequence": row["procedure_sequence"],
                "count": row["duplicate_count"],
            }
            for row in connection.execute(
                """
                SELECT
                    product_test_case_id,
                    procedure_sequence,
                    COUNT(*) AS duplicate_count
                FROM product_test_procedure
                GROUP BY product_test_case_id, procedure_sequence
                HAVING COUNT(*) > 1
                ORDER BY product_test_case_id, procedure_sequence
                """
            ).fetchall()
        ]

        orphan_cases = [
            row["product_test_case_id"]
            for row in connection.execute(
                """
                SELECT c.product_test_case_id
                FROM product_test_case c
                LEFT JOIN product_test_result r
                  ON r.product_test_case_id = c.product_test_case_id
                WHERE r.product_test_result_id IS NULL
                ORDER BY c.product_test_case_id
                """
            ).fetchall()
        ]

        mismatch_total = 0
        combo_counter: Counter[str] = Counter()
        legacy_ap_count = 0
        router_count = 0
        result_combo_count = 0
        for row in connection.execute(
            """
            SELECT
                r.product_test_result_id,
                r.remark,
                c.product_test_case_id
            FROM product_test_result r
            LEFT JOIN product_test_case c
              ON c.product_test_case_id = r.product_test_case_id
            ORDER BY r.product_test_result_id
            """
        ).fetchall():
            combo = _extract_combo(row["remark"])
            case_prefix = _extract_case_prefix(row["product_test_case_id"])
            comparable_case_prefix = _is_comparable_case_prefix(
                row["product_test_case_id"], case_prefix
            )
            if combo:
                result_combo_count += 1
                combo_counter[combo] += 1
                if "AP" in combo:
                    legacy_ap_count += 1
                if "ROUTER" in combo:
                    router_count += 1
            if combo and comparable_case_prefix and combo != case_prefix:
                mismatch_total += 1

        abnormal_case_ids = [
            {
                "product_test_case_id": row["product_test_case_id"],
                "product_test_case_status": row["product_test_case_status"],
                "procedure_count": int(row["procedure_count"] or 0),
                "result_count": int(row["result_count"] or 0),
            }
            for row in connection.execute(
                """
                SELECT
                    c.product_test_case_id,
                    c.product_test_case_status,
                    COUNT(DISTINCT p.product_test_procedure_id) AS procedure_count,
                    COUNT(DISTINCT r.product_test_result_id) AS result_count
                FROM product_test_case c
                LEFT JOIN product_test_procedure p
                  ON p.product_test_case_id = c.product_test_case_id
                LEFT JOIN product_test_result r
                  ON r.product_test_case_id = c.product_test_case_id
                WHERE c.product_test_case_id NOT LIKE 'TEST_CASE-%' AND c.product_test_case_id NOT LIKE 'CASE-%'
                GROUP BY c.product_test_case_id, c.product_test_case_status
                ORDER BY c.product_test_case_id
                """
            ).fetchall()
        ]

        rounds_without_release = [
            row["test_round_id"]
            for row in connection.execute(
                """
                SELECT round.test_round_id
                FROM product_test_round round
                LEFT JOIN product_test_release rel
                  ON rel.test_round_id = round.test_round_id
                WHERE rel.product_test_release_id IS NULL
                ORDER BY round.test_round_id
                """
            ).fetchall()
        ]

        releases_without_round = [
            row["product_test_release_id"]
            for row in connection.execute(
                """
                SELECT product_test_release_id
                FROM product_test_release
                WHERE test_round_id IS NULL
                ORDER BY product_test_release_id
                """
            ).fetchall()
        ]

        status_vocab = {
            "result": {
                row["status"]: int(row["count"])
                for row in connection.execute(
                    """
                    SELECT product_test_result_status AS status, COUNT(*) AS count
                    FROM product_test_result
                    GROUP BY product_test_result_status
                    ORDER BY product_test_result_status
                    """
                ).fetchall()
            },
            "release": {
                row["status"]: int(row["count"])
                for row in connection.execute(
                    """
                    SELECT product_test_release_status AS status, COUNT(*) AS count
                    FROM product_test_release
                    GROUP BY product_test_release_status
                    ORDER BY product_test_release_status
                    """
                ).fetchall()
            },
            "run": {
                row["status"]: int(row["count"])
                for row in connection.execute(
                    """
                    SELECT product_test_run_status AS status, COUNT(*) AS count
                    FROM product_test_run
                    GROUP BY product_test_run_status
                    ORDER BY product_test_run_status
                    """
                ).fetchall()
            },
        }

        return {
            "meta": {
                "source": "read_only_copy",
                "copy": asdict(copy_metadata),
                "remark_combo_pattern": REMARK_COMBO_PATTERN.pattern,
            },
            "table_counts": table_counts,
            "fk_orphans": fk_orphans,
            "procedure_sequence_duplicates": {
                "count": len(procedure_sequence_duplicates),
                "rows": procedure_sequence_duplicates,
            },
            "orphan_cases": {
                "count": len(orphan_cases),
                "case_ids": orphan_cases,
            },
            "case_topology_mismatch": {
                "count": mismatch_total,
                "total_results": table_counts["product_test_result"],
            },
            "combo_usage": {
                "parsed_result_count": result_combo_count,
                "legacy_ap_count": legacy_ap_count,
                "router_count": router_count,
                "top_combos": combo_counter.most_common(10),
            },
            "abnormal_case_ids": abnormal_case_ids,
            "round_gaps": {
                "rounds_without_release_count": len(rounds_without_release),
                "rounds_without_release": rounds_without_release,
                "releases_without_round_count": len(releases_without_round),
                "releases_without_round": releases_without_round,
            },
            "status_vocab": status_vocab,
        }


def _format_text_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    meta = report["meta"]
    lines.append("== Integrity Diagnosis ==")
    lines.append(f"Source DB: {meta['copy']['source_db_path']}")
    lines.append(f"Read-only copy: {meta['copy']['copy_db_path']}")
    lines.append(f"Copied WAL sidecars: {', '.join(meta['copy']['copied_sidecars']) or '(none)'}")
    lines.append("")
    lines.append("[Table Counts]")
    for table_name, count in report["table_counts"].items():
        lines.append(f"- {table_name}: {count}")
    lines.append("")
    lines.append("[FK Orphans]")
    for name, count in report["fk_orphans"].items():
        lines.append(f"- {name}: {count}")
    lines.append("")
    lines.append("[Procedure / Case Integrity]")
    lines.append(
        f"- procedure_sequence_duplicates: {report['procedure_sequence_duplicates']['count']}"
    )
    lines.append(f"- orphan_cases: {report['orphan_cases']['count']}")
    lines.append("")
    mismatch = report["case_topology_mismatch"]
    lines.append("[Case Topology Mismatch]")
    lines.append(
        f"- mismatches: {mismatch['count']} / {mismatch['total_results']}"
    )
    combo_usage = report["combo_usage"]
    lines.append("[Combo Usage]")
    lines.append(f"- parsed_results: {combo_usage['parsed_result_count']}")
    lines.append(f"- legacy_ap_count: {combo_usage['legacy_ap_count']}")
    lines.append(f"- router_count: {combo_usage['router_count']}")
    for combo, count in combo_usage["top_combos"]:
        lines.append(f"  - {combo}: {count}")
    lines.append("")
    lines.append("[Abnormal Case IDs]")
    for row in report["abnormal_case_ids"]:
        lines.append(
            "- {product_test_case_id} | status={product_test_case_status} | "
            "procedures={procedure_count} | results={result_count}".format(**row)
        )
    lines.append("")
    round_gaps = report["round_gaps"]
    lines.append("[Round Gaps]")
    lines.append(
        f"- rounds_without_release ({round_gaps['rounds_without_release_count']}): "
        + ", ".join(round_gaps["rounds_without_release"])
    )
    lines.append(
        f"- releases_without_round ({round_gaps['releases_without_round_count']}): "
        + ", ".join(round_gaps["releases_without_round"])
    )
    lines.append("")
    lines.append("[Status Vocabulary]")
    for table_name, vocab in report["status_vocab"].items():
        status_parts = ", ".join(f"{status}={count}" for status, count in vocab.items())
        lines.append(f"- {table_name}: {status_parts}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose product test data integrity.")
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Path to the SQLite DB file. Defaults to data/product_test_tracking_system.db",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the integrity report as JSON.",
    )
    args = parser.parse_args()

    report = collect_integrity_report(Path(args.db).resolve())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_format_text_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
