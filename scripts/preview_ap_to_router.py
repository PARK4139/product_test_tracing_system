from __future__ import annotations

import json
import re
import shutil
import sqlite3
import tempfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from app.services.topology_normalize import normalize_combo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
COMBO_PATTERN = re.compile(r"\[연결구성\]\s*([^\n\]]+)")


def extract_combo(remark: str | None) -> str:
    match = COMBO_PATTERN.search(remark or "")
    return match.group(1).strip() if match else ""


@contextmanager
def readonly_copy(src: Path):
    temp_dir = Path(tempfile.mkdtemp(prefix="task5_preview_", dir=PROJECT_ROOT))
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
    with readonly_copy(DB_PATH) as (conn, meta):
        rows = conn.execute(
            "SELECT product_test_result_id, remark FROM product_test_result ORDER BY product_test_result_id"
        ).fetchall()
        normalized_counter: Counter[str] = Counter()
        legacy_counter: Counter[str] = Counter()
        sample_rows = []
        ap_remaining = 0
        for row in rows:
            raw_combo = extract_combo(row["remark"])
            normalized = normalize_combo(raw_combo)
            if "AP" in normalized:
                ap_remaining += 1
            if raw_combo:
                legacy_counter[raw_combo] += 1
            normalized_counter[normalized] += 1
            if len(sample_rows) < 25:
                sample_rows.append(
                    {
                        "product_test_result_id": row["product_test_result_id"],
                        "legacy_combo": raw_combo,
                        "normalized_combo": normalized,
                    }
                )
        payload = {
            "mode": "dry-run-preview",
            "meta": meta,
            "totals": {
                "result_count": len(rows),
                "legacy_combo_count": sum(legacy_counter.values()),
                "ap_remaining_after_normalize": ap_remaining,
                "unclassified_count": normalized_counter["UNCLASSIFIED"],
            },
            "top_legacy_combos": legacy_counter.most_common(20),
            "top_normalized_combos": normalized_counter.most_common(20),
            "sample_rows": sample_rows,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
