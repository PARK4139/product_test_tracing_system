from __future__ import annotations

import threading
import traceback
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import app_settings
from app.services.logging_service import get_logger

_logger = get_logger("db")


class Base(DeclarativeBase):
    pass


# ── Shared SQLite PRAGMA setup ───────────────────────────────────────────────

def _apply_sqlite_pragmas(database_api_connection, _connection_record) -> None:
    cursor = database_api_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA mmap_size=67108864")
    cursor.execute("PRAGMA cache_size=-32768")
    cursor.close()


# ── Main DB (user_account, project, project_membership) ─────────────────────

engine = create_engine(
    app_settings.sqlite_database_url,
    connect_args={"check_same_thread": False},
)
event.listen(engine, "connect", _apply_sqlite_pragmas)

session_local = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
)


def get_database_session() -> Iterator[Session]:
    database_session = session_local()
    try:
        yield database_session
    except Exception as exc:
        _logger.error("[db] 세션 예외: %s\n%s", exc, traceback.format_exc())
        raise
    finally:
        database_session.close()


# ── Project DB management (per-project test data) ───────────────────────────

_project_engines: dict[str, Engine] = {}
_project_engines_lock = threading.Lock()

PROJECTS_DIR = app_settings.data_directory_path / "projects"


def _project_db_path(project_id: str) -> Path:
    return PROJECTS_DIR / project_id / "test_data.db"


def _get_or_create_project_engine(project_id: str) -> Engine:
    with _project_engines_lock:
        if project_id in _project_engines:
            return _project_engines[project_id]

    db_path = _project_db_path(project_id)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{db_path.as_posix()}"
    proj_engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(proj_engine, "connect", _apply_sqlite_pragmas)

    from app import models
    models.Base.metadata.create_all(bind=proj_engine)

    with _project_engines_lock:
        _project_engines[project_id] = proj_engine
    return proj_engine


def get_project_database_session(project_id: str) -> Iterator[Session]:
    proj_engine = _get_or_create_project_engine(project_id)
    proj_session_factory = sessionmaker(
        bind=proj_engine,
        autocommit=False,
        autoflush=False,
        class_=Session,
    )
    database_session = proj_session_factory()
    try:
        yield database_session
    except Exception as exc:
        _logger.error("[db] 프로젝트 세션 예외  project_id=%s: %s\n%s",
                      project_id, exc, traceback.format_exc())
        raise
    finally:
        database_session.close()


def attach_project_db(main_session: Session, project_id: str, alias: str | None = None) -> str:
    """ATTACH a project DB to the main session for cross-project queries.
    Returns the schema alias used (e.g. 'prj_HRK9000A')."""
    schema_alias = alias or f"prj_{project_id.replace('-', '_')}"
    db_path = _project_db_path(project_id)
    if not db_path.exists():
        _get_or_create_project_engine(project_id)
    main_session.execute(
        text(f"ATTACH DATABASE '{db_path.as_posix()}' AS \"{schema_alias}\"")
    )
    return schema_alias


def detach_project_db(main_session: Session, alias: str) -> None:
    main_session.execute(text(f'DETACH DATABASE "{alias}"'))


def list_project_ids() -> list[str]:
    if not PROJECTS_DIR.exists():
        return []
    return sorted(
        d.name for d in PROJECTS_DIR.iterdir()
        if d.is_dir() and (d / "test_data.db").exists()
    )


def truncate_application_data() -> None:
    """QC 전용: ORM 테이블의 모든 행을 삭제하고 sqlite_sequence를 비운다."""
    from app import auth
    from app import models

    with auth.active_user_names_lock:
        auth.active_user_names.clear()

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        try:
            for table in reversed(list(models.Base.metadata.sorted_tables)):
                connection.execute(text(f'DELETE FROM "{table.name}"'))
        finally:
            connection.execute(text("PRAGMA foreign_keys=ON"))

    with engine.begin() as connection:
        sequence_table = connection.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence' LIMIT 1")
        ).fetchone()
        if sequence_table is not None:
            connection.execute(text("DELETE FROM sqlite_sequence"))


def initialize_database() -> None:
    from app import models

    try:
        _drop_legacy_tables()
        models.Base.metadata.create_all(bind=engine)
        _ensure_user_account_columns()
        _ensure_defect_columns()
        _ensure_product_test_project_id_columns()
        _ensure_product_test_project_id_indexes()
        _ensure_environment_compatibility_views()
        _logger.info("[db] DB 초기화 완료  url=%s", app_settings.sqlite_database_url)
    except Exception as exc:
        _logger.error("[db] DB 초기화 실패: %s\n%s", exc, traceback.format_exc())
        raise


def _drop_legacy_tables() -> None:
    legacy_tables = [
        "test_result",
        "form_submission",
        "dropdown_option",
        "ui_sample_profile",
    ]
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        try:
            for table_name in legacy_tables:
                connection.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
        finally:
            connection.execute(text("PRAGMA foreign_keys=ON"))


def _ensure_product_test_project_id_columns() -> None:
    """Add project_id TEXT column to existing ProductTest* tables that predate the multi-project schema."""
    tables = [
        "product_test_round",
        "product_test_target_unified",
        "product_test_environment_unified",
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
    with engine.begin() as connection:
        for table_name in tables:
            exists = connection.execute(
                text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t LIMIT 1"),
                {"t": table_name},
            ).fetchone()
            if exists is None:
                continue
            existing = {
                row[1] for row in connection.execute(text(f"PRAGMA table_info({table_name})"))
            }
            if "project_id" not in existing:
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN project_id TEXT")
                )


def _ensure_product_test_project_id_indexes() -> None:
    """CREATE INDEX IF NOT EXISTS for project_id on all ProductTest* tables."""
    index_defs = [
        ("ix_product_test_round_project_id",                 "product_test_round"),
        ("ix_product_test_target_unified_project_id",       "product_test_target_unified"),
        ("ix_product_test_environment_unified_project_id", "product_test_environment_unified"),
        ("ix_product_test_case_project_id",                  "product_test_case"),
        ("ix_product_test_procedure_project_id",             "product_test_procedure"),
        ("ix_product_test_run_project_id",                   "product_test_run"),
        ("ix_product_test_result_project_id",                "product_test_result"),
        ("ix_product_test_procedure_result_project_id",      "product_test_procedure_result"),
        ("ix_product_test_defect_project_id",                "product_test_defect"),
        ("ix_product_test_evidence_project_id",              "product_test_evidence"),
        ("ix_product_test_report_project_id",                "product_test_report"),
        ("ix_product_test_report_snapshot_project_id",       "product_test_report_snapshot"),
        ("ix_product_test_status_transition_project_id",     "product_test_status_transition"),
    ]
    with engine.begin() as connection:
        for index_name, table_name in index_defs:
            connection.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS {index_name}"
                    f" ON {table_name} (project_id)"
                )
            )


def _ensure_defect_columns() -> None:
    """product_test_defect 에 expected_resolution_date 컬럼 추가 (신규 필드)."""
    with engine.begin() as connection:
        existing = {
            row[1] for row in connection.execute(text("PRAGMA table_info(product_test_defect)"))
        }
        if "expected_resolution_date" not in existing:
            connection.execute(
                text("ALTER TABLE product_test_defect ADD COLUMN expected_resolution_date TEXT")
            )


def _ensure_user_account_columns() -> None:
    expected_columns = {
        "display_name": "TEXT",
        "phone_number": "TEXT",
        "company_name": "TEXT",
        "department_name": "TEXT",
        "internal_title": "TEXT",
        "is_approved": "INTEGER DEFAULT 1",
    }
    with engine.begin() as connection:
        existing_column_names = {
            row[1] for row in connection.execute(text("PRAGMA table_info(user_account)"))
        }
        for column_name, column_type in expected_columns.items():
            if column_name in existing_column_names:
                continue
            connection.execute(
                text(f"ALTER TABLE user_account ADD COLUMN {column_name} {column_type}")
            )


def _ensure_environment_compatibility_views() -> None:
    with engine.begin() as connection:
        unified_exists = connection.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='product_test_environment_unified' LIMIT 1")
        ).fetchone()
        if unified_exists is None:
            return
        connection.execute(text('DROP VIEW IF EXISTS product_test_environment'))
        connection.execute(text('DROP VIEW IF EXISTS product_test_environment_definition'))
        connection.execute(text("""
            CREATE VIEW product_test_environment AS
            SELECT
                product_test_environment_id,
                CASE
                    WHEN product_test_environment_id LIKE 'CONFIG-%'
                        THEN 'CONFIG_DEF-' || SUBSTR(product_test_environment_id, LENGTH('CONFIG-') + 1)
                    ELSE product_test_environment_id
                END AS product_test_environment_definition_id,
                product_test_environment_name,
                test_computer_name,
                operating_system_version,
                test_tool_version,
                network_type,
                power_voltage,
                power_frequency,
                power_connector_type,
                captured_at,
                product_test_environment_status,
                created_at,
                created_by,
                updated_at,
                updated_by,
                remark,
                project_id
            FROM product_test_environment_unified
        """))
        connection.execute(text("""
            CREATE VIEW product_test_environment_definition AS
            SELECT
                CASE
                    WHEN product_test_environment_id LIKE 'CONFIG-%'
                        THEN 'CONFIG_DEF-' || SUBSTR(product_test_environment_id, LENGTH('CONFIG-') + 1)
                    ELSE product_test_environment_id
                END AS product_test_environment_definition_id,
                product_test_environment_name AS product_test_environment_definition_name,
                test_country,
                test_city,
                test_company,
                test_building,
                test_floor,
                test_room,
                network_type,
                test_computer_name,
                operating_system_version,
                test_tool_name,
                test_tool_version,
                power_voltage,
                power_frequency,
                power_connector_type,
                power_condition,
                product_test_environment_status AS product_test_environment_definition_status,
                created_at,
                created_by,
                updated_at,
                updated_by,
                remark,
                project_id
            FROM product_test_environment_unified
        """))
