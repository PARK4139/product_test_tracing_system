from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import FormSubmission, TestResult


ALLOWED_COMPANY_NAMES = {
    "컨포커스",
    "윌템스_검안기",
    "윌템스_덴탈",
    "사이언스테라",
    "JHT",
    "윌템스",
    "컨포커스-호롭터",
}


def cleanup_invalid_company_data(database_session: Session) -> dict[str, int]:
    """
    Delete all TestResult rows whose 업체명(key_1) is not in the allowed list,
    then delete orphan FormSubmission rows that have zero remaining TestResult children.

    Notes:
    - This preserves any valid rows (including form_sample_* if 업체명이 허용 리스트에 있으면 유지).
    - 업체명이 NULL/빈문자열인 row도 삭제 대상.
    """
    # collect invalid row ids
    invalid_rows = database_session.scalars(
        select(TestResult.id).where(
            (TestResult.key_1.is_(None))
            | (TestResult.key_1 == "")
            | (TestResult.key_1.not_in(sorted(ALLOWED_COMPANY_NAMES)))
        )
    ).all()
    invalid_ids = sorted({int(x) for x in invalid_rows if int(x) > 0})

    deleted_test_rows = 0
    if invalid_ids:
        result = database_session.execute(delete(TestResult).where(TestResult.id.in_(invalid_ids)))
        deleted_test_rows = int(result.rowcount or 0)
        database_session.commit()

    # delete orphan submissions (no child rows)
    # (minimal approach: scan all FormSubmission IDs and count children)
    submissions = database_session.scalars(select(FormSubmission.submission_id)).all()
    deleted_submissions = 0
    for sid in submissions:
        sub_id = (sid or "").strip()
        if not sub_id:
            continue
        child_count = database_session.scalar(
            select(TestResult.id).where(TestResult.form_submission_id == sub_id).limit(1)
        )
        if child_count is None:
            fs = database_session.get(FormSubmission, sub_id)
            if fs is not None:
                database_session.delete(fs)
                deleted_submissions += 1
    if deleted_submissions:
        database_session.commit()

    return {
        "deleted_test_result_rows": deleted_test_rows,
        "deleted_orphan_form_submissions": deleted_submissions,
    }

