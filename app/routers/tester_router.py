from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.auth import ROLE_ADMIN, ROLE_MASTER_ADMIN, ROLE_TESTER
from app.config import is_qc_mode_enabled
from app.deps import current_role_name_dependency
from app.deps import database_session_dependency
from app.schemas import TestResultDeleteInput, TestResultPartialInput, TestResultSaveAllInput
from app.models import TestResult, UserAccount
from app.services.form_submission_service import (
    assert_tester_may_write_submission,
    create_form_submission,
    get_form_submission,
)
from app.services.test_result_service import (
    list_unreviewed_test_results,
    list_unreviewed_test_results_for_tester,
    mark_high_test_end,
    mark_high_test_start,
    mark_low_test_end,
    mark_low_test_start,
    delete_test_results_by_ids,
    save_all_test_results_atomically,
    upsert_partial_test_result,
)
from app.services.dropdown_option_service import list_dropdown_options_map

tester_router = APIRouter(prefix="/user", tags=["tester"])


def _assert_tester_only(current_role_name: str) -> None:
    if current_role_name != ROLE_TESTER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This role is not allowed for this action.",
        )


def _is_admin_role(current_role_name: str) -> bool:
    return current_role_name in {ROLE_ADMIN, ROLE_MASTER_ADMIN}


def _get_current_user_info(request: Request, database_session) -> tuple[str, str]:
    phone_number = (request.cookies.get("phone_number") or "").strip()
    if not phone_number:
        return "", ""
    user_account = database_session.scalar(
        select(UserAccount).where(UserAccount.phone_number == phone_number)
    )
    if user_account is None:
        return "", ""
    return (
        (user_account.display_name or "").strip(),
        (user_account.company_name or "").strip(),
    )


@tester_router.get("")
def render_tester_dashboard(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    if current_role_name != ROLE_TESTER:
        return RedirectResponse(url="/admin", status_code=303)
    qc_mode_enabled = is_qc_mode_enabled()
    if qc_mode_enabled and not (request.cookies.get("phone_number") or "").strip():
        return RedirectResponse(url="/login", status_code=303)
    phone_number = (request.cookies.get("phone_number") or "").strip()
    current_display_name, current_company_name = _get_current_user_info(
        request=request,
        database_session=database_session,
    )
    if current_role_name == ROLE_TESTER:
        recent_test_results = list_unreviewed_test_results_for_tester(
            database_session=database_session,
            tester_phone=phone_number,
            tester_company_name=current_company_name,
            tester_display_name=current_display_name,
        )
    else:
        recent_test_results = list_unreviewed_test_results(database_session=database_session)
    dropdown_options_map = list_dropdown_options_map(database_session=database_session)
    default_month_options = [str(month) for month in range(1, 13)]
    existing_month_options = [
        str(option_value).strip()
        for option_value in (dropdown_options_map.get("field_01") or [])
        if str(option_value).strip()
    ]
    month_option_set = set(default_month_options)
    merged_month_options = list(default_month_options)
    for option_value in existing_month_options:
        if option_value in month_option_set:
            continue
        merged_month_options.append(option_value)
        month_option_set.add(option_value)
    dropdown_options_map["field_01"] = merged_month_options

    default_count_options = [str(count) for count in range(1, 31)]
    existing_count_options = [
        str(option_value).strip()
        for option_value in (dropdown_options_map.get("field_02") or [])
        if str(option_value).strip()
    ]
    count_option_set = set(default_count_options)
    merged_count_options = list(default_count_options)
    for option_value in existing_count_options:
        if option_value in count_option_set:
            continue
        merged_count_options.append(option_value)
        count_option_set.add(option_value)
    dropdown_options_map["field_02"] = merged_count_options

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="tester_dashboard.html",
        context={
            "request": request,
            "page_title": "Product Test Data Tracing System",
            "recent_test_results": recent_test_results,
            "current_role_name": current_role_name,
            "current_display_name": current_display_name,
            "current_company_name": current_company_name,
            "dropdown_options_map": dropdown_options_map,
        },
    )


@tester_router.get("/rows/review_status")
def get_user_rows_review_status(
    row_ids: list[int] = Query(default=[]),
    database_session: database_session_dependency = None,
    current_role_name: current_role_name_dependency = None,
):
    if not (_is_admin_role(current_role_name) or current_role_name == ROLE_TESTER):
        _assert_tester_only(current_role_name)
    normalized_row_ids = sorted({int(row_id) for row_id in row_ids if int(row_id) > 0})
    if not normalized_row_ids:
        return {"reviewed_row_ids": []}
    reviewed_row_ids = list(
        database_session.scalars(
            select(TestResult.id).where(
                TestResult.id.in_(normalized_row_ids),
                TestResult.is_reviewed.is_(True),
            )
        )
    )
    return {"reviewed_row_ids": [int(row_id) for row_id in reviewed_row_ids]}


@tester_router.post("/submissions")
def create_submission(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _assert_tester_only(current_role_name)
    phone_number = (request.cookies.get("phone_number") or "").strip()
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="로그인(전화번호)이 필요합니다. 다시 로그인해 주세요.",
        )
    sub = create_form_submission(
        database_session=database_session,
        created_by_phone=phone_number,
    )
    return {
        "form_submission_id": sub.submission_id,
        "status": sub.status,
    }


@tester_router.get("/submissions/{form_submission_id}")
def get_tester_submission(
    request: Request,
    form_submission_id: str,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _assert_tester_only(current_role_name)
    sub = get_form_submission(
        database_session=database_session,
        submission_id=form_submission_id,
    )
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found.",
        )
    phone_number = (request.cookies.get("phone_number") or "").strip()
    if (
        phone_number
        and sub.created_by_phone
        and sub.created_by_phone.strip() != phone_number
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 submission에 접근할 수 없습니다.",
        )
    return {
        "form_submission_id": sub.submission_id,
        "status": sub.status,
        "created_at": sub.created_at,
    }


def _tester_may_write_rows(
    request: Request,
    database_session,
    test_result_partial_input: TestResultPartialInput,
) -> None:
    phone = (request.cookies.get("phone_number") or "").strip()
    assert_tester_may_write_submission(
        database_session=database_session,
        submission_id=test_result_partial_input.form_submission_id,
        tester_phone=phone,
    )


@tester_router.post("/rows/upsert")
def upsert_tester_row(
    request: Request,
    test_result_partial_input: TestResultPartialInput,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    if not (_is_admin_role(current_role_name) or current_role_name == ROLE_TESTER):
        _assert_tester_only(current_role_name)
    target_id = (test_result_partial_input.form_submission_id or "").strip()
    if not target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="form_submission_id is required",
        )
    # 제출 완료(submitted) 이후에는 서버에서도 편집을 막는다.
    try:
        assert_tester_may_write_submission(
            database_session=database_session,
            submission_id=target_id,
            tester_phone="",
        )
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception
    current_display_name, _current_company_name = _get_current_user_info(
        request=request,
        database_session=database_session,
    )
    if current_display_name:
        test_result_partial_input.key_2 = current_display_name
        test_result_partial_input.data_writer_name = current_display_name
    if current_role_name == ROLE_TESTER:
        try:
            _tester_may_write_rows(
                request=request,
                database_session=database_session,
                test_result_partial_input=test_result_partial_input,
            )
        except ValueError as exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exception),
            ) from exception

    try:
        test_result_partial_input.form_submission_id = target_id
        test_result = upsert_partial_test_result(
            database_session=database_session,
            test_result_partial_input=test_result_partial_input,
        )
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception

    return {
        "message": "Row upserted.",
        "id": test_result.id,
        "form_submission_id": test_result.form_submission_id,
        "data_writer_name": test_result.data_writer_name,
        "key_1": test_result.key_1,
        "key_2": test_result.key_2,
        "key_3": test_result.key_3,
        "key_4": test_result.key_4,
        "created_at": test_result.created_at,
        "updated_at": test_result.updated_at,
    }


def _assert_tester_draft_submission_for_row(
    request: Request,
    database_session,
    test_result_id: int,
    current_role_name: str,
) -> None:
    if current_role_name != ROLE_TESTER:
        return
    phone = (request.cookies.get("phone_number") or "").strip()
    tr = database_session.get(TestResult, test_result_id)
    if tr is None or not (tr.submission_id or "").strip():
        return
    assert_tester_may_write_submission(
        database_session=database_session,
        submission_id=tr.submission_id,
        tester_phone=phone,
    )


@tester_router.post("/test_result/{id}/low_test/start")
def start_low_test(
    id: int,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _assert_tester_only(current_role_name)
    try:
        _assert_tester_draft_submission_for_row(
            request, database_session, id, current_role_name
        )
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception
    try:
        test_result = mark_low_test_start(database_session=database_session, test_result_id=id)
    except LookupError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception

    return {
        "message": "low_test/start completed.",
        "id": test_result.id,
        "low_test_started_at": test_result.low_test_started_at,
    }


@tester_router.post("/test_result/{id}/low_test/end")
def end_low_test(
    id: int,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _assert_tester_only(current_role_name)
    try:
        _assert_tester_draft_submission_for_row(
            request, database_session, id, current_role_name
        )
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception
    try:
        test_result = mark_low_test_end(database_session=database_session, test_result_id=id)
    except LookupError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception

    return {
        "message": "low_test/end completed.",
        "id": test_result.id,
        "low_test_ended_at": test_result.low_test_ended_at,
        "low_test_delta": test_result.low_test_delta,
    }


@tester_router.post("/test_result/{id}/high_test/start")
def start_high_test(
    id: int,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _assert_tester_only(current_role_name)
    try:
        _assert_tester_draft_submission_for_row(
            request, database_session, id, current_role_name
        )
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception
    try:
        test_result = mark_high_test_start(database_session=database_session, test_result_id=id)
    except LookupError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception

    return {
        "message": "high_test/start completed.",
        "id": test_result.id,
        "high_test_started_at": test_result.high_test_started_at,
    }


@tester_router.post("/test_result/{id}/high_test/end")
def end_high_test(
    id: int,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _assert_tester_only(current_role_name)
    try:
        _assert_tester_draft_submission_for_row(
            request, database_session, id, current_role_name
        )
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception
    try:
        test_result = mark_high_test_end(database_session=database_session, test_result_id=id)
    except LookupError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception

    return {
        "message": "high_test/end completed.",
        "id": test_result.id,
        "high_test_ended_at": test_result.high_test_ended_at,
        "high_test_delta": test_result.high_test_delta,
    }


@tester_router.post("/rows/delete")
def delete_tester_rows(
    request: Request,
    test_result_delete_input: TestResultDeleteInput,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    if not (_is_admin_role(current_role_name) or current_role_name == ROLE_TESTER):
        _assert_tester_only(current_role_name)
    phone = (request.cookies.get("phone_number") or "").strip()
    if current_role_name == ROLE_TESTER:
        for row_id in test_result_delete_input.row_ids:
            tr = database_session.get(TestResult, int(row_id))
            if tr is not None and (tr.submission_id or "").strip():
                try:
                    assert_tester_may_write_submission(
                        database_session=database_session,
                        submission_id=tr.submission_id,
                        tester_phone=phone,
                    )
                except ValueError as exception:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=str(exception),
                    ) from exception

    deleted_count = delete_test_results_by_ids(
        database_session=database_session,
        row_ids=test_result_delete_input.row_ids,
    )
    return {"message": "Rows deleted.", "deleted_count": deleted_count}


@tester_router.post("/rows/save_all")
def save_all_tester_rows(
    request: Request,
    test_result_save_all_input: TestResultSaveAllInput,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    if not (_is_admin_role(current_role_name) or current_role_name == ROLE_TESTER):
        _assert_tester_only(current_role_name)
    for row in test_result_save_all_input.rows:
        target_id = (row.form_submission_id or "").strip()
        if not target_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="form_submission_id is required",
            )
        try:
            assert_tester_may_write_submission(
                database_session=database_session,
                submission_id=target_id,
                tester_phone="",
            )
        except ValueError as exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exception),
            ) from exception
        row.form_submission_id = target_id
    current_display_name, _current_company_name = _get_current_user_info(
        request=request,
        database_session=database_session,
    )
    if current_display_name:
        for row in test_result_save_all_input.rows:
            row.key_2 = current_display_name
            row.data_writer_name = current_display_name
    if current_role_name == ROLE_TESTER:
        for row in test_result_save_all_input.rows:
            try:
                _tester_may_write_rows(
                    request=request,
                    database_session=database_session,
                    test_result_partial_input=row,
                )
            except ValueError as exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exception),
                ) from exception

    try:
        save_all_test_results_atomically(
            database_session=database_session,
            rows=test_result_save_all_input.rows,
            delete_row_ids=test_result_save_all_input.delete_row_ids,
        )
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception

    return {"message": "All rows saved atomically."}
