import csv
from io import BytesIO, StringIO
from datetime import timedelta

from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.auth import ROLE_ADMIN, ROLE_MASTER_ADMIN, ROLE_TESTER
from app.config import is_qc_mode_enabled
from app.deps import current_role_name_dependency, database_session_dependency
from app.models import FormSubmission, TestResult, UserAccount, get_utc_now_datetime
from app.schemas import TestResultReviewCompleteInput
from app.services.form_submission_service import (
    approve_submission,
    count_rows_by_submission_ids,
    list_submission_summaries_for_admin,
    list_submissions_for_admin,
    delete_submission_and_rows,
)
from app.services.test_result_service import (
    list_recent_test_results,
    mark_test_results_review_complete_by_ids,
    mark_test_results_review_pending_by_ids,
)
from app.services.dropdown_option_service import (
    add_dropdown_option_if_missing,
    delete_dropdown_option_if_exists,
    list_dropdown_options_for_field,
)
from app.services.admin_qc_e2e_service import start_admin_qc_e2e_fill
from app.services.product_test_run_service import (
    MASTER_ACTIVE_STATUS_VALUES,
    REPORT_STATUS_VALUES,
    REPORT_TYPE_VALUES,
    SNAPSHOT_TYPE_VALUES,
    TARGET_STATUS_VALUES,
    ENVIRONMENT_STATUS_VALUES,
    EVIDENCE_TYPE_VALUES,
    PRODUCT_TEST_RELEASE_STATUS_VALUES,
    RELEASE_STAGE_VALUES,
    approve_product_test_report,
    compare_product_test_report_snapshots,
    create_product_test_case,
    create_product_test_environment,
    create_product_test_environment_definition,
    create_product_test_procedure,
    create_product_test_report,
    create_product_test_report_snapshot,
    create_product_test_release,
    create_product_test_target,
    create_product_test_target_definition,
    get_product_test_identifier_client_rules,
    get_product_test_identifier_guides,
    build_product_test_report_export_rows,
    build_product_test_run_export_rows,
    build_product_test_trace_export_rows,
    get_product_test_report_detail,
    get_product_test_report_snapshot_detail,
    get_product_test_system_check,
    get_product_test_trace_view,
    get_release_id_by_result_id,
    get_release_id_by_run_id,
    list_case_options,
    list_environment_options,
    list_product_test_cases,
    list_product_test_environment_definitions,
    list_product_test_environments,
    list_product_test_procedures,
    list_product_test_reports,
    list_product_test_report_snapshots,
    list_product_test_releases,
    list_target_options,
    list_product_test_target_definitions,
    list_product_test_targets,
    list_report_release_options,
    reject_product_test_report,
)


admin_router = APIRouter(prefix="/admin", tags=["admin"])


ADMIN_FORM_NOTICE_CONFIG = {
    "draft_saved": {
        "message": "브라우저 임시저장 되었습니다.",
        "level": "success",
        "mode": "non_modal",
    },
    "draft_invalid_id": {
        "suffix": "자동제출 안 한다.",
        "level": "error",
        "mode": "non_modal",
    },
    "submit_success": {
        "suffix": "자동제출 되었습니다.",
        "level": "success",
        "mode": "non_modal",
    },
    "network_error": {
        "message": "자동제출 중 네트워크 오류가 발생했습니다.",
        "level": "error",
        "mode": "non_modal",
    },
    "duplicate_id": {
        "title": "중복 ID",
        "level": "error",
        "mode": "modal",
    },
}


def _is_ajax_request(request: Request) -> bool:
    requested_with = (request.headers.get("x-requested-with") or "").strip().lower()
    accept_header = (request.headers.get("accept") or "").strip().lower()
    return requested_with == "xmlhttprequest" or "application/json" in accept_header


def _admin_create_error_response(request: Request, target_url: str, message: str):
    payload = _admin_notice_payload_from_message(message=message, ok=False)
    if _is_ajax_request(request):
        return JSONResponse(payload, status_code=400)
    return RedirectResponse(url=f"{target_url}?message={message}&message_type=error", status_code=303)


def _admin_create_success_response(
    request: Request,
    target_url: str,
    message: str,
    extra_payload: dict | None = None,
):
    payload = _admin_notice_payload_from_message(message=message, ok=True)
    if _is_ajax_request(request):
        response_payload = dict(payload)
        if extra_payload:
            response_payload.update(extra_payload)
        return JSONResponse(response_payload)
    return RedirectResponse(url=f"{target_url}?message={message}&message_type=success", status_code=303)


def _admin_notice_payload_from_message(*, message: str, ok: bool) -> dict:
    normalized = str(message or "").strip()
    payload = {
        "ok": ok,
        "message": normalized,
        "notice_message": normalized,
        "notice_level": "success" if ok else "error",
        "notice_mode": "non_modal",
        "dialog_title": "",
    }
    if ok:
        success_config = ADMIN_FORM_NOTICE_CONFIG["submit_success"]
        payload["notice_message"] = success_config["suffix"]
        payload["notice_level"] = success_config["level"]
        payload["notice_mode"] = success_config["mode"]
        payload["state_code"] = "submit_success"
        return payload
    lowered = normalized.lower()
    for field_name, guide_message in get_product_test_identifier_guides().items():
        expected_error = f"{field_name} format is invalid."
        if lowered == expected_error.lower():
            payload["notice_message"] = guide_message
            payload["state_code"] = "invalid_id"
            return payload
    if "already exists" in lowered:
        duplicate_field_name = normalized.split(" ", 1)[0].strip().upper()
        payload["notice_mode"] = "modal"
        payload["dialog_title"] = ADMIN_FORM_NOTICE_CONFIG["duplicate_id"]["title"]
        payload["notice_message"] = (
            f"{duplicate_field_name} 중복이다. "
            "다른 ID 넣어라. "
            "다시 제출해라."
        )
        payload["state_code"] = "duplicate_id"
        return payload
    payload["state_code"] = "submit_error"
    return payload


def _csv_streaming_response(*, rows: list[list[str]], file_name: str) -> StreamingResponse:
    text_stream = StringIO()
    writer = csv.writer(text_stream)
    for row in rows:
        writer.writerow(row)
    output_stream = BytesIO()
    output_stream.write("\ufeff".encode("utf-8"))
    output_stream.write(text_stream.getvalue().encode("utf-8"))
    output_stream.seek(0)
    return StreamingResponse(
        output_stream,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


def _ensure_admin_role(current_role_name: str) -> None:
    if current_role_name not in {ROLE_ADMIN, ROLE_MASTER_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This role is not allowed for this action.",
        )


def _admin_identity_context(database_session: Session, request: Request) -> dict:
    qc_mode_enabled = is_qc_mode_enabled()
    cookie_role_name = (request.cookies.get("role_name") or "").strip()
    if qc_mode_enabled and cookie_role_name == ROLE_MASTER_ADMIN:
        return {
            "current_admin_department_name": "",
            "current_admin_display_name": "마스터관리자",
            "current_admin_internal_title": "",
            "admin_greeting_text": "마스터관리자 님, 안녕하세요.",
        }

    normalized_phone_number = (request.cookies.get("phone_number") or "").strip()
    if not normalized_phone_number:
        return {
            "current_admin_department_name": "OO",
            "current_admin_display_name": "OOO",
            "current_admin_internal_title": "프로",
            "admin_greeting_text": "OO부서 OOO프로 님, 안녕하세요.",
        }

    user_account = database_session.scalar(
        select(UserAccount).where(UserAccount.phone_number == normalized_phone_number)
    )
    if user_account is None:
        return {
            "current_admin_department_name": "OO",
            "current_admin_display_name": "OOO",
            "current_admin_internal_title": "프로",
            "admin_greeting_text": "OO부서 OOO프로 님, 안녕하세요.",
        }

    department_name = (user_account.department_name or "").strip() or "OO"
    display_name = (user_account.display_name or "").strip() or "OOO"
    internal_title = (user_account.internal_title or "").strip() or "프로"
    return {
        "current_admin_department_name": department_name,
        "current_admin_display_name": display_name,
        "current_admin_internal_title": internal_title,
        "admin_greeting_text": f"{department_name}부서 {display_name}{internal_title} 님, 안녕하세요.",
    }


def _admin_actor_name(database_session: Session, request: Request) -> str:
    identity_context = _admin_identity_context(database_session=database_session, request=request)
    display_name = str(identity_context.get("current_admin_display_name") or "").strip()
    if display_name:
        return display_name
    return "ADMIN"


def _form_submissions_for_admin(database_session: Session) -> list[dict]:
    subs = list_submissions_for_admin(database_session=database_session, limit=200)
    if not subs:
        return []
    id_list = [s.submission_id for s in subs]
    counts = count_rows_by_submission_ids(database_session=database_session, submission_ids=id_list)
    return [
        {
            "submission": s,
            "row_count": int(counts.get(s.submission_id, 0)),
        }
        for s in subs
    ]


def _submission_summaries_for_admin(database_session: Session) -> list[dict]:
    return list_submission_summaries_for_admin(database_session=database_session, limit=200)


def _tester_accounts_for_admin(database_session: Session) -> list[UserAccount]:
    return list(
        database_session.scalars(
            select(UserAccount)
            .where(UserAccount.role_name == "tester")
            .order_by(UserAccount.created_at.desc())
        )
    )


def _admin_accounts_for_admin(database_session: Session) -> list[UserAccount]:
    return list(
        database_session.scalars(
            select(UserAccount)
            .where(UserAccount.role_name == ROLE_ADMIN)
            .order_by(UserAccount.created_at.desc())
        )
    )


def _render_admin_shell_template(
    request: Request,
    database_session: Session,
    current_role_name: str,
    template_name: str,
    page_title: str,
    extra_context: dict | None = None,
):
    if current_role_name not in {ROLE_ADMIN, ROLE_MASTER_ADMIN}:
        return RedirectResponse(url="/login", status_code=303)
    templates = request.app.state.templates
    context = {
        "request": request,
        "page_title": page_title,
        "current_role_name": current_role_name,
        "can_edit_all_data": current_role_name == ROLE_MASTER_ADMIN,
        **_admin_identity_context(database_session=database_session, request=request),
    }
    if extra_context:
        context.update(extra_context)
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
    )


def _sample_product_test_release_rows() -> list[dict]:
    return [
        {
            "product_test_release_id": "QA_PTREL-HRK_9000A-1.0.0-RC1",
            "upstream_release_id": "HRK_9000A-1.0.0",
            "upstream_release_system": "Huvitz Software Release System",
            "release_stage": "RC",
            "release_sequence": 1,
            "product_test_release_status": "testing",
            "created_at": "2026-05-05 09:00:00",
            "created_by": "SQA_MASTER",
            "updated_at": "2026-05-05 10:30:00",
            "updated_by": "SQA_MASTER",
            "remark": "HRK-9000A RC baseline",
        },
        {
            "product_test_release_id": "QA_PTREL-HRK_9000A-1.0.0-GA",
            "upstream_release_id": "HRK_9000A-1.0.0",
            "upstream_release_system": "Huvitz Software Release System",
            "release_stage": "GA",
            "release_sequence": 0,
            "product_test_release_status": "drafted",
            "created_at": "2026-05-05 11:00:00",
            "created_by": "SQA_MASTER",
            "updated_at": "2026-05-05 11:00:00",
            "updated_by": "SQA_MASTER",
            "remark": "",
        },
    ]


def _sample_product_test_target_definition_rows() -> list[dict]:
    return [
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-HRK_9000A",
            "product_code": "HRK_9000A",
            "manufacturer": "Huvitz",
            "model_name": "HRK-9000A",
            "hardware_revision": "A",
            "default_software_version": "1.0.0",
            "default_firmware_version": "1.0.0",
            "product_test_target_definition_status": "active",
            "created_at": "2026-05-05 09:00:00",
            "created_by": "SQA_MASTER",
            "updated_at": "2026-05-05 09:00:00",
            "updated_by": "SQA_MASTER",
            "remark": "",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-MERCUSYS_MR30G",
            "product_code": "MERCUSYS_MR30G",
            "manufacturer": "MERCUSYS",
            "model_name": "MR30G",
            "hardware_revision": "A1",
            "default_software_version": "1.0.0",
            "default_firmware_version": "1.0.0",
            "product_test_target_definition_status": "active",
            "created_at": "2026-05-05 09:30:00",
            "created_by": "SQA_MASTER",
            "updated_at": "2026-05-05 09:30:00",
            "updated_by": "SQA_MASTER",
            "remark": "",
        },
    ]


def _sample_product_test_target_rows() -> list[dict]:
    return [
        {
            "product_test_target_id": "QA_PTTGT-HRK_9000A-SN001",
            "product_test_target_definition_id": "QA_PTTGTDEF-HRK_9000A",
            "serial_number": "SN001",
            "software_version": "1.0.0",
            "firmware_version": "1.0.0",
            "manufacture_lot": "LOT-202605",
            "product_test_target_status": "active",
            "created_at": "2026-05-05 10:00:00",
            "created_by": "SQA_MASTER",
            "updated_at": "2026-05-05 10:00:00",
            "updated_by": "SQA_MASTER",
            "remark": "",
        }
    ]


def _sample_product_test_environment_definition_rows() -> list[dict]:
    return [
        {
            "product_test_environment_definition_id": "QA_PTENVDEF-HUVITZ-ANYANG-CONNECTIVITY_ROOM",
            "product_test_environment_definition_name": "Huvitz Anyang Connectivity Room Standard Environment",
            "test_country": "Korea",
            "test_city": "Anyang",
            "test_company": "Huvitz",
            "test_building": "",
            "test_floor": "6F",
            "test_room": "Connectivity Room",
            "network_type": "ISOLATED_NETWORK",
            "test_computer_name": "SQA-PC-01",
            "operating_system_version": "Windows 10",
            "test_tool_name": "Product Test Tool",
            "test_tool_version": "1.0.0",
            "power_voltage": "220V",
            "power_frequency": "60Hz",
            "power_connector_type": "OO_CONNECTOR",
            "power_condition": "Commercial AC power",
            "product_test_environment_definition_status": "active",
            "created_at": "2026-05-05 09:00:00",
            "created_by": "SQA_MASTER",
            "updated_at": "2026-05-05 09:00:00",
            "updated_by": "SQA_MASTER",
            "remark": "",
        }
    ]


def _sample_product_test_environment_rows() -> list[dict]:
    return [
        {
            "product_test_environment_id": "QA_PTENV-HUVITZ-ANYANG-CONNECTIVITY_ROOM-20260504-001",
            "product_test_environment_definition_id": "QA_PTENVDEF-HUVITZ-ANYANG-CONNECTIVITY_ROOM",
            "product_test_environment_name": "Anyang Connectivity Room Snapshot",
            "test_computer_name": "SQA-PC-01",
            "operating_system_version": "Windows 10",
            "test_tool_version": "1.0.0",
            "network_type": "ISOLATED_NETWORK",
            "power_voltage": "220V",
            "power_frequency": "60Hz",
            "power_connector_type": "OO_CONNECTOR",
            "captured_at": "2026-05-05 09:15:00",
            "product_test_environment_status": "active",
            "created_at": "2026-05-05 09:15:00",
            "created_by": "SQA_MASTER",
            "updated_at": "2026-05-05 09:15:00",
            "updated_by": "SQA_MASTER",
            "remark": "",
        }
    ]


def _sample_product_test_case_rows() -> list[dict]:
    return [
        {
            "product_test_case_id": "QA_PTCASE-WIFI-AP_CONFIG-001",
            "product_test_case_title": "WiFi AP 설정 적합성 검증",
            "test_category": "WiFi",
            "test_objective": "RS9116 WiFi 모듈 기준으로 AP 설정이 권장 조건을 만족하는지 확인",
            "precondition": "시험 대상 AP 관리자 화면 접근 가능",
            "expected_result": "AP 설정값이 RS9116 모듈 권장 조건을 만족해야 함",
            "product_test_case_status": "active",
            "created_at": "2026-05-05 08:30:00",
            "created_by": "SQA_MASTER",
            "updated_at": "2026-05-05 08:30:00",
            "updated_by": "SQA_MASTER",
            "remark": "",
        }
    ]


def _sample_product_test_procedure_rows() -> list[dict]:
    return [
        {
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-001",
            "product_test_case_id": "QA_PTCASE-WIFI-AP_CONFIG-001",
            "procedure_sequence": 1,
            "procedure_action": "WiFi Band 분리설정 확인",
            "expected_result": "2.4GHz와 5GHz SSID가 분리되어 있어야 함",
            "acceptance_criteria": "2.4GHz, 5GHz의 SSID를 분리하는 것을 권장",
            "required_evidence_type": "screenshot",
            "product_test_procedure_status": "active",
            "created_at": "2026-05-05 08:40:00",
            "created_by": "SQA_MASTER",
            "updated_at": "2026-05-05 08:40:00",
            "updated_by": "SQA_MASTER",
            "remark": "분리하지 않은 경우 임베디드 장비가 2.4GHz로 할당될 가능성이 높음.",
        },
        {
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-002",
            "product_test_case_id": "QA_PTCASE-WIFI-AP_CONFIG-001",
            "procedure_sequence": 2,
            "procedure_action": "WiFi Channel 설정 확인",
            "expected_result": "2.4GHz는 1~11번, 5GHz는 36/40/44/48 고정 채널이어야 함",
            "acceptance_criteria": "DFS 채널이 아닌 36, 40, 44, 48 채널 고정 사용 권장",
            "required_evidence_type": "screenshot",
            "product_test_procedure_status": "active",
            "created_at": "2026-05-05 08:41:00",
            "created_by": "SQA_MASTER",
            "updated_at": "2026-05-05 08:41:00",
            "updated_by": "SQA_MASTER",
            "remark": "DFS 채널 사용 시 검색 실패 가능.",
        },
    ]


@admin_router.get("")
def render_admin_dashboard(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="admin_dashboard.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
            "admin_id_rules": get_product_test_identifier_client_rules(),
            "admin_id_guides": get_product_test_identifier_guides(),
            "admin_notice_config": ADMIN_FORM_NOTICE_CONFIG,
            "release_rows": list_product_test_releases(database_session),
            "release_stage_values": RELEASE_STAGE_VALUES,
            "product_test_release_status_values": PRODUCT_TEST_RELEASE_STATUS_VALUES,
            "target_definition_rows": list_product_test_target_definitions(database_session),
            "target_definition_status_values": MASTER_ACTIVE_STATUS_VALUES,
            "target_rows": list_product_test_targets(database_session),
            "target_status_values": TARGET_STATUS_VALUES,
            "environment_definition_rows": list_product_test_environment_definitions(database_session),
            "environment_definition_status_values": MASTER_ACTIVE_STATUS_VALUES,
            "environment_rows": list_product_test_environments(database_session),
            "environment_status_values": ENVIRONMENT_STATUS_VALUES,
            "case_rows": list_product_test_cases(database_session),
            "case_status_values": MASTER_ACTIVE_STATUS_VALUES,
            "procedure_rows": list_product_test_procedures(database_session),
            "procedure_status_values": MASTER_ACTIVE_STATUS_VALUES,
            "evidence_type_values": EVIDENCE_TYPE_VALUES,
            "report_rows": list_product_test_reports(database_session),
            "report_release_options": list_report_release_options(database_session),
            "report_type_values": REPORT_TYPE_VALUES,
        },
    )


@admin_router.get("/test-configs")
def render_test_config_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="test_config_admin.html",
        page_title="Product Test Data Tracing System",
    )


@admin_router.get("/tests")
def render_test_definition_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="test_definition_admin.html",
        page_title="Product Test Data Tracing System",
    )


@admin_router.get("/test-reports")
def render_test_report_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="test_report_admin.html",
        page_title="Product Test Data Tracing System",
    )


@admin_router.get("/serial-report-trace")
def render_serial_report_trace_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="serial_report_trace_admin.html",
        page_title="Product Test Data Tracing System",
    )


@admin_router.get("/product-test-releases")
def render_product_test_releases_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_releases_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            "rows": list_product_test_releases(database_session),
            "release_stage_values": RELEASE_STAGE_VALUES,
            "product_test_release_status_values": PRODUCT_TEST_RELEASE_STATUS_VALUES,
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@admin_router.post("/product-test-releases/create")
def create_product_test_release_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_release_id: str = Form(""),
    upstream_release_id: str = Form(""),
    upstream_release_system: str = Form(""),
    release_stage: str = Form(""),
    product_test_release_status: str = Form(""),
    remark: str = Form(""),
    return_to: str = Form(""),
):
    _ensure_admin_role(current_role_name)
    try:
        created_row = create_product_test_release(
            database_session,
            product_test_release_id=product_test_release_id,
            upstream_release_id=upstream_release_id,
            upstream_release_system=upstream_release_system,
            release_stage=release_stage,
            product_test_release_status=product_test_release_status,
            actor_name=_admin_actor_name(database_session, request),
            remark=remark,
        )
    except ValueError as exception:
        target_url = (return_to or "").strip() or "/admin/product-test-releases"
        return _admin_create_error_response(request, target_url, str(exception))
    target_url = (return_to or "").strip() or "/admin/product-test-releases"
    return _admin_create_success_response(request, target_url, "Saved", {"created_row": created_row})


@admin_router.get("/product-test-target-definitions")
def render_product_test_target_definitions_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_target_definitions_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            "rows": list_product_test_target_definitions(database_session),
            "status_values": MASTER_ACTIVE_STATUS_VALUES,
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@admin_router.post("/product-test-target-definitions/create")
def create_product_test_target_definition_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_target_definition_id: str = Form(""),
    product_code: str = Form(""),
    manufacturer: str = Form(""),
    model_name: str = Form(""),
    hardware_revision: str = Form(""),
    default_software_version: str = Form(""),
    default_firmware_version: str = Form(""),
    product_test_target_definition_status: str = Form(""),
    remark: str = Form(""),
    return_to: str = Form(""),
):
    _ensure_admin_role(current_role_name)
    try:
        created_row = create_product_test_target_definition(
            database_session,
            product_test_target_definition_id=product_test_target_definition_id,
            product_code=product_code,
            manufacturer=manufacturer,
            model_name=model_name,
            hardware_revision=hardware_revision,
            default_software_version=default_software_version,
            default_firmware_version=default_firmware_version,
            product_test_target_definition_status=product_test_target_definition_status,
            actor_name=_admin_actor_name(database_session, request),
            remark=remark,
        )
    except ValueError as exception:
        target_url = (return_to or "").strip() or "/admin/product-test-target-definitions"
        return _admin_create_error_response(request, target_url, str(exception))
    target_url = (return_to or "").strip() or "/admin/product-test-target-definitions"
    return _admin_create_success_response(request, target_url, "Saved", {"created_row": created_row})


@admin_router.get("/product-test-targets")
def render_product_test_targets_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_targets_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            "rows": list_product_test_targets(database_session),
            "target_definition_rows": list_product_test_target_definitions(database_session),
            "status_values": TARGET_STATUS_VALUES,
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@admin_router.post("/product-test-targets/create")
def create_product_test_target_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_target_id: str = Form(""),
    product_test_target_definition_id: str = Form(""),
    serial_number: str = Form(""),
    software_version: str = Form(""),
    firmware_version: str = Form(""),
    manufacture_lot: str = Form(""),
    product_test_target_status: str = Form(""),
    remark: str = Form(""),
    return_to: str = Form(""),
):
    _ensure_admin_role(current_role_name)
    try:
        created_row = create_product_test_target(
            database_session,
            product_test_target_id=product_test_target_id,
            product_test_target_definition_id=product_test_target_definition_id,
            serial_number=serial_number,
            software_version=software_version,
            firmware_version=firmware_version,
            manufacture_lot=manufacture_lot,
            product_test_target_status=product_test_target_status,
            actor_name=_admin_actor_name(database_session, request),
            remark=remark,
        )
    except ValueError as exception:
        target_url = (return_to or "").strip() or "/admin/product-test-targets"
        return _admin_create_error_response(request, target_url, str(exception))
    target_url = (return_to or "").strip() or "/admin/product-test-targets"
    return _admin_create_success_response(request, target_url, "Saved", {"created_row": created_row})


@admin_router.get("/product-test-environment-definitions")
def render_product_test_environment_definitions_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_environment_definitions_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            "rows": list_product_test_environment_definitions(database_session),
            "status_values": MASTER_ACTIVE_STATUS_VALUES,
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@admin_router.post("/product-test-environment-definitions/create")
def create_product_test_environment_definition_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_environment_definition_id: str = Form(""),
    product_test_environment_definition_name: str = Form(""),
    test_country: str = Form(""),
    test_city: str = Form(""),
    test_company: str = Form(""),
    test_building: str = Form(""),
    test_floor: str = Form(""),
    test_room: str = Form(""),
    network_type: str = Form(""),
    test_computer_name: str = Form(""),
    operating_system_version: str = Form(""),
    test_tool_name: str = Form(""),
    test_tool_version: str = Form(""),
    power_voltage: str = Form(""),
    power_frequency: str = Form(""),
    power_connector_type: str = Form(""),
    power_condition: str = Form(""),
    product_test_environment_definition_status: str = Form(""),
    remark: str = Form(""),
    return_to: str = Form(""),
):
    _ensure_admin_role(current_role_name)
    try:
        created_row = create_product_test_environment_definition(
            database_session,
            product_test_environment_definition_id=product_test_environment_definition_id,
            product_test_environment_definition_name=product_test_environment_definition_name,
            test_country=test_country,
            test_city=test_city,
            test_company=test_company,
            test_building=test_building,
            test_floor=test_floor,
            test_room=test_room,
            network_type=network_type,
            test_computer_name=test_computer_name,
            operating_system_version=operating_system_version,
            test_tool_name=test_tool_name,
            test_tool_version=test_tool_version,
            power_voltage=power_voltage,
            power_frequency=power_frequency,
            power_connector_type=power_connector_type,
            power_condition=power_condition,
            product_test_environment_definition_status=product_test_environment_definition_status,
            actor_name=_admin_actor_name(database_session, request),
            remark=remark,
        )
    except ValueError as exception:
        target_url = (return_to or "").strip() or "/admin/product-test-environment-definitions"
        return _admin_create_error_response(request, target_url, str(exception))
    target_url = (return_to or "").strip() or "/admin/product-test-environment-definitions"
    return _admin_create_success_response(request, target_url, "Saved", {"created_row": created_row})


@admin_router.get("/product-test-environments")
def render_product_test_environments_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_environments_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            "rows": list_product_test_environments(database_session),
            "environment_definition_rows": list_product_test_environment_definitions(database_session),
            "status_values": ENVIRONMENT_STATUS_VALUES,
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@admin_router.post("/product-test-environments/create")
def create_product_test_environment_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_environment_id: str = Form(""),
    product_test_environment_definition_id: str = Form(""),
    product_test_environment_name: str = Form(""),
    test_computer_name: str = Form(""),
    operating_system_version: str = Form(""),
    test_tool_version: str = Form(""),
    network_type: str = Form(""),
    power_voltage: str = Form(""),
    power_frequency: str = Form(""),
    power_connector_type: str = Form(""),
    captured_at: str = Form(""),
    product_test_environment_status: str = Form(""),
    remark: str = Form(""),
    return_to: str = Form(""),
):
    _ensure_admin_role(current_role_name)
    try:
        created_row = create_product_test_environment(
            database_session,
            product_test_environment_id=product_test_environment_id,
            product_test_environment_definition_id=product_test_environment_definition_id,
            product_test_environment_name=product_test_environment_name,
            test_computer_name=test_computer_name,
            operating_system_version=operating_system_version,
            test_tool_version=test_tool_version,
            network_type=network_type,
            power_voltage=power_voltage,
            power_frequency=power_frequency,
            power_connector_type=power_connector_type,
            captured_at=captured_at,
            product_test_environment_status=product_test_environment_status,
            actor_name=_admin_actor_name(database_session, request),
            remark=remark,
        )
    except ValueError as exception:
        target_url = (return_to or "").strip() or "/admin/product-test-environments"
        return _admin_create_error_response(request, target_url, str(exception))
    target_url = (return_to or "").strip() or "/admin/product-test-environments"
    return _admin_create_success_response(request, target_url, "Saved", {"created_row": created_row})


@admin_router.get("/product-test-cases")
def render_product_test_cases_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_cases_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            "rows": list_product_test_cases(database_session),
            "status_values": MASTER_ACTIVE_STATUS_VALUES,
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@admin_router.post("/product-test-cases/create")
def create_product_test_case_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_case_id: str = Form(""),
    product_test_case_title: str = Form(""),
    test_category: str = Form(""),
    test_objective: str = Form(""),
    precondition: str = Form(""),
    expected_result: str = Form(""),
    product_test_case_status: str = Form(""),
    remark: str = Form(""),
    return_to: str = Form(""),
):
    _ensure_admin_role(current_role_name)
    try:
        created_row = create_product_test_case(
            database_session,
            product_test_case_id=product_test_case_id,
            product_test_case_title=product_test_case_title,
            test_category=test_category,
            test_objective=test_objective,
            precondition=precondition,
            expected_result=expected_result,
            product_test_case_status=product_test_case_status,
            actor_name=_admin_actor_name(database_session, request),
            remark=remark,
        )
    except ValueError as exception:
        target_url = (return_to or "").strip() or "/admin/product-test-cases"
        return _admin_create_error_response(request, target_url, str(exception))
    target_url = (return_to or "").strip() or "/admin/product-test-cases"
    return _admin_create_success_response(request, target_url, "Saved", {"created_row": created_row})


@admin_router.get("/product-test-procedures")
def render_product_test_procedures_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_procedures_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            "rows": list_product_test_procedures(database_session),
            "case_rows": list_product_test_cases(database_session),
            "status_values": MASTER_ACTIVE_STATUS_VALUES,
            "evidence_type_values": EVIDENCE_TYPE_VALUES,
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@admin_router.post("/product-test-procedures/create")
def create_product_test_procedure_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_procedure_id: str = Form(""),
    product_test_case_id: str = Form(""),
    procedure_sequence: int = Form(0),
    procedure_action: str = Form(""),
    expected_result: str = Form(""),
    acceptance_criteria: str = Form(""),
    required_evidence_type: str = Form(""),
    product_test_procedure_status: str = Form(""),
    remark: str = Form(""),
    return_to: str = Form(""),
):
    _ensure_admin_role(current_role_name)
    try:
        created_row = create_product_test_procedure(
            database_session,
            product_test_procedure_id=product_test_procedure_id,
            product_test_case_id=product_test_case_id,
            procedure_sequence=procedure_sequence,
            procedure_action=procedure_action,
            expected_result=expected_result,
            acceptance_criteria=acceptance_criteria,
            required_evidence_type=required_evidence_type,
            product_test_procedure_status=product_test_procedure_status,
            actor_name=_admin_actor_name(database_session, request),
            remark=remark,
        )
    except ValueError as exception:
        target_url = (return_to or "").strip() or "/admin/product-test-procedures"
        return _admin_create_error_response(request, target_url, str(exception))
    target_url = (return_to or "").strip() or "/admin/product-test-procedures"
    return _admin_create_success_response(request, target_url, "Saved", {"created_row": created_row})


@admin_router.get("/product-test-reports")
def render_product_test_reports_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_reports_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            "rows": list_product_test_reports(database_session),
            "snapshot_rows": list_product_test_report_snapshots(database_session)[:10],
            "release_options": list_report_release_options(database_session),
            "report_type_values": REPORT_TYPE_VALUES,
            "report_status_values": REPORT_STATUS_VALUES,
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@admin_router.post("/product-test-reports/create")
def create_product_test_report_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_release_id: str = Form(""),
    product_test_report_type: str = Form(""),
    product_test_report_title: str = Form(""),
    remark: str = Form(""),
    return_to: str = Form(""),
):
    _ensure_admin_role(current_role_name)
    actor_name = _admin_actor_name(database_session=database_session, request=request)
    try:
        report = create_product_test_report(
            database_session,
            product_test_release_id=product_test_release_id,
            product_test_report_type=product_test_report_type,
            product_test_report_title=product_test_report_title,
            created_by=actor_name,
            remark=remark,
        )
    except ValueError as exception:
        target_url = (return_to or "").strip() or "/admin/product-test-reports"
        return _admin_create_error_response(request, target_url, str(exception))
    target_url = (return_to or "").strip()
    if target_url:
        return _admin_create_success_response(
            request,
            target_url,
            "Report created",
            {
                "product_test_report_id": report["product_test_report_id"],
                "created_row": report,
            },
        )
    if _is_ajax_request(request):
        return JSONResponse(
            {
                "ok": True,
                "message": "Report created",
                "product_test_report_id": report["product_test_report_id"],
                "redirect_url": f"/admin/product-test-reports/{report['product_test_report_id']}",
            }
        )
    return RedirectResponse(
        url=f"/admin/product-test-reports/{report['product_test_report_id']}?message=Report created&message_type=success",
        status_code=303,
    )


@admin_router.get("/product-test-reports/{product_test_report_id}")
def render_product_test_report_detail_admin(
    product_test_report_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    detail = get_product_test_report_detail(database_session, product_test_report_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_report_detail_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            **detail,
            "snapshot_rows": [
                row for row in list_product_test_report_snapshots(database_session)
                if row["product_test_report_id"] == product_test_report_id
            ],
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@admin_router.post("/product-test-reports/{product_test_report_id}/snapshot")
def create_product_test_report_snapshot_admin(
    product_test_report_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    snapshot_type: str = Form("manual"),
    remark: str = Form(""),
):
    _ensure_admin_role(current_role_name)
    actor_name = _admin_actor_name(database_session=database_session, request=request)
    try:
        snapshot = create_product_test_report_snapshot(
            database_session,
            product_test_report_id=product_test_report_id,
            snapshot_type=snapshot_type,
            created_by=actor_name,
            remark=remark,
        )
    except (LookupError, ValueError) as exception:
        return RedirectResponse(
            url=f"/admin/product-test-reports/{product_test_report_id}?message={str(exception)}&message_type=error",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/admin/product-test-report-snapshots/{snapshot['product_test_report_snapshot_id']}?message=Snapshot created&message_type=success",
        status_code=303,
    )


@admin_router.get("/product-test-reports/{product_test_report_id}/export.csv")
def export_product_test_report_csv(
    product_test_report_id: str,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    rows = build_product_test_report_export_rows(database_session, product_test_report_id)
    return _csv_streaming_response(rows=rows, file_name=f"{product_test_report_id}.csv")


@admin_router.get("/product-test-reports/{product_test_report_id}/print")
def render_product_test_report_print(
    product_test_report_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    detail = get_product_test_report_detail(database_session, product_test_report_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_report_print_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            **detail,
            "generated_at": get_utc_now_datetime().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@admin_router.post("/product-test-reports/{product_test_report_id}/approve")
def approve_product_test_report_admin(
    product_test_report_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    actor_name = _admin_actor_name(database_session=database_session, request=request)
    try:
        approve_product_test_report(
            database_session,
            product_test_report_id=product_test_report_id,
            approved_by=actor_name,
        )
    except (LookupError, ValueError) as exception:
        return RedirectResponse(
            url=f"/admin/product-test-reports/{product_test_report_id}?message={str(exception)}&message_type=error",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/admin/product-test-reports/{product_test_report_id}?message=Report approved&message_type=success",
        status_code=303,
    )


@admin_router.post("/product-test-reports/{product_test_report_id}/reject")
def reject_product_test_report_admin(
    product_test_report_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    rejection_reason: str = Form(""),
):
    _ensure_admin_role(current_role_name)
    actor_name = _admin_actor_name(database_session=database_session, request=request)
    try:
        reject_product_test_report(
            database_session,
            product_test_report_id=product_test_report_id,
            rejected_by=actor_name,
            rejection_reason=rejection_reason,
        )
    except (LookupError, ValueError) as exception:
        return RedirectResponse(
            url=f"/admin/product-test-reports/{product_test_report_id}?message={str(exception)}&message_type=error",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/admin/product-test-reports/{product_test_report_id}?message=Report rejected&message_type=success",
        status_code=303,
    )


@admin_router.get("/product-test-report-snapshots")
def render_product_test_report_snapshots_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_report_snapshots_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            "rows": list_product_test_report_snapshots(database_session),
            "report_rows": list_product_test_reports(database_session),
            "snapshot_type_values": SNAPSHOT_TYPE_VALUES,
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@admin_router.get("/product-test-report-snapshots/diff")
def render_product_test_report_snapshot_diff_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_report_snapshot_diff_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            "snapshot_rows": list_product_test_report_snapshots(database_session),
            "diff_result": None,
            "selected_left_snapshot_id": "",
            "selected_right_snapshot_id": "",
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@admin_router.post("/product-test-report-snapshots/diff")
def compare_product_test_report_snapshot_diff_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    left_snapshot_id: str = Form(""),
    right_snapshot_id: str = Form(""),
):
    _ensure_admin_role(current_role_name)
    diff_result = None
    message = ""
    message_type = "info"
    try:
        diff_result = compare_product_test_report_snapshots(
            database_session,
            left_snapshot_id=left_snapshot_id,
            right_snapshot_id=right_snapshot_id,
        )
    except (LookupError, ValueError) as exception:
        message = str(exception)
        message_type = "error"
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_report_snapshot_diff_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            "snapshot_rows": list_product_test_report_snapshots(database_session),
            "diff_result": diff_result,
            "selected_left_snapshot_id": left_snapshot_id,
            "selected_right_snapshot_id": right_snapshot_id,
            "message": message,
            "message_type": message_type,
        },
    )


@admin_router.get("/product-test-report-snapshots/{product_test_report_snapshot_id}")
def render_product_test_report_snapshot_detail_admin(
    product_test_report_snapshot_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    detail = get_product_test_report_snapshot_detail(database_session, product_test_report_snapshot_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found.")
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_report_snapshot_detail_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            **detail,
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@admin_router.get("/product-test-trace")
def render_product_test_trace_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_release_id: str = Query(""),
    product_test_target_id: str = Query(""),
    product_test_environment_id: str = Query(""),
    product_test_case_id: str = Query(""),
    result_status: str = Query(""),
    defect_status: str = Query(""),
):
    selected_release_id = (product_test_release_id or "").strip()
    trace_detail = None
    if selected_release_id:
        trace_detail = get_product_test_trace_view(
            database_session,
            product_test_release_id=selected_release_id,
            product_test_target_id=product_test_target_id,
            product_test_environment_id=product_test_environment_id,
            product_test_case_id=product_test_case_id,
            result_status=result_status,
            defect_status=defect_status,
        )
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_trace_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            "trace_detail": trace_detail,
            "release_options": list_report_release_options(database_session),
            "target_options": list_target_options(database_session),
            "environment_options": list_environment_options(database_session),
            "case_options": list_case_options(database_session),
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@admin_router.get("/product-test-releases/{product_test_release_id}/trace")
def render_product_test_release_trace_admin(
    product_test_release_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_target_id: str = Query(""),
    product_test_environment_id: str = Query(""),
    product_test_case_id: str = Query(""),
    result_status: str = Query(""),
    defect_status: str = Query(""),
):
    trace_detail = get_product_test_trace_view(
        database_session,
        product_test_release_id=product_test_release_id,
        product_test_target_id=product_test_target_id,
        product_test_environment_id=product_test_environment_id,
        product_test_case_id=product_test_case_id,
        result_status=result_status,
        defect_status=defect_status,
    )
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_trace_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context={
            "trace_detail": trace_detail,
            "release_options": list_report_release_options(database_session),
            "target_options": list_target_options(database_session),
            "environment_options": list_environment_options(database_session),
            "case_options": list_case_options(database_session),
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@admin_router.get("/product-test-releases/{product_test_release_id}/trace/export.csv")
def export_product_test_release_trace_csv(
    product_test_release_id: str,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_target_id: str = Query(""),
    product_test_environment_id: str = Query(""),
    product_test_case_id: str = Query(""),
    result_status: str = Query(""),
    defect_status: str = Query(""),
):
    _ensure_admin_role(current_role_name)
    rows = build_product_test_trace_export_rows(
        database_session,
        product_test_release_id=product_test_release_id,
        product_test_target_id=product_test_target_id,
        product_test_environment_id=product_test_environment_id,
        product_test_case_id=product_test_case_id,
        result_status=result_status,
        defect_status=defect_status,
    )
    return _csv_streaming_response(rows=rows, file_name=f"{product_test_release_id}_trace.csv")


@admin_router.get("/product-test-runs/{product_test_run_id}/trace")
def render_product_test_run_trace_admin(
    product_test_run_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    try:
        release_id = get_release_id_by_run_id(database_session, product_test_run_id)
    except LookupError as exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exception)) from exception
    return RedirectResponse(url=f"/admin/product-test-releases/{release_id}/trace", status_code=303)


@admin_router.get("/product-test-runs/{product_test_run_id}/export.csv")
def export_product_test_run_csv(
    product_test_run_id: str,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    rows = build_product_test_run_export_rows(database_session, product_test_run_id)
    return _csv_streaming_response(rows=rows, file_name=f"{product_test_run_id}.csv")


@admin_router.get("/product-test-results/{product_test_result_id}/trace")
def render_product_test_result_trace_admin(
    product_test_result_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    try:
        release_id = get_release_id_by_result_id(database_session, product_test_result_id)
    except LookupError as exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exception)) from exception
    return RedirectResponse(url=f"/admin/product-test-releases/{release_id}/trace", status_code=303)


@admin_router.get("/product-test-system-check")
def render_product_test_system_check(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    detail = get_product_test_system_check(database_session)
    return _render_admin_shell_template(
        request=request,
        database_session=database_session,
        current_role_name=current_role_name,
        template_name="product_test_system_check_admin.html",
        page_title="Product Test Data Tracing System",
        extra_context=detail,
    )


@admin_router.post("/create_admin")
def create_admin_user_account(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    department_name: str = Form(...),
    display_name: str = Form(...),
    internal_title: str = Form(...),
    phone_number: str = Form(...),
    password: str = Form(...),
):
    _ensure_admin_role(current_role_name)
    normalized_department_name = department_name.strip()
    normalized_display_name = display_name.strip()
    normalized_internal_title = internal_title.strip()
    normalized_phone_number = phone_number.strip()
    normalized_password = password.strip()

    recent_test_results = list_recent_test_results(database_session=database_session, limit=50)
    templates = request.app.state.templates

    if (
        not normalized_department_name
        or not normalized_display_name
        or not normalized_internal_title
        or not normalized_phone_number
        or not normalized_password
    ):
        pending_tester_join_requests = _tester_accounts_for_admin(database_session)
        return templates.TemplateResponse(
            request=request,
            name="admin_dashboard.html",
            context={
                "request": request,
                "page_title": "Product Test Data Tracing System",
                "recent_test_results": recent_test_results,
                "current_role_name": current_role_name,
                "can_edit_all_data": current_role_name == ROLE_MASTER_ADMIN,
                **_admin_identity_context(database_session=database_session, request=request),
                "admin_create_error_message": "모든 항목을 입력해 주세요.",
                "admin_create_success_message": "",
                "tester_create_error_message": "",
                "tester_create_success_message": "",
                "form_submissions": _form_submissions_for_admin(database_session),
                "submission_summaries": _submission_summaries_for_admin(database_session),
                "pending_tester_join_requests": pending_tester_join_requests,
            },
            status_code=400,
        )

    existing_user_account = database_session.scalar(
        select(UserAccount).where(UserAccount.phone_number == normalized_phone_number)
    )
    if existing_user_account is not None:
        pending_tester_join_requests = _tester_accounts_for_admin(database_session)
        return templates.TemplateResponse(
            request=request,
            name="admin_dashboard.html",
            context={
                "request": request,
                "page_title": "Product Test Data Tracing System",
                "recent_test_results": recent_test_results,
                "current_role_name": current_role_name,
                "can_edit_all_data": current_role_name == ROLE_MASTER_ADMIN,
                **_admin_identity_context(database_session=database_session, request=request),
                "admin_create_error_message": "이미 등록된 전화번호입니다.",
                "admin_create_success_message": "",
                "tester_create_error_message": "",
                "tester_create_success_message": "",
                "form_submissions": _form_submissions_for_admin(database_session),
                "submission_summaries": _submission_summaries_for_admin(database_session),
                "pending_tester_join_requests": pending_tester_join_requests,
            },
            status_code=400,
        )

    new_admin_account = UserAccount(
        user_name=normalized_phone_number,
        password_hash=normalized_password,
        role_name=ROLE_ADMIN,
        display_name=normalized_display_name,
        phone_number=normalized_phone_number,
        company_name=None,
        department_name=normalized_department_name,
        internal_title=normalized_internal_title,
        is_approved=True,
    )
    database_session.add(new_admin_account)
    database_session.commit()

    recent_test_results = list_recent_test_results(database_session=database_session, limit=50)
    pending_tester_join_requests = _tester_accounts_for_admin(database_session)
    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={
            "request": request,
            "page_title": "Product Test Data Tracing System",
            "recent_test_results": recent_test_results,
            "current_role_name": current_role_name,
            "can_edit_all_data": current_role_name == ROLE_MASTER_ADMIN,
            **_admin_identity_context(database_session=database_session, request=request),
            "admin_create_error_message": "",
            "admin_create_success_message": "Admin 계정이 생성되었습니다.",
            "tester_create_error_message": "",
            "tester_create_success_message": "",
            "form_submissions": _form_submissions_for_admin(database_session),
            "submission_summaries": _submission_summaries_for_admin(database_session),
            "pending_tester_join_requests": pending_tester_join_requests,
        },
    )


@admin_router.post("/create_tester")
def create_tester_user_account(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    company_name: str = Form(...),
    display_name: str = Form(...),
    phone_number: str = Form(...),
    password: str = Form(...),
):
    _ensure_admin_role(current_role_name)
    normalized_company_name = company_name.strip()
    normalized_display_name = display_name.strip()
    normalized_phone_number = phone_number.strip()
    normalized_password = password.strip()

    recent_test_results = list_recent_test_results(database_session=database_session, limit=50)
    pending_tester_join_requests = _tester_accounts_for_admin(database_session)
    templates = request.app.state.templates

    if (
        not normalized_company_name
        or not normalized_display_name
        or not normalized_phone_number
        or not normalized_password
    ):
        return templates.TemplateResponse(
            request=request,
            name="admin_dashboard.html",
            context={
                "request": request,
                "page_title": "Product Test Data Tracing System",
                "recent_test_results": recent_test_results,
                "current_role_name": current_role_name,
                "can_edit_all_data": current_role_name == ROLE_MASTER_ADMIN,
                **_admin_identity_context(database_session=database_session, request=request),
                "admin_create_error_message": "",
                "admin_create_success_message": "",
                "tester_create_error_message": "모든 항목을 입력해 주세요.",
                "tester_create_success_message": "",
                "form_submissions": _form_submissions_for_admin(database_session),
                "submission_summaries": _submission_summaries_for_admin(database_session),
                "pending_tester_join_requests": pending_tester_join_requests,
            },
            status_code=400,
        )

    existing_user_account = database_session.scalar(
        select(UserAccount).where(UserAccount.phone_number == normalized_phone_number)
    )
    if existing_user_account is not None:
        return templates.TemplateResponse(
            request=request,
            name="admin_dashboard.html",
            context={
                "request": request,
                "page_title": "Product Test Data Tracing System",
                "recent_test_results": recent_test_results,
                "current_role_name": current_role_name,
                "can_edit_all_data": current_role_name == ROLE_MASTER_ADMIN,
                **_admin_identity_context(database_session=database_session, request=request),
                "admin_create_error_message": "",
                "admin_create_success_message": "",
                "tester_create_error_message": "이미 등록된 전화번호입니다.",
                "tester_create_success_message": "",
                "form_submissions": _form_submissions_for_admin(database_session),
                "submission_summaries": _submission_summaries_for_admin(database_session),
                "pending_tester_join_requests": pending_tester_join_requests,
            },
            status_code=400,
        )

    new_tester_account = UserAccount(
        user_name=normalized_phone_number,
        password_hash=normalized_password,
        role_name=ROLE_TESTER,
        display_name=normalized_display_name,
        phone_number=normalized_phone_number,
        company_name=normalized_company_name,
        department_name=None,
        is_approved=True,
    )
    database_session.add(new_tester_account)
    database_session.commit()

    recent_test_results = list_recent_test_results(database_session=database_session, limit=50)
    pending_tester_join_requests = _tester_accounts_for_admin(database_session)
    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={
            "request": request,
            "page_title": "Product Test Data Tracing System",
            "recent_test_results": recent_test_results,
            "current_role_name": current_role_name,
            "can_edit_all_data": current_role_name == ROLE_MASTER_ADMIN,
            **_admin_identity_context(database_session=database_session, request=request),
            "admin_create_error_message": "",
            "admin_create_success_message": "",
            "tester_create_error_message": "",
            "tester_create_success_message": "Tester 계정이 생성되었습니다.",
            "form_submissions": _form_submissions_for_admin(database_session),
            "submission_summaries": _submission_summaries_for_admin(database_session),
            "pending_tester_join_requests": pending_tester_join_requests,
        },
    )


@admin_router.post("/approve_tester_join")
def approve_tester_join_request(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    user_account_id: int = Form(...),
):
    _ensure_admin_role(current_role_name)
    user_account = database_session.get(UserAccount, user_account_id)
    if user_account is not None and user_account.role_name == "tester":
        user_account.is_approved = True
        database_session.commit()

    recent_test_results = list_recent_test_results(database_session=database_session, limit=50)
    pending_tester_join_requests = _tester_accounts_for_admin(database_session)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={
            "request": request,
            "page_title": "Product Test Data Tracing System",
            "recent_test_results": recent_test_results,
            "current_role_name": current_role_name,
            "can_edit_all_data": current_role_name == ROLE_MASTER_ADMIN,
            **_admin_identity_context(database_session=database_session, request=request),
            "admin_create_error_message": "",
            "admin_create_success_message": "업체 등록이 승인되었습니다.",
            "tester_create_error_message": "",
            "tester_create_success_message": "",
            "form_submissions": _form_submissions_for_admin(database_session),
            "submission_summaries": _submission_summaries_for_admin(database_session),
            "pending_tester_join_requests": pending_tester_join_requests,
        },
    )


@admin_router.post("/delete_tester_join")
def delete_tester_join_request(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    user_account_id: int = Form(...),
):
    _ensure_admin_role(current_role_name)
    user_account = database_session.get(UserAccount, user_account_id)
    if user_account is not None and user_account.role_name == "tester":
        database_session.delete(user_account)
        database_session.commit()

    recent_test_results = list_recent_test_results(database_session=database_session, limit=50)
    pending_tester_join_requests = _tester_accounts_for_admin(database_session)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={
            "request": request,
            "page_title": "Product Test Data Tracing System",
            "recent_test_results": recent_test_results,
            "current_role_name": current_role_name,
            "can_edit_all_data": current_role_name == ROLE_MASTER_ADMIN,
            **_admin_identity_context(database_session=database_session, request=request),
            "admin_create_error_message": "",
            "admin_create_success_message": "업체 회원이 삭제되었습니다.",
            "tester_create_error_message": "",
            "tester_create_success_message": "",
            "form_submissions": _form_submissions_for_admin(database_session),
            "submission_summaries": _submission_summaries_for_admin(database_session),
            "pending_tester_join_requests": pending_tester_join_requests,
        },
    )


@admin_router.post("/delete_admin_user")
def delete_admin_user_account(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    user_account_id: int = Form(...),
):
    _ensure_admin_role(current_role_name)
    target_admin_user_account = database_session.get(UserAccount, user_account_id)
    if target_admin_user_account is not None and target_admin_user_account.role_name == ROLE_ADMIN:
        current_phone_number = (request.cookies.get("phone_number") or "").strip()
        target_phone_number = (target_admin_user_account.phone_number or "").strip()
        if current_phone_number and target_phone_number and current_phone_number == target_phone_number:
            return RedirectResponse(url="/admin", status_code=303)
        database_session.delete(target_admin_user_account)
        database_session.commit()
    return RedirectResponse(url="/admin", status_code=303)


@admin_router.post("/submission/approve")
def approve_submission_by_submission_id(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    form_submission_id: str = Form(""),
):
    _ensure_admin_role(current_role_name)
    target_id = (form_submission_id or "").strip()
    if not target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="form_submission_id is required",
        )
    try:
        approve_submission(
            database_session=database_session,
            submission_id=target_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return RedirectResponse(url="/admin", status_code=303)


@admin_router.post("/submission/delete")
def delete_submission_by_form_submission_id(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    form_submission_id: str = Form(""),
):
    _ensure_admin_role(current_role_name)
    target_id = (form_submission_id or "").strip()
    if not target_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="form_submission_id is required",
        )
    try:
        delete_submission_and_rows(database_session=database_session, submission_id=target_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(url="/admin", status_code=303)




 




@admin_router.post("/rows/review_complete")
def mark_admin_rows_review_complete(
    test_result_review_complete_input: TestResultReviewCompleteInput,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    updated_count = mark_test_results_review_complete_by_ids(
        database_session=database_session,
        row_ids=test_result_review_complete_input.row_ids,
    )
    return {"message": "Rows review-completed.", "updated_count": updated_count}


@admin_router.post("/rows/review_pending")
def mark_admin_rows_review_pending(
    test_result_review_complete_input: TestResultReviewCompleteInput,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    updated_count = mark_test_results_review_pending_by_ids(
        database_session=database_session,
        row_ids=test_result_review_complete_input.row_ids,
    )
    return {"message": "Rows review-pending.", "updated_count": updated_count}


@admin_router.post("/dropdown_options/add")
def add_admin_dropdown_option(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    field_name: str = Form(...),
    option_value: str = Form(...),
):
    _ensure_admin_role(current_role_name)
    try:
        add_dropdown_option_if_missing(
            database_session=database_session,
            field_name=field_name,
            option_value=option_value,
        )
    except ValueError:
        return RedirectResponse(url="/admin", status_code=303)
    return RedirectResponse(url="/admin", status_code=303)


@admin_router.post("/dropdown_options/delete")
def delete_admin_dropdown_option(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    field_name: str = Form(...),
    option_value: str = Form(...),
):
    _ensure_admin_role(current_role_name)
    try:
        delete_dropdown_option_if_exists(
            database_session=database_session,
            field_name=field_name,
            option_value=option_value,
        )
    except ValueError:
        return RedirectResponse(url="/admin", status_code=303)
    return RedirectResponse(url="/admin", status_code=303)


@admin_router.get("/dropdown_options/{field_name}")
def list_admin_dropdown_options_by_field(
    field_name: str,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    try:
        option_values = list_dropdown_options_for_field(
            database_session=database_session,
            field_name=field_name,
        )
    except ValueError:
        option_values = []
    return {"field_name": field_name, "option_values": option_values}


@admin_router.get("/input_activity_status")
def get_input_activity_status(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    active_cutoff = get_utc_now_datetime() - timedelta(seconds=8)
    unreviewed = or_(TestResult.is_reviewed == False, TestResult.is_reviewed.is_(None))  # noqa: E712
    tester_draft_submission = exists(
        select(1).where(
            FormSubmission.submission_id == TestResult.form_submission_id,
            FormSubmission.status == "draft",
            FormSubmission.created_by_phone.is_not(None),
            exists(
                select(1).where(
                    UserAccount.phone_number == FormSubmission.created_by_phone,
                    UserAccount.role_name == ROLE_TESTER,
                )
            ),
        )
    )
    active_row_ids = list(
        database_session.scalars(
            select(TestResult.id).where(
                and_(
                    unreviewed,
                    tester_draft_submission,
                    TestResult.updated_at >= active_cutoff,
                )
            )
        )
    )
    active_user_rows = list(
        database_session.execute(
            select(UserAccount.company_name, UserAccount.display_name)
            .join(FormSubmission, UserAccount.phone_number == FormSubmission.created_by_phone)
            .join(TestResult, TestResult.form_submission_id == FormSubmission.submission_id)
            .where(
                and_(
                    unreviewed,
                    FormSubmission.status == "draft",
                    UserAccount.role_name == ROLE_TESTER,
                    TestResult.updated_at >= active_cutoff,
                )
            )
            .distinct()
        )
    )
    tracked_row_count = int(
        database_session.scalar(
            select(func.count(TestResult.id)).where(
                and_(
                    unreviewed,
                    tester_draft_submission,
                )
            )
        )
        or 0
    )
    normalized_user_names = []
    normalized_user_labels = []
    for company_name, display_name in active_user_rows:
        normalized_company_name = str(company_name or "").strip()
        normalized_display_name = str(display_name or "").strip()
        if normalized_display_name:
            normalized_user_names.append(normalized_display_name)
        if normalized_company_name and normalized_display_name:
            normalized_user_labels.append(f"{normalized_company_name} 업체 {normalized_display_name} 사용자")
        elif normalized_display_name:
            normalized_user_labels.append(f"{normalized_display_name} 사용자")
        elif normalized_company_name:
            normalized_user_labels.append(f"{normalized_company_name} 업체 사용자")
    return {
        "is_user_input_active": bool(active_row_ids),
        "active_row_ids": [int(row_id) for row_id in active_row_ids],
        "active_user_names": normalized_user_names,
        "active_user_labels": normalized_user_labels,
        "tracked_row_count": tracked_row_count,
    }


@admin_router.post("/qc/e2e-fill")
def start_admin_qc_e2e_fill_route(
    request: Request,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    if not is_qc_mode_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="QC mode required.",
        )
    admin_url = f"{request.url.scheme}://{request.url.netloc}/admin"
    ok, message = start_admin_qc_e2e_fill(admin_url=admin_url)
    status_code = 200 if ok else 409
    return JSONResponse({"ok": ok, "message": message}, status_code=status_code)


@admin_router.get("/rows/by_ids")
def list_admin_rows_by_ids(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    row_ids: list[int] = Query(default=[]),
):
    _ensure_admin_role(current_role_name)
    normalized_row_ids = sorted({int(row_id) for row_id in row_ids if int(row_id) > 0})
    if not normalized_row_ids:
        return {"rows": []}
    rows = list(
        database_session.scalars(
            select(TestResult).where(TestResult.id.in_(normalized_row_ids))
        )
    )

    def _to_text(value):
        if value is None:
            return ""
        return str(value)

    rows_payload = []
    for row in rows:
        rows_payload.append(
            {
                "id": int(row.id),
                "form_submission_id": _to_text(row.form_submission_id),
                "key_1": _to_text(row.key_1),
                "key_2": _to_text(row.key_2 or row.data_writer_name),
                "key_3": _to_text(row.key_3),
                "key_4": _to_text(row.key_4),
                "field_01": _to_text(row.field_01),
                "field_02": _to_text(row.field_02),
                "low_test_started_at": _to_text(row.low_test_started_at),
                "low_test_ended_at": _to_text(row.low_test_ended_at),
                "low_test_delta": _to_text(row.low_test_delta),
                "high_test_started_at": _to_text(row.high_test_started_at),
                "high_test_ended_at": _to_text(row.high_test_ended_at),
                "high_test_delta": _to_text(row.high_test_delta),
                "is_reviewed": bool(row.is_reviewed),
                "created_at": _to_text(row.created_at),
                "updated_at": _to_text(row.updated_at),
            }
        )
    return {"rows": rows_payload}
