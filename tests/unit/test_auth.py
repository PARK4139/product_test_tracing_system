from __future__ import annotations

import pytest
from fastapi import HTTPException, status

from app.auth import ROLE_ADMIN, ROLE_TESTER, ensure_role_allowed


def test_ensure_role_allowed_ok() -> None:
    ensure_role_allowed(ROLE_TESTER, {ROLE_TESTER, ROLE_ADMIN})


def test_ensure_role_allowed_forbidden() -> None:
    with pytest.raises(HTTPException) as exc_info:
        ensure_role_allowed(ROLE_TESTER, {ROLE_ADMIN})
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
