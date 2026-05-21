from __future__ import annotations

import pytest

from app.config import parse_config_bool


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        (None, True, True),
        (None, False, False),
        ("true", False, True),
        ("FALSE", True, False),
        ("1", False, True),
        ("0", True, False),
        ("yes", False, True),
        ("no", True, False),
        ("maybe", True, True),
        ("maybe", False, False),
    ],
)
def test_parse_config_bool(value: object, default: bool, expected: bool) -> None:
    assert parse_config_bool(value, default) is expected
