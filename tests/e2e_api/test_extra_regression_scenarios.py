"""추가 회귀 시나리오: 인증·일반 테스터 화면·런 취소·결함 반려·관리자 마스터 데이터·리포트 반려."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

RELEASE_ID = "SQA_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1"
TARGET_ID = "SQA_PRODUCT_TEST_TARGET_ID-MERCUSYS_MR30G-SN001"
ENV_ID = "SQA_PRODUCT_TEST_ENVIRONMENT_ID-HUVITZ-ANYANG-CONNECTIVITY_ROOM-20260504-001"
REPORT_ID = "SQA_PRODUCT_TEST_REPORT_ID-SQA_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1-FULL-001"
DEFECT_OPENED = "SQA_PRODUCT_TEST_DEFECT_ID-20260504-0002"


def _cookies(role: str, phone: str = "") -> dict[str, str]:
    return {"role_name": role, "phone_number": phone}


def test_regression_join_page_and_logout(client: TestClient) -> None:
    join = client.get("/join")
    assert join.status_code == 200
    out = client.post("/logout", follow_redirects=False)
    assert out.status_code == 303
    assert "/login" in (out.headers.get("location") or "")


def test_regression_tester_login_dashboard_logout(client: TestClient, user_account_factory: Any) -> None:
    factory, roles = user_account_factory
    phone = "01060001111"
    factory(phone_number=phone, password="pw1", role_name=roles["ROLE_TESTER"])
    login = client.post("/login", data={"phone_number": phone, "password": "pw1"}, follow_redirects=False)
    assert login.status_code == 303
    dash = client.get("/user")
    assert dash.status_code == 200
    lo = client.post("/logout", follow_redirects=False)
    assert lo.status_code == 303
    login_page = client.get("/login")
    assert login_page.status_code == 200


def test_regression_admin_role_get_user_redirects_to_admin(client: TestClient) -> None:
    res = client.get("/user", cookies=_cookies("master_admin"), follow_redirects=False)
    assert res.status_code == 303
    assert "/admin" in (res.headers.get("location") or "")


def test_regression_seeded_start_run_then_cancel(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    start = client.post(
        "/tester/product-test-runs/start",
        cookies=_cookies("tester"),
        data={
            "product_test_release_id": RELEASE_ID,
            "product_test_target_id": TARGET_ID,
            "product_test_environment_id": ENV_ID,
        },
        follow_redirects=False,
    )
    assert start.status_code == 303
    loc = start.headers["location"]
    run_id = loc.split("/tester/product-test-runs/")[1].split("?")[0]
    cancel = client.post(
        f"/tester/product-test-runs/{run_id}/cancel",
        cookies=_cookies("tester"),
        data={"transition_reason": "regression_cancel_smoke"},
        follow_redirects=False,
    )
    assert cancel.status_code == 303


def test_regression_seeded_defect_reject_from_opened(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    res = client.post(
        f"/tester/product-test-defects/{DEFECT_OPENED}/reject",
        cookies=_cookies("tester"),
        data={
            "rejection_reason": "not_a_defect",
            "transition_reason": "regression_reject_e2e",
        },
        follow_redirects=False,
    )
    assert res.status_code == 303


def test_regression_admin_product_test_releases_page(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    page = client.get("/admin/product-test-releases", cookies=_cookies("master_admin"))
    assert page.status_code == 200
    assert RELEASE_ID in page.text


def test_regression_admin_product_test_cases_page(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    page = client.get("/admin/product-test-cases", cookies=_cookies("master_admin"))
    assert page.status_code == 200
    assert "SQA_PRODUCT_TEST_CASE_ID" in page.text or "WIFI" in page.text.upper()


def test_regression_admin_report_snapshots_index(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    page = client.get("/admin/product-test-report-snapshots", cookies=_cookies("master_admin"))
    assert page.status_code == 200


def test_regression_admin_reject_report_with_reason(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    res = client.post(
        f"/admin/product-test-reports/{REPORT_ID}/reject",
        cookies=_cookies("master_admin"),
        data={"rejection_reason": "regression_sample_reject_reason"},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert "message=" in (res.headers.get("location") or "")


def test_regression_export_append_forbidden_for_tester(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    res = client.post(
        "/admin/export/xlsx/append",
        cookies=_cookies("tester"),
        data={"excel_file_path": "nope.xlsx", "sheet_name": "Sheet1"},
    )
    assert res.status_code == 403
