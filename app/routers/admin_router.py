import csv
from io import BytesIO, StringIO

from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import ROLE_ADMIN, ROLE_MASTER_ADMIN, ROLE_TESTER
from app.services.logging_service import get_logger
from app.config import app_settings, is_qc_mode_enabled

_logger = get_logger("admin_router")
_client_logger = get_logger("client_browser")
from app.deps import current_role_name_dependency, database_session_dependency
from app.models import UserAccount, get_utc_now_datetime
from app.db import truncate_application_data
from app.services.admin_product_test_ui_service import (
    get_admin_product_test_ui_client_config_payload,
    get_first_blocking_prerequisite_field,
    list_product_test_id_candidates,
    validate_product_test_identifier_values,
)
from app.services.admin_qc_e2e_service import start_admin_qc_e2e_fill
from app.services.product_test_field_update_service import bulk_delete_product_test_entities, bulk_update_product_test_fields
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
    create_product_test_procedure,
    create_product_test_report,
    create_product_test_report_snapshot,
    create_product_test_release,
    create_product_test_target,
    create_product_test_target_definition,
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
    list_product_test_environments,
    list_product_test_procedures,
    list_product_test_report_snapshots,
    list_product_test_releases,
    list_product_test_reports,
    list_target_options,
    list_product_test_target_definitions,
    list_product_test_targets,
    reject_product_test_report,
)


admin_router = APIRouter(prefix="/admin", tags=["admin"])


# ── 브라우저 → 서버 파일 로그 ────────────────────────────────────────────────────

class _ClientLogEntry(BaseModel):
    level: str = Field(default="info", pattern="^(debug|info|warn|error)$")
    tag: str = Field(default="client")
    message: str = Field(max_length=4096)


@admin_router.post("/debug/client-log", status_code=204)
async def post_client_log(entries: list[_ClientLogEntry]) -> None:
    """브라우저 JS가 보내는 디버그 로그를 data/logs/client.log 에 기록한다."""
    import logging
    from datetime import datetime, timezone

    logs_dir = app_settings.data_directory_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "client.log"

    lines: list[str] = []
    for entry in entries:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        line = f"{ts} [{entry.level.upper():5}] [{entry.tag}] {entry.message}"
        lines.append(line)
        _client_logger.debug("[client] %s | %s", entry.tag, entry.message)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


ADMIN_FORM_NOTICE_CONFIG = {
    "draft_saved": {
        "message": "브라우저 임시저장 되었습니다.",
        "level": "success",
        "mode": "non_modal",
    },
    "draft_invalid_id": {
        "suffix": "자동제출 안 한다.",
        "level": "guide",
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
        "level": "guide",
        "mode": "non_modal",
    },
}


def _admin_dashboard_product_tracing_template_context(*, database_session: Session) -> dict:
    """admin_dashboard.html 표용 키. 식별자 규칙·안내·입력 순서는 ``GET /admin/api/product-test/ui/client-config`` 로 제공한다."""
    return {
        "release_rows": list_product_test_releases(database_session),
        "release_stage_values": RELEASE_STAGE_VALUES,
        "product_test_release_status_values": PRODUCT_TEST_RELEASE_STATUS_VALUES,
        "target_definition_rows": list_product_test_target_definitions(database_session),
        "target_definition_status_values": MASTER_ACTIVE_STATUS_VALUES,
        "target_rows": list_product_test_targets(database_session),
        "target_status_values": TARGET_STATUS_VALUES,
        "environment_rows": list_product_test_environments(database_session),
        "environment_status_values": ENVIRONMENT_STATUS_VALUES,
        "case_rows": list_product_test_cases(database_session),
        "case_status_values": MASTER_ACTIVE_STATUS_VALUES,
        "procedure_rows": list_product_test_procedures(database_session),
        "procedure_status_values": MASTER_ACTIVE_STATUS_VALUES,
        "evidence_type_values": EVIDENCE_TYPE_VALUES,
        "report_rows": list_product_test_reports(database_session),
        "report_type_values": REPORT_TYPE_VALUES,
    }


def _is_ajax_request(request: Request) -> bool:
    requested_with = (request.headers.get("x-requested-with") or "").strip().lower()
    accept_header = (request.headers.get("accept") or "").strip().lower()
    return requested_with == "xmlhttprequest" or "application/json" in accept_header


def _admin_create_error_response(request: Request, target_url: str, message: str):
    _logger.warning("[admin_router] error_response  url=%s  message=%s", target_url, message)
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
            payload["notice_level"] = "guide"
            payload["notice_mode"] = "non_modal"
            payload["dialog_title"] = ""
            payload["state_code"] = "invalid_id"
            return payload
    if "already exists" in lowered:
        duplicate_field_name = normalized.split(" ", 1)[0].strip().upper()
        dup_cfg = ADMIN_FORM_NOTICE_CONFIG["duplicate_id"]
        payload["notice_level"] = dup_cfg.get("level", "guide")
        payload["notice_mode"] = dup_cfg.get("mode", "non_modal")
        payload["dialog_title"] = ""
        payload["notice_message"] = (
            f"{dup_cfg.get('title', '중복 ID')}\n\n"
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


class AdminProductTestIdCandidatesRequest(BaseModel):
    form_action: str = ""
    field_name: str = ""
    values: dict[str, str] = Field(default_factory=dict)
    datalist_hints: dict[str, list[str]] = Field(default_factory=dict)


class AdminProductTestValidateIdentifiersRequest(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)


class AdminProductTestBlockingPrerequisiteRequest(BaseModel):
    form_action: str = ""
    target_field_name: str = ""
    values: dict[str, str] = Field(default_factory=dict)


class AdminProductTestFieldUpdateItem(BaseModel):
    entity_type: str
    entity_id: str
    field_name: str
    value: str = ""


class AdminProductTestBulkFieldUpdateRequest(BaseModel):
    updates: list[AdminProductTestFieldUpdateItem] = Field(default_factory=list)


class AdminProductTestBulkDeleteRequest(BaseModel):
    entity_type: str
    entity_ids: list[str] = Field(default_factory=list)


@admin_router.get("/api/product-test/ui/client-config")
def admin_product_test_ui_get_client_config(
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    payload = get_admin_product_test_ui_client_config_payload()
    payload["notice_config"] = ADMIN_FORM_NOTICE_CONFIG
    return payload


@admin_router.post("/api/product-test/ui/id-candidates")
def admin_product_test_ui_post_id_candidates(
    current_role_name: current_role_name_dependency,
    payload: AdminProductTestIdCandidatesRequest,
):
    _ensure_admin_role(current_role_name)
    candidates = list_product_test_id_candidates(
        form_action=payload.form_action,
        field_name=payload.field_name,
        values=payload.values,
        datalist_hints=payload.datalist_hints,
    )
    return {"ok": True, "candidates": candidates}


@admin_router.post("/api/product-test/ui/validate-identifiers")
def admin_product_test_ui_post_validate_identifiers(
    current_role_name: current_role_name_dependency,
    payload: AdminProductTestValidateIdentifiersRequest,
):
    _ensure_admin_role(current_role_name)
    errors = validate_product_test_identifier_values(payload.values)
    return {"ok": len(errors) == 0, "errors": errors}


@admin_router.post("/api/product-test/ui/first-blocking-prerequisite")
def admin_product_test_ui_post_first_blocking_prerequisite(
    current_role_name: current_role_name_dependency,
    payload: AdminProductTestBlockingPrerequisiteRequest,
):
    _ensure_admin_role(current_role_name)
    blocking = get_first_blocking_prerequisite_field(
        form_action=payload.form_action,
        target_field_name=payload.target_field_name,
        values=payload.values,
    )
    return {"ok": True, "blocking_field_name": blocking}


@admin_router.post("/api/product-test/fields/bulk-update")
def admin_product_test_bulk_field_update(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    payload: AdminProductTestBulkFieldUpdateRequest,
):
    _ensure_admin_role(current_role_name)
    actor_name = _admin_actor_name(database_session, request)
    try:
        result = bulk_update_product_test_fields(
            database_session,
            updates=[item.model_dump() for item in payload.updates],
            updated_by=actor_name,
        )
    except (ValueError, LookupError) as exception:
        database_session.rollback()
        return JSONResponse(
            status_code=400,
            content={"ok": False, "message": str(exception)},
        )
    return JSONResponse({"ok": True, **result})


@admin_router.post("/api/product-test/entities/bulk-delete")
def admin_product_test_bulk_delete_entities(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    payload: AdminProductTestBulkDeleteRequest,
):
    _ensure_admin_role(current_role_name)
    try:
        result = bulk_delete_product_test_entities(
            database_session,
            entity_type=payload.entity_type,
            entity_ids=payload.entity_ids,
        )
    except Exception as exception:
        database_session.rollback()
        return JSONResponse(
            status_code=400,
            content={"ok": False, "message": str(exception)},
        )
    return JSONResponse({"ok": True, **result})


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
            "product_test_release_id": "SQA_PRODUCT_TEST_RELEASE_ID-HRK_9000A-1.0.0-RC1",
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
            "product_test_release_id": "SQA_PRODUCT_TEST_RELEASE_ID-HRK_9000A-1.0.0-GA",
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
            "product_test_target_definition_id": "SQA_PRODUCT_TEST_TARGET_DEFINITION_ID-HRK_9000A",
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
            "product_test_target_definition_id": "SQA_PRODUCT_TEST_TARGET_DEFINITION_ID-MERCUSYS_MR30G",
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
            "product_test_target_id": "SQA_PRODUCT_TEST_TARGET_ID-HRK_9000A-SN001",
            "product_test_target_definition_id": "SQA_PRODUCT_TEST_TARGET_DEFINITION_ID-HRK_9000A",
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



@admin_router.post("/product-test-environments/create")
def create_product_test_environment_admin(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_environment_id: str = Form(""),
    product_test_environment_name: str = Form(""),
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
            product_test_environment_name=product_test_environment_name,
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

    if (
        not normalized_department_name
        or not normalized_display_name
        or not normalized_internal_title
        or not normalized_phone_number
        or not normalized_password
    ):
        return RedirectResponse(url="/admin?message=모든+항목을+입력해+주세요.&message_type=error", status_code=303)

    existing_user_account = database_session.scalar(
        select(UserAccount).where(UserAccount.phone_number == normalized_phone_number)
    )
    if existing_user_account is not None:
        return RedirectResponse(url="/admin?message=이미+등록된+전화번호입니다.&message_type=error", status_code=303)

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
    return RedirectResponse(url="/admin?message=Admin+계정이+생성되었습니다.&message_type=success", status_code=303)


@admin_router.post("/create_tester")
def create_tester_user_account(
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

    if (
        not normalized_company_name
        or not normalized_display_name
        or not normalized_phone_number
        or not normalized_password
    ):
        return RedirectResponse(url="/admin?message=모든+항목을+입력해+주세요.&message_type=error", status_code=303)

    existing_user_account = database_session.scalar(
        select(UserAccount).where(UserAccount.phone_number == normalized_phone_number)
    )
    if existing_user_account is not None:
        return RedirectResponse(url="/admin?message=이미+등록된+전화번호입니다.&message_type=error", status_code=303)

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
    return RedirectResponse(url="/admin?message=Tester+계정이+생성되었습니다.&message_type=success", status_code=303)


@admin_router.post("/approve_tester_join")
def approve_tester_join_request(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    user_account_id: int = Form(...),
):
    _ensure_admin_role(current_role_name)
    user_account = database_session.get(UserAccount, user_account_id)
    if user_account is not None and user_account.role_name == "tester":
        user_account.is_approved = True
        database_session.commit()
    return RedirectResponse(url="/admin?message=업체+등록이+승인되었습니다.&message_type=success", status_code=303)


@admin_router.post("/delete_tester_join")
def delete_tester_join_request(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    user_account_id: int = Form(...),
):
    _ensure_admin_role(current_role_name)
    user_account = database_session.get(UserAccount, user_account_id)
    if user_account is not None and user_account.role_name == "tester":
        database_session.delete(user_account)
        database_session.commit()
    return RedirectResponse(url="/admin?message=업체+회원이+삭제되었습니다.&message_type=success", status_code=303)


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


@admin_router.post("/qc/db-truncate")
def admin_qc_db_truncate_route(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    if not is_qc_mode_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="QC mode required.",
        )
    truncate_application_data()
    database_session.expire_all()
    return JSONResponse({"ok": True, "message": "Database truncated."})
