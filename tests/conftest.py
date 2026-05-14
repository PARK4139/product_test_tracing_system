from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text

_fd, _TEST_DB_TEMP = tempfile.mkstemp(suffix=".sqlite3")
os.close(_fd)
TEST_SQLITE_FILE = Path(_TEST_DB_TEMP).resolve()
os.environ["PRODUCT_TEST_SQLITE_URL"] = f"sqlite:///{TEST_SQLITE_FILE.as_posix()}"
os.environ.setdefault("PRODUCT_TEST_QC_MODE", "false")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    try:
        if TEST_SQLITE_FILE.exists():
            TEST_SQLITE_FILE.unlink(missing_ok=True)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def reset_database() -> None:
    from app import models
    from app.db import engine, initialize_database

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
    models.Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
    initialize_database()
    yield


@pytest.fixture(autouse=True)
def _reset_auth_active_users() -> None:
    from app import auth

    auth.active_user_names.clear()
    yield
    auth.active_user_names.clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded_wifi_ap_db(client):
    from app.db import session_local
    from app.services.product_test_run_service import seed_product_test_wifi_ap_configuration_sample_data

    with session_local() as database_session:
        seed_product_test_wifi_ap_configuration_sample_data(database_session)
        database_session.commit()
    return client


@pytest.fixture
def user_account_factory():
    from app.auth import ROLE_ADMIN, ROLE_MASTER_ADMIN, ROLE_TESTER
    from app.db import session_local
    from app.models import UserAccount

    def _create(
        *,
        phone_number: str,
        password: str = "secret",
        role_name: str = ROLE_TESTER,
        is_approved: bool = True,
        user_name: str | None = None,
    ) -> None:
        with session_local() as database_session:
            database_session.add(
                UserAccount(
                    user_name=user_name or phone_number,
                    password_hash=password,
                    role_name=role_name,
                    phone_number=phone_number,
                    is_approved=is_approved,
                )
            )
            database_session.commit()

    return _create, {"ROLE_TESTER": ROLE_TESTER, "ROLE_ADMIN": ROLE_ADMIN, "ROLE_MASTER_ADMIN": ROLE_MASTER_ADMIN}
