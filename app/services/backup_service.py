"""Daily SQLite DB backup service.

Runs on app startup + background thread at midnight.
Backups are stored in data/backups/{YYYY-MM-DD}/ with no automatic deletion.
Uses SQLite VACUUM INTO for safe hot-backup (no locks, consistent snapshot).
"""

from __future__ import annotations

import shutil
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.logging_service import get_logger

_logger = get_logger("backup_service")


def _log(message: str) -> None:
    _logger.info("[backup_service] %s", message)


def _backup_sqlite_file(source_path: Path, dest_path: Path) -> bool:
    if not source_path.exists():
        return False
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(source_path))
        conn.execute(f"VACUUM INTO '{dest_path}'")
        conn.close()
        _log(f"backed up: {source_path.name} -> {dest_path}")
        return True
    except Exception as exc:
        _log(f"VACUUM INTO failed for {source_path.name}: {exc}, falling back to file copy")
        try:
            shutil.copy2(str(source_path), str(dest_path))
            _log(f"file-copy backup: {source_path.name} -> {dest_path}")
            return True
        except Exception as copy_exc:
            _log(f"backup failed for {source_path.name}: {copy_exc}")
            return False


BACKUP_ROOT = Path.home() / "Downloads" / "product_test_db_backups"


def run_backup(data_directory_path: Path) -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_dir = BACKUP_ROOT / today
    if backup_dir.exists():
        _log(f"backup already exists for {today}, skipping")
        return 0

    backup_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    main_db = data_directory_path / "product_test_tracking_system.db"
    if _backup_sqlite_file(main_db, backup_dir / main_db.name):
        count += 1

    projects_dir = data_directory_path / "projects"
    if projects_dir.exists():
        for project_dir in sorted(projects_dir.iterdir()):
            if not project_dir.is_dir():
                continue
            test_db = project_dir / "test_data.db"
            if test_db.exists():
                dest = backup_dir / f"{project_dir.name}.db"
                if _backup_sqlite_file(test_db, dest):
                    count += 1

    _log(f"daily backup complete: {count} file(s) -> {backup_dir}")
    return count


def _backup_loop(data_directory_path: Path) -> None:
    while True:
        now = datetime.now(timezone.utc)
        tomorrow_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        seconds_until_midnight = (tomorrow_midnight - now).total_seconds()
        _log(f"next backup in {seconds_until_midnight:.0f}s (midnight UTC)")
        time.sleep(max(seconds_until_midnight, 60))
        try:
            run_backup(data_directory_path)
        except Exception as exc:
            _log(f"backup error: {exc}")


def start_backup_daemon(data_directory_path: Path) -> None:
    try:
        run_backup(data_directory_path)
    except Exception as exc:
        _log(f"startup backup error: {exc}")

    thread = threading.Thread(
        target=_backup_loop,
        args=(data_directory_path,),
        daemon=True,
        name="backup-daemon",
    )
    thread.start()
    _log("backup daemon started")
