"""TASK 15-1: round table -> 7 canonical campaigns + 8 device shell cleanup."""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
ACTOR = "task15_1_round_normalize_v1"
NOW = datetime.now(timezone.utc).isoformat()

CANONICAL_CAMPAIGNS = (
    "WIFI_1ST",
    "WIFI_1ST_IMPROVE",
    "WIFI_2ND",
    "WIFI_2ND_IMPROVE",
    "DOWNGRADE",
    "WIFI_SMOKE",
    "WBS",
)

ROUND_RENAMES = {
    "ROUND-WIFI_DOWNGRADE_COMPARE_20260526": "ROUND-DOWNGRADE",
}

DEVICE_SHELL_ROUNDS = (
    "ROUND-HDC_9100_1_0_5A",
    "ROUND-HDR_9000_1_1_7E",
    "ROUND-HDR_9000_1_1_8",
    "ROUND-HLM_9000_1_1_14B",
    "ROUND-HRK_9000A_1_1_0A",
    "ROUND-HRK_9000A_1_1_1A",
    "ROUND-HRK_9000A_1_1_1D",
    "ROUND-HTR_1A_1_1_8",
)

NEW_ROUNDS = {
    "ROUND-WIFI_SMOKE": {
        "test_round_name": "단독제품 WiFi Smoke (양산)",
        "migration_status": "CONFIRMED",
        "migration_note": "v2 양산 캠페인 라운드 (마스터 확정)",
    },
    "ROUND-WBS": {
        "test_round_name": "단독제품 WBS (양산)",
        "migration_status": "CONFIRMED",
        "migration_note": "v2 양산 캠페인 라운드 (마스터 확정)",
    },
}


def campaign_token(round_id: str) -> str:
    if round_id.startswith("ROUND-"):
        return round_id.removeprefix("ROUND-")
    return round_id


def infer_release_target_round(
    release_id: str,
    current_round_id: str | None,
    upstream_release_id: str | None,
) -> tuple[str | None, str]:
    rid = release_id.upper()
    upstream = (upstream_release_id or "").upper()

    # WBS before WIFI_1_1_1D (WIFI_1_1_1D_WBS contains both tokens)
    if "WBS" in rid or "WBS" in upstream:
        return "ROUND-WBS", "token:wbs"
    if "SMOKE" in rid:
        return "ROUND-WIFI_SMOKE", "token:smoke"
    # WIFI_1_1_1D HRK 1.1.1D series + HDR empty tree -> WIFI_SMOKE (user confirmed 2026-06-09)
    if "WIFI_1_1_1D" in rid or "WIFI_1_1_1D" in upstream:
        return "ROUND-WIFI_SMOKE", "token:wifi_1_1_1d_to_smoke"
    if "DOWNGRADE" in rid or "DOWNGRADE" in upstream:
        return "ROUND-DOWNGRADE", "token:downgrade"
    if "WIFI_2ND_IMPROVE" in rid or "TBD_REPORT_NO4" in rid:
        return "ROUND-WIFI_2ND_IMPROVE", "token:wifi_2nd_improve"
    if "WIFI_2ND" in rid or "WIFI_2ND" in upstream:
        return "ROUND-WIFI_2ND", "token:wifi_2nd"
    if "WIFI_1ST_IMPROVE" in rid or "TBD_REPORT_NO2" in rid:
        return "ROUND-WIFI_1ST_IMPROVE", "token:wifi_1st_improve"
    if "WIFI_1ST" in rid or "WIFI_1ST" in upstream:
        return "ROUND-WIFI_1ST", "token:wifi_1st"

    if current_round_id == "ROUND-HRK_9000A_1_1_0A":
        return "ROUND-DOWNGRADE", "device_round:hrk_0a"
    if current_round_id == "ROUND-HRK_9000A_1_1_1A":
        return "ROUND-WIFI_2ND", "device_round:hrk_1a"

    if current_round_id and current_round_id not in DEVICE_SHELL_ROUNDS:
        return current_round_id, "unchanged:already_canonical"

    return None, "unmapped:no_rule"


def backup_database(src: Path) -> Path:
    backup_dir = PROJECT_ROOT / "data" / "backups" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{src.stem}.task15_1_{datetime.now().strftime('%H%M%S')}.db"
    with sqlite3.connect(str(src)) as source, sqlite3.connect(str(backup_path)) as dest:
        source.backup(dest)
    return backup_path


@contextmanager
def db_session(apply: bool):
    if apply:
        backup_path = backup_database(DB_PATH)
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        meta = {"backup_path": str(backup_path), "mode": "apply"}
        try:
            yield conn, meta
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return

    live = sqlite3.connect(str(DB_PATH))
    live.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    live.close()

    temp_dir = Path(tempfile.mkdtemp(prefix="task15_1_", dir=PROJECT_ROOT))
    try:
        for suffix in ("", "-wal", "-shm"):
            sidecar = Path(f"{DB_PATH}{suffix}")
            if sidecar.exists():
                shutil.copy2(sidecar, temp_dir / sidecar.name)
        copy_path = temp_dir / DB_PATH.name
        conn = sqlite3.connect(str(copy_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn, {"copy_path": str(copy_path), "mode": "dry-run"}
            conn.rollback()
        finally:
            conn.close()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def collect_plan(conn: sqlite3.Connection) -> dict:
    existing_rounds = {
        row["test_round_id"]: dict(row)
        for row in conn.execute("SELECT * FROM product_test_round").fetchall()
    }
    project_id = next(iter(existing_rounds.values())).get("project_id") if existing_rounds else None

    round_deletes = []
    for round_id in DEVICE_SHELL_ROUNDS:
        row = existing_rounds.get(round_id)
        if not row:
            continue
        rel_cnt = conn.execute(
            "SELECT COUNT(*) FROM product_test_release WHERE test_round_id=?",
            (round_id,),
        ).fetchone()[0]
        round_deletes.append(
            {
                "round_id": round_id,
                "release_count_before_remap": rel_cnt,
                "result_count": conn.execute(
                    """
                    SELECT COUNT(*) FROM product_test_result res
                    JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
                    JOIN product_test_release rel ON rel.product_test_release_id = run.product_test_release_id
                    WHERE rel.test_round_id=?
                    """,
                    (round_id,),
                ).fetchone()[0],
            }
        )

    round_renames = []
    for old_id, new_id in ROUND_RENAMES.items():
        if old_id not in existing_rounds:
            continue
        rel_cnt = conn.execute(
            "SELECT COUNT(*) FROM product_test_release WHERE test_round_id=?",
            (old_id,),
        ).fetchone()[0]
        round_renames.append({"old_id": old_id, "new_id": new_id, "release_fk_rows": rel_cnt})

    round_creates = []
    for round_id, spec in NEW_ROUNDS.items():
        if round_id in existing_rounds:
            continue
        round_creates.append({"round_id": round_id, **spec, "project_id": project_id})

    release_changes = []
    unmapped_releases = []
    for row in conn.execute(
        """
        SELECT product_test_release_id, test_round_id, upstream_release_id
        FROM product_test_release
        ORDER BY product_test_release_id
        """
    ).fetchall():
        old_round = row["test_round_id"]
        target_round, reason = infer_release_target_round(
            row["product_test_release_id"],
            old_round,
            row["upstream_release_id"],
        )
        if target_round is None:
            unmapped_releases.append(
                {
                    "release_id": row["product_test_release_id"],
                    "current_round_id": old_round,
                    "upstream_release_id": row["upstream_release_id"],
                    "reason": reason,
                }
            )
            continue
        for rename_old, rename_new in ROUND_RENAMES.items():
            if target_round == rename_old:
                target_round = rename_new
        if target_round != old_round:
            release_changes.append(
                {
                    "release_id": row["product_test_release_id"],
                    "old_round_id": old_round,
                    "new_round_id": target_round,
                    "reason": reason,
                }
            )

    post_round_ids = set()
    for round_id in existing_rounds:
        if round_id in DEVICE_SHELL_ROUNDS:
            continue
        post_round_ids.add(ROUND_RENAMES.get(round_id, round_id))
    post_round_ids.update(NEW_ROUNDS)
    post_campaigns = sorted(campaign_token(rid) for rid in post_round_ids)

    final_round_list = sorted(post_round_ids)

    return {
        "current_round_count": len(existing_rounds),
        "target_round_count": len(post_round_ids),
        "final_round_ids": final_round_list,
        "round_renames": round_renames,
        "round_creates": round_creates,
        "round_deletes": round_deletes,
        "release_round_remaps": release_changes,
        "unmapped_releases": unmapped_releases,
        "post_campaign_tokens": post_campaigns,
    }


def apply_plan(conn: sqlite3.Connection, plan: dict) -> None:
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        sample = conn.execute("SELECT * FROM product_test_round LIMIT 1").fetchone()
        if not sample:
            raise RuntimeError("product_test_round is empty")
        columns = sample.keys()

        for item in plan["release_round_remaps"]:
            conn.execute(
                """
                UPDATE product_test_release
                SET test_round_id=?, updated_at=?, updated_by=?
                WHERE product_test_release_id=?
                """,
                (item["new_round_id"], NOW, ACTOR, item["release_id"]),
            )

        for item in plan["round_renames"]:
            old_row = conn.execute(
                "SELECT * FROM product_test_round WHERE test_round_id=?",
                (item["old_id"],),
            ).fetchone()
            row_dict = dict(old_row)
            row_dict["test_round_id"] = item["new_id"]
            row_dict["updated_at"] = NOW
            row_dict["updated_by"] = ACTOR
            placeholders = ",".join("?" for _ in columns)
            conn.execute(
                f"INSERT INTO product_test_round ({','.join(columns)}) VALUES ({placeholders})",
                tuple(row_dict[col] for col in columns),
            )
            conn.execute(
                "UPDATE product_test_release SET test_round_id=? WHERE test_round_id=?",
                (item["new_id"], item["old_id"]),
            )
            conn.execute("DELETE FROM product_test_round WHERE test_round_id=?", (item["old_id"],))

        for item in plan["round_creates"]:
            conn.execute(
                """
                INSERT INTO product_test_round (
                    test_round_id, test_round_name, workday, start_date, end_date,
                    date_quality, migration_status, migration_note, project_id,
                    created_at, created_by, updated_at, updated_by
                ) VALUES (?, ?, NULL, NULL, NULL, 'INFER', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["round_id"],
                    item["test_round_name"],
                    item["migration_status"],
                    item["migration_note"],
                    item["project_id"],
                    NOW,
                    ACTOR,
                    NOW,
                    ACTOR,
                ),
            )

        for item in plan["round_deletes"]:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM product_test_release WHERE test_round_id=?",
                (item["round_id"],),
            ).fetchone()[0]
            if remaining:
                raise RuntimeError(f"Cannot delete {item['round_id']}: {remaining} releases remain")
            conn.execute("DELETE FROM product_test_round WHERE test_round_id=?", (item["round_id"],))
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def summarize(plan: dict) -> dict:
    return {
        "round_renames": len(plan["round_renames"]),
        "round_creates": len(plan["round_creates"]),
        "round_deletes": len(plan["round_deletes"]),
        "release_round_remaps": len(plan["release_round_remaps"]),
        "unmapped_releases": len(plan["unmapped_releases"]),
        "current_round_count": plan["current_round_count"],
        "target_round_count": plan["target_round_count"],
        "final_round_ids": plan["final_round_ids"],
        "post_campaign_tokens": plan["post_campaign_tokens"],
        "device_shell_empty_deletes": sum(
            1 for item in plan["round_deletes"] if item["release_count_before_remap"] == 0
        ),
        "device_shell_with_data": [
            item for item in plan["round_deletes"] if item["release_count_before_remap"] > 0
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="TASK 15-1 round normalization")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with db_session(args.apply) as (conn, meta):
        plan = collect_plan(conn)
        if args.apply and plan["unmapped_releases"]:
            raise SystemExit(
                f"Refusing apply: {len(plan['unmapped_releases'])} unmapped releases. Resolve first."
            )
        if args.apply:
            apply_plan(conn, plan)
        payload = {
            "step": "15-1",
            "mode": meta["mode"],
            "meta": meta,
            "canonical_campaigns": list(CANONICAL_CAMPAIGNS),
            "summary": summarize(plan),
            "round_renames": plan["round_renames"],
            "round_creates": plan["round_creates"],
            "round_deletes": plan["round_deletes"],
            "release_round_remaps": plan["release_round_remaps"],
            "unmapped_releases": plan["unmapped_releases"],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
