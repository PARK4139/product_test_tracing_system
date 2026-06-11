import re

from fastapi import APIRouter, Form, HTTPException, Request, status
from sqlalchemy import select

from app.deps import database_session_dependency
from app.models import FormSubmission
from app.services.form_submission_service import submit_submission
from app.services.submission_id_service import normalize_id_segment, today_yyyymmdd

submission_router = APIRouter(prefix="/submission", tags=["submission"])

_FORM_ID_RE = re.compile(r"^form_(.+?)_(.+?)_(\d{8})_(\d+)$")


def _generate_form_submission_id(database_session, company_name: str, display_name: str) -> str:
    normalized_company = normalize_id_segment(company_name, fallback="company")
    normalized_writer = normalize_id_segment(display_name, fallback="writer")
    date_text = today_yyyymmdd()
    prefix = f"form_{normalized_company}_{normalized_writer}_{date_text}_"
    existing = database_session.scalars(
        select(FormSubmission.submission_id).where(FormSubmission.submission_id.like(f"{prefix}%"))
    ).all()
    max_index = 0
    for sid in existing:
        m = _FORM_ID_RE.match(str(sid or "").strip())
        if not m:
            continue
        if m.group(1) != normalized_company or m.group(2) != normalized_writer or m.group(3) != date_text:
            continue
        try:
            idx = int(m.group(4))
        except ValueError:
            continue
        if idx > max_index:
            max_index = idx
    return f"{prefix}{max_index + 1}"


@submission_router.post("/create")
def create_submission(
    request: Request,
    database_session: database_session_dependency,
    company_name: str = Form(""),
    display_name: str = Form(""),
):
    submission_id = _generate_form_submission_id(
        database_session,
        company_name=company_name,
        display_name=display_name,
    )
    created_by_phone = (request.cookies.get("phone_number") or "").strip() or None
    row = FormSubmission(
        submission_id=submission_id,
        status="draft",
        created_by_phone=created_by_phone,
    )
    database_session.add(row)
    database_session.commit()
    database_session.refresh(row)
    return {"form_submission_id": row.submission_id, "status": row.status}


@submission_router.post("/submit")
def submit_existing_submission(
    database_session: database_session_dependency,
    form_submission_id: str = Form(""),
):
    target_id = (form_submission_id or "").strip()
    if not target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="form_submission_id is required",
        )
    try:
        fs = submit_submission(database_session=database_session, submission_id=target_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"form_submission_id": fs.submission_id, "status": fs.status}
