from __future__ import annotations

from sqlalchemy import inspect, select

from app.db import engine, session_local
from app.models import ProductTestRound


def test_round_model_schema() -> None:
    inspector = inspect(engine)

    table_names = set(inspector.get_table_names())
    assert "product_test_round" in table_names
    assert "product_test_release" not in table_names

    round_columns = {
        column["name"]: column for column in inspector.get_columns("product_test_round")
    }

    expected_round_columns = {
        "test_round_id",
        "test_round_name",
        "workday",
        "start_date",
        "end_date",
        "date_quality",
        "migration_status",
        "migration_note",
        "project_id",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
    }
    assert expected_round_columns.issubset(round_columns)


def test_round_is_orm_queryable() -> None:
    with session_local() as database_session:
        database_session.add(
            ProductTestRound(
                test_round_id="TEST_ROUND-SCHEMA_SYNC",
                test_round_name="Schema Sync Round",
                workday="5",
                start_date="2026-06-08",
                end_date="2026-06-12",
                date_quality="EXACT",
                migration_status="SEEDED",
                migration_note="schema sync test",
                project_id=None,
                created_at="2026-06-08T00:00:00Z",
                created_by="test",
                updated_at="2026-06-08T00:00:00Z",
                updated_by="test",
            )
        )
        database_session.commit()

        round_row = database_session.scalar(
            select(ProductTestRound).where(
                ProductTestRound.test_round_id == "TEST_ROUND-SCHEMA_SYNC"
            )
        )

    assert round_row is not None
    assert round_row.test_round_name == "Schema Sync Round"
