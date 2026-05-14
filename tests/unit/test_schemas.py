from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import LoginFormInput


def test_login_form_input_valid() -> None:
    payload = LoginFormInput(user_name="u1", password="p1")
    assert payload.user_name == "u1"


def test_test_result_partial_requires_keys() -> None:
    from app.schemas import TestResultPartialInput

    with pytest.raises(ValidationError):
        TestResultPartialInput.model_validate({"key_1": "a"})
