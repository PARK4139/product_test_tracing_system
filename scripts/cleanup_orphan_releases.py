from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "product_test_tracking_system.db"
FALLBACK_RELEASE_ID = "RELEASE-FALLBACK-WIFI_CONNECTIVITY_TEST_2026"
ROUND_LEGACY_IDS = {
    "RELEASE-WIFI_1ST",
    "RELEASE-WIFI_2ND",
    "RELEASE-WIFI_DOWNGRADE",
    "RELEASE-WIFI_1_1_1D",
}
ROUND_FIXES = {
    "RELEASE-TBD_REPORT_NO2": "ROUND-WIFI_1ST_IMPROVE",
    "RELEASE-TBD_REPORT_NO4": "ROUND-WIFI_2ND_IMPROVE",
    "RELEASE-TBD_REPORT_NOTBD": "ROUND-HRK_9000A_1_1_1D",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cleanup orphan/NULL-round releases.")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the real database.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    return parser.parse_args()


def copy_wal_bundle(src_db: Path, temp_dir: Path) -> Path:
    db_copy = temp_dir / src_db.name
    shutil.copy2(src_db, db_copy)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(src_db) + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, temp_dir / sidecar.name)
    return db_copy


def backup_database() -> Path:
    backup_dir = ROOT_DIR / "data" / "backups" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{DB_PATH.stem}.task14_{datetime.now(timezone.utc).strftime('%H%M%S')}{DB_PATH.suffix}"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def fetch_scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return 0 if row is None or row[0] is None else int(row[0])


def fetch_release_row(conn: sqlite3.Connection, release_id: str) -> dict:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT product_test_release_id, upstream_release_id, release_stage, test_round_id, remark
        FROM product_test_release
        WHERE product_test_release_id = ?
        """,
        (release_id,),
    ).fetchone()
    return dict(row) if row else {}


def validate_state(conn: sqlite3.Connection) -> dict:
    fallback_refs = {
        "run_ref_count": fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM product_test_run WHERE product_test_release_id = ?",
            (FALLBACK_RELEASE_ID,),
        ),
        "report_ref_count": fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM product_test_report WHERE product_test_release_id = ?",
            (FALLBACK_RELEASE_ID,),
        ),
        "snapshot_ref_count": fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM product_test_report_snapshot WHERE product_test_release_id = ?",
            (FALLBACK_RELEASE_ID,),
        ),
        "upstream_child_count": fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM product_test_release WHERE upstream_release_id = ?",
            (FALLBACK_RELEASE_ID,),
        ),
    }
    if any(count != 0 for count in fallback_refs.values()):
        raise SystemExit("Fallback release has inbound references; stop and inspect.")

    round_fix_rows: dict[str, dict] = {}
    for release_id, round_id in ROUND_FIXES.items():
        row = fetch_release_row(conn, release_id)
        if not row:
            raise SystemExit(f"Missing TBD release: {release_id}")
        if row["test_round_id"] is not None:
            raise SystemExit(f"TBD release already has round_id: {release_id}")
        round_exists = fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM product_test_round WHERE test_round_id = ?",
            (round_id,),
        )
        if round_exists != 1:
            raise SystemExit(f"Missing target round_id: {round_id}")
        report_count = fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM product_test_report WHERE product_test_release_id = ?",
            (release_id,),
        )
        round_fix_rows[release_id] = {
            **row,
            "target_round_id": round_id,
            "report_count": report_count,
            "round_exists": round_exists,
        }

    round_legacy_counts = {
        release_id: {
            "descendant_release_count": fetch_scalar(
                conn,
                """
                WITH RECURSIVE tree(product_test_release_id) AS (
                    SELECT product_test_release_id
                    FROM product_test_release
                    WHERE product_test_release_id = ?
                    UNION ALL
                    SELECT child.product_test_release_id
                    FROM product_test_release child
                    JOIN tree parent ON child.upstream_release_id = parent.product_test_release_id
                )
                SELECT COUNT(*) - 1 FROM tree
                """,
                (release_id,),
            ),
            "run_count": fetch_scalar(
                conn,
                """
                WITH RECURSIVE tree(product_test_release_id) AS (
                    SELECT product_test_release_id
                    FROM product_test_release
                    WHERE product_test_release_id = ?
                    UNION ALL
                    SELECT child.product_test_release_id
                    FROM product_test_release child
                    JOIN tree parent ON child.upstream_release_id = parent.product_test_release_id
                )
                SELECT COUNT(*)
                FROM product_test_run run
                WHERE run.product_test_release_id IN (SELECT product_test_release_id FROM tree)
                """,
                (release_id,),
            ),
        }
        for release_id in sorted(ROUND_LEGACY_IDS)
    }

    return {
        "fallback_release": fetch_release_row(conn, FALLBACK_RELEASE_ID),
        "fallback_refs": fallback_refs,
        "round_fix_rows": round_fix_rows,
        "null_round_release_count": fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM product_test_release WHERE test_round_id IS NULL",
        ),
        "round_legacy_counts": round_legacy_counts,
    }


def apply_cleanup(conn: sqlite3.Connection) -> dict:
    now_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "DELETE FROM product_test_release WHERE product_test_release_id = ?",
        (FALLBACK_RELEASE_ID,),
    )
    updated_rows = []
    for release_id, round_id in ROUND_FIXES.items():
        row = fetch_release_row(conn, release_id)
        new_remark = ((row.get("remark") or "").strip() + "\n[round 보정] 제목기준 추론").strip()
        conn.execute(
            """
            UPDATE product_test_release
            SET test_round_id = ?, remark = ?, updated_at = ?, updated_by = ?
            WHERE product_test_release_id = ?
            """,
            (round_id, new_remark, now_text, "TASK14_RELEASE_CLEANUP", release_id),
        )
        updated_rows.append({"release_id": release_id, "target_round_id": round_id})
    conn.commit()
    return {
        "deleted_release_id": FALLBACK_RELEASE_ID,
        "updated_rows": updated_rows,
    }


def run_dry_run(json_mode: bool) -> None:
    with TemporaryDirectory() as tmp:
        db_copy = copy_wal_bundle(DB_PATH, Path(tmp))
        conn = sqlite3.connect(db_copy)
        try:
            payload = validate_state(conn)
            payload["planned_delete"] = FALLBACK_RELEASE_ID
            payload["planned_updates"] = [
                {"release_id": release_id, "target_round_id": round_id}
                for release_id, round_id in ROUND_FIXES.items()
            ]
            payload["post_cleanup_null_round_release_count"] = payload["null_round_release_count"] - 4
        finally:
            conn.close()
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print("[TASK 14 dry-run] release cleanup")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_apply(json_mode: bool) -> None:
    backup_path = backup_database()
    conn = sqlite3.connect(DB_PATH)
    try:
        payload = validate_state(conn)
        payload["changes"] = apply_cleanup(conn)
        payload["backup_path"] = str(backup_path)
        payload["post_cleanup_null_round_release_count"] = fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM product_test_release WHERE test_round_id IS NULL",
        )
    finally:
        conn.close()
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print("[TASK 14 apply] release cleanup")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    args = parse_args()
    if args.apply:
        run_apply(args.json)
        return
    run_dry_run(args.json)


if __name__ == "__main__":
    main()
