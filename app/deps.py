from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_role_name
from app.db import get_database_session, get_project_database_session


database_session_dependency = Annotated[Session, Depends(get_database_session)]
current_role_name_dependency = Annotated[str, Depends(get_current_role_name)]


def _get_project_session_from_query(
    project_id: str = Query(..., alias="project_id"),
) -> Iterator[Session]:
    yield from get_project_database_session(project_id)


project_database_session_dependency = Annotated[
    Session, Depends(_get_project_session_from_query)
]
