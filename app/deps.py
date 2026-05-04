from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth import get_current_role_name
from app.db import get_database_session


database_session_dependency = Annotated[Session, Depends(get_database_session)]
current_role_name_dependency = Annotated[str, Depends(get_current_role_name)]
