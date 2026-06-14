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


def _purge_dummy_seed_data() -> None:
    """세션 종료 시 dummy_ 접두어 더미 데이터를 FK 역순으로 삭제한다."""
    from app.db import engine

    # 삭제 순서: 자식 테이블 → 부모 테이블 (FK 역순)
    stmts = [
        "DELETE FROM product_test_status_transition WHERE entity_id LIKE 'dummy_%'",
        "DELETE FROM product_test_evidence         WHERE product_test_run_id IN "
        "  (SELECT product_test_run_id FROM product_test_run WHERE test_round_id LIKE 'dummy_%')",
        "DELETE FROM product_test_procedure_result WHERE product_test_run_id IN "
        "  (SELECT product_test_run_id FROM product_test_run WHERE test_round_id LIKE 'dummy_%')",
        "DELETE FROM product_test_result           WHERE product_test_run_id IN "
        "  (SELECT product_test_run_id FROM product_test_run WHERE test_round_id LIKE 'dummy_%')",
        "DELETE FROM product_test_run              WHERE test_round_id        LIKE 'dummy_%'",
        "DELETE FROM product_test_report_snapshot  WHERE product_test_report_id LIKE 'dummy_%'",
        "DELETE FROM product_test_report           WHERE product_test_report_id LIKE 'dummy_%'",
        "DELETE FROM product_test_round            WHERE test_round_id        LIKE 'dummy_%'",
        "DELETE FROM product_test_target_unified   WHERE product_test_target_id LIKE 'dummy_%'",
    ]
    try:
        with engine.begin() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            for stmt in stmts:
                conn.execute(text(stmt))
            conn.execute(text("PRAGMA foreign_keys=ON"))
    except Exception:
        pass  # 임시 DB 삭제 직전이므로 오류 무시


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

    # 마지막 TC 완료 후 dummy_ 더미 데이터 삭제
    _purge_dummy_seed_data()

    try:
        os.unlink(_TMP_DB)
    except OSError:
        pass
