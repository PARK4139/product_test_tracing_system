from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.services.topology_normalize import normalize_combo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
NOW = datetime.now(timezone.utc).isoformat()
ACTOR = "migrate_ap_to_router_v1"
COMBO_PATTERN = re.compile(r"\[연결구성\]\s*([^\n\]]+)")
COMBO_TOKEN_PATTERN = re.compile(r"(25AP_[A-Z0-9_]+|1AP_[A-Z0-9_]+)")


def backup_database(src: Path) -> Path:
    backup_dir = PROJECT_ROOT / "data" / "backups" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{src.stem}.task5_{datetime.now().strftime('%H%M%S')}.db"
    with sqlite3.connect(str(src)) as source, sqlite3.connect(str(backup_path)) as dest:
        source.backup(dest)
    return backup_path


@contextmanager
def readonly_copy(src: Path):
    temp_dir = Path(tempfile.mkdtemp(prefix="task5_migrate_", dir=PROJECT_ROOT))
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


def replace_combo_text(raw_text: str | None) -> tuple[str | None, list[dict]]:
    if raw_text is None:
        return None, []
    replacements: list[dict] = []

    def _replace(match: re.Match[str]) -> str:
        legacy_combo = match.group(1)
        normalized_combo = normalize_combo(legacy_combo)
        replacements.append(
            {
                "legacy_combo": legacy_combo,
                "normalized_combo": normalized_combo,
                "changed": legacy_combo != normalized_combo,
            }
        )
        return normalized_combo

    new_text = COMBO_TOKEN_PATTERN.sub(_replace, raw_text)
    return new_text, replacements


def preserve_old_and_new_remark(old_remark: str | None) -> str | None:
    new_remark, replacements = replace_combo_text(old_remark)
    if old_remark is None or new_remark == old_remark:
        return new_remark
    changed_legacy = [item["legacy_combo"] for item in replacements if item["changed"]]
    if not changed_legacy:
        return new_remark
    unique_legacy = ", ".join(dict.fromkeys(changed_legacy))
    return f"[구 연결구성] {unique_legacy}\n{new_remark}"


def collect_changes(conn: sqlite3.Connection) -> dict:
    result_changes = []
    for row in conn.execute("SELECT product_test_result_id, remark FROM product_test_result ORDER BY product_test_result_id").fetchall():
        legacy_combo = extract_combo(row["remark"])
        normalized_combo = normalize_combo(legacy_combo)
        if legacy_combo != normalized_combo:
            new_remark, replacements = replace_combo_text(row["remark"])
            result_changes.append(
                {
                    "table": "product_test_result",
                    "id": row["product_test_result_id"],
                    "legacy_combo": legacy_combo,
                    "normalized_combo": normalized_combo,
                    "remark_changed": new_remark != row["remark"],
                    "replacements": replacements,
                }
            )

    release_changes = []
    for row in conn.execute(
        """
        SELECT product_test_release_id, upstream_release_id, remark
        FROM product_test_release
        WHERE product_test_release_id LIKE '%AP%' OR upstream_release_id LIKE '%AP%' OR remark LIKE '%AP%'
        ORDER BY product_test_release_id
        """
    ).fetchall():
        new_id, id_replacements = replace_combo_text(row["product_test_release_id"])
        new_upstream, upstream_replacements = replace_combo_text(row["upstream_release_id"])
        new_remark, remark_replacements = replace_combo_text(row["remark"])
        release_changes.append(
            {
                "table": "product_test_release",
                "id": row["product_test_release_id"],
                "new_id": new_id,
                "new_upstream_release_id": new_upstream,
                "remark_changed": new_remark != row["remark"],
                "id_changed": new_id != row["product_test_release_id"],
                "upstream_changed": new_upstream != row["upstream_release_id"],
                "replacements": id_replacements + upstream_replacements + remark_replacements,
            }
        )

    run_changes = []
    for row in conn.execute(
        """
        SELECT product_test_run_id, product_test_release_id, remark
        FROM product_test_run
        WHERE product_test_release_id LIKE '%AP%' OR remark LIKE '%AP%'
        ORDER BY product_test_run_id
        """
    ).fetchall():
        new_release_id, release_replacements = replace_combo_text(row["product_test_release_id"])
        new_remark, remark_replacements = replace_combo_text(row["remark"])
        run_changes.append(
            {
                "table": "product_test_run",
                "id": row["product_test_run_id"],
                "new_product_test_release_id": new_release_id,
                "release_id_changed": new_release_id != row["product_test_release_id"],
                "remark_changed": new_remark != row["remark"],
                "replacements": release_replacements + remark_replacements,
            }
        )

    release_id_mapping = {
        change["id"]: change["new_id"]
        for change in release_changes
        if change["id_changed"]
    }
    dependent_fk_counts = {
        "run_release_fk_rows": conn.execute(
            f"""
            SELECT COUNT(*) FROM product_test_run
            WHERE product_test_release_id IN ({",".join("?" for _ in release_id_mapping) or "''"})
            """,
            tuple(release_id_mapping.keys()),
        ).fetchone()[0] if release_id_mapping else 0,
        "report_release_fk_rows": conn.execute(
            f"""
            SELECT COUNT(*) FROM product_test_report
            WHERE product_test_release_id IN ({",".join("?" for _ in release_id_mapping) or "''"})
            """,
            tuple(release_id_mapping.keys()),
        ).fetchone()[0] if release_id_mapping else 0,
        "snapshot_release_fk_rows": conn.execute(
            f"""
            SELECT COUNT(*) FROM product_test_report_snapshot
            WHERE product_test_release_id IN ({",".join("?" for _ in release_id_mapping) or "''"})
            """,
            tuple(release_id_mapping.keys()),
        ).fetchone()[0] if release_id_mapping else 0,
        "release_upstream_rows": conn.execute(
            f"""
            SELECT COUNT(*) FROM product_test_release
            WHERE upstream_release_id IN ({",".join("?" for _ in release_id_mapping) or "''"})
            """,
            tuple(release_id_mapping.keys()),
        ).fetchone()[0] if release_id_mapping else 0,
    }

    return {
        "result_changes": result_changes,
        "release_changes": release_changes,
        "run_changes": run_changes,
        "release_id_mapping": release_id_mapping,
        "dependent_fk_counts": dependent_fk_counts,
    }


def apply_changes(conn: sqlite3.Connection, changes: dict) -> None:
    release_id_mapping: dict[str, str] = changes["release_id_mapping"]
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        for change in changes["result_changes"]:
            row = conn.execute("SELECT remark FROM product_test_result WHERE product_test_result_id=?", (change["id"],)).fetchone()
            legacy_combo = extract_combo(row["remark"])
            new_remark = row["remark"].replace(f"[연결구성] {legacy_combo}", f"[구 연결구성] {legacy_combo}\n[연결구성] {change['normalized_combo']}", 1)
            conn.execute(
                "UPDATE product_test_result SET remark=?, updated_at=?, updated_by=? WHERE product_test_result_id=?",
                (new_remark, NOW, ACTOR, change["id"]),
            )

        changed_release_ids = set(release_id_mapping.keys())
        release_rows = conn.execute("SELECT * FROM product_test_release").fetchall()
        release_columns = [description[0] for description in conn.execute("SELECT * FROM product_test_release LIMIT 1").description]
        release_changes_by_id = {change["id"]: change for change in changes["release_changes"]}

        for row in release_rows:
            row_dict = dict(zip(release_columns, row))
            old_id = row_dict["product_test_release_id"]
            if old_id not in changed_release_ids:
                continue
            target_id = release_id_mapping[old_id]
            target_upstream = release_id_mapping.get(row_dict["upstream_release_id"], row_dict["upstream_release_id"])
            new_remark = preserve_old_and_new_remark(row_dict["remark"])
            conn.execute(
                """
                INSERT INTO product_test_release (
                    product_test_release_id, upstream_release_id, upstream_release_system, release_stage,
                    release_sequence, product_test_release_status, created_at, created_by, updated_at,
                    updated_by, remark, release_visible, project_id, test_round_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_id,
                    target_upstream,
                    row_dict["upstream_release_system"],
                    row_dict["release_stage"],
                    row_dict["release_sequence"],
                    row_dict["product_test_release_status"],
                    row_dict["created_at"],
                    row_dict["created_by"],
                    NOW,
                    ACTOR,
                    new_remark,
                    row_dict["release_visible"],
                    row_dict["project_id"],
                    row_dict["test_round_id"],
                ),
            )

        for row in release_rows:
            row_dict = dict(zip(release_columns, row))
            old_id = row_dict["product_test_release_id"]
            if old_id in changed_release_ids:
                continue
            target_upstream = release_id_mapping.get(row_dict["upstream_release_id"], row_dict["upstream_release_id"])
            new_remark = preserve_old_and_new_remark(row_dict["remark"])
            if new_remark != row_dict["remark"] or target_upstream != row_dict["upstream_release_id"]:
                conn.execute(
                    """
                    UPDATE product_test_release
                    SET upstream_release_id=?, remark=?, updated_at=?, updated_by=?
                    WHERE product_test_release_id=?
                    """,
                    (target_upstream, new_remark, NOW, ACTOR, old_id),
                )

        for old_id, new_id in release_id_mapping.items():
            conn.execute(
                "UPDATE product_test_run SET product_test_release_id=? WHERE product_test_release_id=?",
                (new_id, old_id),
            )
            conn.execute(
                "UPDATE product_test_report SET product_test_release_id=? WHERE product_test_release_id=?",
                (new_id, old_id),
            )
            conn.execute(
                "UPDATE product_test_report_snapshot SET product_test_release_id=? WHERE product_test_release_id=?",
                (new_id, old_id),
            )

        for change in changes["run_changes"]:
            row = conn.execute("SELECT remark FROM product_test_run WHERE product_test_run_id=?", (change["id"],)).fetchone()
            new_remark = preserve_old_and_new_remark(row["remark"])
            conn.execute(
                """
                UPDATE product_test_run
                SET product_test_release_id=?, remark=?, updated_at=?, updated_by=?
                WHERE product_test_run_id=?
                """,
                (change["new_product_test_release_id"], new_remark, NOW, ACTOR, change["id"]),
            )
        for old_id in changed_release_ids:
            conn.execute("DELETE FROM product_test_release WHERE product_test_release_id=?", (old_id,))
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def summarize(changes: dict) -> dict:
    return {
        "result_rows_to_change": len(changes["result_changes"]),
        "release_rows_to_change": len(changes["release_changes"]),
        "run_rows_to_change": len(changes["run_changes"]),
        "release_id_rows_to_rename": len(changes["release_id_mapping"]),
        "dependent_fk_counts": changes["dependent_fk_counts"],
        "sample_result_changes": changes["result_changes"][:15],
        "sample_release_changes": changes["release_changes"][:15],
        "sample_run_changes": changes["run_changes"][:15],
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
        changes = collect_changes(conn)
        if args.apply:
            apply_changes(conn, changes)
            conn.commit()
        payload = {
            "mode": "apply" if args.apply else "dry-run",
            "backup_path": str(backup_path) if backup_path else "",
            "meta": meta,
            "summary": summarize(changes),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    finally:
        conn.close()
        if not args.apply:
            ctx.__exit__(None, None, None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
