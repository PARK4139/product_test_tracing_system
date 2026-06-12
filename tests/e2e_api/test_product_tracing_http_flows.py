from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

RUN_ID_SEED = "SQA_PRODUCT_TEST_RUN_ID-20260504-0001"
RESULT_ID = "SQA_PRODUCT_TEST_RESULT_ID-20260504-0001"
PROC_RESULT_ID = "SQA_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0001"
DEFECT_ID = "SQA_PRODUCT_TEST_DEFECT_ID-20260504-0001"
RELEASE_ID = "SQA_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1"
TARGET_ID = "SQA_PRODUCT_TEST_TARGET_ID-MERCUSYS_MR30G-SN001"
ENV_ID = "SQA_PRODUCT_TEST_ENVIRONMENT_ID-HUVITZ-ANYANG-CONNECTIVITY_ROOM-20260504-001"
CASE_ID = "SQA_PRODUCT_TEST_CASE_ID-WIFI-AP_CONFIG-001"


def _cookies(role: str, phone: str = "") -> dict[str, str]:
    return {"role_name": role, "phone_number": phone}


def test_pt_e2e_001_login_bad_and_ok(client: TestClient, user_account_factory: Any) -> None:
    factory, roles = user_account_factory
    factory(
        phone_number="01099990001",
        password="correct",
        role_name=roles["ROLE_TESTER"],
    )
    bad = client.post("/login", data={"phone_number": "01099990001", "password": "wrong"})
    assert bad.status_code == 400
    ok = client.post("/login", data={"phone_number": "01099990001", "password": "correct"}, follow_redirects=False)
    assert ok.status_code == 303
    assert ok.headers.get("set-cookie", "").lower().find("role_name") >= 0


def test_pt_e2e_002_product_test_runs_list_and_detail(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    res = client.get("/tester/product-test-runs", cookies=_cookies("tester"))
    assert res.status_code == 200
    detail = client.get(f"/tester/product-test-runs/{RUN_ID_SEED}", cookies=_cookies("tester"))
    assert detail.status_code == 200


def test_pt_e2e_003_start_and_finish_run(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    start = client.post(
        "/tester/product-test-runs/start",
        cookies=_cookies("tester"),
        data={
            "test_round_id": RELEASE_ID,
            "product_test_target_id": TARGET_ID,
            "product_test_environment_id": ENV_ID,
        },
        follow_redirects=False,
    )
    assert start.status_code == 303
    location = start.headers["location"]
    assert "/tester/product-test-runs/" in location
    new_run_id = location.split("/tester/product-test-runs/")[1].split("?")[0]
    assert new_run_id.startswith("SQA_PRODUCT_TEST_RUN_ID-")
    fin = client.post(
        f"/tester/product-test-runs/{new_run_id}/finish",
        cookies=_cookies("tester"),
        data={"transition_reason": "e2e_finish"},
        follow_redirects=False,
    )
    assert fin.status_code == 303


def test_pt_e2e_004_save_procedure_result(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    res = client.post(
        "/tester/product-test-procedure-results/save",
        cookies=_cookies("tester"),
        data={
            "product_test_run_id": RUN_ID_SEED,
            "product_test_result_id": RESULT_ID,
            "product_test_procedure_result_id": PROC_RESULT_ID,
            "product_test_procedure_result_status": "passed",
            "actual_result": "e2e_ok",
            "judgement_reason": "",
            "remark": "",
        },
        follow_redirects=False,
    )
    assert res.status_code == 303


def test_pt_e2e_005_evidence_and_defect_detail(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    ev = client.post(
        "/tester/product-test-evidence/save",
        cookies=_cookies("tester"),
        data={
            "product_test_run_id": RUN_ID_SEED,
            "product_test_result_id": RESULT_ID,
            "product_test_procedure_result_id": PROC_RESULT_ID,
            "product_test_defect_id": "",
            "product_test_evidence_type": "log_file",
            "file_path": "/evidence/e2e/test.log",
            "remark": "e2e",
        },
        follow_redirects=False,
    )
    assert ev.status_code == 303
    page = client.get(f"/tester/product-test-defects/{DEFECT_ID}", cookies=_cookies("tester"))
    assert page.status_code == 200


def test_pt_e2e_006_defect_assign(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    res = client.post(
        f"/tester/product-test-defects/{DEFECT_ID}/assign",
        cookies=_cookies("tester"),
        data={"assigned_to": "dev_owner", "transition_reason": "e2e_assign"},
        follow_redirects=False,
    )
    assert res.status_code == 303


def test_pt_e2e_007_admin_and_export(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    dash = client.get("/admin", cookies=_cookies("master_admin"))
    assert dash.status_code == 200
    assert 'data-admin-tab-label="Round Trace"' in dash.text
    assert f'data-round-trace-url="/admin/product-test-rounds/{RELEASE_ID}/trace"' in dash.text
    assert 'data-admin-tab-label="Runs"' in dash.text
    assert RUN_ID_SEED in dash.text
    assert f'data-run-trace-url="/admin/product-test-runs/{RUN_ID_SEED}/trace"' in dash.text
    xlsx = client.get("/admin/export/xlsx", cookies=_cookies("master_admin"))
    assert xlsx.status_code == 200
    assert "spreadsheetml" in (xlsx.headers.get("content-type") or "").lower()
    forbidden = client.get("/admin/export/xlsx", cookies=_cookies("tester"))
    assert forbidden.status_code == 403


def test_admin_run_trace_ajax_panel(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    response = client.get(
        f"/admin/product-test-runs/{RUN_ID_SEED}/trace",
        cookies=_cookies("master_admin"),
        headers={
            "accept": "text/html",
            "x-requested-with": "XMLHttpRequest",
        },
    )
    assert response.status_code == 200
    assert f"Run Trace | {RUN_ID_SEED}" in response.text
    assert RESULT_ID in response.text
    redirect = client.get(
        f"/admin/product-test-runs/{RUN_ID_SEED}/trace",
        cookies=_cookies("master_admin"),
        follow_redirects=False,
    )
    assert redirect.status_code == 303


def test_admin_round_trace_ajax_panel(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    response = client.get(
        f"/admin/product-test-rounds/{RELEASE_ID}/trace",
        cookies=_cookies("master_admin"),
        headers={
            "accept": "text/html",
            "x-requested-with": "XMLHttpRequest",
        },
    )
    assert response.status_code == 200
    assert f"Round Trace | {RELEASE_ID}" in response.text
    assert RUN_ID_SEED in response.text
    redirect = client.get(
        f"/admin/product-test-rounds/{RELEASE_ID}/trace",
        cookies=_cookies("master_admin"),
        follow_redirects=False,
    )
    assert redirect.status_code == 200


def test_admin_product_test_ui_json_api(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    cookies = _cookies("master_admin")
    cfg = client.get("/admin/api/product-test/ui/client-config", cookies=cookies)
    assert cfg.status_code == 200
    payload = cfg.json()
    assert "id_rules" in payload and "write_order_plans" in payload
    cand = client.post(
        "/admin/api/product-test/ui/id-candidates",
        cookies=cookies,
        json={
            "form_action": "/admin",
            "field_name": "test_round_id",
            "values": {"upstream_release_id": "HRK_9000A-1.0.0", "release_stage": "RC"},
            "datalist_hints": {},
        },
    )
    assert cand.status_code == 200
    assert "SQA_PRODUCT_TEST_RELEASE_ID-HRK_9000A-1.0.0-RC1" in cand.json().get("candidates", [])


def test_pt_test_case_start_route(seeded_wifi_ap_db: TestClient) -> None:
    """PT-E2E-004 companion: start result HTTP route (seed DB already has a result)."""
    client = seeded_wifi_ap_db
    res = client.post(
        "/tester/product-test-results/start",
        cookies=_cookies("tester"),
        data={"product_test_run_id": RUN_ID_SEED, "product_test_case_id": CASE_ID},
        follow_redirects=False,
    )
    assert res.status_code == 303


def test_pt_e2e_defect_save(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    res = client.post(
        "/tester/product-test-defects/save",
        cookies=_cookies("tester"),
        data={
            "product_test_run_id": RUN_ID_SEED,
            "product_test_result_id": RESULT_ID,
            "product_test_procedure_result_id": PROC_RESULT_ID,
            "defect_title": "e2e defect",
            "defect_description": "desc",
            "defect_severity": "minor",
            "defect_priority": "low",
            "assigned_to": "",
            "remark": "",
        },
        follow_redirects=False,
    )
    assert res.status_code == 303


def test_pt_e2e_008_qc_mode_root_redirect(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("PRODUCT_TEST_QC_MODE", "true")
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers.get("location", "").endswith("/admin")
    login = client.get("/login", follow_redirects=False)
    assert login.status_code == 303
    assert login.headers.get("location", "").endswith("/admin")
    monkeypatch.setenv("PRODUCT_TEST_QC_MODE", "false")
