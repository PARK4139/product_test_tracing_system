"""회귀 TC: /admin/api/product-test/fields/bulk-update
커버:
  - 일반 텍스트 필드 단건 업데이트
  - status 필드 업데이트
  - test_round_id PK cascade rename
  - 허용되지 않는 PK 필드 거부 (400)
  - 화이트리스트 외 필드 거부 (400)
  - 복수 업데이트 한 번에 (bulk)
  - 존재하지 않는 entity_id (400)
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

ADMIN_COOKIES = {"role_name": "admin"}

ROUND_ID = "SQA_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1"
RUN_ID   = "SQA_PRODUCT_TEST_RUN_ID-20260504-0001"
REPORT_ID = "SQA_PRODUCT_TEST_REPORT_ID-SQA_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1-FULL-001"


def _post(client: TestClient, updates: list[dict]) -> tuple[int, dict]:
    r = client.post(
        "/admin/api/product-test/fields/bulk-update",
        json={"updates": updates},
        cookies=ADMIN_COOKIES,
    )
    return r.status_code, r.json()


# ─────────────────────────────────────────────
# 1. 일반 텍스트 필드 업데이트
# ─────────────────────────────────────────────
def test_update_round_name(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    status, body = _post(client, [
        {"entity_type": "product_test_round", "entity_id": ROUND_ID,
         "field_name": "test_round_name", "value": "NEW NAME"},
    ])
    assert status == 200, body
    assert body["ok"] is True

    # DB에서 확인
    r = client.get("/admin", cookies=ADMIN_COOKIES)
    assert r.status_code == 200
    assert "NEW NAME" in r.text


# ─────────────────────────────────────────────
# 2. status 필드 업데이트
# ─────────────────────────────────────────────
def test_update_target_status(seeded_wifi_ap_db: TestClient) -> None:
    from app.db import session_local
    from app.models import ProductTestTargetUnified

    client = seeded_wifi_ap_db
    with session_local() as db:
        target = db.query(ProductTestTargetUnified).first()
        assert target is not None
        target_id = target.product_test_target_id

    status, body = _post(client, [
        {"entity_type": "product_test_target", "entity_id": target_id,
         "field_name": "product_test_target_status", "value": "inactive"},
    ])
    assert status == 200, body
    assert body["ok"] is True

    with session_local() as db:
        row = db.get(ProductTestTargetUnified, target_id)
        assert row.product_test_target_status == "inactive"


# ─────────────────────────────────────────────
# 3. test_round_id cascade rename
# ─────────────────────────────────────────────
def test_cascade_rename_test_round_id(seeded_wifi_ap_db: TestClient) -> None:
    from app.db import session_local
    from app.models import ProductTestRound, ProductTestRun

    client = seeded_wifi_ap_db
    new_id = "NEW_ROUND_ID_FOR_CASCADE_TEST"

    status, body = _post(client, [
        {"entity_type": "product_test_round", "entity_id": ROUND_ID,
         "field_name": "test_round_id", "value": new_id},
    ])
    assert status == 200, body
    assert body["ok"] is True

    with session_local() as db:
        # 기존 ID 사라짐
        assert db.get(ProductTestRound, ROUND_ID) is None
        # 새 ID 존재
        assert db.get(ProductTestRound, new_id) is not None
        # FK cascade 확인: run도 새 ID 참조
        run = db.get(ProductTestRun, RUN_ID)
        assert run is not None
        assert run.test_round_id == new_id


# ─────────────────────────────────────────────
# 4. 허용되지 않는 PK 필드 거부 (400)
# ─────────────────────────────────────────────
def test_reject_non_cascade_pk_field(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    status, body = _post(client, [
        {"entity_type": "product_test_report", "entity_id": REPORT_ID,
         "field_name": "product_test_report_id", "value": "anything"},
    ])
    assert status == 400, body
    assert body["ok"] is False
    assert "not allowed" in body["message"].lower()


# ─────────────────────────────────────────────
# 5. 화이트리스트 외 필드 거부 (400)
# ─────────────────────────────────────────────
def test_reject_unlisted_field(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    status, body = _post(client, [
        {"entity_type": "product_test_round", "entity_id": ROUND_ID,
         "field_name": "created_by", "value": "hacker"},
    ])
    assert status == 400, body
    assert body["ok"] is False


# ─────────────────────────────────────────────
# 6. 복수 업데이트 (bulk)
# ─────────────────────────────────────────────
def test_bulk_multiple_fields(seeded_wifi_ap_db: TestClient) -> None:
    from app.db import session_local
    from app.models import ProductTestTargetUnified

    client = seeded_wifi_ap_db
    with session_local() as db:
        target = db.query(ProductTestTargetUnified).first()
        target_id = target.product_test_target_id

    status, body = _post(client, [
        {"entity_type": "product_test_round", "entity_id": ROUND_ID,
         "field_name": "test_round_name", "value": "BULK A"},
        {"entity_type": "product_test_target", "entity_id": target_id,
         "field_name": "remark", "value": "BULK B"},
    ])
    assert status == 200, body
    assert body["ok"] is True

    with session_local() as db:
        rnd = db.get(__import__("app.models", fromlist=["ProductTestRound"]).ProductTestRound, ROUND_ID)
        assert rnd.test_round_name == "BULK A"
        tgt = db.get(ProductTestTargetUnified, target_id)
        assert tgt.remark == "BULK B"


# ─────────────────────────────────────────────
# 7. 존재하지 않는 entity_id → 400
# ─────────────────────────────────────────────
def test_reject_missing_entity(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    status, body = _post(client, [
        {"entity_type": "product_test_round", "entity_id": "NO_SUCH_ID",
         "field_name": "test_round_name", "value": "x"},
    ])
    assert status == 400, body
    assert body["ok"] is False


# ─────────────────────────────────────────────
# 8. 인증 없이 호출 → 401/403
# ─────────────────────────────────────────────
def test_bulk_update_requires_admin(seeded_wifi_ap_db: TestClient) -> None:
    client = seeded_wifi_ap_db
    r = client.post(
        "/admin/api/product-test/fields/bulk-update",
        json={"updates": [{"entity_type": "product_test_round", "entity_id": ROUND_ID,
                            "field_name": "test_round_name", "value": "x"}]},
        # 쿠키 없음
    )
    assert r.status_code in (401, 403), r.status_code
