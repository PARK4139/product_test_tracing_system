"""QC 전용 ``POST /admin/qc/db-truncate`` 회귀."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.models import ProductTestRelease


def _admin_cookies() -> dict[str, str]:
    return {"role_name": "master_admin", "phone_number": ""}


def test_qc_db_truncate_returns_403_when_qc_mode_off(client: TestClient) -> None:
    res = client.post("/admin/qc/db-truncate", cookies=_admin_cookies())
    assert res.status_code == 403


def test_qc_db_truncate_clears_data_when_qc_mode_on(
    monkeypatch: pytest.MonkeyPatch, seeded_wifi_ap_db: TestClient
) -> None:
    monkeypatch.setenv("PRODUCT_TEST_QC_MODE", "true")
    client = seeded_wifi_ap_db
    before = client.get("/admin/product-test-releases", cookies=_admin_cookies())
    assert before.status_code == 200
    assert "SQA_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G" in before.text

    res = client.post("/admin/qc/db-truncate", cookies=_admin_cookies())
    assert res.status_code == 200
    assert res.json().get("ok") is True

    after = client.get("/admin/product-test-releases", cookies=_admin_cookies())
    assert after.status_code == 200
    assert "SQA_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G" not in after.text

    from app.db import session_local

    with session_local() as database_session:
        count = database_session.scalar(select(func.count()).select_from(ProductTestRelease))
        assert count == 0
