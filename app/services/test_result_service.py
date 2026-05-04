from datetime import datetime

from sqlalchemy import and_, delete, exists, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import FormSubmission, TestResult, get_utc_now_datetime
from app.schemas import TestResultPartialInput


PARTIAL_UPDATE_FIELD_NAMES = [
    "form_submission_id",
    "data_writer_name",
    "is_reviewed",
    "field_01",
    "field_02",
    "field_03",
    "field_04",
    "field_05",
    "field_06",
    "field_07",
    "field_08",
    "field_09",
    "field_10",
    "field_11",
    "field_12",
    "field_13",
    "field_14",
    "field_15",
    "field_16",
    "field_17",
    "field_18",
    "field_19",
    "field_20",
    "field_21",
    "low_test_started_at",
    "low_test_ended_at",
    "low_test_delta",
    "high_test_started_at",
    "high_test_ended_at",
    "high_test_delta",
]


def _strip_if_string(value):
    if isinstance(value, str):
        return value.strip()
    return value


def upsert_partial_test_result(
    database_session: Session,
    test_result_partial_input: TestResultPartialInput,
) -> TestResult:
    return _upsert_partial_test_result_internal(
        database_session=database_session,
        test_result_partial_input=test_result_partial_input,
        commit=True,
    )


def _upsert_partial_test_result_internal(
    database_session: Session,
    test_result_partial_input: TestResultPartialInput,
    commit: bool,
) -> TestResult:
    key_1 = _strip_if_string(test_result_partial_input.key_1)
    key_2 = _strip_if_string(test_result_partial_input.key_2)
    key_3 = _strip_if_string(test_result_partial_input.key_3)
    key_4 = _strip_if_string(test_result_partial_input.key_4)
    form_submission_id = _strip_if_string(test_result_partial_input.form_submission_id)
    if not key_1 or not key_2 or not key_3 or not key_4:
        raise ValueError("key_1, key_2, key_3, and key_4 must be non-empty after trimming.")
    if not form_submission_id:
        raise ValueError("form_submission_id is required.")

    existing_test_result = database_session.scalar(
        select(TestResult).where(
            TestResult.form_submission_id == form_submission_id,
            TestResult.key_1 == key_1,
            TestResult.key_2 == key_2,
            TestResult.key_3 == key_3,
            TestResult.key_4 == key_4,
        )
    )

    if existing_test_result is None:
        existing_test_result = TestResult(
            key_1=key_1,
            key_2=key_2,
            key_3=key_3,
            key_4=key_4,
        )
        database_session.add(existing_test_result)
    elif bool(existing_test_result.is_reviewed):
        raise ValueError("입력승인이 되어 수정할수 없는 데이터가 생겼습니다.")

    for field_name in PARTIAL_UPDATE_FIELD_NAMES:
        new_value = _strip_if_string(getattr(test_result_partial_input, field_name))
        if new_value is not None:
            setattr(existing_test_result, field_name, new_value)

    # enforce: form_submission_id must always be present for new writes
    if not (existing_test_result.form_submission_id or "").strip():
        raise ValueError("form_submission_id is required.")

    existing_test_result.data_writer_name = key_2

    if commit:
        try:
            database_session.commit()
        except IntegrityError as exception:
            database_session.rollback()
            raise ValueError(
                "A row with the same form_submission_id, key_1, key_2, key_3, key_4 already exists."
            ) from exception
        database_session.refresh(existing_test_result)
    return existing_test_result


def list_recent_test_results(database_session: Session, limit: int = 20) -> list[TestResult]:
    result_rows = database_session.scalars(
        select(TestResult).order_by(TestResult.updated_at.desc()).limit(limit)
    )
    return list(result_rows)


def list_unreviewed_test_results(database_session: Session) -> list[TestResult]:
    """draft submission 또는 form_submission_id 없는 미검토 행."""
    unreviewed = or_(TestResult.is_reviewed == False, TestResult.is_reviewed.is_(None))  # noqa: E712
    draft_or_legacy = or_(
        TestResult.form_submission_id.is_(None),
        TestResult.form_submission_id == "",
        exists(
            select(1).where(
                FormSubmission.submission_id == TestResult.form_submission_id,
                FormSubmission.status == "draft",
            )
        ),
    )
    result_rows = database_session.scalars(
        select(TestResult)
        .where(unreviewed, draft_or_legacy)
        .order_by(TestResult.updated_at.desc())
    )
    return list(result_rows)


def list_unreviewed_test_results_for_tester(
    database_session: Session,
    tester_phone: str,
    tester_company_name: str = "",
    tester_display_name: str = "",
) -> list[TestResult]:
    """로그인 tester 본인의 draft/legacy 미승인 행 조회."""
    normalized_phone = (tester_phone or "").strip()
    normalized_company_name = (tester_company_name or "").strip()
    normalized_display_name = (tester_display_name or "").strip()
    if not normalized_phone and not (normalized_company_name and normalized_display_name):
        return []
    unreviewed = or_(TestResult.is_reviewed == False, TestResult.is_reviewed.is_(None))  # noqa: E712
    owner_by_row = and_(
        TestResult.key_1 == normalized_company_name,
        or_(
            TestResult.key_2 == normalized_display_name,
            TestResult.data_writer_name == normalized_display_name,
        ),
    )
    owned_draft = exists(
        select(1).where(
            FormSubmission.submission_id == TestResult.form_submission_id,
            FormSubmission.status == "draft",
            or_(
                FormSubmission.created_by_phone == normalized_phone,
                and_(
                    FormSubmission.created_by_phone.is_(None),
                    owner_by_row,
                ),
            ),
        )
    )
    legacy_without_submission = and_(
        or_(
            TestResult.form_submission_id.is_(None),
            TestResult.form_submission_id == "",
        ),
        owner_by_row,
    )
    result_rows = database_session.scalars(
        select(TestResult)
        .where(unreviewed, or_(owned_draft, legacy_without_submission))
        .order_by(TestResult.updated_at.desc())
    )
    return list(result_rows)


def _get_test_result_or_raise(database_session: Session, test_result_id: int) -> TestResult:
    test_result = database_session.get(TestResult, test_result_id)
    if test_result is None:
        raise LookupError("Test result not found.")
    return test_result


def _assert_not_reviewed(test_result: TestResult) -> None:
    if bool(test_result.is_reviewed):
        raise ValueError("입력승인이 되어 수정할수 없는 데이터가 생겼습니다.")


def _commit_and_refresh(database_session: Session, test_result: TestResult) -> TestResult:
    database_session.commit()
    database_session.refresh(test_result)
    return test_result


def _to_delta_string(started_at: datetime, ended_at: datetime) -> str:
    return str(ended_at - started_at)


def mark_low_test_start(database_session: Session, test_result_id: int) -> TestResult:
    test_result = _get_test_result_or_raise(database_session, test_result_id)
    _assert_not_reviewed(test_result)
    if test_result.low_test_started_at is not None:
        raise ValueError("low_test/start cannot run twice.")
    test_result.low_test_started_at = get_utc_now_datetime()
    return _commit_and_refresh(database_session, test_result)


def mark_low_test_end(database_session: Session, test_result_id: int) -> TestResult:
    test_result = _get_test_result_or_raise(database_session, test_result_id)
    _assert_not_reviewed(test_result)
    if test_result.low_test_started_at is None:
        raise ValueError("low_test/end requires low_test/start.")
    if test_result.low_test_ended_at is not None:
        raise ValueError("low_test/end cannot run twice.")
    test_result.low_test_ended_at = get_utc_now_datetime()
    test_result.low_test_delta = _to_delta_string(
        test_result.low_test_started_at,
        test_result.low_test_ended_at,
    )
    return _commit_and_refresh(database_session, test_result)


def mark_high_test_start(database_session: Session, test_result_id: int) -> TestResult:
    test_result = _get_test_result_or_raise(database_session, test_result_id)
    _assert_not_reviewed(test_result)
    if test_result.high_test_started_at is not None:
        raise ValueError("high_test/start cannot run twice.")
    test_result.high_test_started_at = get_utc_now_datetime()
    return _commit_and_refresh(database_session, test_result)


def mark_high_test_end(database_session: Session, test_result_id: int) -> TestResult:
    test_result = _get_test_result_or_raise(database_session, test_result_id)
    _assert_not_reviewed(test_result)
    if test_result.high_test_started_at is None:
        raise ValueError("high_test/end requires high_test/start.")
    if test_result.high_test_ended_at is not None:
        raise ValueError("high_test/end cannot run twice.")
    test_result.high_test_ended_at = get_utc_now_datetime()
    test_result.high_test_delta = _to_delta_string(
        test_result.high_test_started_at,
        test_result.high_test_ended_at,
    )
    return _commit_and_refresh(database_session, test_result)


def delete_test_results_by_ids(database_session: Session, row_ids: list[int]) -> int:
    normalized_row_ids = sorted({int(row_id) for row_id in row_ids if int(row_id) > 0})
    if not normalized_row_ids:
        return 0
    result = database_session.execute(
        delete(TestResult).where(TestResult.id.in_(normalized_row_ids))
    )
    database_session.commit()
    return int(result.rowcount or 0)


def save_all_test_results_atomically(
    database_session: Session,
    rows: list[TestResultPartialInput],
    delete_row_ids: list[int],
) -> None:
    normalized_delete_row_ids = sorted(
        {
            int(row_id)
            for row_id in delete_row_ids
            if str(row_id).strip() and int(row_id) > 0
        }
    )
    try:
        for row in rows:
            _upsert_partial_test_result_internal(
                database_session=database_session,
                test_result_partial_input=row,
                commit=False,
            )
        if normalized_delete_row_ids:
            database_session.execute(
                delete(TestResult).where(TestResult.id.in_(normalized_delete_row_ids))
            )
        database_session.commit()
    except IntegrityError as exception:
        database_session.rollback()
        raise ValueError(
            "A row with the same form_submission_id, key_1, key_2, key_3, key_4 already exists."
        ) from exception
    except Exception:
        database_session.rollback()
        raise


def mark_test_results_review_complete_by_ids(database_session: Session, row_ids: list[int]) -> int:
    normalized_row_ids = sorted({int(row_id) for row_id in row_ids if int(row_id) > 0})
    if not normalized_row_ids:
        return 0
    result = database_session.execute(
        update(TestResult)
        .where(TestResult.id.in_(normalized_row_ids))
        .values(is_reviewed=True)
    )
    database_session.commit()
    return int(result.rowcount or 0)


def mark_test_results_review_pending_by_ids(database_session: Session, row_ids: list[int]) -> int:
    normalized_row_ids = sorted({int(row_id) for row_id in row_ids if int(row_id) > 0})
    if not normalized_row_ids:
        return 0
    result = database_session.execute(
        update(TestResult)
        .where(TestResult.id.in_(normalized_row_ids))
        .values(is_reviewed=False)
    )
    database_session.commit()
    return int(result.rowcount or 0)
