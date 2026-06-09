"""STEP D dry-run: run/result topology AP→ROUTER normalization preview."""
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
AP_TOPO_PATTERN = re.compile(r"(25AP_[A-Z0-9_]+|1AP_[A-Z0-9_]+)")
LEGACY_COMBO_MARKER = re.compile(r"\[구 연결구성\]")


def extract_combo(remark: str | None) -> str:
    match = COMBO_PATTERN.search(remark or "")
    return match.group(1).strip() if match else ""


def replace_topology_tokens(text: str, *, preserve_legacy_blocks: bool = False) -> tuple[str, list[dict]]:
    replacements: list[dict] = []

    def _replace_segment(segment: str) -> str:
        def _replace(match: re.Match[str]) -> str:
            legacy = match.group(1)
            normalized = normalize_combo(legacy)
            replacements.append(
                {
                    "legacy": legacy,
                    "normalized": normalized,
                    "changed": legacy != normalized,
                }
            )
            if normalized != "UNCLASSIFIED" and legacy != normalized:
                return normalized
            fallback = legacy.replace("25AP", "25ROUTER").replace("1AP", "1ROUTER")
            return fallback

        return AP_TOPO_PATTERN.sub(_replace, segment)

    if not preserve_legacy_blocks:
        return _replace_segment(text), replacements

    parts = re.split(r"(\[구 연결구성\][^\n]*)", text)
    rebuilt: list[str] = []
    for part in parts:
        if part.startswith("[구 연결구성]"):
            rebuilt.append(part)
        else:
            rebuilt.append(_replace_segment(part))
    return "".join(rebuilt), replacements


def classify_combo(combo: str) -> str:
    if not combo:
        return "EMPTY"
    normalized = normalize_combo(combo)
    if normalized == "UNCLASSIFIED":
        return "UNCLASSIFIED"
    if normalized in CANONICAL_TOPOLOGIES:
        return "CANONICAL"
    return "UNCLASSIFIED"


@contextmanager
def readonly_db(src: Path):
    conn_live = sqlite3.connect(str(src))
    conn_live.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn_live.close()

    temp_dir = Path(tempfile.mkdtemp(prefix="step_d_dryrun_", dir=PROJECT_ROOT))
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


def main() -> int:
    with readonly_db(DB_PATH) as (conn, meta):
        runs = conn.execute(
            "SELECT product_test_run_id, remark FROM product_test_run ORDER BY product_test_run_id"
        ).fetchall()
        results = conn.execute(
            "SELECT product_test_result_id, remark, product_test_run_id FROM product_test_result ORDER BY product_test_result_id"
        ).fetchall()

        run_id_changes = []
        run_remark_changes = []
        for row in runs:
            old_id = row["product_test_run_id"]
            new_id, id_repl = replace_topology_tokens(old_id)
            if new_id != old_id:
                run_id_changes.append(
                    {
                        "old_id": old_id,
                        "new_id": new_id,
                        "replacements": id_repl,
                    }
                )
            old_remark = row["remark"] or ""
            new_remark, remark_repl = replace_topology_tokens(old_remark, preserve_legacy_blocks=True)
            if new_remark != old_remark:
                run_remark_changes.append(
                    {
                        "run_id": old_id,
                        "replacements": remark_repl,
                    }
                )

        result_combo_line_changes = []
        result_remark_other_changes = []
        result_id_changes = []
        for row in results:
            old_id = row["product_test_result_id"]
            new_id, id_repl = replace_topology_tokens(old_id)
            if new_id != old_id:
                result_id_changes.append(
                    {
                        "old_id": old_id,
                        "new_id": new_id,
                        "replacements": id_repl,
                    }
                )
            old_remark = row["remark"] or ""
            combo = extract_combo(old_remark)
            normalized_combo = normalize_combo(combo) if combo else ""
            if combo and AP_TOPO_PATTERN.search(combo):
                result_combo_line_changes.append(
                    {
                        "result_id": row["product_test_result_id"],
                        "legacy_combo": combo,
                        "normalized_combo": normalized_combo,
                    }
                )
            new_remark, remark_repl = replace_topology_tokens(old_remark, preserve_legacy_blocks=True)
            if new_remark != old_remark:
                result_remark_other_changes.append(
                    {
                        "result_id": row["product_test_result_id"],
                        "replacements": remark_repl,
                    }
                )

        before_class = Counter()
        after_class = Counter()
        after_combo_counter = Counter()
        for row in results:
            combo = extract_combo(row["remark"])
            before_class[classify_combo(combo)] += 1
            if combo and AP_TOPO_PATTERN.search(combo):
                combo = normalize_combo(combo)
            after_class[classify_combo(combo)] += 1
            if combo:
                after_combo_counter[normalize_combo(combo) if combo else "EMPTY"] += 1

        run_fk_orphans = 0
        if run_id_changes:
            new_ids = {item["new_id"] for item in run_id_changes}
            old_ids = {item["old_id"] for item in run_id_changes}
            collisions = new_ids & (old_ids - {item["old_id"] for item in run_id_changes if item["new_id"] in old_ids})
            run_fk_impact = conn.execute(
                f"""
                SELECT COUNT(*) FROM product_test_result
                WHERE product_test_run_id IN ({",".join("?" for _ in run_id_changes)})
                """,
                tuple(item["old_id"] for item in run_id_changes),
            ).fetchone()[0]
        else:
            collisions = set()
            run_fk_impact = 0

        post_run_ids = {item["new_id"] for item in run_id_changes} | {
            row["product_test_run_id"]
            for row in runs
            if row["product_test_run_id"] not in {item["old_id"] for item in run_id_changes}
        }
        ap_remaining_run_ids = [
            rid
            for rid in post_run_ids
            if re.search(r"(?<![A-Z])\d+AP(?:_|$)", rid)
            and "TARGET_AP" not in rid
        ]

        post_result_combos = []
        for row in results:
            remark = row["remark"] or ""
            new_remark, _ = replace_topology_tokens(remark)
            combo = extract_combo(new_remark)
            if combo:
                post_result_combos.append(combo)
        ap_remaining_combos = [c for c in post_result_combos if AP_TOPO_PATTERN.search(c)]

        payload = {
            "step": "D",
            "mode": "dry-run",
            "meta": meta,
            "impact": {
                "run_id_rows": len(run_id_changes),
                "run_remark_rows": len(run_remark_changes),
                "result_combo_line_rows": len(result_combo_line_changes),
                "result_remark_other_rows": len(result_remark_other_changes),
                "result_legacy_preserved_rows": sum(
                    1 for row in results if "[구 연결구성]" in (row["remark"] or "")
                ),
                "result_id_rows": len(result_id_changes),
                "result_run_fk_rows": run_fk_impact,
            },
            "classification": {
                "before": dict(before_class),
                "after": dict(after_class),
                "after_unclassified": after_class.get("UNCLASSIFIED", 0),
                "after_canonical": after_class.get("CANONICAL", 0),
                "after_empty": after_class.get("EMPTY", 0),
            },
            "residual_ap_tokens": {
                "run_ids": ap_remaining_run_ids,
                "result_combos": ap_remaining_combos,
            },
            "run_id_collisions": sorted(collisions),
            "sample_run_id_changes": run_id_changes[:20],
            "sample_result_combo_line_changes": result_combo_line_changes[:10],
            "sample_result_remark_other_changes": result_remark_other_changes[:10],
            "topology_distribution_after": after_combo_counter.most_common(30),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
