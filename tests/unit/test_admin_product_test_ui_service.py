from __future__ import annotations

from app.services.admin_product_test_ui_service import (
    get_first_blocking_prerequisite_field,
    list_product_test_id_candidates,
    validate_product_test_identifier_values,
)


def test_list_round_id_candidates() -> None:
    candidates = list_product_test_id_candidates(
        form_action="/admin",
        field_name="test_round_id",
        values={"upstream_release_id": "HRK_9000A-1.0.0", "release_stage": "RC"},
        datalist_hints=None,
    )
    assert "SQA_PRODUCT_TEST_RELEASE_ID-HRK_9000A-1.0.0-RC1" in candidates


def test_first_blocking_upstream_missing() -> None:
    blocking = get_first_blocking_prerequisite_field(
        form_action="/admin",
        target_field_name="test_round_id",
        values={"upstream_release_system": "Huvitz Software Release System"},
    )
    assert blocking == "upstream_release_id"


def test_validate_identifiers_skips_empty_values() -> None:
    assert validate_product_test_identifier_values({"test_round_id": ""}) == []
