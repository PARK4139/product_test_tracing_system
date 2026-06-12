"""
Playwright E2E conftest: live_server + DB reseed fixture

부모 conftest(tests/conftest.py)의 reset_database autouse fixture를
override해서 playwright 테스트마다 seeded DB를 사용하도록 한다.
"""
from __future__ import annotations

import os
import socket
import tempfile
import threading
import time
from collections.abc import Generator

import pytest
from sqlalchemy import text

# ── DB 경로 설정 (app 모듈 import 전에 설정해야 함) ─────────────────
_fd, _TMP_DB = tempfile.mkstemp(suffix=".playwright.db")
os.close(_fd)
os.environ["PRODUCT_TEST_SQLITE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ.setdefault("PRODUCT_TEST_QC_MODE", "false")

LIVE_SERVER_PORT = 18999
LIVE_SERVER_BASE = f"http://127.0.0.1:{LIVE_SERVER_PORT}"


def _boot_server() -> None:
    import uvicorn
    from app.main import app
    uvicorn.run(app, host="127.0.0.1", port=LIVE_SERVER_PORT, log_level="error")


# ── 부모 conftest reset_database override ────────────────────────────
# 부모 conftest의 autouse reset_database가 playwright DB를 매 테스트마다
# DROP하지 못하도록 no-op으로 override한다.
@pytest.fixture(autouse=True)
def reset_database():
    """playwright 테스트용 override: 테스트마다 seed 데이터 재주입."""
    from app import models
    from app.db import engine, initialize_database, session_local
    from app.services.product_test_run_service import (
        seed_product_test_wifi_ap_configuration_sample_data,
    )

    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
    models.Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
    initialize_database()
    with session_local() as db:
        seed_product_test_wifi_ap_configuration_sample_data(db)
        db.commit()
    yield


# ── session-scoped 서버 기동 ─────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def live_server() -> Generator[str, None, None]:
    from app import models
    from app.db import engine, initialize_database, session_local
    from app.services.product_test_run_service import (
        seed_product_test_wifi_ap_configuration_sample_data,
    )

    # 최초 1회 DB 초기화
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
    models.Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
    initialize_database()
    with session_local() as db:
        seed_product_test_wifi_ap_configuration_sample_data(db)
        db.commit()

    t = threading.Thread(target=_boot_server, daemon=True)
    t.start()

    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", LIVE_SERVER_PORT), timeout=0.5):
                break
        except OSError:
            time.sleep(0.2)
    else:
        pytest.fail("live_server: server startup timeout")

    yield LIVE_SERVER_BASE

    try:
        os.unlink(_TMP_DB)
    except OSError:
        pass
