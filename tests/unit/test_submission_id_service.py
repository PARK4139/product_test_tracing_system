from __future__ import annotations

import pytest

from app.services.submission_id_service import normalize_company_name, normalize_id_segment


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", "no_company"),
        ("   ", "no_company"),
        ("ACME Corp", "ACMECorp"),
        ("가나다", "가나다"),
        ("A_B", "AB"),
    ],
    ids=["PT-UT-001-empty", "PT-UT-001-ws", "PT-UT-001-spaces", "PT-UT-001-ko", "PT-UT-001-underscore"],
)
def test_normalize_company_name(value: str, expected: str) -> None:
    assert normalize_company_name(value) == expected


@pytest.mark.parametrize(
    ("value", "fallback", "expected"),
    [
        ("", "fb", "fb"),
        ("  x  ", "fb", "x"),
        ("A_B", "fb", "AB"),
    ],
)
def test_normalize_id_segment(value: str, fallback: str, expected: str) -> None:
    assert normalize_id_segment(value, fallback) == expected
