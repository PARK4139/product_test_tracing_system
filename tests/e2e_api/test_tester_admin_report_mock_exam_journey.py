"""
모의시험 시나리오 (E2E): 테스터 관점 입력 후 관리자가 Test Report를 확인하는 흐름.

1) 테스터 계정으로 로그인
2) Product Test 런 목록·상세 확인 (배정된 시험 확인)
3) 프로시저 결과 저장 (시험지 제출에 해당)
4) 증적 첨부
5) 별도 Admin 클라이언트로 리포트 목록·상세·CSV·인쇄 화면 확인 (검토자 확인)
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app

RUN_ID = "SQA_PRODUCT_TEST_RUN_ID-20260504-0001"
RESULT_ID = "SQA_PRODUCT_TEST_RESULT_ID-20260504-0001"
PROC_RESULT_ID = "SQA_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0003"
REPORT_ID = "SQA_PRODUCT_TEST_REPORT_ID-SQA_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1-FULL-001"


def _admin_cookies() -> dict[str, str]:
    return {"role_name": "master_admin", "phone_number": ""}


def test_mock_exam_tester_workflow_then_admin_report_review(
    seeded_wifi_ap_db: TestClient,
    user_account_factory: Any,
) -> None:
    tester_client = seeded_wifi_ap_db
    factory, roles = user_account_factory
    phone = "01070001234"
    password = "mock-exam-pass"
    factory(phone_number=phone, password=password, role_name=roles["ROLE_TESTER"])

    login = tester_client.post(
        "/login",
        data={"phone_number": phone, "password": password},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert "/user" in (login.headers.get("location") or "")

    runs_page = tester_client.get("/tester/product-test-runs")
    assert runs_page.status_code == 200
    assert RUN_ID in runs_page.text

    detail = tester_client.get(f"/tester/product-test-runs/{RUN_ID}")
    assert detail.status_code == 200

    save_proc = tester_client.post(
        "/tester/product-test-procedure-results/save",
        data={
            "product_test_run_id": RUN_ID,
            "product_test_result_id": RESULT_ID,
            "product_test_procedure_result_id": PROC_RESULT_ID,
            "product_test_procedure_result_status": "passed",
            "actual_result": "모의시험: 채널 대역폭 점검 완료",
            "judgement_reason": "mock_exam_e2e",
            "remark": "",
        },
        follow_redirects=False,
    )
    assert save_proc.status_code == 303

    evidence = tester_client.post(
        "/tester/product-test-evidence/save",
        data={
            "product_test_run_id": RUN_ID,
            "product_test_result_id": RESULT_ID,
            "product_test_procedure_result_id": PROC_RESULT_ID,
            "product_test_defect_id": "",
            "product_test_evidence_type": "text",
            "file_path": "/evidence/mock_exam/e2e_note.txt",
            "remark": "mock_exam_attachment",
        },
        follow_redirects=False,
    )
    assert evidence.status_code == 303

    with TestClient(app) as admin_client:
        list_page = admin_client.get("/admin/product-test-reports", cookies=_admin_cookies())
        assert list_page.status_code == 200

        report_page = admin_client.get(
            f"/admin/product-test-reports/{REPORT_ID}",
            cookies=_admin_cookies(),
        )
        assert report_page.status_code == 200
        body_lower = report_page.text.lower()
        assert "wifi" in body_lower or "report" in body_lower or "ptrpt" in body_lower

        csv_export = admin_client.get(
            f"/admin/product-test-reports/{REPORT_ID}/export.csv",
            cookies=_admin_cookies(),
        )
        assert csv_export.status_code == 200
        assert len(csv_export.content) > 10

        print_page = admin_client.get(
            f"/admin/product-test-reports/{REPORT_ID}/print",
            cookies=_admin_cookies(),
        )
        assert print_page.status_code == 200
