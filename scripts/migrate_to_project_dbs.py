"""Migrate existing single-DB data into per-project SQLite databases.

Usage:
    python -m scripts.migrate_to_project_dbs

What it does:
1. Reads all rows from the main DB that have a project_id set
2. Groups them by project_id
3. Creates data/projects/{project_id}/test_data.db for each project
4. Copies the rows into the project DB
5. Rows without project_id stay in the main DB (legacy/unassigned)

Safe to run multiple times — skips projects that already have a test_data.db.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, event, inspect, text
from app.config import app_settings
from app.db import _apply_sqlite_pragmas, PROJECTS_DIR, Base

PRODUCT_TEST_TABLES = [
    "product_test_release",
    "product_test_target_definition",
    "product_test_target",
    "product_test_environment_definition",
    "product_test_environment",
    "product_test_case",
    "product_test_procedure",
    "product_test_run",
    "product_test_result",
    "product_test_procedure_result",
    "product_test_defect",
    "product_test_evidence",
    "product_test_report",
    "product_test_report_snapshot",
    "product_test_status_transition",
]


def migrate() -> None:
    main_engine = create_engine(
        app_settings.sqlite_database_url,
        connect_args={"check_same_thread": False},
    )
    event.listen(main_engine, "connect", _apply_sqlite_pragmas)

    from app import models
    Base.metadata.create_all(bind=main_engine)

    with main_engine.connect() as conn:
        project_ids: set[str] = set()
        for table_name in PRODUCT_TEST_TABLES:
            result = conn.execute(
                text(f"SELECT DISTINCT project_id FROM {table_name} WHERE project_id IS NOT NULL AND project_id != ''")
            )
            for row in result:
                project_ids.add(row[0])

    if not project_ids:
        print("No project_id values found in existing data. Nothing to migrate.")
        return

    print(f"Found {len(project_ids)} project(s): {sorted(project_ids)}")

    for project_id in sorted(project_ids):
        project_dir = PROJECTS_DIR / project_id
        db_path = project_dir / "test_data.db"

        if db_path.exists():
            print(f"  SKIP {project_id}: test_data.db already exists")
            continue

        project_dir.mkdir(parents=True, exist_ok=True)
        proj_url = f"sqlite:///{db_path.as_posix()}"
        proj_engine = create_engine(proj_url, connect_args={"check_same_thread": False})
        event.listen(proj_engine, "connect", _apply_sqlite_pragmas)
        Base.metadata.create_all(bind=proj_engine)

        total_rows = 0
        with main_engine.connect() as main_conn:
            inspector = inspect(main_engine)
            for table_name in PRODUCT_TEST_TABLES:
                if not inspector.has_table(table_name):
                    continue

                columns = [col["name"] for col in inspector.get_columns(table_name)]
                cols_csv = ", ".join(f'"{c}"' for c in columns)
                placeholders = ", ".join(f":{c}" for c in columns)

                rows = main_conn.execute(
                    text(f"SELECT {cols_csv} FROM {table_name} WHERE project_id = :pid"),
                    {"pid": project_id},
                ).fetchall()

                if not rows:
                    continue

                with proj_engine.begin() as proj_conn:
                    for row in rows:
                        row_dict = dict(zip(columns, row))
                        proj_conn.execute(
                            text(f"INSERT OR IGNORE INTO {table_name} ({cols_csv}) VALUES ({placeholders})"),
                            row_dict,
                        )

                total_rows += len(rows)
                print(f"  {project_id}/{table_name}: {len(rows)} rows")

        proj_engine.dispose()
        print(f"  DONE {project_id}: {total_rows} total rows migrated")

    print("\nMigration complete.")


if __name__ == "__main__":
    migrate()
