"""사용자 입장(페르소나)별 E2E 회귀 시나리오.

계획(역할 → 대표 여정):

- **방문자**: 루트에서 로그인 유도, 로그인·가입 화면 접근, 중복 가입 시도 시 오류.
- **가입 직후 테스터(미승인)**: `/join` 성공 후 동일 계정으로 로그인 시 승인 대기 메시지.
- **운영 관리자(master_admin)**: 대시보드·리포트 목록·엑셀보내기, 미승인 테스터 승인 처리.
- **일반 관리자(admin)**: 로그인 후 `/admin` 접근, `/user`는 관리자 홈으로 리다이렉트.
- **승인된 테스터**: 제품 시험 런·결함 상세·제출 초안 생성; 관리자 콘솔은 접근 불가.

`test.py`가 ``tests/e2e_api/test_*.py``를 자동 수집하므로 별도 등록은 필요 없다.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import session_local
from app.models import UserAccount

RELEASE_ID = "SQA_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1"
DEFECT_READ = "SQA_PRODUCT_TEST_DEFECT_ID-20260504-0001"


def _cookies(role: str, phone: str = "") -> dict[str, str]:
    return {"role_name": role, "phone_number": phone}


def _user_account_id_by_phone(phone: str) -> int:
    with session_local() as database_session:
        row = database_session.scalar(select(UserAccount).where(UserAccount.phone_number == phone))
        assert row is not None
        return int(row.id)


def test_persona_guest_root_redirects_to_login(client: TestClient) -> None:
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 303
    assert "/login" in (res.headers.get("location") or "")


def test_persona_guest_login_page_ok(client: TestClient) -> None:
    res = client.get("/login")
    assert res.status_code == 200


def test_persona_guest_duplicate_join_returns_400(client: TestClient) -> None:
    phone = "01050101010"
    form = {
        "company_name": "GuestDupCo",
        "display_name": "DupUser",
        "phone_number": phone,
        "password": "pw-dup-1",
    }
    first = client.post("/join", data=form)
    assert first.status_code == 200
    second = client.post("/join", data=form)
    assert second.status_code == 400
    body = second.content.decode("utf-8")
    assert "message_text" in body


def test_persona_pending_tester_cannot_login_until_approved(client: TestClient) -> None:
    phone = "01050202020"
    join = client.post(
        "/join",
        data={
            "company_name": "PendingCo",
            "display_name": "PendingUser",
            "phone_number": phone,
            "password": "pw-pending",
        },
    )
    assert join.status_code == 200
    assert "start_success_modal_flow" in join.text
    bad_login = client.post(
        "/login",
        data={"phone_number": phone, "password": "pw-pending"},
    )
    assert bad_login.status_code == 400
    assert "Tester" in bad_login.text


def test_persona_master_admin_approves_joined_tester_then_login_ok(client: TestClient) -> None:
    phone = "01050303030"
    join = client.post(
        "/join",
        data={
            "company_name": "ApproveCo",
            "display_name": "ApproveUser",
            "phone_number": phone,
            "password": "pw-approve",
        },
    )
    assert join.status_code == 200
    uid = _user_account_id_by_phone(phone)
    approve = client.post(
        "/admin/approve_tester_join",
        cookies=_cookies("master_admin"),
        data={"user_account_id": str(uid)},
    )
    assert approve.status_code == 200
    ok = client.post(
        "/login",
        data={"phone_number": phone, "password": "pw-approve"},
        follow_redirects=False,
    )
    assert ok.status_code == 303
    assert "/user" in (ok.headers.get("location") or "")


def test_persona_sub_admin_login_sees_admin_not_tester_dashboard(
    client: TestClient, user_account_factory: Any
) -> None:
    factory, roles = user_account_factory
    phone = "01050404040"
    factory(phone_number=phone, password="pw-admin", role_name=roles["ROLE_ADMIN"])
    login = client.post(
        "/login",
        data={"phone_number": phone, "password": "pw-admin"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert "/admin" in (login.headers.get("location") or "")
    admin_home = client.get("/admin")
    assert admin_home.status_code == 200
    user_as_admin = client.get("/user", follow_redirects=False)
    assert user_as_admin.status_code == 303
    assert "/admin" in (user_as_admin.headers.get("location") or "")


def test_persona_master_admin_home_reports_list_and_export_xlsx(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    home = client.get("/admin", cookies=_cookies("master_admin"))
    assert home.status_code == 200
    reports = client.get("/admin/product-test-reports", cookies=_cookies("master_admin"))
    assert reports.status_code == 200
    assert RELEASE_ID in reports.text
    xlsx = client.get("/admin/export/xlsx", cookies=_cookies("master_admin"))
    assert xlsx.status_code == 200
    assert "spreadsheetml" in (xlsx.headers.get("content-type") or "").lower()


def test_persona_tester_product_test_runs_and_defect_detail(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    listing = client.get("/tester/product-test-runs", cookies=_cookies("tester"))
    assert listing.status_code == 200
    defect_page = client.get(f"/tester/product-test-defects/{DEFECT_READ}", cookies=_cookies("tester"))
    assert defect_page.status_code == 200


def test_persona_tester_cannot_open_admin_console(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    res = client.get("/admin", cookies=_cookies("tester"), follow_redirects=False)
    assert res.status_code == 303
    assert "/login" in (res.headers.get("location") or "")


def test_persona_authenticated_tester_creates_submission_draft(
    client: TestClient, user_account_factory: Any
) -> None:
    factory, roles = user_account_factory
    phone = "01050505050"
    factory(phone_number=phone, password="pw-t", role_name=roles["ROLE_TESTER"])
    client.post(
        "/login",
        data={"phone_number": phone, "password": "pw-t"},
        follow_redirects=False,
    )
    created = client.post(
        "/submission/create",
        data={"company_name": "SubCo", "display_name": "SubWriter"},
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload.get("status") == "draft"
    assert "form_" in str(payload.get("form_submission_id") or "")
