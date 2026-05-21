from __future__ import annotations

import pytest

from app.services.product_test_run_service import build_product_code, get_product_test_identifier_client_rules


def test_build_product_code_normalizes() -> None:
    assert build_product_code("Huvitz", "HRK-9000A") == "HUVITZ_HRK_9000A"


def test_build_product_code_rejects_empty() -> None:
    with pytest.raises(ValueError, match="required"):
        build_product_code("", "X")


def test_get_product_test_identifier_client_rules_keys() -> None:
    rules = get_product_test_identifier_client_rules()
    assert "product_test_release_id" in rules
    assert rules["product_test_release_id"].startswith("^")
