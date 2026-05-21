from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import app_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    app_settings.sqlite_database_url,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(database_api_connection, _connection_record) -> None:
    cursor = database_api_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    # 로컬 SQLite 읽기 위주 워크로드: mmap + 페이지 캐시 (파일 DB만; 메모리/테스트 DB는 제외)
    url = app_settings.sqlite_database_url
    if url.startswith("sqlite:///") and ":memory:" not in url:
        cursor.execute("PRAGMA mmap_size=67108864")  # 최대 64 MiB mmap
        cursor.execute("PRAGMA cache_size=-32768")  # 약 32 MiB 페이지 캐시
    cursor.close()


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
    finally:
        database_session.close()


def truncate_application_data() -> None:
    """QC 전용: ORM 테이블의 모든 행을 삭제하고 sqlite_sequence를 비운 뒤 UI·dropdown 기본값만 재주입한다."""
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

    _ensure_ui_sample_profiles()
    _ensure_default_dropdown_options()


def initialize_database() -> None:
    from app import models

    models.Base.metadata.create_all(bind=engine)
    _ensure_product_test_indexes()
    _migrate_product_test_status_values_to_uppercase()
    _ensure_user_account_columns()
    _migrate_test_result_to_four_key_if_needed()
    _ensure_test_result_columns()
    _ensure_test_result_submission_key_unique_constraint()
    _ensure_form_submission_columns()
    _backfill_form_submissions()
    _ensure_ui_sample_profiles()
    _ensure_default_dropdown_options()


def _migrate_product_test_status_values_to_uppercase() -> None:
    status_columns = (
        ("product_test_release", "product_test_release_status"),
        ("product_test_target_definition", "product_test_target_definition_status"),
        ("product_test_target", "product_test_target_status"),
        ("product_test_environment_definition", "product_test_environment_definition_status"),
        ("product_test_environment", "product_test_environment_status"),
        ("product_test_case", "product_test_case_status"),
        ("product_test_procedure", "product_test_procedure_status"),
        ("product_test_report", "product_test_report_status"),
    )
    with engine.begin() as connection:
        for table_name, column_name in status_columns:
            table_exists = connection.execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:table_name LIMIT 1"
                ),
                {"table_name": table_name},
            ).fetchone()
            if table_exists is None:
                continue
            connection.execute(
                text(
                    f"""
                    UPDATE {table_name}
                    SET {column_name} = UPPER(TRIM({column_name}))
                    WHERE {column_name} IS NOT NULL
                      AND TRIM({column_name}) <> ''
                      AND {column_name} != UPPER(TRIM({column_name}))
                    """
                )
            )

        transition_table_exists = connection.execute(
            text(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='product_test_status_transition' LIMIT 1"
            )
        ).fetchone()
        if transition_table_exists is not None:
            connection.execute(
                text(
                    """
                    UPDATE product_test_status_transition
                    SET from_status = UPPER(TRIM(from_status))
                    WHERE entity_type IN ('product_test_release', 'product_test_report')
                      AND from_status IS NOT NULL
                      AND TRIM(from_status) <> ''
                      AND from_status != UPPER(TRIM(from_status))
                    """
                )
            )
            connection.execute(
                text(
                    """
                    UPDATE product_test_status_transition
                    SET to_status = UPPER(TRIM(to_status))
                    WHERE entity_type IN ('product_test_release', 'product_test_report')
                      AND to_status IS NOT NULL
                      AND TRIM(to_status) <> ''
                      AND to_status != UPPER(TRIM(to_status))
                    """
                )
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


def _ensure_form_submission_columns() -> None:
    """form_submission: submission_id, status, created_at, submitted_at, decided_at (+ ORM extras)."""
    with engine.begin() as connection:
        table_exists = connection.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='form_submission' LIMIT 1")
        ).fetchone()
        if table_exists is None:
            return
        existing_column_names = {
            row[1] for row in connection.execute(text("PRAGMA table_info(form_submission)"))
        }
        if "submitted_at" not in existing_column_names:
            connection.execute(
                text("ALTER TABLE form_submission ADD COLUMN submitted_at DATETIME")
            )


def _ensure_test_result_columns() -> None:
    expected_columns = {
        "submission_id": "TEXT",
        "form_submission_id": "TEXT",
        "data_writer_name": "TEXT",
        "is_reviewed": "INTEGER DEFAULT 0",
        # Additional operational columns (nullable by default)
        "field_11": "TEXT",
        "field_12": "TEXT",
        "field_13": "TEXT",
        "field_14": "TEXT",
        "field_15": "TEXT",
        "field_16": "TEXT",
        "field_17": "TEXT",
        "field_18": "TEXT",
        "field_19": "TEXT",
        "field_20": "TEXT",
        "field_21": "TEXT",
    }
    with engine.begin() as connection:
        existing_column_names = {
            row[1] for row in connection.execute(text("PRAGMA table_info(test_result)"))
        }
        for column_name, column_type in expected_columns.items():
            if column_name in existing_column_names:
                continue
            connection.execute(
                text(f"ALTER TABLE test_result ADD COLUMN {column_name} {column_type}")
            )

        # Backfill: prefer existing submission_id -> form_submission_id
        existing_column_names = {
            row[1] for row in connection.execute(text("PRAGMA table_info(test_result)"))
        }
        if "form_submission_id" in existing_column_names and "submission_id" in existing_column_names:
            connection.execute(
                text(
                    """
                    UPDATE test_result
                    SET form_submission_id = submission_id
                    WHERE (form_submission_id IS NULL OR TRIM(form_submission_id) = '')
                      AND submission_id IS NOT NULL AND TRIM(submission_id) <> ''
                    """
                )
            )


def _ensure_test_result_submission_key_unique_constraint() -> None:
    with engine.begin() as connection:
        table_exists = connection.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='test_result' LIMIT 1")
        ).fetchone()
        if table_exists is None:
            return
        table_sql = str(table_exists[0] or "")
        if "uq_test_result_submission_key_quintet" in table_sql or (
            "UNIQUE (form_submission_id, key_1, key_2, key_3, key_4)" in table_sql
        ):
            return

        connection.execute(
            text(
                """
                CREATE TABLE test_result__new (
                    id INTEGER NOT NULL,
                    key_1 TEXT NOT NULL,
                    key_2 TEXT NOT NULL,
                    key_3 TEXT NOT NULL,
                    key_4 TEXT NOT NULL,
                    submission_id TEXT,
                    form_submission_id TEXT,
                    data_writer_name TEXT,
                    is_reviewed INTEGER NOT NULL DEFAULT 0,
                    field_01 TEXT,
                    field_02 TEXT,
                    field_03 TEXT,
                    field_04 TEXT,
                    field_05 TEXT,
                    field_06 TEXT,
                    field_07 TEXT,
                    field_08 TEXT,
                    field_09 TEXT,
                    field_10 TEXT,
                    field_11 TEXT,
                    field_12 TEXT,
                    field_13 TEXT,
                    field_14 TEXT,
                    field_15 TEXT,
                    field_16 TEXT,
                    field_17 TEXT,
                    field_18 TEXT,
                    field_19 TEXT,
                    field_20 TEXT,
                    field_21 TEXT,
                    low_test_started_at DATETIME,
                    low_test_ended_at DATETIME,
                    low_test_delta TEXT,
                    high_test_started_at DATETIME,
                    high_test_ended_at DATETIME,
                    high_test_delta TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    CONSTRAINT uq_test_result_submission_key_quintet
                        UNIQUE (form_submission_id, key_1, key_2, key_3, key_4)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO test_result__new (
                    id, key_1, key_2, key_3, key_4, submission_id, form_submission_id, data_writer_name, is_reviewed,
                    field_01, field_02, field_03, field_04, field_05, field_06, field_07, field_08,
                    field_09, field_10, field_11, field_12, field_13, field_14, field_15, field_16,
                    field_17, field_18, field_19, field_20, field_21,
                    low_test_started_at, low_test_ended_at, low_test_delta,
                    high_test_started_at, high_test_ended_at, high_test_delta,
                    created_at, updated_at
                )
                SELECT
                    id, key_1, key_2, key_3, key_4, submission_id, form_submission_id, data_writer_name, is_reviewed,
                    field_01, field_02, field_03, field_04, field_05, field_06, field_07, field_08,
                    field_09, field_10, field_11, field_12, field_13, field_14, field_15, field_16,
                    field_17, field_18, field_19, field_20, field_21,
                    low_test_started_at, low_test_ended_at, low_test_delta,
                    high_test_started_at, high_test_ended_at, high_test_delta,
                    created_at, updated_at
                FROM test_result
                """
            )
        )
        connection.execute(text("DROP TABLE test_result"))
        connection.execute(text("ALTER TABLE test_result__new RENAME TO test_result"))


def _migrate_test_result_to_four_key_if_needed() -> None:
    """MVP(3-key) DB → 운영(4-key) 스키마: key_1=업체명, key_2=양식, key_3=모델, key_4=공정."""
    with engine.begin() as connection:
        table_exists = connection.execute(
            text(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='test_result' LIMIT 1"
            )
        ).fetchone()
        if table_exists is None:
            return

        existing_column_names = {
            row[1] for row in connection.execute(text("PRAGMA table_info(test_result)"))
        }
        if "key_4" in existing_column_names:
            return

        connection.execute(
            text(
                """
                CREATE TABLE test_result__new (
                    id INTEGER NOT NULL,
                    key_1 TEXT NOT NULL,
                    key_2 TEXT NOT NULL,
                    key_3 TEXT NOT NULL,
                    key_4 TEXT NOT NULL,
                    submission_id TEXT,
                    data_writer_name TEXT,
                    is_reviewed INTEGER NOT NULL DEFAULT 0,
                    field_01 TEXT,
                    field_02 TEXT,
                    field_03 TEXT,
                    field_04 TEXT,
                    field_05 TEXT,
                    field_06 TEXT,
                    field_07 TEXT,
                    field_08 TEXT,
                    field_09 TEXT,
                    field_10 TEXT,
                    low_test_started_at TEXT,
                    low_test_ended_at TEXT,
                    low_test_delta TEXT,
                    high_test_started_at TEXT,
                    high_test_ended_at TEXT,
                    high_test_delta TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (id),
                    CONSTRAINT uq_test_result_key_quartet
                        UNIQUE (key_1, key_2, key_3, key_4)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO test_result__new (
                    id, key_1, key_2, key_3, key_4, submission_id, data_writer_name, is_reviewed,
                    field_01, field_02, field_03, field_04, field_05, field_06, field_07, field_08,
                    field_09, field_10,
                    low_test_started_at, low_test_ended_at, low_test_delta,
                    high_test_started_at, high_test_ended_at, high_test_delta,
                    created_at, updated_at
                )
                SELECT
                    id,
                    key_1,
                    COALESCE(NULLIF(TRIM(data_writer_name), ''), '미입력'),
                    key_2,
                    key_3,
                    submission_id,
                    COALESCE(NULLIF(TRIM(data_writer_name), ''), '미입력'),
                    is_reviewed,
                    field_01, field_02, field_03, field_04, field_05, field_06, field_07, field_08,
                    field_09, field_10,
                    low_test_started_at, low_test_ended_at, low_test_delta,
                    high_test_started_at, high_test_ended_at, high_test_delta,
                    created_at, updated_at
                FROM test_result
                """
            )
        )
        connection.execute(text("DROP TABLE test_result"))
        connection.execute(text("ALTER TABLE test_result__new RENAME TO test_result"))

        connection.execute(
            text("UPDATE dropdown_option SET field_name = 'key_4' WHERE field_name = 'key_3'")
        )
        connection.execute(
            text("UPDATE dropdown_option SET field_name = 'key_3' WHERE field_name = 'key_2'")
        )


def _backfill_form_submissions() -> None:
    from app.services.form_submission_service import backfill_form_submissions_from_test_results

    session = session_local()
    try:
        backfill_form_submissions_from_test_results(session)
    finally:
        session.close()


def _ensure_product_test_indexes() -> None:
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_product_test_run_product_test_release_id ON product_test_run (product_test_release_id)",
        "CREATE INDEX IF NOT EXISTS ix_product_test_result_product_test_run_id ON product_test_result (product_test_run_id)",
        "CREATE INDEX IF NOT EXISTS ix_product_test_procedure_result_product_test_result_id ON product_test_procedure_result (product_test_result_id)",
        "CREATE INDEX IF NOT EXISTS ix_product_test_evidence_product_test_result_id ON product_test_evidence (product_test_result_id)",
        "CREATE INDEX IF NOT EXISTS ix_product_test_evidence_product_test_procedure_result_id ON product_test_evidence (product_test_procedure_result_id)",
        "CREATE INDEX IF NOT EXISTS ix_product_test_defect_product_test_result_id ON product_test_defect (product_test_result_id)",
        "CREATE INDEX IF NOT EXISTS ix_product_test_report_product_test_release_id ON product_test_report (product_test_release_id)",
        "CREATE INDEX IF NOT EXISTS ix_product_test_report_snapshot_product_test_report_id ON product_test_report_snapshot (product_test_report_id)",
        "CREATE INDEX IF NOT EXISTS ix_product_test_report_snapshot_product_test_release_id ON product_test_report_snapshot (product_test_release_id)",
        "CREATE INDEX IF NOT EXISTS ix_product_test_report_snapshot_snapshot_type ON product_test_report_snapshot (snapshot_type)",
        "CREATE INDEX IF NOT EXISTS ix_product_test_status_transition_entity_type_entity_id ON product_test_status_transition (entity_type, entity_id)",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _ensure_ui_sample_profiles() -> None:
    from app.services.ui_sample_profile_service import ensure_default_ui_sample_profiles

    session = session_local()
    try:
        ensure_default_ui_sample_profiles(session)
    finally:
        session.close()


def _ensure_default_dropdown_options() -> None:
    from app.services.dropdown_option_service import ensure_default_dropdown_options

    session = session_local()
    try:
        ensure_default_dropdown_options(session)
    finally:
        session.close()
