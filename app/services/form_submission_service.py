from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FormSubmission, get_utc_now_datetime


def submit_submission(*, database_session: Session, submission_id: str) -> FormSubmission:
    row = database_session.scalar(
        select(FormSubmission).where(FormSubmission.submission_id == submission_id)
    )
    if row is None:
        raise LookupError("Submission not found.")
    if row.status != "draft":
        raise ValueError("Only draft submissions can be submitted.")
    row.status = "submitted"
    row.submitted_at = get_utc_now_datetime()
    row.updated_at = get_utc_now_datetime()
    database_session.commit()
    database_session.refresh(row)
    return row
