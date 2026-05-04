from threading import Lock
from typing import Annotated

from fastapi import Header, HTTPException, Request, status


ROLE_TESTER = "tester"
ROLE_ADMIN = "admin"
ROLE_MASTER_ADMIN = "master_admin"
MAX_ACTIVE_USERS = 999
active_user_names: set[str] = set()
active_user_names_lock = Lock()


def get_current_role_name(
    request: Request,
    x_user_role: Annotated[str | None, Header()] = None,
) -> str:
    cookie_role_name = request.cookies.get("role_name")
    if cookie_role_name:
        return cookie_role_name
    if x_user_role is None:
        return ROLE_TESTER
    return x_user_role


def ensure_role_allowed(current_role_name: str, allowed_role_names: set[str]) -> None:
    if current_role_name not in allowed_role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This role is not allowed for this action.",
        )


def ensure_active_user_limit(user_name: str) -> None:
    normalized_user_name = user_name.strip().lower()
    with active_user_names_lock:
        if normalized_user_name in active_user_names:
            return None
        if len(active_user_names) >= MAX_ACTIVE_USERS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Active user limit reached (max 999). Please try again later.",
            )
        active_user_names.add(normalized_user_name)
