"""Submission 단위 상태 (form_submission) — TestResult.submission_id와 연동."""

from __future__ import annotations

import secrets

from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import Session

from app.models import FormSubmission, TestResult, get_utc_now_datetime

STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_APPROVED = "approved"


def generate_new_submission_id() -> str:
    return f"sub_{secrets.token_urlsafe(18).replace('-', 'x')}"


def create_form_submission(
    database_session: Session,
    created_by_phone: str,
) -> FormSubmission:
    phone = (created_by_phone or "").strip()
    row = FormSubmission(
        submission_id=generate_new_submission_id(),
        status=STATUS_DRAFT,
        created_by_phone=phone or None,
    )
    database_session.add(row)
    database_session.commit()
    database_session.refresh(row)
    return row


def get_form_submission(
    database_session: Session, submission_id: str
) -> FormSubmission | None:
    if not (submission_id or "").strip():
        return None
    return database_session.get(FormSubmission, submission_id.strip())


def _normalize_phone(phone: str) -> str:
    return (phone or "").strip()


def assert_tester_may_write_submission(
    database_session: Session,
    submission_id: str | None,
    tester_phone: str,
) -> None:
    """새/수정 row 저장: 유효한 draft 제출이 있어야 함."""
    sid = (submission_id or "").strip()
    if not sid:
        raise ValueError("먼저 '시험(제출) 시작'으로 submission을 생성한 뒤 입력해 주세요.")

    fs = database_session.get(FormSubmission, sid)
    if fs is None:
        raise ValueError("유효하지 않은 submission_id 입니다. 시험을 다시 시작해 주세요.")
    if fs.status != STATUS_DRAFT:
        raise ValueError("이미 제출 완료되었거나 승인된 제출 건은 수정할 수 없습니다.")
    phone = _normalize_phone(tester_phone)
    if phone and fs.created_by_phone and fs.created_by_phone != phone:
        raise ValueError("다른 사용자의 제출 건입니다.")


def assert_row_belongs_to_draft_submission(
    database_session: Session, test_result_id: int, submission_id: str | None, tester_phone: str
) -> None:
    """low/high 타이머·삭제 등 기존 행 작업."""
    if not (submission_id or "").strip():
        return
    assert_tester_may_write_submission(
        database_session, submission_id=submission_id, tester_phone=tester_phone
    )
    tr = database_session.get(TestResult, test_result_id)
    if tr is not None and (tr.submission_id or "").strip() != (submission_id or "").strip():
        raise ValueError("행이 현재 submission과 일치하지 않습니다.")


def list_submissions_for_admin(
    database_session: Session, limit: int = 200
) -> list[FormSubmission]:
    rows = database_session.scalars(
        select(FormSubmission)
        .where(FormSubmission.status != STATUS_APPROVED)
        .order_by(FormSubmission.created_at.desc())
        .limit(limit)
    )
    return list(rows)


def count_rows_by_submission_ids(
    database_session: Session, submission_ids: list[str]
) -> dict[str, int]:
    """한 번의 집계로 submission_id별 test_result 행 수를 구한다."""
    if not submission_ids:
        return {}
    normalized = sorted({(s or "").strip() for s in submission_ids if (s or "").strip()})
    if not normalized:
        return {}
    result_rows = database_session.execute(
        select(TestResult.form_submission_id, func.count())
        .where(TestResult.form_submission_id.in_(normalized))
        .group_by(TestResult.form_submission_id)
    ).all()
    return {str(sid or ""): int(n) for sid, n in result_rows if sid}


def count_reviewed_rows_by_submission_ids(
    database_session: Session, submission_ids: list[str]
) -> dict[str, int]:
    """submission_id별 is_reviewed True 인 TestResult 행 수."""
    if not submission_ids:
        return {}
    normalized = sorted({(s or "").strip() for s in submission_ids if (s or "").strip()})
    if not normalized:
        return {}
    result_rows = database_session.execute(
        select(TestResult.form_submission_id, func.count())
        .where(
            TestResult.form_submission_id.in_(normalized),
            TestResult.is_reviewed.is_(True),
        )
        .group_by(TestResult.form_submission_id)
    ).all()
    return {str(sid or ""): int(n) for sid, n in result_rows if sid}


def list_submission_summaries_for_admin(
    database_session: Session, limit: int = 200
) -> list[dict]:
    """FormSubmission 추적: 행 수·검토 완료 행 수 포함(상태 전체, 최신순)."""
    rows = database_session.scalars(
        select(FormSubmission)
        .order_by(FormSubmission.created_at.desc())
        .limit(limit)
    )
    subs = list(rows)
    if not subs:
        return []
    id_list = [s.submission_id for s in subs]
    total_map = count_rows_by_submission_ids(database_session, id_list)
    reviewed_map = count_reviewed_rows_by_submission_ids(database_session, id_list)
    return [
        {
            "submission": s,
            "row_count": int(total_map.get(s.submission_id, 0)),
            "reviewed_row_count": int(reviewed_map.get(s.submission_id, 0)),
        }
        for s in subs
    ]


def count_test_rows_for_submission(
    database_session: Session, submission_id: str
) -> int:
    n = database_session.scalar(
        select(func.count()).select_from(TestResult).where(TestResult.form_submission_id == submission_id)
    )
    return int(n or 0)


def submit_submission(database_session: Session, submission_id: str) -> FormSubmission:
    norm = (submission_id or "").strip()
    if not norm:
        raise ValueError("submission_id is required.")
    fs = database_session.get(FormSubmission, norm)
    if fs is None:
        raise LookupError("Submission not found.")
    if fs.status != STATUS_DRAFT:
        raise ValueError("제출할 수 있는 상태가 아닙니다 (draft만 가능).")

    n = count_test_rows_for_submission(database_session=database_session, submission_id=fs.submission_id)
    if n < 1:
        raise ValueError("제출하려면 submission에 시험 행이 1행 이상 있어야 합니다.")

    now = get_utc_now_datetime()
    fs.status = STATUS_SUBMITTED
    fs.submitted_at = now
    database_session.commit()
    database_session.refresh(fs)
    return fs


def approve_submission(
    database_session: Session, submission_id: str
) -> FormSubmission:
    norm = (submission_id or "").strip()
    if not norm:
        raise ValueError("form_submission_id is required.")
    fs = database_session.get(FormSubmission, norm)
    if fs is None:
        raise LookupError("Submission not found.")
    if fs.status == STATUS_APPROVED:
        return fs
    if fs.status == STATUS_DRAFT:
        raise ValueError("승인 전에 먼저 제출 완료(submitted) 상태가 되어야 합니다.")
    if fs.status != STATUS_SUBMITTED:
        raise ValueError("승인할 수 있는 상태가 아닙니다 (submitted만 가능).")

    n = count_test_rows_for_submission(
        database_session=database_session, submission_id=fs.submission_id
    )
    if n < 1:
        raise ValueError("승인하려면 submission에 시험 행이 1행 이상 있어야 합니다.")

    now = get_utc_now_datetime()
    fs.status = STATUS_APPROVED
    fs.decided_at = now
    fs.rejection_reason = None

    database_session.execute(
        update(TestResult)
        .where(TestResult.form_submission_id == fs.submission_id)
        .values(is_reviewed=True)
    )
    database_session.commit()
    database_session.refresh(fs)
    return fs


def delete_submission_and_rows(database_session: Session, submission_id: str) -> None:
    """ADMIN DELETION = REJECTION. approved는 삭제 불가."""
    norm = (submission_id or "").strip()
    if not norm:
        raise ValueError("form_submission_id is required.")
    fs = database_session.get(FormSubmission, norm)
    if fs is None:
        raise LookupError("Submission not found.")
    if fs.status == STATUS_APPROVED:
        raise ValueError("승인된 제출 건은 삭제할 수 없습니다.")

    database_session.execute(
        TestResult.__table__.delete().where(TestResult.form_submission_id == fs.submission_id)
    )
    database_session.delete(fs)
    database_session.commit()


def backfill_form_submissions_from_test_results(database_session: Session) -> None:
    """기존 test_result.submission_id에 대해 form_submission 행이 없으면 삽입 (손실 없음)."""
    sub_ids = database_session.scalars(
        select(TestResult.submission_id)
        .where(
            and_(
                TestResult.submission_id.is_not(None),
                TestResult.submission_id != "",
            )
        )
        .distinct()
    )
    for sid in sub_ids:
        if not sid or not str(sid).strip():
            continue
        s = str(sid).strip()
        existing = database_session.get(FormSubmission, s)
        if existing is not None:
            continue
        is_rev = database_session.scalars(
            select(TestResult.is_reviewed).where(TestResult.submission_id == s)
        ).all()
        all_approved = bool(is_rev) and all(bool(x) for x in is_rev)
        fs = FormSubmission(
            submission_id=s,
            status=STATUS_APPROVED if all_approved else STATUS_DRAFT,
            created_by_phone=None,
        )
        if all_approved:
            fs.decided_at = get_utc_now_datetime()
        database_session.add(fs)
    database_session.commit()
