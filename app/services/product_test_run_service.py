from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import (
    ProductTestCase,
    ProductTestDefect,
    ProductTestEnvironment,
    ProductTestEnvironmentDefinition,
    ProductTestEvidence,
    ProductTestProcedure,
    ProductTestProcedureResult,
    ProductTestRelease,
    ProductTestReport,
    ProductTestReportSnapshot,
    ProductTestResult,
    ProductTestRun,
    ProductTestStatusTransition,
    ProductTestTarget,
    ProductTestTargetDefinition,
    get_utc_now_datetime,
)


RUN_STATUS_VALUES = ("running", "finished", "cancelled")
RESULT_STATUS_VALUES = ("testing", "passed", "failed", "blocked", "skipped")
PROCEDURE_RESULT_STATUS_VALUES = ("testing", "passed", "failed", "blocked", "skipped")
REPORT_TYPE_VALUES = ("FULL", "WIFI", "REGRESSION", "HOTFIX", "CUSTOMER")
REPORT_STATUS_VALUES = ("DRAFT", "APPROVED", "REJECTED")
SNAPSHOT_TYPE_VALUES = ("draft", "approval", "manual", "export")
SNAPSHOT_FORMAT_VALUES = ("json",)
DEFECT_SEVERITY_VALUES = ("critical", "major", "minor", "trivial")
DEFECT_PRIORITY_VALUES = ("high", "medium", "low")
DEFECT_STATUS_VALUES = ("opened", "assigned", "fixed", "retested", "closed", "rejected")
EVIDENCE_TYPE_VALUES = (
    "screenshot",
    "log_file",
    "photo",
    "video",
    "csv",
    "excel",
    "measurement_file",
    "text",
    "other",
)
SKIPPED_REASON_EXAMPLES = (
    "out_of_scope",
    "not_applicable",
    "covered_by_previous_result",
    "covered_by_other_test_case",
    "excluded_by_sqa_decision",
    "duplicate_test",
)
BLOCKED_REASON_EXAMPLES = (
    "blocker_resolved",
    "environment_issue",
    "target_issue",
    "tool_issue",
    "permission_issue",
    "precondition_not_met",
)

RELEASE_STAGE_VALUES = ("RC", "GA", "HF")
PRODUCT_TEST_RELEASE_STATUS_VALUES = ("DRAFT", "TESTING", "REJECTED", "APPROVED", "ARCHIVED")
MASTER_ACTIVE_STATUS_VALUES = ("DRAFT", "ACTIVE", "DEPRECATED")
TARGET_STATUS_VALUES = ("ACTIVE", "INACTIVE", "DAMAGED", "RETURNED", "ARCHIVED")
ENVIRONMENT_STATUS_VALUES = ("ACTIVE", "INACTIVE", "ARCHIVED")
ENTITY_TYPE_VALUES = (
    "product_test_release",
    "product_test_run",
    "product_test_result",
    "product_test_procedure_result",
    "product_test_defect",
    "product_test_report",
)

ENTITY_TRANSITIONS = {
    "product_test_release": {
        "DRAFT": {"TESTING"},
        "TESTING": {"APPROVED", "REJECTED"},
        "REJECTED": {"TESTING"},
        "APPROVED": set(),
        "ARCHIVED": set(),
    },
    "product_test_run": {
        "running": {"finished", "cancelled"},
        "finished": set(),
        "cancelled": set(),
    },
    "product_test_result": {
        "testing": {"passed", "failed", "blocked", "skipped"},
        "blocked": {"testing"},
        "skipped": {"testing"},
        "failed": set(),
        "passed": set(),
    },
    "product_test_procedure_result": {
        "testing": {"passed", "failed", "blocked", "skipped"},
        "blocked": {"testing"},
        "skipped": {"testing"},
        "failed": set(),
        "passed": set(),
    },
    "product_test_defect": {
        "opened": {"assigned", "rejected"},
        "assigned": {"fixed", "rejected"},
        "fixed": {"retested"},
        "retested": {"closed", "assigned"},
        "closed": set(),
        "rejected": set(),
    },
    "product_test_report": {
        "DRAFT": {"APPROVED", "REJECTED"},
        "APPROVED": set(),
        "REJECTED": set(),
    },
}

_sample_product_test_release_rows = [
    {
        "product_test_release_id": "QA_PTREL-HRK_9000A-1.0.0-RC1",
        "upstream_release_id": "HRK_9000A-1.0.0",
        "upstream_release_system": "Huvitz Software Release System",
        "release_stage": "RC",
        "release_sequence": 1,
        "product_test_release_status": "TESTING",
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
        "product_test_release_status": "DRAFT",
        "created_at": "2026-05-05 11:00:00",
        "created_by": "SQA_MASTER",
        "updated_at": "2026-05-05 11:00:00",
        "updated_by": "SQA_MASTER",
        "remark": "",
    },
]

_sample_product_test_target_definition_rows = [
    {
        "product_test_target_definition_id": "QA_PTTGTDEF-HRK_9000A",
        "product_code": "HRK_9000A",
        "manufacturer": "Huvitz",
        "model_name": "HRK-9000A",
        "hardware_revision": "A",
        "default_software_version": "1.0.0",
        "default_firmware_version": "1.0.0",
        "product_test_target_definition_status": "ACTIVE",
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
        "product_test_target_definition_status": "ACTIVE",
        "created_at": "2026-05-05 09:30:00",
        "created_by": "SQA_MASTER",
        "updated_at": "2026-05-05 09:30:00",
        "updated_by": "SQA_MASTER",
        "remark": "",
    },
]

_sample_product_test_target_rows = [
    {
        "product_test_target_id": "QA_PTTGT-HRK_9000A-SN001",
        "product_test_target_definition_id": "QA_PTTGTDEF-HRK_9000A",
        "serial_number": "SN001",
        "software_version": "1.0.0",
        "firmware_version": "1.0.0",
        "manufacture_lot": "LOT-202605",
        "product_test_target_status": "ACTIVE",
        "created_at": "2026-05-05 10:00:00",
        "created_by": "SQA_MASTER",
        "updated_at": "2026-05-05 10:00:00",
        "updated_by": "SQA_MASTER",
        "remark": "",
    }
]

_sample_product_test_environment_definition_rows = [
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
        "product_test_environment_definition_status": "ACTIVE",
        "created_at": "2026-05-05 09:00:00",
        "created_by": "SQA_MASTER",
        "updated_at": "2026-05-05 09:00:00",
        "updated_by": "SQA_MASTER",
        "remark": "",
    }
]

_sample_product_test_environment_rows = [
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
        "product_test_environment_status": "ACTIVE",
        "created_at": "2026-05-05 09:15:00",
        "created_by": "SQA_MASTER",
        "updated_at": "2026-05-05 09:15:00",
        "updated_by": "SQA_MASTER",
        "remark": "",
    }
]

_sample_product_test_case_rows = [
    {
        "product_test_case_id": "QA_PTCASE-WIFI-AP_CONFIG-001",
        "product_test_case_title": "WiFi AP 설정 적합성 검증",
        "test_category": "WiFi",
        "test_objective": "RS9116 WiFi 모듈 기준으로 AP 설정이 권장 조건을 만족하는지 확인",
        "precondition": "시험 대상 AP 관리자 화면 접근 가능",
        "expected_result": "AP 설정값이 RS9116 모듈 권장 조건을 만족해야 함",
        "product_test_case_status": "ACTIVE",
        "created_at": "2026-05-05 08:30:00",
        "created_by": "SQA_MASTER",
        "updated_at": "2026-05-05 08:30:00",
        "updated_by": "SQA_MASTER",
        "remark": "",
    }
]

_sample_product_test_procedure_rows = [
    {
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-001",
            "product_test_case_id": "QA_PTCASE-WIFI-AP_CONFIG-001",
        "procedure_sequence": 1,
        "procedure_action": "WiFi Band 분리설정 확인",
        "expected_result": "2.4GHz와 5GHz SSID가 분리되어 있어야 함",
        "acceptance_criteria": "2.4GHz, 5GHz의 SSID를 분리하는 것을 권장",
        "required_evidence_type": "screenshot",
        "product_test_procedure_status": "ACTIVE",
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
        "expected_result": "2.4GHz는 1~11번 고정 채널, 5GHz는 DFS가 아닌 36, 40, 44, 48 채널이어야 함",
        "acceptance_criteria": "2.4GHz는 1~11번 채널 고정 사용 권장. 5GHz는 DFS가 아닌 36, 40, 44, 48 채널 고정 사용 권장",
        "required_evidence_type": "screenshot",
        "product_test_procedure_status": "ACTIVE",
        "created_at": "2026-05-05 08:41:00",
        "created_by": "SQA_MASTER",
        "updated_at": "2026-05-05 08:41:00",
        "updated_by": "SQA_MASTER",
        "remark": "5GHz에서 DFS 채널을 사용하는 경우 WiFi 모듈이 AP를 검색하지 못할 수 있음.",
    },
    {
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-003",
            "product_test_case_id": "QA_PTCASE-WIFI-AP_CONFIG-001",
        "procedure_sequence": 3,
        "procedure_action": "Channel Bandwidth 설정 확인",
        "expected_result": "Channel Bandwidth가 20MHz로 설정되어 있어야 함",
        "acceptance_criteria": "20MHz 사용 권장",
        "required_evidence_type": "screenshot",
        "product_test_procedure_status": "active",
        "created_at": "2026-05-05 08:42:00",
        "created_by": "SQA_MASTER",
        "updated_at": "2026-05-05 08:42:00",
        "updated_by": "SQA_MASTER",
        "remark": "WiFi 모듈 RS9116은 20MHz만 지원함.",
    },
    {
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-004",
            "product_test_case_id": "QA_PTCASE-WIFI-AP_CONFIG-001",
        "procedure_sequence": 4,
        "procedure_action": "WiFi 규격 Mode 설정 확인",
        "expected_result": "WiFi Mode가 802.11 a/b/g/n, WiFi 4 호환 범위여야 함",
        "acceptance_criteria": "802.11 a/b/g/n, WiFi 4 권장",
        "required_evidence_type": "screenshot",
        "product_test_procedure_status": "active",
        "created_at": "2026-05-05 08:43:00",
        "created_by": "SQA_MASTER",
        "updated_at": "2026-05-05 08:43:00",
        "updated_by": "SQA_MASTER",
        "remark": "일반적으로 하위 호환은 되나 WiFi 6(ax)부터 Beacon 제어 방식 차이로 parsing 이 안 될 가능성이 있음.",
    },
    {
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-005",
            "product_test_case_id": "QA_PTCASE-WIFI-AP_CONFIG-001",
        "procedure_sequence": 5,
        "procedure_action": "WiFi Security 설정 확인",
        "expected_result": "AP Security가 WPA2로 설정되어 있어야 함",
        "acceptance_criteria": "WPA2 설정 권장",
        "required_evidence_type": "screenshot",
        "product_test_procedure_status": "active",
        "created_at": "2026-05-05 08:44:00",
        "created_by": "SQA_MASTER",
        "updated_at": "2026-05-05 08:44:00",
        "updated_by": "SQA_MASTER",
        "remark": "WPA3 설정 시 접속 오류 발생 가능.",
    },
]


def _now_text() -> str:
    return get_utc_now_datetime().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _normalize_identifier_segment(value: str) -> str:
    normalized = str(value or "").strip()
    normalized = normalized.replace("?", " UNKNOWN ")
    normalized = normalized.replace("(", " ").replace(")", " ")
    normalized = re.sub(r"[\/\\\s:\*\|\"'<>]+", "_", normalized)
    normalized = normalized.replace("-", "_")
    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_").upper()


def build_product_code(manufacturer: str, model_name: str) -> str:
    left = _normalize_identifier_segment(manufacturer)
    right = _normalize_identifier_segment(model_name)
    if not left or not right:
        raise ValueError("manufacturer and model_name are required for product_code normalization.")
    return f"{left}_{right}"


def _as_dict(row: Any, columns: list[str]) -> dict[str, Any]:
    return {column_name: getattr(row, column_name) for column_name in columns}


def _commit_or_rollback(database_session: Session) -> None:
    try:
        database_session.commit()
    except Exception:
        database_session.rollback()
        raise


def _validate_in(value: str, allowed_values: tuple[str, ...], field_name: str) -> str:
    normalized = str(value or "").strip()
    if normalized not in allowed_values:
        raise ValueError(f"invalid {field_name}.")
    return normalized


_PRODUCT_TEST_ID_RULES: dict[str, re.Pattern[str]] = {
    "product_test_release_id": re.compile(r"^QA_PTREL-[A-Z0-9_]+-[0-9]+(?:\.[0-9]+)*-(?:RC[0-9]+|GA|HF[0-9]+)$"),
    "product_test_target_definition_id": re.compile(r"^QA_PTTGTDEF-[A-Z0-9_]+$"),
    "product_test_target_id": re.compile(r"^QA_PTTGT-[A-Z0-9_]+-[A-Z0-9_]+$"),
    "product_test_environment_definition_id": re.compile(r"^QA_PTENVDEF-[A-Z0-9_]+(?:-[A-Z0-9_]+){2,}$"),
    "product_test_environment_id": re.compile(r"^QA_PTENV-[A-Z0-9_]+(?:-[A-Z0-9_]+){2,}-\d{8}-\d{3}$"),
    "product_test_case_id": re.compile(r"^QA_PTCASE-[A-Z0-9_]+(?:-[A-Z0-9_]+)+-\d{3}$"),
    "product_test_procedure_id": re.compile(r"^QA_PTPROC-[A-Z0-9_]+(?:-[A-Z0-9_]+)+-\d{3}$"),
}

PRODUCT_TEST_IDENTIFIER_GUIDES: dict[str, str] = {
    "product_test_release_id": "PRODUCT_TEST_RELEASE_ID 작성규칙위반. QA_PTREL-ITEM-1.0.0-RC1 쓰거나 QA_PTREL-ITEM-1.0.0-GA 써라.",
    "product_test_target_definition_id": "PRODUCT_TEST_TARGET_DEFINITION_ID 작성규칙위반. QA_PTTGTDEF-HRK_9000A 써라.",
    "product_test_target_id": "PRODUCT_TEST_TARGET_ID 작성규칙위반. QA_PTTGT-HRK_9000A-SN001 써라.",
    "product_test_environment_definition_id": "PRODUCT_TEST_ENVIRONMENT_DEFINITION_ID 작성규칙위반. QA_PTENVDEF-COMPANY-CITY-ROOM 써라.",
    "product_test_environment_id": "PRODUCT_TEST_ENVIRONMENT_ID 작성규칙위반. QA_PTENV-COMPANY-CITY-ROOM-YYYYMMDD-001 써라.",
    "product_test_case_id": "PRODUCT_TEST_CASE_ID 작성규칙위반. QA_PTCASE-WIFI-AP_CONFIG-001 써라.",
    "product_test_procedure_id": "PRODUCT_TEST_PROCEDURE_ID 작성규칙위반. QA_PTPROC-WIFI-AP_CONFIG-001-001 써라.",
}


def get_product_test_identifier_client_rules() -> dict[str, str]:
    return {field_name: pattern.pattern for field_name, pattern in _PRODUCT_TEST_ID_RULES.items()}


def get_product_test_identifier_guides() -> dict[str, str]:
    return dict(PRODUCT_TEST_IDENTIFIER_GUIDES)


def _validate_product_test_identifier_format(field_name: str, field_value: str) -> str:
    normalized = str(field_value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    pattern = _PRODUCT_TEST_ID_RULES.get(field_name)
    if pattern is not None and not pattern.fullmatch(normalized):
        raise ValueError(f"{field_name} format is invalid.")
    if "/" in normalized or "\\" in normalized or re.search(r"\s", normalized):
        raise ValueError(f"{field_name} format is invalid.")
    return normalized


def _next_prefixed_id(database_session: Session, model, column_name: str, prefix: str) -> str:
    values = list(
        database_session.scalars(
            select(getattr(model, column_name)).where(getattr(model, column_name).like(f"{prefix}-%"))
        )
    )
    max_number = 0
    for value in values:
        match = re.search(r"-(\d+)$", str(value or ""))
        if not match:
            continue
        max_number = max(max_number, int(match.group(1)))
    return f"{prefix}-{max_number + 1:04d}"


def _insert_status_transition(
    database_session: Session,
    *,
    entity_type: str,
    entity_id: str,
    from_status: str | None,
    to_status: str,
    transition_reason: str,
    transitioned_by: str,
) -> ProductTestStatusTransition:
    _validate_in(entity_type, ENTITY_TYPE_VALUES, "entity_type")
    today_text = get_utc_now_datetime().astimezone().strftime("%Y%m%d")
    transition_id = _next_prefixed_id(
        database_session,
        ProductTestStatusTransition,
        "product_test_status_transition_id",
        f"QA_PTST-{today_text}",
    )
    now_text = _now_text()
    row = ProductTestStatusTransition(
        product_test_status_transition_id=transition_id,
        entity_type=entity_type,
        entity_id=entity_id,
        from_status=(from_status or "").strip() or None,
        to_status=to_status,
        transition_reason=(transition_reason or "").strip() or None,
        transitioned_at=now_text,
        transitioned_by=transitioned_by,
        created_at=now_text,
        created_by=transitioned_by,
        remark=None,
    )
    database_session.add(row)
    return row


def _status_column_name(entity_type: str) -> str:
    return {
        "product_test_release": "product_test_release_status",
        "product_test_run": "product_test_run_status",
        "product_test_result": "product_test_result_status",
        "product_test_procedure_result": "product_test_procedure_result_status",
        "product_test_defect": "product_test_defect_status",
        "product_test_report": "product_test_report_status",
    }[entity_type]


def _entity_model(entity_type: str):
    return {
        "product_test_release": ProductTestRelease,
        "product_test_run": ProductTestRun,
        "product_test_result": ProductTestResult,
        "product_test_procedure_result": ProductTestProcedureResult,
        "product_test_defect": ProductTestDefect,
        "product_test_report": ProductTestReport,
    }[entity_type]


def _load_entity_row(database_session: Session, entity_type: str, entity_id: str):
    entity_model = _entity_model(entity_type)
    row = database_session.get(entity_model, entity_id)
    if row is None:
        raise LookupError(f"{entity_type} not found.")
    return row


def _raise_locked_release_error() -> None:
    raise ValueError(
        "This Product Test Release has an approved Product Test Report. Source records are locked. Create a new run/result or use an admin correction flow."
    )


def _release_is_locked(database_session: Session, product_test_release_id: str) -> bool:
    approved_report_count = (
        database_session.scalar(
            select(func.count()).select_from(ProductTestReport).where(
                ProductTestReport.product_test_release_id == product_test_release_id,
                ProductTestReport.product_test_report_status == "APPROVED",
            )
        )
        or 0
    )
    return int(approved_report_count) > 0


def _ensure_release_not_locked_for_source_mutation(
    database_session: Session,
    *,
    product_test_release_id: str,
) -> None:
    if _release_is_locked(database_session, product_test_release_id):
        _raise_locked_release_error()


def _ensure_run_not_locked_for_source_mutation(
    database_session: Session,
    *,
    product_test_run_id: str,
) -> ProductTestRun:
    run_row = database_session.get(ProductTestRun, product_test_run_id)
    if run_row is None:
        raise LookupError("Run not found.")
    _ensure_release_not_locked_for_source_mutation(
        database_session,
        product_test_release_id=run_row.product_test_release_id,
    )
    return run_row


def _ensure_result_not_locked_for_source_mutation(
    database_session: Session,
    *,
    product_test_result_id: str,
) -> ProductTestResult:
    result_row = database_session.get(ProductTestResult, product_test_result_id)
    if result_row is None:
        raise LookupError("Result not found.")
    run_row = database_session.get(ProductTestRun, result_row.product_test_run_id)
    if run_row is None:
        raise LookupError("Run not found.")
    _ensure_release_not_locked_for_source_mutation(
        database_session,
        product_test_release_id=run_row.product_test_release_id,
    )
    return result_row


def _ensure_defect_not_locked_for_source_mutation(
    database_session: Session,
    *,
    product_test_defect_id: str,
) -> ProductTestDefect:
    defect_row = database_session.get(ProductTestDefect, product_test_defect_id)
    if defect_row is None:
        raise LookupError("Defect not found.")
    _ensure_result_not_locked_for_source_mutation(
        database_session,
        product_test_result_id=defect_row.product_test_result_id,
    )
    return defect_row


def _validate_transition_guard(
    database_session: Session,
    *,
    entity_type: str,
    row: Any,
    current_status: str,
    to_status: str,
    transition_reason: str,
    transitioned_by: str,
    field_updates: dict[str, Any],
) -> None:
    reason_text = str(transition_reason or "").strip()
    if entity_type == "product_test_release":
        if to_status == "ARCHIVED":
            raise ValueError("ARCHIVED is deprecated and not a normal transition target.")
        return
    if entity_type == "product_test_run":
        if to_status == "finished" and not str(field_updates.get("finished_at") or "").strip():
            raise ValueError("finished_at is required.")
        if to_status == "cancelled":
            cancel_reason = str(field_updates.get("cancel_reason") or reason_text).strip()
            if not cancel_reason:
                raise ValueError("cancel_reason is required.")
            if not str(field_updates.get("cancelled_by") or transitioned_by).strip():
                raise ValueError("cancelled_by is required.")
        return
    if entity_type in {"product_test_result", "product_test_procedure_result"}:
        if to_status in {"failed", "blocked", "skipped"} and not reason_text:
            raise ValueError("judgement_reason is required for failed, blocked, skipped.")
        return
    if entity_type == "product_test_defect":
        original_result_row = database_session.get(ProductTestResult, row.product_test_result_id)
        if original_result_row is None:
            raise ValueError("Original product_test_result not found.")
        scoped_evidence_count = database_session.scalar(
            select(func.count(ProductTestEvidence.product_test_evidence_id)).where(
                ProductTestEvidence.product_test_result_id == row.product_test_result_id,
                ProductTestEvidence.product_test_defect_id == row.product_test_defect_id,
            )
        ) or 0
        if to_status == "assigned" and not str(field_updates.get("assigned_to") or "").strip():
            raise ValueError("assigned_to is required.")
        if to_status in {"assigned", "fixed"} and row.defect_severity in {"critical", "major"} and int(scoped_evidence_count) <= 0:
            raise ValueError("critical/major defect requires at least one linked evidence before assigned or fixed.")
        if to_status == "fixed":
            if not str(field_updates.get("fixed_at") or "").strip():
                raise ValueError("fixed_at is required.")
            if not str(field_updates.get("fixed_by") or transitioned_by).strip():
                raise ValueError("fixed_by is required.")
            if not str(field_updates.get("fix_description") or "").strip():
                raise ValueError("fix_description is required.")
        if to_status == "retested":
            retest_product_test_result_id = str(field_updates.get("retest_product_test_result_id") or "").strip()
            if not retest_product_test_result_id:
                raise ValueError("retest_product_test_result_id is required.")
            if not str(field_updates.get("retested_at") or "").strip():
                raise ValueError("retested_at is required.")
            if not str(field_updates.get("retested_by") or transitioned_by).strip():
                raise ValueError("retested_by is required.")
            retest_result_row = database_session.get(ProductTestResult, retest_product_test_result_id)
            if retest_result_row is None:
                raise ValueError("Unknown retest_product_test_result_id.")
            if retest_result_row.product_test_result_id == original_result_row.product_test_result_id:
                raise ValueError("retest_product_test_result_id must point to a new Product Test Result.")
            if retest_result_row.product_test_case_id != original_result_row.product_test_case_id:
                raise ValueError("retest result must have the same product_test_case_id as the original defect result.")
            if retest_result_row.product_test_result_status != "passed":
                raise ValueError("retest result must be passed before defect can be marked retested.")
        if to_status == "closed":
            if current_status != "retested":
                raise ValueError("closed requires previous status retested.")
            if not str(field_updates.get("closed_at") or "").strip():
                raise ValueError("closed_at is required.")
            if not str(field_updates.get("closed_by") or transitioned_by).strip():
                raise ValueError("closed_by is required.")
            if not str(row.retest_product_test_result_id or "").strip():
                raise ValueError("retest_product_test_result_id is required before close.")
            retest_result_row = database_session.get(ProductTestResult, row.retest_product_test_result_id)
            if retest_result_row is None or retest_result_row.product_test_result_status != "passed":
                raise ValueError("retest result must be passed before close.")
        if to_status == "rejected" and not reason_text:
            raise ValueError("rejection_reason is required.")
        return
    if entity_type == "product_test_report":
        if to_status == "APPROVED":
            open_defect_count = database_session.scalar(
                select(func.count(ProductTestDefect.product_test_defect_id))
                .join(ProductTestResult, ProductTestResult.product_test_result_id == ProductTestDefect.product_test_result_id)
                .join(ProductTestRun, ProductTestRun.product_test_run_id == ProductTestResult.product_test_run_id)
                .where(
                    ProductTestRun.product_test_release_id == row.product_test_release_id,
                    ProductTestDefect.product_test_defect_status.in_(("opened", "assigned", "fixed", "retested")),
                )
            ) or 0
            if int(open_defect_count) > 0:
                raise ValueError("Open defects exist for this release. Approval is blocked.")
            if not str(field_updates.get("approved_at") or "").strip():
                raise ValueError("approved_at is required.")
            if not str(field_updates.get("approved_by") or transitioned_by).strip():
                raise ValueError("approved_by is required.")
        if to_status == "REJECTED":
            if not reason_text:
                raise ValueError("rejection_reason is required.")
            if not str(field_updates.get("rejected_at") or "").strip():
                raise ValueError("rejected_at is required.")
            if not str(field_updates.get("rejected_by") or transitioned_by).strip():
                raise ValueError("rejected_by is required.")
        return


def ensure_product_test_status_transition_recorded(
    database_session: Session,
    *,
    entity_type: str,
    entity_id: str,
    to_status: str,
    transition_reason: str,
    transitioned_by: str,
    **field_updates: Any,
) -> dict[str, Any]:
    row = _load_entity_row(database_session, entity_type, entity_id)
    status_column_name = _status_column_name(entity_type)
    current_status = str(getattr(row, status_column_name) or "").strip()
    new_status = str(to_status or "").strip()
    allowed_next_values = ENTITY_TRANSITIONS.get(entity_type, {}).get(current_status)
    if allowed_next_values is None:
        raise ValueError(f"Unsupported current status: {current_status}")
    if new_status not in allowed_next_values:
        raise ValueError(f"Forbidden transition: {entity_type} {current_status} -> {new_status}")
    _validate_transition_guard(
        database_session,
        entity_type=entity_type,
        row=row,
        current_status=current_status,
        to_status=new_status,
        transition_reason=transition_reason,
        transitioned_by=transitioned_by,
        field_updates=field_updates,
    )
    setattr(row, status_column_name, new_status)
    _insert_status_transition(
        database_session,
        entity_type=entity_type,
        entity_id=entity_id,
        from_status=current_status,
        to_status=new_status,
        transition_reason=transition_reason,
        transitioned_by=transitioned_by,
    )
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "from_status": current_status,
        "to_status": new_status,
    }


def _query_all_rows(database_session: Session, model, order_by_column: str | None = None) -> list[Any]:
    statement = select(model)
    if order_by_column:
        statement = statement.order_by(getattr(model, order_by_column))
    return list(database_session.scalars(statement))


def _list_with_fallback(
    database_session: Session,
    *,
    model,
    columns: list[str],
    fallback_rows: list[dict[str, Any]],
    order_by_column: str | None = None,
) -> list[dict[str, Any]]:
    rows = _query_all_rows(database_session, model, order_by_column)
    if rows:
        return [_as_dict(row, columns) for row in rows]
    return [dict(row) for row in fallback_rows]


def list_product_test_releases(database_session: Session) -> list[dict[str, Any]]:
    return _list_with_fallback(
        database_session,
        model=ProductTestRelease,
        columns=[
            "product_test_release_id",
            "upstream_release_id",
            "upstream_release_system",
            "release_stage",
            "release_sequence",
            "product_test_release_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
        fallback_rows=_sample_product_test_release_rows,
        order_by_column="created_at",
    )


def list_product_test_target_definitions(database_session: Session) -> list[dict[str, Any]]:
    return _list_with_fallback(
        database_session,
        model=ProductTestTargetDefinition,
        columns=[
            "product_test_target_definition_id",
            "product_code",
            "manufacturer",
            "model_name",
            "hardware_revision",
            "default_software_version",
            "default_firmware_version",
            "product_test_target_definition_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
        fallback_rows=_sample_product_test_target_definition_rows,
        order_by_column="created_at",
    )


def list_product_test_targets(database_session: Session) -> list[dict[str, Any]]:
    return _list_with_fallback(
        database_session,
        model=ProductTestTarget,
        columns=[
            "product_test_target_id",
            "product_test_target_definition_id",
            "serial_number",
            "software_version",
            "firmware_version",
            "manufacture_lot",
            "product_test_target_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
        fallback_rows=_sample_product_test_target_rows,
        order_by_column="created_at",
    )


def list_product_test_environment_definitions(database_session: Session) -> list[dict[str, Any]]:
    return _list_with_fallback(
        database_session,
        model=ProductTestEnvironmentDefinition,
        columns=[
            "product_test_environment_definition_id",
            "product_test_environment_definition_name",
            "test_country",
            "test_city",
            "test_company",
            "test_building",
            "test_floor",
            "test_room",
            "network_type",
            "test_computer_name",
            "operating_system_version",
            "test_tool_name",
            "test_tool_version",
            "power_voltage",
            "power_frequency",
            "power_connector_type",
            "power_condition",
            "product_test_environment_definition_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
        fallback_rows=_sample_product_test_environment_definition_rows,
        order_by_column="created_at",
    )


def list_product_test_environments(database_session: Session) -> list[dict[str, Any]]:
    return _list_with_fallback(
        database_session,
        model=ProductTestEnvironment,
        columns=[
            "product_test_environment_id",
            "product_test_environment_definition_id",
            "product_test_environment_name",
            "test_computer_name",
            "operating_system_version",
            "test_tool_version",
            "network_type",
            "power_voltage",
            "power_frequency",
            "power_connector_type",
            "captured_at",
            "product_test_environment_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
        fallback_rows=_sample_product_test_environment_rows,
        order_by_column="created_at",
    )


def list_product_test_cases(database_session: Session) -> list[dict[str, Any]]:
    return _list_with_fallback(
        database_session,
        model=ProductTestCase,
        columns=[
            "product_test_case_id",
            "product_test_case_title",
            "test_category",
            "test_objective",
            "precondition",
            "expected_result",
            "product_test_case_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
        fallback_rows=_sample_product_test_case_rows,
        order_by_column="created_at",
    )


def list_product_test_procedures(database_session: Session) -> list[dict[str, Any]]:
    return _list_with_fallback(
        database_session,
        model=ProductTestProcedure,
        columns=[
            "product_test_procedure_id",
            "product_test_case_id",
            "procedure_sequence",
            "procedure_action",
            "expected_result",
            "acceptance_criteria",
            "required_evidence_type",
            "product_test_procedure_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
        fallback_rows=_sample_product_test_procedure_rows,
        order_by_column="product_test_case_id",
    )


def list_release_options(database_session: Session) -> list[dict[str, Any]]:
    return list_product_test_releases(database_session)


def list_target_options(database_session: Session) -> list[dict[str, Any]]:
    return list_product_test_targets(database_session)


def list_environment_options(database_session: Session) -> list[dict[str, Any]]:
    return list_product_test_environments(database_session)


def list_case_options(database_session: Session) -> list[dict[str, Any]]:
    return list_product_test_cases(database_session)


def _find_fallback_row(rows: list[dict[str, Any]], key_name: str, key_value: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get(key_name) == key_value:
            return dict(row)
    return None


def create_product_test_release(
    database_session: Session,
    *,
    product_test_release_id: str,
    upstream_release_id: str,
    upstream_release_system: str,
    release_stage: str,
    product_test_release_status: str,
    actor_name: str,
    remark: str,
) -> dict[str, Any]:
    release_id = _validate_product_test_identifier_format("product_test_release_id", product_test_release_id)
    upstream_id = str(upstream_release_id or "").strip()
    upstream_system = str(upstream_release_system or "").strip()
    stage = _validate_in(str(release_stage or "").strip().upper(), RELEASE_STAGE_VALUES, "release_stage")
    status_value = _validate_in(
        str(product_test_release_status or "").strip().upper(),
        PRODUCT_TEST_RELEASE_STATUS_VALUES,
        "product_test_release_status",
    )
    if not release_id or not upstream_id or not upstream_system:
        raise ValueError("product_test_release_id, upstream_release_id, upstream_release_system are required.")
    if database_session.get(ProductTestRelease, release_id) is not None:
        raise ValueError("product_test_release_id already exists.")
    if stage == "GA":
        release_sequence = 0
    else:
        current_max_sequence = (
            database_session.scalar(
                select(func.max(ProductTestRelease.release_sequence)).where(
                    ProductTestRelease.upstream_release_id == upstream_id,
                    ProductTestRelease.release_stage == stage,
                )
            )
            or 0
        )
        release_sequence = int(current_max_sequence) + 1
    now_text = _now_text()
    row = ProductTestRelease(
        product_test_release_id=release_id,
        upstream_release_id=upstream_id,
        upstream_release_system=upstream_system,
        release_stage=stage,
        release_sequence=release_sequence,
        product_test_release_status=status_value,
        created_at=now_text,
        created_by=actor_name,
        updated_at=now_text,
        updated_by=actor_name,
        remark=str(remark or "").strip() or None,
    )
    database_session.add(row)
    _insert_status_transition(
        database_session,
        entity_type="product_test_release",
        entity_id=release_id,
        from_status=None,
        to_status=status_value,
        transition_reason="create_release",
        transitioned_by=actor_name,
    )
    _commit_or_rollback(database_session)
    return _as_dict(
        row,
        [
            "product_test_release_id",
            "upstream_release_id",
            "upstream_release_system",
            "release_stage",
            "release_sequence",
            "product_test_release_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
    )


def create_product_test_target_definition(
    database_session: Session,
    *,
    product_test_target_definition_id: str,
    product_code: str,
    manufacturer: str,
    model_name: str,
    hardware_revision: str,
    default_software_version: str,
    default_firmware_version: str,
    product_test_target_definition_status: str,
    actor_name: str,
    remark: str,
) -> dict[str, Any]:
    definition_id = _validate_product_test_identifier_format("product_test_target_definition_id", product_test_target_definition_id)
    manufacturer_value = str(manufacturer or "").strip()
    model_name_value = str(model_name or "").strip()
    if not definition_id or not manufacturer_value or not model_name_value:
        raise ValueError("product_test_target_definition_id, manufacturer, model_name are required.")
    if database_session.get(ProductTestTargetDefinition, definition_id) is not None:
        raise ValueError("product_test_target_definition_id already exists.")
    normalized_product_code = str(product_code or "").strip() or build_product_code(manufacturer_value, model_name_value)
    status_value = _validate_in(
        str(product_test_target_definition_status or "").strip().upper(),
        MASTER_ACTIVE_STATUS_VALUES,
        "product_test_target_definition_status",
    )
    now_text = _now_text()
    row = ProductTestTargetDefinition(
        product_test_target_definition_id=definition_id,
        product_code=normalized_product_code,
        manufacturer=manufacturer_value,
        model_name=model_name_value,
        hardware_revision=str(hardware_revision or "").strip() or None,
        default_software_version=str(default_software_version or "").strip() or None,
        default_firmware_version=str(default_firmware_version or "").strip() or None,
        product_test_target_definition_status=status_value,
        created_at=now_text,
        created_by=actor_name,
        updated_at=now_text,
        updated_by=actor_name,
        remark=str(remark or "").strip() or None,
    )
    database_session.add(row)
    _commit_or_rollback(database_session)
    return _as_dict(
        row,
        [
            "product_test_target_definition_id",
            "product_code",
            "manufacturer",
            "model_name",
            "hardware_revision",
            "default_software_version",
            "default_firmware_version",
            "product_test_target_definition_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
    )


def create_product_test_target(
    database_session: Session,
    *,
    product_test_target_id: str,
    product_test_target_definition_id: str,
    serial_number: str,
    software_version: str,
    firmware_version: str,
    manufacture_lot: str,
    product_test_target_status: str,
    actor_name: str,
    remark: str,
) -> dict[str, Any]:
    target_id = _validate_product_test_identifier_format("product_test_target_id", product_test_target_id)
    definition_id = str(product_test_target_definition_id or "").strip()
    serial_number_value = str(serial_number or "").strip()
    if not target_id or not definition_id or not serial_number_value:
        raise ValueError("product_test_target_id, product_test_target_definition_id, serial_number are required.")
    if database_session.get(ProductTestTarget, target_id) is not None:
        raise ValueError("product_test_target_id already exists.")
    if database_session.get(ProductTestTargetDefinition, definition_id) is None:
        raise ValueError("Unknown product_test_target_definition_id.")
    status_value = _validate_in(
        str(product_test_target_status or "").strip().upper(),
        TARGET_STATUS_VALUES,
        "product_test_target_status",
    )
    now_text = _now_text()
    row = ProductTestTarget(
        product_test_target_id=target_id,
        product_test_target_definition_id=definition_id,
        serial_number=serial_number_value,
        software_version=str(software_version or "").strip() or None,
        firmware_version=str(firmware_version or "").strip() or None,
        manufacture_lot=str(manufacture_lot or "").strip() or None,
        product_test_target_status=status_value,
        created_at=now_text,
        created_by=actor_name,
        updated_at=now_text,
        updated_by=actor_name,
        remark=str(remark or "").strip() or None,
    )
    database_session.add(row)
    _commit_or_rollback(database_session)
    return _as_dict(
        row,
        [
            "product_test_target_id",
            "product_test_target_definition_id",
            "serial_number",
            "software_version",
            "firmware_version",
            "manufacture_lot",
            "product_test_target_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
    )


def create_product_test_environment_definition(
    database_session: Session,
    *,
    product_test_environment_definition_id: str,
    product_test_environment_definition_name: str,
    test_country: str,
    test_city: str,
    test_company: str,
    test_building: str,
    test_floor: str,
    test_room: str,
    network_type: str,
    test_computer_name: str,
    operating_system_version: str,
    test_tool_name: str,
    test_tool_version: str,
    power_voltage: str,
    power_frequency: str,
    power_connector_type: str,
    power_condition: str,
    product_test_environment_definition_status: str,
    actor_name: str,
    remark: str,
) -> dict[str, Any]:
    definition_id = _validate_product_test_identifier_format("product_test_environment_definition_id", product_test_environment_definition_id)
    definition_name = str(product_test_environment_definition_name or "").strip()
    if not definition_id or not definition_name:
        raise ValueError("product_test_environment_definition_id and name are required.")
    if database_session.get(ProductTestEnvironmentDefinition, definition_id) is not None:
        raise ValueError("product_test_environment_definition_id already exists.")
    status_value = _validate_in(
        str(product_test_environment_definition_status or "").strip().upper(),
        MASTER_ACTIVE_STATUS_VALUES,
        "product_test_environment_definition_status",
    )
    now_text = _now_text()
    row = ProductTestEnvironmentDefinition(
        product_test_environment_definition_id=definition_id,
        product_test_environment_definition_name=definition_name,
        test_country=str(test_country or "").strip() or None,
        test_city=str(test_city or "").strip() or None,
        test_company=str(test_company or "").strip() or None,
        test_building=str(test_building or "").strip() or None,
        test_floor=str(test_floor or "").strip() or None,
        test_room=str(test_room or "").strip() or None,
        network_type=str(network_type or "").strip() or None,
        test_computer_name=str(test_computer_name or "").strip() or None,
        operating_system_version=str(operating_system_version or "").strip() or None,
        test_tool_name=str(test_tool_name or "").strip() or None,
        test_tool_version=str(test_tool_version or "").strip() or None,
        power_voltage=str(power_voltage or "").strip() or None,
        power_frequency=str(power_frequency or "").strip() or None,
        power_connector_type=str(power_connector_type or "").strip() or None,
        power_condition=str(power_condition or "").strip() or None,
        product_test_environment_definition_status=status_value,
        created_at=now_text,
        created_by=actor_name,
        updated_at=now_text,
        updated_by=actor_name,
        remark=str(remark or "").strip() or None,
    )
    database_session.add(row)
    _commit_or_rollback(database_session)
    return _as_dict(
        row,
        [
            "product_test_environment_definition_id",
            "product_test_environment_definition_name",
            "test_country",
            "test_city",
            "test_company",
            "test_building",
            "test_floor",
            "test_room",
            "network_type",
            "test_computer_name",
            "operating_system_version",
            "test_tool_name",
            "test_tool_version",
            "power_voltage",
            "power_frequency",
            "power_connector_type",
            "power_condition",
            "product_test_environment_definition_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
    )


def create_product_test_environment(
    database_session: Session,
    *,
    product_test_environment_id: str,
    product_test_environment_definition_id: str,
    product_test_environment_name: str,
    test_computer_name: str,
    operating_system_version: str,
    test_tool_version: str,
    network_type: str,
    power_voltage: str,
    power_frequency: str,
    power_connector_type: str,
    captured_at: str,
    product_test_environment_status: str,
    actor_name: str,
    remark: str,
) -> dict[str, Any]:
    environment_id = _validate_product_test_identifier_format("product_test_environment_id", product_test_environment_id)
    definition_id = str(product_test_environment_definition_id or "").strip()
    environment_name = str(product_test_environment_name or "").strip()
    if not environment_id or not definition_id or not environment_name:
        raise ValueError("product_test_environment_id, definition_id, name are required.")
    if database_session.get(ProductTestEnvironment, environment_id) is not None:
        raise ValueError("product_test_environment_id already exists.")
    if database_session.get(ProductTestEnvironmentDefinition, definition_id) is None:
        raise ValueError("Unknown product_test_environment_definition_id.")
    status_value = _validate_in(
        str(product_test_environment_status or "").strip().upper(),
        ENVIRONMENT_STATUS_VALUES,
        "product_test_environment_status",
    )
    now_text = _now_text()
    row = ProductTestEnvironment(
        product_test_environment_id=environment_id,
        product_test_environment_definition_id=definition_id,
        product_test_environment_name=environment_name,
        test_computer_name=str(test_computer_name or "").strip() or None,
        operating_system_version=str(operating_system_version or "").strip() or None,
        test_tool_version=str(test_tool_version or "").strip() or None,
        network_type=str(network_type or "").strip() or None,
        power_voltage=str(power_voltage or "").strip() or None,
        power_frequency=str(power_frequency or "").strip() or None,
        power_connector_type=str(power_connector_type or "").strip() or None,
        captured_at=str(captured_at or "").strip() or None,
        product_test_environment_status=status_value,
        created_at=now_text,
        created_by=actor_name,
        updated_at=now_text,
        updated_by=actor_name,
        remark=str(remark or "").strip() or None,
    )
    database_session.add(row)
    _commit_or_rollback(database_session)
    return _as_dict(
        row,
        [
            "product_test_environment_id",
            "product_test_environment_definition_id",
            "product_test_environment_name",
            "test_computer_name",
            "operating_system_version",
            "test_tool_version",
            "network_type",
            "power_voltage",
            "power_frequency",
            "power_connector_type",
            "captured_at",
            "product_test_environment_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
    )


def create_product_test_case(
    database_session: Session,
    *,
    product_test_case_id: str,
    product_test_case_title: str,
    test_category: str,
    test_objective: str,
    precondition: str,
    expected_result: str,
    product_test_case_status: str,
    actor_name: str,
    remark: str,
) -> dict[str, Any]:
    case_id = _validate_product_test_identifier_format("product_test_case_id", product_test_case_id)
    title = str(product_test_case_title or "").strip()
    category = str(test_category or "").strip()
    if not case_id or not title or not category:
        raise ValueError("product_test_case_id, title, category are required.")
    if database_session.get(ProductTestCase, case_id) is not None:
        raise ValueError("product_test_case_id already exists.")
    status_value = _validate_in(
        str(product_test_case_status or "").strip().upper(),
        MASTER_ACTIVE_STATUS_VALUES,
        "product_test_case_status",
    )
    now_text = _now_text()
    row = ProductTestCase(
        product_test_case_id=case_id,
        product_test_case_title=title,
        test_category=category,
        test_objective=str(test_objective or "").strip() or None,
        precondition=str(precondition or "").strip() or None,
        expected_result=str(expected_result or "").strip() or None,
        product_test_case_status=status_value,
        created_at=now_text,
        created_by=actor_name,
        updated_at=now_text,
        updated_by=actor_name,
        remark=str(remark or "").strip() or None,
    )
    database_session.add(row)
    _commit_or_rollback(database_session)
    return _as_dict(
        row,
        [
            "product_test_case_id",
            "product_test_case_title",
            "test_category",
            "test_objective",
            "precondition",
            "expected_result",
            "product_test_case_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
    )


def create_product_test_procedure(
    database_session: Session,
    *,
    product_test_procedure_id: str,
    product_test_case_id: str,
    procedure_sequence: int,
    procedure_action: str,
    expected_result: str,
    acceptance_criteria: str,
    required_evidence_type: str,
    product_test_procedure_status: str,
    actor_name: str,
    remark: str,
) -> dict[str, Any]:
    procedure_id = _validate_product_test_identifier_format("product_test_procedure_id", product_test_procedure_id)
    case_id = str(product_test_case_id or "").strip()
    action_text = str(procedure_action or "").strip()
    acceptance_text = str(acceptance_criteria or "").strip()
    if not procedure_id or not case_id or not action_text or not acceptance_text:
        raise ValueError("product_test_procedure_id, product_test_case_id, procedure_action, acceptance_criteria are required.")
    if database_session.get(ProductTestProcedure, procedure_id) is not None:
        raise ValueError("product_test_procedure_id already exists.")
    if database_session.get(ProductTestCase, case_id) is None:
        raise ValueError("Unknown product_test_case_id.")
    status_value = _validate_in(
        str(product_test_procedure_status or "").strip().upper(),
        MASTER_ACTIVE_STATUS_VALUES,
        "product_test_procedure_status",
    )
    evidence_type = str(required_evidence_type or "").strip()
    if evidence_type:
        _validate_in(evidence_type, EVIDENCE_TYPE_VALUES, "required_evidence_type")
    now_text = _now_text()
    row = ProductTestProcedure(
        product_test_procedure_id=procedure_id,
        product_test_case_id=case_id,
        procedure_sequence=int(procedure_sequence),
        procedure_action=action_text,
        expected_result=str(expected_result or "").strip() or None,
        acceptance_criteria=acceptance_text,
        required_evidence_type=evidence_type or None,
        product_test_procedure_status=status_value,
        created_at=now_text,
        created_by=actor_name,
        updated_at=now_text,
        updated_by=actor_name,
        remark=str(remark or "").strip() or None,
    )
    database_session.add(row)
    _commit_or_rollback(database_session)
    return _as_dict(
        row,
        [
            "product_test_procedure_id",
            "product_test_case_id",
            "procedure_sequence",
            "procedure_action",
            "expected_result",
            "acceptance_criteria",
            "required_evidence_type",
            "product_test_procedure_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
    )


def _upsert_model_row(
    database_session: Session,
    model,
    primary_key_name: str,
    values: dict[str, Any],
):
    primary_key_value = values[primary_key_name]
    row = database_session.get(model, primary_key_value)
    if row is None:
        row = model(**values)
        database_session.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    return row


def _delete_row_if_exists(database_session: Session, model, primary_key_value: str) -> None:
    row = database_session.get(model, primary_key_value)
    if row is not None:
        database_session.delete(row)


def _ensure_seed_status_transition(
    database_session: Session,
    *,
    entity_type: str,
    entity_id: str,
    from_status: str | None,
    to_status: str,
    transition_reason: str,
    transitioned_by: str,
    transitioned_at: str,
    remark: str | None = None,
) -> ProductTestStatusTransition:
    existing_row = database_session.scalar(
        select(ProductTestStatusTransition).where(
            ProductTestStatusTransition.entity_type == entity_type,
            ProductTestStatusTransition.entity_id == entity_id,
            ProductTestStatusTransition.from_status == from_status,
            ProductTestStatusTransition.to_status == to_status,
            ProductTestStatusTransition.transition_reason == transition_reason,
        )
    )
    if existing_row is not None:
        existing_row.transitioned_at = transitioned_at
        existing_row.transitioned_by = transitioned_by
        existing_row.created_at = transitioned_at
        existing_row.created_by = transitioned_by
        existing_row.remark = remark
        return existing_row
    row = ProductTestStatusTransition(
        product_test_status_transition_id=_next_prefixed_id(
            database_session,
            ProductTestStatusTransition,
            "product_test_status_transition_id",
            "PTST",
        ),
        entity_type=entity_type,
        entity_id=entity_id,
        from_status=from_status,
        to_status=to_status,
        transition_reason=transition_reason,
        transitioned_at=transitioned_at,
        transitioned_by=transitioned_by,
        created_at=transitioned_at,
        created_by=transitioned_by,
        remark=remark,
    )
    database_session.add(row)
    return row


def seed_product_test_wifi_ap_configuration_sample_data(database_session: Session) -> None:
    actor_name = "SQA_MASTER"
    seed_created_at = "2026-05-04 09:00"
    seed_updated_at = "2026-05-04 10:30"

    target_definition_rows = [
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-HRK_9000A",
            "product_code": "HRK_9000A",
            "manufacturer": "Huvitz",
            "model_name": "HRK-9000A",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-HUVITZ_HLM_9000",
            "product_code": "HUVITZ_HLM_9000",
            "manufacturer": "Huvitz",
            "model_name": "HLM-9000",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-HUVITZ_HTR_TBD",
            "product_code": "HUVITZ_HTR_TBD",
            "manufacturer": "Huvitz",
            "model_name": "HTR(TBD)",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-HUVITZ_HDR_9000_OP",
            "product_code": "HUVITZ_HDR_9000_OP",
            "manufacturer": "Huvitz",
            "model_name": "HDR-9000_OP",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-HUVITZ_HDR_9000_JUNCTION_BOX",
            "product_code": "HUVITZ_HDR_9000_JUNCTION_BOX",
            "manufacturer": "Huvitz",
            "model_name": "HDR-9000_JUNCTION_BOX",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-HUVITZ_HDR_9000_UNKNOWN",
            "product_code": "HUVITZ_HDR_9000_UNKNOWN",
            "manufacturer": "Huvitz",
            "model_name": "HDR-9000_?",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-HUVITZ_HDC_9100",
            "product_code": "HUVITZ_HDC_9100",
            "manufacturer": "Huvitz",
            "model_name": "HDC-9100",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-MERCUSYS_MR30G",
            "product_code": "MERCUSYS_MR30G",
            "manufacturer": "MERCUSYS",
            "model_name": "MR30G",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-TBD_LENS",
            "product_code": "TBD_LENS",
            "manufacturer": "TBD",
            "model_name": "Lens",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-TBD_MODELAI",
            "product_code": "TBD_MODELAI",
            "manufacturer": "TBD",
            "model_name": "모델아이",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-TBD_JUNCTION_BOX_POWER_CABLE",
            "product_code": "TBD_JUNCTION_BOX_POWER_CABLE",
            "manufacturer": "TBD",
            "model_name": "Junction Box Power Cable",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-TBD_HDC_POWER_CABLE",
            "product_code": "TBD_HDC_POWER_CABLE",
            "manufacturer": "TBD",
            "model_name": "HDC Power Cable",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-TBD_HLM_POWER_CABLE_L_FORM_POWER_CABLE",
            "product_code": "TBD_HLM_POWER_CABLE_L_FORM_POWER_CABLE",
            "manufacturer": "TBD",
            "model_name": "HLM Power Cable : L-form Power Cable",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-TBD_OP_SIGNAL_AND_POWER_CABLE",
            "product_code": "TBD_OP_SIGNAL_AND_POWER_CABLE",
            "manufacturer": "TBD",
            "model_name": "OP Signal and Power Cable",
        },
        {
            "product_test_target_definition_id": "QA_PTTGTDEF-TBD_HDR_SIGNAL_AND_POWER_CABLE",
            "product_code": "TBD_HDR_SIGNAL_AND_POWER_CABLE",
            "manufacturer": "TBD",
            "model_name": "HDR Signal and Power Cable",
        },
    ]

    for item in target_definition_rows:
        _upsert_model_row(
            database_session,
            ProductTestTargetDefinition,
            "product_test_target_definition_id",
            {
                "product_test_target_definition_id": item["product_test_target_definition_id"],
                "product_code": item["product_code"],
                "manufacturer": item["manufacturer"],
                "model_name": item["model_name"],
                "hardware_revision": None,
                "default_software_version": None,
                "default_firmware_version": None,
                "product_test_target_definition_status": "active",
                "created_at": seed_created_at,
                "created_by": actor_name,
                "updated_at": seed_updated_at,
                "updated_by": actor_name,
                "remark": None,
            },
        )

    _upsert_model_row(
        database_session,
        ProductTestTarget,
        "product_test_target_id",
        {
            "product_test_target_id": "QA_PTTGT-MERCUSYS_MR30G-SN001",
            "product_test_target_definition_id": "QA_PTTGTDEF-MERCUSYS_MR30G",
            "serial_number": "SN001",
            "software_version": "1.0.0",
            "firmware_version": "1.0.3",
            "manufacture_lot": None,
            "product_test_target_status": "active",
            "created_at": seed_created_at,
            "created_by": actor_name,
            "updated_at": seed_updated_at,
            "updated_by": actor_name,
            "remark": None,
        },
    )

    _upsert_model_row(
        database_session,
        ProductTestEnvironmentDefinition,
        "product_test_environment_definition_id",
        {
            "product_test_environment_definition_id": "QA_PTENVDEF-HUVITZ-ANYANG-CONNECTIVITY_ROOM",
            "product_test_environment_definition_name": "Huvitz Anyang Connectivity Room Standard Environment",
            "test_country": "Korea",
            "test_city": "Anyang",
            "test_company": "Huvitz",
            "test_building": None,
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
            "created_at": seed_created_at,
            "created_by": actor_name,
            "updated_at": seed_updated_at,
            "updated_by": actor_name,
            "remark": None,
        },
    )

    _upsert_model_row(
        database_session,
        ProductTestEnvironment,
        "product_test_environment_id",
        {
            "product_test_environment_id": "QA_PTENV-HUVITZ-ANYANG-CONNECTIVITY_ROOM-20260504-001",
            "product_test_environment_definition_id": "QA_PTENVDEF-HUVITZ-ANYANG-CONNECTIVITY_ROOM",
            "product_test_environment_name": "Huvitz Anyang Connectivity Room Snapshot 20260504",
            "test_computer_name": "SQA-PC-01",
            "operating_system_version": "Windows 10",
            "test_tool_version": "1.0.0",
            "network_type": "ISOLATED_NETWORK",
            "power_voltage": "220V",
            "power_frequency": "60Hz",
            "power_connector_type": "OO_CONNECTOR",
            "captured_at": "2026-05-04 09:00",
            "product_test_environment_status": "active",
            "created_at": seed_created_at,
            "created_by": actor_name,
            "updated_at": seed_updated_at,
            "updated_by": actor_name,
            "remark": None,
        },
    )

    _upsert_model_row(
        database_session,
        ProductTestCase,
        "product_test_case_id",
        {
            "product_test_case_id": "QA_PTCASE-WIFI-AP_CONFIG-001",
            "product_test_case_title": "WiFi AP 설정 적합성 검증",
            "test_category": "WiFi",
            "test_objective": "RS9116 WiFi 모듈 기준으로 AP 설정이 권장 조건을 만족하는지 확인",
            "precondition": "시험 대상 AP 관리자 화면 접근 가능",
            "expected_result": "AP 설정값이 RS9116 모듈 권장 조건을 만족해야 함",
            "product_test_case_status": "active",
            "created_at": seed_created_at,
            "created_by": actor_name,
            "updated_at": seed_updated_at,
            "updated_by": actor_name,
            "remark": None,
        },
    )

    procedure_seed_rows = [
        {
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-001",
            "procedure_sequence": 1,
            "procedure_action": "WiFi Band 분리설정 확인",
            "expected_result": "2.4GHz와 5GHz SSID가 분리되어 있어야 함",
            "acceptance_criteria": "2.4GHz, 5GHz의 SSID를 분리하는 것을 권장",
            "required_evidence_type": "screenshot",
            "remark": "분리하지 않은 경우 임베디드 장비가 2.4GHz로 할당될 가능성이 높음. 원하는 SSID에 접근할 수 있도록 분리 권장.",
        },
        {
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-002",
            "procedure_sequence": 2,
            "procedure_action": "WiFi Channel 설정 확인",
            "expected_result": "2.4GHz는 1~11번 고정 채널, 5GHz는 DFS가 아닌 36, 40, 44, 48 채널이어야 함",
            "acceptance_criteria": "2.4GHz는 1~11번 채널 고정 사용 권장. 5GHz는 DFS 채널이 아닌 36, 40, 44, 48 채널 고정 사용 권장",
            "required_evidence_type": "screenshot",
            "remark": "5GHz에서 DFS 채널을 사용하는 경우 WiFi 모듈이 AP를 검색하지 못할 수 있음.",
        },
        {
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-003",
            "procedure_sequence": 3,
            "procedure_action": "Channel Bandwidth 설정 확인",
            "expected_result": "Channel Bandwidth가 20MHz로 설정되어 있어야 함",
            "acceptance_criteria": "20MHz 사용 권장",
            "required_evidence_type": "screenshot",
            "remark": "WiFi 모듈 RS9116은 20MHz만 지원함.",
        },
        {
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-004",
            "procedure_sequence": 4,
            "procedure_action": "WiFi 규격 Mode 설정 확인",
            "expected_result": "WiFi Mode가 802.11 a/b/g/n, WiFi 4 호환 범위여야 함",
            "acceptance_criteria": "802.11 a/b/g/n, WiFi 4 권장",
            "required_evidence_type": "screenshot",
            "remark": "일반적으로 하위 호환은 되나 WiFi 6(ax)부터 Beacon 제어 방식 차이로 AP에 따라 정상 parsing이 안 될 가능성이 있음.",
        },
        {
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-005",
            "procedure_sequence": 5,
            "procedure_action": "WiFi Security 설정 확인",
            "expected_result": "AP Security가 WPA2로 설정되어 있어야 함",
            "acceptance_criteria": "WPA2 설정 권장",
            "required_evidence_type": "screenshot",
            "remark": "WiFi 모듈 기준 WPA2 설정이 적용된 AP만 scan 가능. WPA3 설정 시 접속 오류 발생 가능.",
        },
    ]
    for item in procedure_seed_rows:
        _upsert_model_row(
            database_session,
            ProductTestProcedure,
            "product_test_procedure_id",
            {
                "product_test_procedure_id": item["product_test_procedure_id"],
                "product_test_case_id": "QA_PTCASE-WIFI-AP_CONFIG-001",
                "procedure_sequence": item["procedure_sequence"],
                "procedure_action": item["procedure_action"],
                "expected_result": item["expected_result"],
                "acceptance_criteria": item["acceptance_criteria"],
                "required_evidence_type": item["required_evidence_type"],
                "product_test_procedure_status": "active",
                "created_at": seed_created_at,
                "created_by": actor_name,
                "updated_at": seed_updated_at,
                "updated_by": actor_name,
                "remark": item["remark"],
            },
        )

    _upsert_model_row(
        database_session,
        ProductTestRelease,
        "product_test_release_id",
        {
            "product_test_release_id": "QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1",
            "upstream_release_id": "MERCUSYS_MR30G-1.0.0",
            "upstream_release_system": "DEV",
            "release_stage": "RC",
            "release_sequence": 1,
            "product_test_release_status": "testing",
            "created_at": seed_created_at,
            "created_by": actor_name,
            "updated_at": seed_updated_at,
            "updated_by": actor_name,
            "remark": None,
        },
    )

    _upsert_model_row(
        database_session,
        ProductTestRun,
        "product_test_run_id",
        {
            "product_test_run_id": "QA_PTRUN-20260504-0001",
            "product_test_release_id": "QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1",
            "product_test_target_id": "QA_PTTGT-MERCUSYS_MR30G-SN001",
            "product_test_environment_id": "QA_PTENV-HUVITZ-ANYANG-CONNECTIVITY_ROOM-20260504-001",
            "product_test_run_status": "finished",
            "started_at": "2026-05-04 10:00",
            "started_by": "Tester-A",
            "finished_at": "2026-05-04 10:30",
            "cancelled_at": None,
            "cancelled_by": None,
            "cancel_reason": None,
            "created_at": "2026-05-04 10:00",
            "created_by": "Tester-A",
            "updated_at": "2026-05-04 10:30",
            "updated_by": "Tester-A",
            "remark": None,
        },
    )

    _upsert_model_row(
        database_session,
        ProductTestResult,
        "product_test_result_id",
        {
            "product_test_result_id": "QA_PTRES-20260504-0001",
            "product_test_run_id": "QA_PTRUN-20260504-0001",
            "product_test_case_id": "QA_PTCASE-WIFI-AP_CONFIG-001",
            "product_test_result_status": "failed",
            "actual_result": "5GHz Channel이 DFS 채널로 설정되어 있고 Security가 WPA3로 설정되어 있음",
            "judgement_reason": "Procedure 2, Procedure 5 기준 미충족",
            "result_judged_at": "2026-05-04 10:30",
            "result_judged_by": "Tester-A",
            "created_at": "2026-05-04 10:00",
            "created_by": "Tester-A",
            "updated_at": "2026-05-04 10:30",
            "updated_by": "Tester-A",
            "remark": None,
        },
    )

    procedure_result_seed_rows = [
        {
            "product_test_procedure_result_id": "QA_PTPRES-20260504-0001",
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-001",
            "product_test_procedure_result_status": "passed",
            "actual_result": "2.4GHz와 5GHz SSID가 분리되어 있음",
            "judgement_reason": None,
        },
        {
            "product_test_procedure_result_id": "QA_PTPRES-20260504-0002",
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-002",
            "product_test_procedure_result_status": "failed",
            "actual_result": "5GHz Channel이 DFS 채널로 설정되어 있음",
            "judgement_reason": "DFS 채널 사용으로 RS9116 AP scan 실패 가능",
        },
        {
            "product_test_procedure_result_id": "QA_PTPRES-20260504-0003",
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-003",
            "product_test_procedure_result_status": "passed",
            "actual_result": "Channel Bandwidth 20MHz 확인",
            "judgement_reason": None,
        },
        {
            "product_test_procedure_result_id": "QA_PTPRES-20260504-0004",
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-004",
            "product_test_procedure_result_status": "passed",
            "actual_result": "WiFi Mode가 802.11 b/g/n 호환으로 설정됨",
            "judgement_reason": None,
        },
        {
            "product_test_procedure_result_id": "QA_PTPRES-20260504-0005",
            "product_test_procedure_id": "QA_PTPROC-WIFI-AP_CONFIG-001-005",
            "product_test_procedure_result_status": "failed",
            "actual_result": "AP Security가 WPA3로 설정되어 있음",
            "judgement_reason": "WPA2 권장 조건 미충족",
        },
    ]
    for item in procedure_result_seed_rows:
        _upsert_model_row(
            database_session,
            ProductTestProcedureResult,
            "product_test_procedure_result_id",
            {
                "product_test_procedure_result_id": item["product_test_procedure_result_id"],
                "product_test_result_id": "QA_PTRES-20260504-0001",
                "product_test_procedure_id": item["product_test_procedure_id"],
                "product_test_procedure_result_status": item["product_test_procedure_result_status"],
                "actual_result": item["actual_result"],
                "judgement_reason": item["judgement_reason"],
                "judged_at": "2026-05-04 10:30",
                "judged_by": "Tester-A",
                "created_at": "2026-05-04 10:00",
                "created_by": "Tester-A",
                "updated_at": "2026-05-04 10:30",
                "updated_by": "Tester-A",
                "remark": None,
            },
        )

    for index, procedure_result_id in enumerate(
        [
            "QA_PTPRES-20260504-0001",
            "QA_PTPRES-20260504-0002",
            "QA_PTPRES-20260504-0003",
            "QA_PTPRES-20260504-0004",
            "QA_PTPRES-20260504-0005",
        ],
        start=1,
    ):
        _upsert_model_row(
            database_session,
            ProductTestEvidence,
            "product_test_evidence_id",
            {
                "product_test_evidence_id": f"QA_PTEVD-20260504-{index:04d}",
                "product_test_result_id": "QA_PTRES-20260504-0001",
                "product_test_procedure_result_id": procedure_result_id,
                "product_test_defect_id": None,
                "product_test_evidence_type": "screenshot",
                "file_name": f"wifi_ap_config_{index:03d}.png",
                "file_path": f"/evidence/2026/05/04/wifi_ap_config_{index:03d}.png",
                "file_hash": None,
                "captured_at": "2026-05-04 10:25",
                "captured_by": "Tester-A",
                "created_at": "2026-05-04 10:25",
                "created_by": "Tester-A",
                "updated_at": "2026-05-04 10:25",
                "updated_by": "Tester-A",
                "remark": None,
            },
        )

    defect_seed_rows = [
        {
            "product_test_defect_id": "QA_PTDEF-20260504-0001",
            "product_test_procedure_result_id": "QA_PTPRES-20260504-0002",
            "defect_title": "5GHz DFS Channel 설정으로 RS9116 AP Scan 실패 가능",
            "defect_description": "5GHz 채널이 DFS 채널로 설정되어 있어 RS9116 WiFi 모듈이 AP를 검색하지 못할 수 있음.",
        },
        {
            "product_test_defect_id": "QA_PTDEF-20260504-0002",
            "product_test_procedure_result_id": "QA_PTPRES-20260504-0005",
            "defect_title": "WPA3 Security 설정으로 WiFi 접속 오류 가능",
            "defect_description": "WPA3 Security 설정으로 인해 RS9116 WiFi 모듈 접속 오류가 발생할 수 있음.",
        },
    ]
    for item in defect_seed_rows:
        _upsert_model_row(
            database_session,
            ProductTestDefect,
            "product_test_defect_id",
            {
                "product_test_defect_id": item["product_test_defect_id"],
                "product_test_result_id": "QA_PTRES-20260504-0001",
                "product_test_procedure_result_id": item["product_test_procedure_result_id"],
                "defect_title": item["defect_title"],
                "defect_description": item["defect_description"],
                "defect_severity": "major",
                "defect_priority": "high",
                "product_test_defect_status": "opened",
                "assigned_to": None,
                "fixed_at": None,
                "fixed_by": None,
                "fix_description": None,
                "retest_product_test_result_id": None,
                "retested_at": None,
                "retested_by": None,
                "closed_at": None,
                "closed_by": None,
                "rejection_reason": None,
                "created_at": "2026-05-04 10:30",
                "created_by": "Tester-A",
                "updated_at": "2026-05-04 10:30",
                "updated_by": "Tester-A",
                "remark": None,
            },
        )

    _upsert_model_row(
        database_session,
        ProductTestReport,
        "product_test_report_id",
        {
            "product_test_report_id": "QA_PTRPT-QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1-FULL-001",
            "product_test_release_id": "QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1",
            "product_test_report_type": "FULL",
            "product_test_report_status": "DRAFT",
            "product_test_report_title": "WiFi AP 설정 적합성 시험 보고서",
            "created_at": "2026-05-04 10:35",
            "created_by": actor_name,
            "updated_at": "2026-05-04 10:35",
            "updated_by": actor_name,
            "approved_at": None,
            "approved_by": None,
            "rejected_at": None,
            "rejected_by": None,
            "rejection_reason": None,
            "remark": None,
        },
    )

    transition_seed_rows = [
        ("product_test_release", "QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1", None, "DRAFT", "seed_release_drafted", actor_name, "2026-05-04 09:05"),
        ("product_test_release", "QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1", "DRAFT", "TESTING", "seed_release_testing", actor_name, "2026-05-04 09:10"),
        ("product_test_run", "QA_PTRUN-20260504-0001", None, "running", "seed_run_started", "Tester-A", "2026-05-04 10:00"),
        ("product_test_run", "QA_PTRUN-20260504-0001", "running", "finished", "seed_run_finished", "Tester-A", "2026-05-04 10:30"),
        ("product_test_result", "QA_PTRES-20260504-0001", None, "testing", "seed_result_started", "Tester-A", "2026-05-04 10:00"),
        ("product_test_result", "QA_PTRES-20260504-0001", "testing", "failed", "seed_result_failed", "Tester-A", "2026-05-04 10:30"),
        ("product_test_report", "QA_PTRPT-QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1-FULL-001", None, "DRAFT", "seed_report_drafted", actor_name, "2026-05-04 10:35"),
        ("product_test_defect", "QA_PTDEF-20260504-0001", None, "opened", "seed_defect_opened", "Tester-A", "2026-05-04 10:30"),
        ("product_test_defect", "QA_PTDEF-20260504-0002", None, "opened", "seed_defect_opened", "Tester-A", "2026-05-04 10:30"),
    ]
    for item in procedure_result_seed_rows:
        transition_seed_rows.append(
            (
                "product_test_procedure_result",
                item["product_test_procedure_result_id"],
                None,
                "testing",
                "seed_procedure_result_started",
                "Tester-A",
                "2026-05-04 10:00",
            )
        )
        transition_seed_rows.append(
            (
                "product_test_procedure_result",
                item["product_test_procedure_result_id"],
                "testing",
                item["product_test_procedure_result_status"],
                f"seed_procedure_result_{item['product_test_procedure_result_status']}",
                "Tester-A",
                "2026-05-04 10:30",
            )
        )
    for item in transition_seed_rows:
        _ensure_seed_status_transition(
            database_session,
            entity_type=item[0],
            entity_id=item[1],
            from_status=item[2],
            to_status=item[3],
            transition_reason=item[4],
            transitioned_by=item[5],
            transitioned_at=item[6],
        )

    # Clean up earlier seed/sample IDs after dependent rows have been rewired.
    legacy_procedure_ids = [
        "PTPROC-WIFI-AP-CONFIG-001-001",
        "PTPROC-WIFI-AP-CONFIG-001-002",
        "PTPROC-WIFI-AP-CONFIG-001-003",
        "PTPROC-WIFI-AP-CONFIG-001-004",
        "PTPROC-WIFI-AP-CONFIG-001-005",
    ]
    for legacy_procedure_id in legacy_procedure_ids:
        _delete_row_if_exists(database_session, ProductTestProcedure, legacy_procedure_id)
    _delete_row_if_exists(database_session, ProductTestCase, "PTCASE-WIFI-AP-CONFIG-001")

    _commit_or_rollback(database_session)


def list_runs(database_session: Session) -> list[dict[str, Any]]:
    rows = _query_all_rows(database_session, ProductTestRun, "started_at")
    return [
        _as_dict(
            row,
            [
                "product_test_run_id",
                "product_test_release_id",
                "product_test_target_id",
                "product_test_environment_id",
                "product_test_run_status",
                "started_at",
                "started_by",
                "finished_at",
                "cancelled_at",
                "cancelled_by",
                "cancel_reason",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
                "remark",
            ],
        )
        for row in rows
    ]


def start_run(
    database_session: Session,
    *,
    product_test_release_id: str,
    product_test_target_id: str,
    product_test_environment_id: str,
    started_by: str,
) -> dict[str, Any]:
    release = database_session.get(ProductTestRelease, str(product_test_release_id or "").strip())
    target = database_session.get(ProductTestTarget, str(product_test_target_id or "").strip())
    environment = database_session.get(ProductTestEnvironment, str(product_test_environment_id or "").strip())
    if release is None:
        raise ValueError("Unknown product_test_release_id.")
    if target is None:
        raise ValueError("Unknown product_test_target_id.")
    if environment is None:
        raise ValueError("Unknown product_test_environment_id.")
    _ensure_release_not_locked_for_source_mutation(
        database_session,
        product_test_release_id=release.product_test_release_id,
    )
    run_id = _next_prefixed_id(database_session, ProductTestRun, "product_test_run_id", "QA_PTRUN")
    now_text = _now_text()
    row = ProductTestRun(
        product_test_run_id=run_id,
        product_test_release_id=release.product_test_release_id,
        product_test_target_id=target.product_test_target_id,
        product_test_environment_id=environment.product_test_environment_id,
        product_test_run_status="running",
        started_at=now_text,
        started_by=started_by,
        finished_at=None,
        cancelled_at=None,
        cancelled_by=None,
        cancel_reason=None,
        created_at=now_text,
        created_by=started_by,
        updated_at=now_text,
        updated_by=started_by,
        remark=None,
    )
    database_session.add(row)
    _insert_status_transition(
        database_session,
        entity_type="product_test_run",
        entity_id=run_id,
        from_status=None,
        to_status="running",
        transition_reason="start_run",
        transitioned_by=started_by,
    )
    _commit_or_rollback(database_session)
    return _as_dict(
        row,
        [
            "product_test_run_id",
            "product_test_release_id",
            "product_test_target_id",
            "product_test_environment_id",
            "product_test_run_status",
            "started_at",
            "started_by",
            "finished_at",
            "cancelled_at",
            "cancelled_by",
            "cancel_reason",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
    )


def _summarize_result_status(procedure_rows: list[ProductTestProcedureResult]) -> str:
    if not procedure_rows:
        return "testing"
    statuses = [row.product_test_procedure_result_status for row in procedure_rows]
    if any(status_value == "failed" for status_value in statuses):
        return "failed"
    if all(status_value == "passed" for status_value in statuses):
        return "passed"
    if any(status_value == "blocked" for status_value in statuses):
        return "blocked"
    if all(status_value == "skipped" for status_value in statuses):
        return "skipped"
    return "testing"


def finish_run(database_session: Session, *, product_test_run_id: str, finished_by: str, reason: str) -> dict[str, Any]:
    run_row = _ensure_run_not_locked_for_source_mutation(
        database_session,
        product_test_run_id=product_test_run_id,
    )
    ensure_product_test_status_transition_recorded(
        database_session,
        entity_type="product_test_run",
        entity_id=product_test_run_id,
        to_status="finished",
        transition_reason=str(reason or "").strip() or "finish_run",
        transitioned_by=finished_by,
        finished_at=_now_text(),
    )
    now_text = _now_text()
    run_row.finished_at = now_text
    run_row.updated_at = now_text
    run_row.updated_by = finished_by
    _commit_or_rollback(database_session)
    return _as_dict(run_row, ["product_test_run_id", "finished_at", "product_test_run_status"])


def cancel_run(database_session: Session, *, product_test_run_id: str, cancelled_by: str, reason: str) -> dict[str, Any]:
    run_row = _ensure_run_not_locked_for_source_mutation(
        database_session,
        product_test_run_id=product_test_run_id,
    )
    reason_text = str(reason or "").strip() or "cancel_run"
    ensure_product_test_status_transition_recorded(
        database_session,
        entity_type="product_test_run",
        entity_id=product_test_run_id,
        to_status="cancelled",
        transition_reason=reason_text,
        transitioned_by=cancelled_by,
        cancelled_at=_now_text(),
        cancelled_by=cancelled_by,
        cancel_reason=reason_text,
    )
    now_text = _now_text()
    run_row.cancelled_at = now_text
    run_row.cancelled_by = cancelled_by
    run_row.cancel_reason = reason_text
    run_row.updated_at = now_text
    run_row.updated_by = cancelled_by
    _commit_or_rollback(database_session)
    return _as_dict(run_row, ["product_test_run_id", "cancelled_at", "product_test_run_status"])


def start_product_test_result(
    database_session: Session,
    *,
    product_test_run_id: str,
    product_test_case_id: str,
    started_by: str,
) -> dict[str, Any]:
    run_row = _ensure_run_not_locked_for_source_mutation(
        database_session,
        product_test_run_id=product_test_run_id,
    )
    if run_row.product_test_run_status != "running":
        raise ValueError("Only running run can create result.")
    case_row = database_session.get(ProductTestCase, product_test_case_id)
    if case_row is None:
        raise ValueError("Unknown product_test_case_id.")
    existing_row = database_session.scalar(
        select(ProductTestResult).where(
            ProductTestResult.product_test_run_id == product_test_run_id,
            ProductTestResult.product_test_case_id == product_test_case_id,
        ).order_by(ProductTestResult.created_at.desc())
    )
    if existing_row is not None:
        return _as_dict(
            existing_row,
            [
                "product_test_result_id",
                "product_test_run_id",
                "product_test_case_id",
                "product_test_result_status",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
                "remark",
            ],
        )
    procedures = list(
        database_session.scalars(
            select(ProductTestProcedure)
            .where(ProductTestProcedure.product_test_case_id == product_test_case_id)
            .order_by(ProductTestProcedure.procedure_sequence.asc())
        )
    )
    if not procedures:
        raise ValueError("No product_test_procedure rows found for this case.")
    result_id = _next_prefixed_id(database_session, ProductTestResult, "product_test_result_id", "QA_PTRES")
    now_text = _now_text()
    result_row = ProductTestResult(
        product_test_result_id=result_id,
        product_test_run_id=product_test_run_id,
        product_test_case_id=product_test_case_id,
        product_test_result_status="testing",
        actual_result=None,
        judgement_reason=None,
        result_judged_at=None,
        result_judged_by=None,
        created_at=now_text,
        created_by=started_by,
        updated_at=now_text,
        updated_by=started_by,
        remark=None,
    )
    database_session.add(result_row)
    _insert_status_transition(
        database_session,
        entity_type="product_test_result",
        entity_id=result_id,
        from_status=None,
        to_status="testing",
        transition_reason="start_product_test_result",
        transitioned_by=started_by,
    )
    for procedure_row in procedures:
        procedure_result_id = _next_prefixed_id(
            database_session,
            ProductTestProcedureResult,
            "product_test_procedure_result_id",
            "QA_PTPRES",
        )
        new_row = ProductTestProcedureResult(
            product_test_procedure_result_id=procedure_result_id,
            product_test_result_id=result_id,
            product_test_procedure_id=procedure_row.product_test_procedure_id,
            product_test_procedure_result_status="testing",
            actual_result=None,
            judgement_reason=None,
            judged_at=None,
            judged_by=None,
            created_at=now_text,
            created_by=started_by,
            updated_at=now_text,
            updated_by=started_by,
            remark=procedure_row.remark,
        )
        database_session.add(new_row)
        _insert_status_transition(
            database_session,
            entity_type="product_test_procedure_result",
            entity_id=procedure_result_id,
            from_status=None,
            to_status="testing",
            transition_reason="start_product_test_result",
            transitioned_by=started_by,
        )
    _commit_or_rollback(database_session)
    return _as_dict(
        result_row,
        [
            "product_test_result_id",
            "product_test_run_id",
            "product_test_case_id",
            "product_test_result_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
    )


def save_procedure_result(
    database_session: Session,
    *,
    product_test_result_id: str,
    product_test_procedure_result_id: str,
    next_status: str,
    actual_result: str,
    judgement_reason: str,
    remark: str,
    updated_by: str,
) -> dict[str, Any]:
    next_status_value = _validate_in(str(next_status or "").strip(), PROCEDURE_RESULT_STATUS_VALUES, "product_test_procedure_result_status")
    if next_status_value in {"failed", "blocked", "skipped"} and not str(judgement_reason or "").strip():
        raise ValueError("judgement_reason is required for failed, blocked, skipped.")
    result_row = _ensure_result_not_locked_for_source_mutation(
        database_session,
        product_test_result_id=product_test_result_id,
    )
    procedure_result_row = database_session.get(ProductTestProcedureResult, product_test_procedure_result_id)
    if procedure_result_row is None:
        raise LookupError("Result or procedure result not found.")
    if procedure_result_row.product_test_result_id != product_test_result_id:
        raise ValueError("procedure result scope mismatch.")
    if procedure_result_row.product_test_procedure_result_status != next_status_value:
        ensure_product_test_status_transition_recorded(
            database_session,
            entity_type="product_test_procedure_result",
            entity_id=product_test_procedure_result_id,
            to_status=next_status_value,
            transition_reason=str(judgement_reason or "").strip() or "procedure_result_update",
            transitioned_by=updated_by,
        )
    now_text = _now_text()
    procedure_result_row.actual_result = str(actual_result or "").strip() or None
    procedure_result_row.judgement_reason = str(judgement_reason or "").strip() or None
    procedure_result_row.judged_at = now_text
    procedure_result_row.judged_by = updated_by
    procedure_result_row.updated_at = now_text
    procedure_result_row.updated_by = updated_by
    procedure_result_row.remark = str(remark or "").strip() or None

    procedure_rows = list(
        database_session.scalars(
            select(ProductTestProcedureResult).where(
                ProductTestProcedureResult.product_test_result_id == product_test_result_id
            )
        )
    )
    summarized_status = _summarize_result_status(procedure_rows)
    if result_row.product_test_result_status != summarized_status:
        ensure_product_test_status_transition_recorded(
            database_session,
            entity_type="product_test_result",
            entity_id=product_test_result_id,
            to_status=summarized_status,
            transition_reason=(result_row.judgement_reason or "auto_summary"),
            transitioned_by=updated_by,
        )
    result_row.actual_result = " | ".join(
        row.actual_result for row in procedure_rows if row.actual_result
    ) or None
    result_row.judgement_reason = " | ".join(
        sorted({row.judgement_reason for row in procedure_rows if row.judgement_reason})
    ) or None
    result_row.result_judged_at = now_text
    result_row.result_judged_by = updated_by
    result_row.updated_at = now_text
    result_row.updated_by = updated_by
    _commit_or_rollback(database_session)
    return _as_dict(
        procedure_result_row,
        [
            "product_test_procedure_result_id",
            "product_test_result_id",
            "product_test_procedure_id",
            "product_test_procedure_result_status",
            "actual_result",
            "judgement_reason",
            "judged_at",
            "judged_by",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
    )


def save_evidence(
    database_session: Session,
    *,
    product_test_result_id: str,
    product_test_procedure_result_id: str,
    product_test_defect_id: str = "",
    product_test_evidence_type: str,
    file_path: str,
    created_by: str,
    remark: str,
) -> dict[str, Any]:
    result_row = _ensure_result_not_locked_for_source_mutation(
        database_session,
        product_test_result_id=str(product_test_result_id or "").strip(),
    )
    evidence_type = _validate_in(str(product_test_evidence_type or "").strip(), EVIDENCE_TYPE_VALUES, "product_test_evidence_type")
    file_path_value = str(file_path or "").strip()
    if not file_path_value:
        raise ValueError("file_path is required.")
    procedure_result_id = str(product_test_procedure_result_id or "").strip()
    if procedure_result_id:
        procedure_result_row = database_session.get(ProductTestProcedureResult, procedure_result_id)
        if procedure_result_row is None or procedure_result_row.product_test_result_id != result_row.product_test_result_id:
            raise ValueError("procedure result scope mismatch.")
    defect_id = str(product_test_defect_id or "").strip()
    if defect_id:
        defect_row = database_session.get(ProductTestDefect, defect_id)
        if defect_row is None or defect_row.product_test_result_id != result_row.product_test_result_id:
            raise ValueError("defect scope mismatch.")
        if procedure_result_id and defect_row.product_test_procedure_result_id and defect_row.product_test_procedure_result_id != procedure_result_id:
            raise ValueError("defect and procedure result scope mismatch.")
    evidence_id = _next_prefixed_id(database_session, ProductTestEvidence, "product_test_evidence_id", "QA_PTEVD")
    now_text = _now_text()
    file_name = file_path_value.split("/")[-1].split("\\")[-1]
    row = ProductTestEvidence(
        product_test_evidence_id=evidence_id,
        product_test_result_id=result_row.product_test_result_id,
        product_test_procedure_result_id=procedure_result_id or None,
        product_test_defect_id=defect_id or None,
        product_test_evidence_type=evidence_type,
        file_name=file_name or None,
        file_path=file_path_value,
        file_hash=None,
        captured_at=now_text,
        captured_by=created_by,
        created_at=now_text,
        created_by=created_by,
        updated_at=now_text,
        updated_by=created_by,
        remark=str(remark or "").strip() or None,
    )
    database_session.add(row)
    _commit_or_rollback(database_session)
    return _as_dict(
        row,
        [
            "product_test_evidence_id",
            "product_test_result_id",
            "product_test_procedure_result_id",
            "product_test_defect_id",
            "product_test_evidence_type",
            "file_name",
            "file_path",
            "file_hash",
            "captured_at",
            "captured_by",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
    )


def save_defect(
    database_session: Session,
    *,
    product_test_result_id: str,
    product_test_procedure_result_id: str,
    defect_title: str,
    defect_description: str,
    defect_severity: str,
    defect_priority: str,
    assigned_to: str,
    created_by: str,
    remark: str,
) -> dict[str, Any]:
    result_row = _ensure_result_not_locked_for_source_mutation(
        database_session,
        product_test_result_id=str(product_test_result_id or "").strip(),
    )
    title = str(defect_title or "").strip()
    description = str(defect_description or "").strip()
    if not title or not description:
        raise ValueError("defect_title and defect_description are required.")
    severity_value = _validate_in(str(defect_severity or "").strip(), DEFECT_SEVERITY_VALUES, "defect_severity")
    priority_value = _validate_in(str(defect_priority or "").strip(), DEFECT_PRIORITY_VALUES, "defect_priority")
    procedure_result_id = str(product_test_procedure_result_id or "").strip()
    procedure_result_row = None
    if procedure_result_id:
        procedure_result_row = database_session.get(ProductTestProcedureResult, procedure_result_id)
        if procedure_result_row is None or procedure_result_row.product_test_result_id != result_row.product_test_result_id:
            raise ValueError("procedure result scope mismatch.")
    failed_scope = result_row.product_test_result_status == "failed" or (
        procedure_result_row is not None and procedure_result_row.product_test_procedure_result_status == "failed"
    )
    if not failed_scope:
        raise ValueError("Defect can be created only from failed result or failed procedure result.")
    normalized_title = re.sub(r"\s+", " ", title).strip().lower()
    scoped_defect_rows = list(
        database_session.scalars(
            select(ProductTestDefect).where(
                ProductTestDefect.product_test_result_id == result_row.product_test_result_id
            )
        )
    )
    for scoped_defect_row in scoped_defect_rows:
        existing_scope_id = str(scoped_defect_row.product_test_procedure_result_id or "").strip()
        if existing_scope_id != procedure_result_id:
            continue
        duplicate_title = re.sub(r"\s+", " ", str(scoped_defect_row.defect_title or "")).strip().lower()
        if duplicate_title == normalized_title:
            raise ValueError("Duplicate defect title exists for this result scope.")
    evidence_rows = list(
        database_session.scalars(
            select(ProductTestEvidence).where(
                ProductTestEvidence.product_test_result_id == result_row.product_test_result_id
            )
        )
    )
    if procedure_result_row is not None:
        evidence_rows = [
            row for row in evidence_rows
            if row.product_test_procedure_result_id == procedure_result_row.product_test_procedure_result_id
        ]
    warning_remark = ""
    if severity_value in {"critical", "major"} and not evidence_rows:
        warning_remark = "경고: critical/major defect 에 evidence 가 없습니다."
    defect_id = _next_prefixed_id(database_session, ProductTestDefect, "product_test_defect_id", "QA_PTDEF")
    now_text = _now_text()
    row = ProductTestDefect(
        product_test_defect_id=defect_id,
        product_test_result_id=result_row.product_test_result_id,
        product_test_procedure_result_id=procedure_result_id or None,
        defect_title=title,
        defect_description=description,
        defect_severity=severity_value,
        defect_priority=priority_value,
        product_test_defect_status="opened",
        assigned_to=str(assigned_to or "").strip() or None,
        fixed_at=None,
        fixed_by=None,
        fix_description=None,
        retest_product_test_result_id=None,
        retested_at=None,
        retested_by=None,
        closed_at=None,
        closed_by=None,
        rejection_reason=None,
        created_at=now_text,
        created_by=created_by,
        updated_at=now_text,
        updated_by=created_by,
        remark=" ".join(value for value in [str(remark or "").strip(), warning_remark] if value) or None,
    )
    database_session.add(row)
    _insert_status_transition(
        database_session,
        entity_type="product_test_defect",
        entity_id=defect_id,
        from_status=None,
        to_status="opened",
        transition_reason="create_defect",
        transitioned_by=created_by,
    )
    _commit_or_rollback(database_session)
    return _as_dict(
        row,
        [
            "product_test_defect_id",
            "product_test_result_id",
            "product_test_procedure_result_id",
            "defect_title",
            "defect_description",
            "defect_severity",
            "defect_priority",
            "product_test_defect_status",
            "assigned_to",
            "fixed_at",
            "fixed_by",
            "fix_description",
            "retest_product_test_result_id",
            "retested_at",
            "retested_by",
            "closed_at",
            "closed_by",
            "rejection_reason",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
    )


def get_run_detail(database_session: Session, product_test_run_id: str) -> dict[str, Any] | None:
    run_row = database_session.get(ProductTestRun, product_test_run_id)
    if run_row is None:
        return None
    approved_report_count = (
        database_session.scalar(
            select(func.count()).select_from(ProductTestReport).where(
                ProductTestReport.product_test_release_id == run_row.product_test_release_id,
                ProductTestReport.product_test_report_status == "APPROVED",
            )
        )
        or 0
    )
    result_row = database_session.scalar(
        select(ProductTestResult)
        .where(ProductTestResult.product_test_run_id == product_test_run_id)
        .order_by(ProductTestResult.created_at.desc())
    )
    procedure_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    defect_rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    if result_row is not None:
        procedure_result_models = list(
            database_session.scalars(
                select(ProductTestProcedureResult)
                .where(ProductTestProcedureResult.product_test_result_id == result_row.product_test_result_id)
            )
        )
        procedure_by_id = {
            row.product_test_procedure_id: row
            for row in database_session.scalars(
                select(ProductTestProcedure).where(
                    ProductTestProcedure.product_test_case_id == result_row.product_test_case_id
                )
            )
        }
        for row in procedure_result_models:
            procedure_row = procedure_by_id.get(row.product_test_procedure_id)
            row_evidence_count = (
                database_session.scalar(
                    select(func.count()).select_from(ProductTestEvidence).where(
                        ProductTestEvidence.product_test_procedure_result_id
                        == row.product_test_procedure_result_id
                    )
                )
                or 0
            )
            procedure_rows.append(
                {
                    "product_test_procedure_result_id": row.product_test_procedure_result_id,
                    "product_test_result_id": row.product_test_result_id,
                    "product_test_procedure_id": row.product_test_procedure_id,
                    "procedure_sequence": procedure_row.procedure_sequence if procedure_row else 0,
                    "procedure_action": procedure_row.procedure_action if procedure_row else "",
                    "expected_result": procedure_row.expected_result if procedure_row else "",
                    "acceptance_criteria": procedure_row.acceptance_criteria if procedure_row else "",
                    "required_evidence_type": procedure_row.required_evidence_type if procedure_row else "",
                    "status": row.product_test_procedure_result_status,
                    "actual_result": row.actual_result or "",
                    "judgement_reason": row.judgement_reason or "",
                    "remark": row.remark or "",
                    "evidence_count": int(row_evidence_count),
                    "created_at": row.created_at,
                    "created_by": row.created_by,
                    "updated_at": row.updated_at,
                    "updated_by": row.updated_by,
                }
            )
        procedure_rows.sort(key=lambda row: int(row["procedure_sequence"]))
        evidence_rows = [
            _as_dict(
                row,
                [
                    "product_test_evidence_id",
                    "product_test_result_id",
                    "product_test_procedure_result_id",
                    "product_test_defect_id",
                    "product_test_evidence_type",
                    "file_name",
                    "file_path",
                    "file_hash",
                    "captured_at",
                    "captured_by",
                    "created_at",
                    "created_by",
                    "updated_at",
                    "updated_by",
                    "remark",
                ],
            )
            for row in database_session.scalars(
                select(ProductTestEvidence).where(
                    ProductTestEvidence.product_test_result_id == result_row.product_test_result_id
                )
            )
        ]
        defect_rows = [
            {
                **_as_dict(
                    row,
                    [
                        "product_test_defect_id",
                        "product_test_result_id",
                        "product_test_procedure_result_id",
                        "defect_title",
                        "defect_description",
                        "defect_severity",
                        "defect_priority",
                        "assigned_to",
                        "fixed_at",
                        "fixed_by",
                        "fix_description",
                        "retest_product_test_result_id",
                        "retested_at",
                        "retested_by",
                        "closed_at",
                        "closed_by",
                        "rejection_reason",
                        "created_at",
                        "created_by",
                        "updated_at",
                        "updated_by",
                        "remark",
                    ],
                ),
                "status": row.product_test_defect_status,
            }
            for row in database_session.scalars(
                select(ProductTestDefect).where(
                    ProductTestDefect.product_test_result_id == result_row.product_test_result_id
                )
            )
        ]
    trace_entity_ids = {run_row.product_test_run_id}
    if result_row is not None:
        trace_entity_ids.add(result_row.product_test_result_id)
        trace_entity_ids.update(row["product_test_procedure_result_id"] for row in procedure_rows)
        trace_entity_ids.update(row["product_test_defect_id"] for row in defect_rows)
    transition_rows = [
        _as_dict(
            row,
            [
                "product_test_status_transition_id",
                "entity_type",
                "entity_id",
                "from_status",
                "to_status",
                "transition_reason",
                "transitioned_at",
                "transitioned_by",
            ],
        )
        for row in database_session.scalars(
            select(ProductTestStatusTransition)
            .where(ProductTestStatusTransition.entity_id.in_(sorted(trace_entity_ids)))
            .order_by(ProductTestStatusTransition.transitioned_at.desc())
        )
    ]
    return {
        "run": {
            **_as_dict(
                run_row,
                [
                    "product_test_run_id",
                    "product_test_release_id",
                    "product_test_target_id",
                    "product_test_environment_id",
                    "started_at",
                    "started_by",
                    "finished_at",
                    "cancelled_at",
                    "cancelled_by",
                    "cancel_reason",
                    "created_at",
                    "created_by",
                    "updated_at",
                    "updated_by",
                    "remark",
                ],
            ),
            "status": run_row.product_test_run_status,
            "selected_product_test_case_id": result_row.product_test_case_id if result_row else "",
            "source_locked": approved_report_count > 0,
        },
        "result": (
            {
                **_as_dict(
                    result_row,
                    [
                        "product_test_result_id",
                        "product_test_run_id",
                        "product_test_case_id",
                        "actual_result",
                        "judgement_reason",
                        "result_judged_at",
                        "result_judged_by",
                        "created_at",
                        "created_by",
                        "updated_at",
                        "updated_by",
                        "remark",
                    ],
                ),
                "status": result_row.product_test_result_status,
            }
            if result_row
            else None
        ),
        "procedure_rows": procedure_rows,
        "evidence_rows": evidence_rows,
        "defect_rows": defect_rows,
        "transition_rows": transition_rows,
        "release_summary": _as_dict(
            database_session.get(ProductTestRelease, run_row.product_test_release_id),
            [
                "product_test_release_id",
                "upstream_release_id",
                "upstream_release_system",
                "release_stage",
                "release_sequence",
                "product_test_release_status",
            ],
        ),
        "target_summary": _target_summary(database_session, run_row.product_test_target_id),
        "environment_summary": _environment_summary(database_session, run_row.product_test_environment_id),
        "release_options": list_release_options(database_session),
        "target_options": list_target_options(database_session),
        "environment_options": list_environment_options(database_session),
        "case_options": list_case_options(database_session),
    }


def list_report_release_options(database_session: Session) -> list[dict[str, Any]]:
    return list_release_options(database_session)


def list_product_test_reports(database_session: Session) -> list[dict[str, Any]]:
    rows = _query_all_rows(database_session, ProductTestReport, "created_at")
    return [
        _as_dict(
            row,
            [
                "product_test_report_id",
                "product_test_release_id",
                "product_test_report_type",
                "product_test_report_status",
                "product_test_report_title",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
                "approved_at",
                "approved_by",
                "rejected_at",
                "rejected_by",
                "rejection_reason",
                "remark",
            ],
        )
        for row in rows
    ]


def list_product_test_report_snapshots(database_session: Session) -> list[dict[str, Any]]:
    rows = _query_all_rows(database_session, ProductTestReportSnapshot, "created_at")
    return [
        _as_dict(
            row,
            [
                "product_test_report_snapshot_id",
                "product_test_report_id",
                "product_test_release_id",
                "snapshot_type",
                "snapshot_format",
                "snapshot_hash",
                "source_data_locked",
                "created_at",
                "created_by",
                "remark",
            ],
        )
        for row in rows
    ]


def get_product_test_report_snapshot_detail(
    database_session: Session,
    product_test_report_snapshot_id: str,
) -> dict[str, Any] | None:
    row = database_session.get(ProductTestReportSnapshot, product_test_report_snapshot_id)
    if row is None:
        return None
    payload_object = json.loads(row.snapshot_payload)
    return {
        "snapshot": _as_dict(
            row,
            [
                "product_test_report_snapshot_id",
                "product_test_report_id",
                "product_test_release_id",
                "snapshot_type",
                "snapshot_format",
                "snapshot_payload",
                "snapshot_hash",
                "source_data_locked",
                "created_at",
                "created_by",
                "remark",
            ],
        ),
        "snapshot_payload_pretty": json.dumps(payload_object, ensure_ascii=False, indent=2, sort_keys=True),
        "snapshot_payload_object": payload_object,
    }


def create_product_test_report(
    database_session: Session,
    *,
    product_test_release_id: str,
    product_test_report_type: str,
    product_test_report_title: str,
    created_by: str,
    remark: str,
) -> dict[str, Any]:
    release_id = str(product_test_release_id or "").strip()
    report_type_value = _validate_in(str(product_test_report_type or "").strip().upper(), REPORT_TYPE_VALUES, "product_test_report_type")
    title = str(product_test_report_title or "").strip()
    if not release_id or not title:
        raise ValueError("product_test_release_id and product_test_report_title are required.")
    if database_session.get(ProductTestRelease, release_id) is None:
        raise ValueError("Unknown product_test_release_id.")
    report_id = _next_prefixed_id(database_session, ProductTestReport, "product_test_report_id", "QA_PTRPT")
    now_text = _now_text()
    row = ProductTestReport(
        product_test_report_id=report_id,
        product_test_release_id=release_id,
        product_test_report_type=report_type_value,
        product_test_report_status="DRAFT",
        product_test_report_title=title,
        created_at=now_text,
        created_by=created_by,
        updated_at=now_text,
        updated_by=created_by,
        approved_at=None,
        approved_by=None,
        rejected_at=None,
        rejected_by=None,
        rejection_reason=None,
        remark=str(remark or "").strip() or None,
    )
    database_session.add(row)
    _insert_status_transition(
        database_session,
        entity_type="product_test_report",
        entity_id=report_id,
        from_status=None,
        to_status="DRAFT",
        transition_reason="create_report",
        transitioned_by=created_by,
    )
    _commit_or_rollback(database_session)
    return _as_dict(
        row,
        [
            "product_test_report_id",
            "product_test_release_id",
            "product_test_report_type",
            "product_test_report_status",
            "product_test_report_title",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "approved_at",
            "approved_by",
            "rejected_at",
            "rejected_by",
            "rejection_reason",
            "remark",
        ],
    )


def _build_product_test_report_snapshot_payload(detail: dict[str, Any]) -> dict[str, Any]:
    flat_result_rows = []
    flat_procedure_result_rows = []
    flat_defect_rows = []
    flat_evidence_rows = []
    for result in detail["result_details"]:
        flat_result_rows.append(
            {
                "product_test_result_id": result["product_test_result_id"],
                "product_test_run_id": result["product_test_run_id"],
                "product_test_case_id": result["product_test_case_id"],
                "product_test_case_title": result["product_test_case_title"],
                "product_test_result_status": result["product_test_result_status"],
                "actual_result": result["actual_result"],
                "judgement_reason": result["judgement_reason"],
                "result_judged_at": result["result_judged_at"],
                "result_judged_by": result["result_judged_by"],
            }
        )
        flat_defect_rows.extend(result["defect_rows"])
        flat_evidence_rows.extend(result["evidence_rows"])
        for procedure in result["procedure_rows"]:
            flat_procedure_result_rows.append(
                {
                    "product_test_result_id": result["product_test_result_id"],
                    "product_test_procedure_result_id": procedure.get("product_test_procedure_result_id", ""),
                    "product_test_procedure_id": procedure.get("product_test_procedure_id", ""),
                    "procedure_sequence": procedure["procedure_sequence"],
                    "procedure_action": procedure["procedure_action"],
                    "expected_result": procedure["expected_result"],
                    "acceptance_criteria": procedure["acceptance_criteria"],
                    "required_evidence_type": procedure["required_evidence_type"],
                    "product_test_procedure_result_status": procedure["product_test_procedure_result_status"],
                    "actual_result": procedure["actual_result"],
                    "judgement_reason": procedure["judgement_reason"],
                    "evidence_count": procedure["evidence_count"],
                }
            )
            flat_defect_rows.extend(procedure["defect_rows"])
            flat_evidence_rows.extend(procedure["evidence_rows"])
    dedup_defects = {row["product_test_defect_id"]: row for row in flat_defect_rows if row.get("product_test_defect_id")}
    dedup_evidences = {row["product_test_evidence_id"]: row for row in flat_evidence_rows if row.get("product_test_evidence_id")}
    return {
        "report_header": detail["report"],
        "release_summary": detail["release_summary"],
        "run_summaries": detail["run_summaries"],
        "result_summary": detail["result_summary"],
        "result_details": detail["result_details"],
        "product_test_results": flat_result_rows,
        "product_test_procedure_results": flat_procedure_result_rows,
        "product_test_defects": list(dedup_defects.values()),
        "product_test_evidences": list(dedup_evidences.values()),
        "product_test_status_transitions": detail["status_transitions"],
    }


def create_product_test_report_snapshot(
    database_session: Session,
    product_test_report_id: str,
    snapshot_type: str,
    created_by: str,
    remark: str | None = None,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    report_row = database_session.get(ProductTestReport, str(product_test_report_id or "").strip())
    if report_row is None:
        raise LookupError("Report not found.")
    snapshot_type_value = _validate_in(str(snapshot_type or "").strip(), SNAPSHOT_TYPE_VALUES, "snapshot_type")
    detail = get_product_test_report_detail(database_session, report_row.product_test_report_id)
    if detail is None:
        raise LookupError("Report detail not found.")
    payload_object = _build_product_test_report_snapshot_payload(detail)
    snapshot_payload = json.dumps(payload_object, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    snapshot_hash = hashlib.sha256(snapshot_payload.encode("utf-8")).hexdigest()
    today_text = get_utc_now_datetime().astimezone().strftime("%Y%m%d")
    snapshot_id = _next_prefixed_id(
        database_session,
        ProductTestReportSnapshot,
        "product_test_report_snapshot_id",
        f"QA_PTRPTSNAP-{today_text}",
    )
    now_text = _now_text()
    source_data_locked = 1 if snapshot_type_value == "approval" or _release_is_locked(database_session, report_row.product_test_release_id) else 0
    row = ProductTestReportSnapshot(
        product_test_report_snapshot_id=snapshot_id,
        product_test_report_id=report_row.product_test_report_id,
        product_test_release_id=report_row.product_test_release_id,
        snapshot_type=snapshot_type_value,
        snapshot_format="json",
        snapshot_payload=snapshot_payload,
        snapshot_hash=snapshot_hash,
        source_data_locked=source_data_locked,
        created_at=now_text,
        created_by=created_by,
        remark=str(remark or "").strip() or None,
    )
    database_session.add(row)
    if commit:
        _commit_or_rollback(database_session)
    return _as_dict(
        row,
        [
            "product_test_report_snapshot_id",
            "product_test_report_id",
            "product_test_release_id",
            "snapshot_type",
            "snapshot_format",
            "snapshot_hash",
            "source_data_locked",
            "created_at",
            "created_by",
            "remark",
        ],
    )


def _collect_release_graph(database_session: Session, product_test_release_id: str) -> dict[str, Any]:
    release_row = database_session.get(ProductTestRelease, product_test_release_id)
    run_rows = list(
        database_session.scalars(
            select(ProductTestRun)
            .where(ProductTestRun.product_test_release_id == product_test_release_id)
            .order_by(ProductTestRun.started_at.desc())
        )
    )
    run_ids = [row.product_test_run_id for row in run_rows]
    result_rows = []
    procedure_result_rows = []
    evidence_rows = []
    defect_rows = []
    if run_ids:
        result_rows = list(
            database_session.scalars(
                select(ProductTestResult)
                .where(ProductTestResult.product_test_run_id.in_(run_ids))
                .order_by(ProductTestResult.created_at.desc())
            )
        )
    result_ids = [row.product_test_result_id for row in result_rows]
    if result_ids:
        procedure_result_rows = list(
            database_session.scalars(
                select(ProductTestProcedureResult).where(
                    ProductTestProcedureResult.product_test_result_id.in_(result_ids)
                )
            )
        )
        evidence_rows = list(
            database_session.scalars(
                select(ProductTestEvidence).where(ProductTestEvidence.product_test_result_id.in_(result_ids))
            )
        )
        defect_rows = list(
            database_session.scalars(
                select(ProductTestDefect).where(ProductTestDefect.product_test_result_id.in_(result_ids))
            )
        )
    report_rows = list(
        database_session.scalars(
            select(ProductTestReport)
            .where(ProductTestReport.product_test_release_id == product_test_release_id)
            .order_by(ProductTestReport.created_at.desc())
        )
    )
    entity_ids = set(run_ids + result_ids + [row.product_test_procedure_result_id for row in procedure_result_rows] + [row.product_test_defect_id for row in defect_rows] + [row.product_test_report_id for row in report_rows])
    status_transitions = []
    if entity_ids:
        status_transitions = list(
            database_session.scalars(
                select(ProductTestStatusTransition)
                .where(ProductTestStatusTransition.entity_id.in_(entity_ids))
                .order_by(ProductTestStatusTransition.transitioned_at.desc())
            )
        )
    return {
        "release": release_row,
        "runs": run_rows,
        "results": result_rows,
        "procedure_results": procedure_result_rows,
        "evidences": evidence_rows,
        "defects": defect_rows,
        "reports": report_rows,
        "status_transitions": status_transitions,
    }


def approve_product_test_report(database_session: Session, *, product_test_report_id: str, approved_by: str) -> dict[str, Any]:
    report_row = database_session.get(ProductTestReport, product_test_report_id)
    if report_row is None:
        raise LookupError("Report not found.")
    graph = _collect_release_graph(database_session, report_row.product_test_release_id)
    if any(row.product_test_defect_status in {"opened", "assigned", "fixed", "retested"} for row in graph["defects"]):
        raise ValueError("Open defects exist for this release. Approval is blocked.")
    create_product_test_report_snapshot(
        database_session,
        product_test_report_id=product_test_report_id,
        snapshot_type="approval",
        created_by=approved_by,
        remark="auto snapshot before approval",
        commit=False,
    )
    ensure_product_test_status_transition_recorded(
        database_session,
        entity_type="product_test_report",
        entity_id=product_test_report_id,
        to_status="APPROVED",
        transition_reason="approve_report",
        transitioned_by=approved_by,
        approved_at=_now_text(),
        approved_by=approved_by,
    )
    now_text = _now_text()
    report_row.approved_at = now_text
    report_row.approved_by = approved_by
    report_row.updated_at = now_text
    report_row.updated_by = approved_by
    _commit_or_rollback(database_session)
    return _as_dict(report_row, ["product_test_report_id", "product_test_report_status", "approved_at", "approved_by"])


def reject_product_test_report(database_session: Session, *, product_test_report_id: str, rejected_by: str, rejection_reason: str) -> dict[str, Any]:
    report_row = database_session.get(ProductTestReport, product_test_report_id)
    if report_row is None:
        raise LookupError("Report not found.")
    reason_text = str(rejection_reason or "").strip()
    if not reason_text:
        raise ValueError("rejection_reason is required.")
    ensure_product_test_status_transition_recorded(
        database_session,
        entity_type="product_test_report",
        entity_id=product_test_report_id,
        to_status="REJECTED",
        transition_reason=reason_text,
        transitioned_by=rejected_by,
        rejected_at=_now_text(),
        rejected_by=rejected_by,
    )
    now_text = _now_text()
    report_row.rejected_at = now_text
    report_row.rejected_by = rejected_by
    report_row.rejection_reason = reason_text
    report_row.updated_at = now_text
    report_row.updated_by = rejected_by
    _commit_or_rollback(database_session)
    return _as_dict(report_row, ["product_test_report_id", "product_test_report_status", "rejected_at", "rejected_by", "rejection_reason"])


def _target_summary(database_session: Session, product_test_target_id: str) -> dict[str, Any]:
    target_row = database_session.get(ProductTestTarget, product_test_target_id)
    if target_row is None:
        fallback = _find_fallback_row(_sample_product_test_target_rows, "product_test_target_id", product_test_target_id) or {}
        definition_row = _find_fallback_row(_sample_product_test_target_definition_rows, "product_test_target_definition_id", fallback.get("product_test_target_definition_id", "")) or {}
        return {
            "product_test_target_id": product_test_target_id,
            "product_code": definition_row.get("product_code", ""),
            "manufacturer": definition_row.get("manufacturer", ""),
            "model_name": definition_row.get("model_name", ""),
            "serial_number": fallback.get("serial_number", ""),
            "software_version": fallback.get("software_version", ""),
            "firmware_version": fallback.get("firmware_version", ""),
            "manufacture_lot": fallback.get("manufacture_lot", ""),
        }
    definition_row = database_session.get(ProductTestTargetDefinition, target_row.product_test_target_definition_id)
    return {
        "product_test_target_id": target_row.product_test_target_id,
        "product_code": definition_row.product_code if definition_row else "",
        "manufacturer": definition_row.manufacturer if definition_row else "",
        "model_name": definition_row.model_name if definition_row else "",
        "serial_number": target_row.serial_number,
        "software_version": target_row.software_version or "",
        "firmware_version": target_row.firmware_version or "",
        "manufacture_lot": target_row.manufacture_lot or "",
    }


def _environment_summary(database_session: Session, product_test_environment_id: str) -> dict[str, Any]:
    environment_row = database_session.get(ProductTestEnvironment, product_test_environment_id)
    if environment_row is None:
        fallback = _find_fallback_row(_sample_product_test_environment_rows, "product_test_environment_id", product_test_environment_id) or {}
        definition_row = _find_fallback_row(_sample_product_test_environment_definition_rows, "product_test_environment_definition_id", fallback.get("product_test_environment_definition_id", "")) or {}
        return {
            "product_test_environment_id": product_test_environment_id,
            "product_test_environment_name": fallback.get("product_test_environment_name", ""),
            "test_country": definition_row.get("test_country", ""),
            "test_city": definition_row.get("test_city", ""),
            "test_company": definition_row.get("test_company", ""),
            "test_building": definition_row.get("test_building", ""),
            "test_floor": definition_row.get("test_floor", ""),
            "test_room": definition_row.get("test_room", ""),
            "network_type": fallback.get("network_type", definition_row.get("network_type", "")),
            "test_computer_name": fallback.get("test_computer_name", definition_row.get("test_computer_name", "")),
            "operating_system_version": fallback.get("operating_system_version", definition_row.get("operating_system_version", "")),
            "test_tool_version": fallback.get("test_tool_version", definition_row.get("test_tool_version", "")),
            "power_voltage": fallback.get("power_voltage", definition_row.get("power_voltage", "")),
            "power_frequency": fallback.get("power_frequency", definition_row.get("power_frequency", "")),
            "power_connector_type": fallback.get("power_connector_type", definition_row.get("power_connector_type", "")),
            "power_condition": definition_row.get("power_condition", ""),
        }
    definition_row = database_session.get(ProductTestEnvironmentDefinition, environment_row.product_test_environment_definition_id)
    return {
        "product_test_environment_id": environment_row.product_test_environment_id,
        "product_test_environment_name": environment_row.product_test_environment_name,
        "test_country": definition_row.test_country if definition_row else "",
        "test_city": definition_row.test_city if definition_row else "",
        "test_company": definition_row.test_company if definition_row else "",
        "test_building": definition_row.test_building if definition_row else "",
        "test_floor": definition_row.test_floor if definition_row else "",
        "test_room": definition_row.test_room if definition_row else "",
        "network_type": environment_row.network_type or (definition_row.network_type if definition_row else ""),
        "test_computer_name": environment_row.test_computer_name or (definition_row.test_computer_name if definition_row else ""),
        "operating_system_version": environment_row.operating_system_version or (definition_row.operating_system_version if definition_row else ""),
        "test_tool_version": environment_row.test_tool_version or (definition_row.test_tool_version if definition_row else ""),
        "power_voltage": environment_row.power_voltage or (definition_row.power_voltage if definition_row else ""),
        "power_frequency": environment_row.power_frequency or (definition_row.power_frequency if definition_row else ""),
        "power_connector_type": environment_row.power_connector_type or (definition_row.power_connector_type if definition_row else ""),
        "power_condition": definition_row.power_condition if definition_row else "",
    }


def get_product_test_report_detail(database_session: Session, product_test_report_id: str) -> dict[str, Any] | None:
    report_row = database_session.get(ProductTestReport, product_test_report_id)
    if report_row is None:
        return None
    graph = _collect_release_graph(database_session, report_row.product_test_release_id)
    result_rows = graph["results"]
    procedure_rows = graph["procedure_results"]
    evidence_rows = graph["evidences"]
    defect_rows = graph["defects"]
    case_map = {
        row.product_test_case_id: row
        for row in database_session.scalars(select(ProductTestCase))
    }
    procedure_map = {
        row.product_test_procedure_id: row
        for row in database_session.scalars(select(ProductTestProcedure))
    }
    result_details = []
    for result_row in result_rows:
        scoped_procedure_rows = [
            row for row in procedure_rows
            if row.product_test_result_id == result_row.product_test_result_id
        ]
        procedure_detail_rows = []
        for procedure_result_row in scoped_procedure_rows:
            procedure_row = procedure_map.get(procedure_result_row.product_test_procedure_id)
            scoped_evidence_rows = [
                row for row in evidence_rows
                if row.product_test_procedure_result_id == procedure_result_row.product_test_procedure_result_id
            ]
            scoped_defect_rows = [
                row for row in defect_rows
                if row.product_test_procedure_result_id == procedure_result_row.product_test_procedure_result_id
            ]
            procedure_detail_rows.append(
                {
                    "product_test_procedure_result_id": procedure_result_row.product_test_procedure_result_id,
                    "product_test_procedure_id": procedure_result_row.product_test_procedure_id,
                    "procedure_sequence": procedure_row.procedure_sequence if procedure_row else 0,
                    "procedure_action": procedure_row.procedure_action if procedure_row else "",
                    "expected_result": procedure_row.expected_result if procedure_row else "",
                    "acceptance_criteria": procedure_row.acceptance_criteria if procedure_row else "",
                    "required_evidence_type": procedure_row.required_evidence_type if procedure_row else "",
                    "product_test_procedure_result_status": procedure_result_row.product_test_procedure_result_status,
                    "actual_result": procedure_result_row.actual_result or "",
                    "judgement_reason": procedure_result_row.judgement_reason or "",
                    "evidence_count": len(scoped_evidence_rows),
                    "evidence_rows": [
                        _as_dict(
                            row,
                            [
                                "product_test_evidence_id",
                                "product_test_result_id",
                                "product_test_procedure_result_id",
                                "product_test_defect_id",
                                "product_test_evidence_type",
                                "file_name",
                                "file_path",
                                "file_hash",
                                "captured_at",
                                "captured_by",
                                "remark",
                            ],
                        )
                        for row in scoped_evidence_rows
                    ],
                    "defect_rows": [
                        {
                            **_as_dict(
                                row,
                                [
                                    "product_test_defect_id",
                                    "product_test_result_id",
                                    "product_test_procedure_result_id",
                                    "defect_title",
                                    "defect_description",
                                    "defect_severity",
                                    "defect_priority",
                                    "assigned_to",
                                    "fix_description",
                                    "retest_product_test_result_id",
                                    "rejection_reason",
                                ],
                            ),
                            "product_test_defect_status": row.product_test_defect_status,
                        }
                        for row in scoped_defect_rows
                    ],
                }
            )
        case_row = case_map.get(result_row.product_test_case_id)
        result_details.append(
            {
                "product_test_result_id": result_row.product_test_result_id,
                "product_test_run_id": result_row.product_test_run_id,
                "product_test_case_id": result_row.product_test_case_id,
                "product_test_case_title": case_row.product_test_case_title if case_row else "",
                "product_test_result_status": result_row.product_test_result_status,
                "actual_result": result_row.actual_result or "",
                "judgement_reason": result_row.judgement_reason or "",
                "result_judged_at": result_row.result_judged_at or "",
                "result_judged_by": result_row.result_judged_by or "",
                "procedure_rows": procedure_detail_rows,
                "defect_rows": [
                    {
                        **_as_dict(
                            row,
                            [
                                "product_test_defect_id",
                                "product_test_result_id",
                                "product_test_procedure_result_id",
                                "defect_title",
                                "defect_description",
                                "defect_severity",
                                "defect_priority",
                                "assigned_to",
                                "fix_description",
                                "retest_product_test_result_id",
                                "rejection_reason",
                            ],
                        ),
                        "status": row.product_test_defect_status,
                    }
                    for row in defect_rows
                    if row.product_test_result_id == result_row.product_test_result_id
                ],
                "evidence_rows": [
                    _as_dict(
                        row,
                        [
                            "product_test_evidence_id",
                            "product_test_result_id",
                            "product_test_procedure_result_id",
                            "product_test_defect_id",
                            "product_test_evidence_type",
                            "file_name",
                            "file_path",
                            "file_hash",
                            "captured_at",
                            "captured_by",
                            "remark",
                        ],
                    )
                    for row in evidence_rows
                    if row.product_test_result_id == result_row.product_test_result_id
                ],
            }
        )
    open_defect_count = len([row for row in defect_rows if row.product_test_defect_status in {"opened", "assigned", "fixed", "retested"}])
    procedure_failed_count = len(
        [row for row in procedure_rows if row.product_test_procedure_result_status == "failed"]
    )
    return {
        "report": _as_dict(
            report_row,
            [
                "product_test_report_id",
                "product_test_release_id",
                "product_test_report_type",
                "product_test_report_status",
                "product_test_report_title",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
                "approved_at",
                "approved_by",
                "rejected_at",
                "rejected_by",
                "rejection_reason",
                "remark",
            ],
        ),
        "release_summary": _as_dict(
            graph["release"],
            [
                "product_test_release_id",
                "upstream_release_id",
                "upstream_release_system",
                "release_stage",
                "release_sequence",
                "product_test_release_status",
            ],
        ) if graph["release"] else {"product_test_release_id": report_row.product_test_release_id},
        "run_summaries": [
            {
                "product_test_run_id": row.product_test_run_id,
                "product_test_target_id": row.product_test_target_id,
                "product_test_environment_id": row.product_test_environment_id,
                "product_test_run_status": row.product_test_run_status,
                "started_at": row.started_at,
                "started_by": row.started_by,
                "finished_at": row.finished_at or "",
                "target_summary": _target_summary(database_session, row.product_test_target_id),
                "environment_summary": _environment_summary(database_session, row.product_test_environment_id),
            }
            for row in graph["runs"]
        ],
        "result_summary": {
            "total_result_count": len(result_rows),
            "passed_count": len([row for row in result_rows if row.product_test_result_status == "passed"]),
            "failed_count": len([row for row in result_rows if row.product_test_result_status == "failed"]),
            "blocked_count": len([row for row in result_rows if row.product_test_result_status == "blocked"]),
            "skipped_count": len([row for row in result_rows if row.product_test_result_status == "skipped"]),
            "procedure_result_count": len(procedure_rows),
            "procedure_failed_count": procedure_failed_count,
            "defect_count": len(defect_rows),
            "open_defect_count": open_defect_count,
            "unresolved_defect_count": open_defect_count,
            "evidence_count": len(evidence_rows),
        },
        "result_details": result_details,
        "status_transitions": [
            _as_dict(
                row,
                [
                    "product_test_status_transition_id",
                    "entity_type",
                    "entity_id",
                    "from_status",
                    "to_status",
                    "transition_reason",
                    "transitioned_at",
                    "transitioned_by",
                    "created_at",
                    "created_by",
                    "remark",
                ],
            )
            for row in graph["status_transitions"]
        ],
        "approval_blocked": open_defect_count > 0,
    }


def compare_product_test_report_snapshots(
    database_session: Session,
    left_snapshot_id: str,
    right_snapshot_id: str,
) -> dict[str, Any]:
    left_row = database_session.get(ProductTestReportSnapshot, str(left_snapshot_id or "").strip())
    right_row = database_session.get(ProductTestReportSnapshot, str(right_snapshot_id or "").strip())
    if left_row is None or right_row is None:
        raise LookupError("Both snapshot IDs must exist.")
    if left_row.snapshot_format != "json" or right_row.snapshot_format != "json":
        raise ValueError("Both snapshots must use json format.")
    warnings: list[str] = []
    if left_row.product_test_release_id != right_row.product_test_release_id:
        warnings.append("Snapshots belong to different product_test_release_id values.")
    for row in (left_row, right_row):
        if not re.fullmatch(r"[0-9a-f]{64}", str(row.snapshot_hash or "")):
            warnings.append(f"Snapshot hash invalid: {row.product_test_report_snapshot_id}")
    left_payload = json.loads(left_row.snapshot_payload)
    right_payload = json.loads(right_row.snapshot_payload)
    left_results = {row["product_test_result_id"]: row for row in left_payload.get("product_test_results", [])}
    right_results = {row["product_test_result_id"]: row for row in right_payload.get("product_test_results", [])}
    left_cases = {row["product_test_case_id"] for row in left_results.values() if row.get("product_test_case_id")}
    right_cases = {row["product_test_case_id"] for row in right_results.values() if row.get("product_test_case_id")}
    left_procedures = {
        row["product_test_procedure_result_id"]: row
        for row in left_payload.get("product_test_procedure_results", [])
        if row.get("product_test_procedure_result_id")
    }
    right_procedures = {
        row["product_test_procedure_result_id"]: row
        for row in right_payload.get("product_test_procedure_results", [])
        if row.get("product_test_procedure_result_id")
    }
    left_defects = {row["product_test_defect_id"]: row for row in left_payload.get("product_test_defects", []) if row.get("product_test_defect_id")}
    right_defects = {row["product_test_defect_id"]: row for row in right_payload.get("product_test_defects", []) if row.get("product_test_defect_id")}
    left_evidences = {row["product_test_evidence_id"]: row for row in left_payload.get("product_test_evidences", []) if row.get("product_test_evidence_id")}
    right_evidences = {row["product_test_evidence_id"]: row for row in right_payload.get("product_test_evidences", []) if row.get("product_test_evidence_id")}
    changed_result_statuses = []
    for result_id in sorted(set(left_results) & set(right_results)):
        if left_results[result_id].get("product_test_result_status") != right_results[result_id].get("product_test_result_status"):
            changed_result_statuses.append(
                {
                    "product_test_result_id": result_id,
                    "product_test_case_id": right_results[result_id].get("product_test_case_id") or left_results[result_id].get("product_test_case_id"),
                    "left_status": left_results[result_id].get("product_test_result_status"),
                    "right_status": right_results[result_id].get("product_test_result_status"),
                }
            )
    changed_procedure_statuses = []
    for procedure_result_id in sorted(set(left_procedures) & set(right_procedures)):
        if left_procedures[procedure_result_id].get("product_test_procedure_result_status") != right_procedures[procedure_result_id].get("product_test_procedure_result_status"):
            changed_procedure_statuses.append(
                {
                    "product_test_procedure_result_id": procedure_result_id,
                    "product_test_procedure_id": right_procedures[procedure_result_id].get("product_test_procedure_id") or left_procedures[procedure_result_id].get("product_test_procedure_id"),
                    "left_status": left_procedures[procedure_result_id].get("product_test_procedure_result_status"),
                    "right_status": right_procedures[procedure_result_id].get("product_test_procedure_result_status"),
                }
            )
    changed_defect_statuses = []
    for defect_id in sorted(set(left_defects) & set(right_defects)):
        left_status = left_defects[defect_id].get("status") or left_defects[defect_id].get("product_test_defect_status")
        right_status = right_defects[defect_id].get("status") or right_defects[defect_id].get("product_test_defect_status")
        if left_status != right_status:
            changed_defect_statuses.append(
                {
                    "product_test_defect_id": defect_id,
                    "left_status": left_status,
                    "right_status": right_status,
                }
            )
    changed_evidence_hashes = []
    for evidence_id in sorted(set(left_evidences) & set(right_evidences)):
        if (left_evidences[evidence_id].get("file_hash") or "") != (right_evidences[evidence_id].get("file_hash") or ""):
            changed_evidence_hashes.append(
                {
                    "product_test_evidence_id": evidence_id,
                    "left_file_hash": left_evidences[evidence_id].get("file_hash") or "",
                    "right_file_hash": right_evidences[evidence_id].get("file_hash") or "",
                }
            )
    return {
        "left_snapshot": _as_dict(left_row, ["product_test_report_snapshot_id", "product_test_report_id", "product_test_release_id", "snapshot_type", "snapshot_hash"]),
        "right_snapshot": _as_dict(right_row, ["product_test_report_snapshot_id", "product_test_report_id", "product_test_release_id", "snapshot_type", "snapshot_hash"]),
        "warnings": warnings,
        "added_product_test_case_ids": sorted(right_cases - left_cases),
        "removed_product_test_case_ids": sorted(left_cases - right_cases),
        "changed_product_test_result_statuses": changed_result_statuses,
        "changed_product_test_procedure_result_statuses": changed_procedure_statuses,
        "added_defect_ids": sorted(set(right_defects) - set(left_defects)),
        "removed_defect_ids": sorted(set(left_defects) - set(right_defects)),
        "changed_defect_statuses": changed_defect_statuses,
        "added_evidence_ids": sorted(set(right_evidences) - set(left_evidences)),
        "removed_evidence_ids": sorted(set(left_evidences) - set(right_evidences)),
        "changed_evidence_hashes": changed_evidence_hashes,
    }


def get_product_test_trace_view(
    database_session: Session,
    *,
    product_test_release_id: str,
    product_test_target_id: str = "",
    product_test_environment_id: str = "",
    product_test_case_id: str = "",
    result_status: str = "",
    defect_status: str = "",
) -> dict[str, Any]:
    graph = _collect_release_graph(database_session, product_test_release_id)
    target_id = str(product_test_target_id or "").strip()
    environment_id = str(product_test_environment_id or "").strip()
    case_id = str(product_test_case_id or "").strip()
    result_status_value = str(result_status or "").strip()
    defect_status_value = str(defect_status or "").strip()
    case_map = {
        row.product_test_case_id: row
        for row in database_session.scalars(select(ProductTestCase))
    }
    procedure_map = {
        row.product_test_procedure_id: row
        for row in database_session.scalars(select(ProductTestProcedure))
    }
    run_trace_rows = []
    for run_row in graph["runs"]:
        if target_id and run_row.product_test_target_id != target_id:
            continue
        if environment_id and run_row.product_test_environment_id != environment_id:
            continue
        result_rows = []
        scoped_result_rows = [
            row for row in graph["results"]
            if row.product_test_run_id == run_row.product_test_run_id
        ]
        for result_row in scoped_result_rows:
            if case_id and result_row.product_test_case_id != case_id:
                continue
            if result_status_value and result_row.product_test_result_status != result_status_value:
                continue
            procedure_rows = []
            scoped_procedure_rows = [
                row for row in graph["procedure_results"]
                if row.product_test_result_id == result_row.product_test_result_id
            ]
            for procedure_result_row in scoped_procedure_rows:
                procedure_row = procedure_map.get(procedure_result_row.product_test_procedure_id)
                procedure_rows.append(
                    {
                        "product_test_procedure_result_id": procedure_result_row.product_test_procedure_result_id,
                        "product_test_procedure_result_status": procedure_result_row.product_test_procedure_result_status,
                        "procedure_sequence": procedure_row.procedure_sequence if procedure_row else 0,
                        "procedure_action": procedure_row.procedure_action if procedure_row else "",
                        "expected_result": procedure_row.expected_result if procedure_row else "",
                        "acceptance_criteria": procedure_row.acceptance_criteria if procedure_row else "",
                        "required_evidence_type": procedure_row.required_evidence_type if procedure_row else "",
                        "actual_result": procedure_result_row.actual_result or "",
                        "judgement_reason": procedure_result_row.judgement_reason or "",
                        "evidence_rows": [
                            _as_dict(
                                row,
                                [
                                    "product_test_evidence_id",
                                    "product_test_evidence_type",
                                    "file_name",
                                    "file_path",
                                    "file_hash",
                                    "captured_at",
                                    "captured_by",
                                    "remark",
                                ],
                            )
                            for row in graph["evidences"]
                            if row.product_test_procedure_result_id == procedure_result_row.product_test_procedure_result_id
                        ],
                    }
                )
            scoped_defect_rows = [
                row for row in graph["defects"]
                if row.product_test_result_id == result_row.product_test_result_id
            ]
            if defect_status_value:
                scoped_defect_rows = [
                    row for row in scoped_defect_rows
                    if row.product_test_defect_status == defect_status_value
                ]
            result_rows.append(
                {
                    "product_test_result_id": result_row.product_test_result_id,
                    "product_test_result_status": result_row.product_test_result_status,
                    "product_test_case_id": result_row.product_test_case_id,
                    "case_row": case_map.get(result_row.product_test_case_id),
                    "procedure_rows": procedure_rows,
                    "defect_rows": [
                        {
                            **_as_dict(
                                row,
                                [
                                    "product_test_defect_id",
                                    "defect_title",
                                    "defect_severity",
                                    "defect_priority",
                                    "assigned_to",
                                    "retest_product_test_result_id",
                                ],
                            ),
                            "status": row.product_test_defect_status,
                        }
                        for row in scoped_defect_rows
                    ],
                }
            )
        run_trace_rows.append(
            {
                "product_test_run_id": run_row.product_test_run_id,
                "product_test_run_status": run_row.product_test_run_status,
                "target_summary": _target_summary(database_session, run_row.product_test_target_id),
                "environment_summary": _environment_summary(database_session, run_row.product_test_environment_id),
                "result_rows": result_rows,
            }
        )
    return {
        "release": _as_dict(
            graph["release"],
            [
                "product_test_release_id",
                "upstream_release_id",
                "upstream_release_system",
                "release_stage",
                "release_sequence",
                "product_test_release_status",
            ],
        ) if graph["release"] else {"product_test_release_id": product_test_release_id},
        "filters": {
            "product_test_release_id": product_test_release_id,
            "product_test_target_id": target_id,
            "product_test_environment_id": environment_id,
            "product_test_case_id": case_id,
            "result_status": result_status_value,
            "defect_status": defect_status_value,
        },
        "run_trace_rows": run_trace_rows,
        "report_rows": [
            _as_dict(
                row,
                [
                    "product_test_report_id",
                    "product_test_report_type",
                    "product_test_report_status",
                    "product_test_report_title",
                ],
            )
            for row in graph["reports"]
        ],
        "status_transition_rows": [
            _as_dict(
                row,
                [
                    "product_test_status_transition_id",
                    "entity_type",
                    "entity_id",
                    "from_status",
                    "to_status",
                    "transition_reason",
                    "transitioned_at",
                    "transitioned_by",
                ],
            )
            for row in graph["status_transitions"]
        ],
        "release_options": list_release_options(database_session),
        "target_options": list_target_options(database_session),
        "environment_options": list_environment_options(database_session),
        "case_options": list_case_options(database_session),
    }


def get_release_id_by_run_id(database_session: Session, product_test_run_id: str) -> str:
    run_row = database_session.get(ProductTestRun, product_test_run_id)
    if run_row is None:
        raise LookupError("Run not found.")
    return run_row.product_test_release_id


def _append_export_section(rows: list[list[str]], title: str, header: list[str], body_rows: list[list[Any]]) -> None:
    rows.append([title])
    rows.append(header)
    for body_row in body_rows:
        rows.append(["" if value is None else str(value) for value in body_row])
    rows.append([])


def build_product_test_report_export_rows(database_session: Session, product_test_report_id: str) -> list[list[str]]:
    detail = get_product_test_report_detail(database_session, product_test_report_id)
    if detail is None:
        raise LookupError("Report not found.")
    rows: list[list[str]] = []
    _append_export_section(
        rows,
        "Report Header",
        [
            "product_test_report_id",
            "product_test_release_id",
            "product_test_report_type",
            "product_test_report_status",
            "product_test_report_title",
            "approved_at",
            "approved_by",
            "rejected_at",
            "rejected_by",
            "rejection_reason",
            "remark",
        ],
        [[
            detail["report"]["product_test_report_id"],
            detail["report"]["product_test_release_id"],
            detail["report"]["product_test_report_type"],
            detail["report"]["product_test_report_status"],
            detail["report"]["product_test_report_title"],
            detail["report"]["approved_at"],
            detail["report"]["approved_by"],
            detail["report"]["rejected_at"],
            detail["report"]["rejected_by"],
            detail["report"]["rejection_reason"],
            detail["report"]["remark"],
        ]],
    )
    _append_export_section(
        rows,
        "Release Summary",
        [
            "product_test_release_id",
            "upstream_release_id",
            "upstream_release_system",
            "release_stage",
            "release_sequence",
            "product_test_release_status",
        ],
        [[
            detail["release_summary"].get("product_test_release_id"),
            detail["release_summary"].get("upstream_release_id"),
            detail["release_summary"].get("upstream_release_system"),
            detail["release_summary"].get("release_stage"),
            detail["release_summary"].get("release_sequence"),
            detail["release_summary"].get("product_test_release_status"),
        ]],
    )
    _append_export_section(
        rows,
        "Target Summary",
        [
            "product_test_run_id",
            "product_test_target_id",
            "product_code",
            "manufacturer",
            "model_name",
            "serial_number",
            "software_version",
            "firmware_version",
            "manufacture_lot",
        ],
        [[
            run["product_test_run_id"],
            run["target_summary"].get("product_test_target_id"),
            run["target_summary"].get("product_code"),
            run["target_summary"].get("manufacturer"),
            run["target_summary"].get("model_name"),
            run["target_summary"].get("serial_number"),
            run["target_summary"].get("software_version"),
            run["target_summary"].get("firmware_version"),
            run["target_summary"].get("manufacture_lot"),
        ] for run in detail["run_summaries"]],
    )
    _append_export_section(
        rows,
        "Environment Summary",
        [
            "product_test_run_id",
            "product_test_environment_id",
            "product_test_environment_name",
            "test_country",
            "test_city",
            "test_company",
            "test_building",
            "test_floor",
            "test_room",
            "network_type",
            "test_computer_name",
            "operating_system_version",
            "test_tool_version",
            "power_voltage",
            "power_frequency",
            "power_connector_type",
            "power_condition",
        ],
        [[
            run["product_test_run_id"],
            run["environment_summary"].get("product_test_environment_id"),
            run["environment_summary"].get("product_test_environment_name"),
            run["environment_summary"].get("test_country"),
            run["environment_summary"].get("test_city"),
            run["environment_summary"].get("test_company"),
            run["environment_summary"].get("test_building"),
            run["environment_summary"].get("test_floor"),
            run["environment_summary"].get("test_room"),
            run["environment_summary"].get("network_type"),
            run["environment_summary"].get("test_computer_name"),
            run["environment_summary"].get("operating_system_version"),
            run["environment_summary"].get("test_tool_version"),
            run["environment_summary"].get("power_voltage"),
            run["environment_summary"].get("power_frequency"),
            run["environment_summary"].get("power_connector_type"),
            run["environment_summary"].get("power_condition"),
        ] for run in detail["run_summaries"]],
    )
    summary = detail["result_summary"]
    _append_export_section(
        rows,
        "Result Summary",
        [
            "total_result_count",
            "passed_count",
            "failed_count",
            "blocked_count",
            "skipped_count",
            "procedure_result_count",
            "procedure_failed_count",
            "defect_count",
            "open_defect_count",
            "unresolved_defect_count",
            "evidence_count",
        ],
        [[
            summary.get("total_result_count"),
            summary.get("passed_count"),
            summary.get("failed_count"),
            summary.get("blocked_count"),
            summary.get("skipped_count"),
            summary.get("procedure_result_count"),
            summary.get("procedure_failed_count"),
            summary.get("defect_count"),
            summary.get("open_defect_count"),
            summary.get("unresolved_defect_count"),
            summary.get("evidence_count"),
        ]],
    )
    _append_export_section(
        rows,
        "Result Detail",
        [
            "product_test_result_id",
            "product_test_run_id",
            "product_test_case_id",
            "product_test_case_title",
            "product_test_result_status",
            "actual_result",
            "judgement_reason",
            "result_judged_at",
            "result_judged_by",
        ],
        [[
            result["product_test_result_id"],
            result["product_test_run_id"],
            result["product_test_case_id"],
            result["product_test_case_title"],
            result["product_test_result_status"],
            result["actual_result"],
            result["judgement_reason"],
            result["result_judged_at"],
            result["result_judged_by"],
        ] for result in detail["result_details"]],
    )
    procedure_detail_rows: list[list[Any]] = []
    defect_detail_rows: list[list[Any]] = []
    evidence_detail_rows: list[list[Any]] = []
    for result in detail["result_details"]:
        for procedure in result["procedure_rows"]:
            procedure_detail_rows.append([
                result["product_test_result_id"],
                procedure["procedure_sequence"],
                procedure["procedure_action"],
                procedure["expected_result"],
                procedure["acceptance_criteria"],
                procedure["required_evidence_type"],
                procedure["product_test_procedure_result_status"],
                procedure["actual_result"],
                procedure["judgement_reason"],
                procedure["evidence_count"],
            ])
            for defect in procedure["defect_rows"]:
                defect_detail_rows.append([
                    result["product_test_result_id"],
                    defect["product_test_defect_id"],
                    defect["defect_title"],
                    defect["defect_description"],
                    defect["defect_severity"],
                    defect["defect_priority"],
                    defect["product_test_defect_status"],
                    defect["assigned_to"],
                    defect["fix_description"],
                    defect["retest_product_test_result_id"],
                    defect["rejection_reason"],
                ])
            for evidence in procedure["evidence_rows"]:
                evidence_detail_rows.append([
                    result["product_test_result_id"],
                    procedure["procedure_sequence"],
                    evidence["product_test_evidence_id"],
                    evidence["product_test_evidence_type"],
                    evidence["file_name"],
                    evidence["file_path"],
                    evidence["file_hash"],
                    evidence["captured_at"],
                    evidence["captured_by"],
                    evidence["remark"],
                ])
    _append_export_section(
        rows,
        "Procedure Result Detail",
        [
            "product_test_result_id",
            "procedure_sequence",
            "procedure_action",
            "expected_result",
            "acceptance_criteria",
            "required_evidence_type",
            "product_test_procedure_result_status",
            "actual_result",
            "judgement_reason",
            "evidence_count",
        ],
        procedure_detail_rows,
    )
    _append_export_section(
        rows,
        "Defect Detail",
        [
            "product_test_result_id",
            "product_test_defect_id",
            "defect_title",
            "defect_description",
            "defect_severity",
            "defect_priority",
            "product_test_defect_status",
            "assigned_to",
            "fix_description",
            "retest_product_test_result_id",
            "rejection_reason",
        ],
        defect_detail_rows,
    )
    _append_export_section(
        rows,
        "Evidence Detail",
        [
            "product_test_result_id",
            "procedure_sequence",
            "product_test_evidence_id",
            "product_test_evidence_type",
            "file_name",
            "file_path",
            "file_hash",
            "captured_at",
            "captured_by",
            "remark",
        ],
        evidence_detail_rows,
    )
    _append_export_section(
        rows,
        "Status Transition History",
        [
            "product_test_status_transition_id",
            "entity_type",
            "entity_id",
            "from_status",
            "to_status",
            "transition_reason",
            "transitioned_at",
            "transitioned_by",
        ],
        [[
            row["product_test_status_transition_id"],
            row["entity_type"],
            row["entity_id"],
            row["from_status"],
            row["to_status"],
            row["transition_reason"],
            row["transitioned_at"],
            row["transitioned_by"],
        ] for row in detail["status_transitions"]],
    )
    return rows


def build_product_test_trace_export_rows(
    database_session: Session,
    *,
    product_test_release_id: str,
    product_test_target_id: str = "",
    product_test_environment_id: str = "",
    product_test_case_id: str = "",
    result_status: str = "",
    defect_status: str = "",
) -> list[list[str]]:
    detail = get_product_test_trace_view(
        database_session,
        product_test_release_id=product_test_release_id,
        product_test_target_id=product_test_target_id,
        product_test_environment_id=product_test_environment_id,
        product_test_case_id=product_test_case_id,
        result_status=result_status,
        defect_status=defect_status,
    )
    rows: list[list[str]] = []
    _append_export_section(
        rows,
        "Release",
        [
            "product_test_release_id",
            "upstream_release_id",
            "upstream_release_system",
            "release_stage",
            "release_sequence",
            "product_test_release_status",
        ],
        [[
            detail["release"].get("product_test_release_id"),
            detail["release"].get("upstream_release_id"),
            detail["release"].get("upstream_release_system"),
            detail["release"].get("release_stage"),
            detail["release"].get("release_sequence"),
            detail["release"].get("product_test_release_status"),
        ]],
    )
    run_rows: list[list[Any]] = []
    procedure_rows: list[list[Any]] = []
    evidence_rows: list[list[Any]] = []
    defect_rows: list[list[Any]] = []
    for run in detail["run_trace_rows"]:
        run_rows.append([
            run["product_test_run_id"],
            run["product_test_run_status"],
            run["target_summary"].get("product_test_target_id"),
            run["target_summary"].get("serial_number"),
            run["environment_summary"].get("product_test_environment_id"),
            run["environment_summary"].get("product_test_environment_name"),
        ])
        for result in run["result_rows"]:
            for procedure in result["procedure_rows"]:
                procedure_rows.append([
                    run["product_test_run_id"],
                    result["product_test_result_id"],
                    result["product_test_case_id"],
                    result["product_test_result_status"],
                    procedure["product_test_procedure_result_id"],
                    procedure["procedure_sequence"],
                    procedure["procedure_action"],
                    procedure["product_test_procedure_result_status"],
                    procedure["actual_result"],
                    procedure["judgement_reason"],
                ])
                for evidence in procedure["evidence_rows"]:
                    evidence_rows.append([
                        result["product_test_result_id"],
                        procedure["product_test_procedure_result_id"],
                        evidence["product_test_evidence_id"],
                        evidence["product_test_evidence_type"],
                        evidence["file_name"],
                        evidence["file_path"],
                        evidence["captured_at"],
                    ])
            for defect in result["defect_rows"]:
                defect_rows.append([
                    result["product_test_result_id"],
                    defect["product_test_defect_id"],
                    defect["defect_title"],
                    defect["defect_severity"],
                    defect["defect_priority"],
                    defect["status"],
                    defect["assigned_to"],
                    defect["retest_product_test_result_id"],
                ])
    _append_export_section(
        rows,
        "Runs",
        [
            "product_test_run_id",
            "product_test_run_status",
            "product_test_target_id",
            "serial_number",
            "product_test_environment_id",
            "product_test_environment_name",
        ],
        run_rows,
    )
    _append_export_section(
        rows,
        "Procedure Results",
        [
            "product_test_run_id",
            "product_test_result_id",
            "product_test_case_id",
            "product_test_result_status",
            "product_test_procedure_result_id",
            "procedure_sequence",
            "procedure_action",
            "product_test_procedure_result_status",
            "actual_result",
            "judgement_reason",
        ],
        procedure_rows,
    )
    _append_export_section(
        rows,
        "Evidence",
        [
            "product_test_result_id",
            "product_test_procedure_result_id",
            "product_test_evidence_id",
            "product_test_evidence_type",
            "file_name",
            "file_path",
            "captured_at",
        ],
        evidence_rows,
    )
    _append_export_section(
        rows,
        "Defects",
        [
            "product_test_result_id",
            "product_test_defect_id",
            "defect_title",
            "defect_severity",
            "defect_priority",
            "product_test_defect_status",
            "assigned_to",
            "retest_product_test_result_id",
        ],
        defect_rows,
    )
    _append_export_section(
        rows,
        "Report",
        [
            "product_test_report_id",
            "product_test_report_type",
            "product_test_report_status",
            "product_test_report_title",
        ],
        [[
            row["product_test_report_id"],
            row["product_test_report_type"],
            row["product_test_report_status"],
            row["product_test_report_title"],
        ] for row in detail["report_rows"]],
    )
    _append_export_section(
        rows,
        "Status Transitions",
        [
            "product_test_status_transition_id",
            "entity_type",
            "entity_id",
            "from_status",
            "to_status",
            "transition_reason",
            "transitioned_at",
            "transitioned_by",
        ],
        [[
            row["product_test_status_transition_id"],
            row["entity_type"],
            row["entity_id"],
            row["from_status"],
            row["to_status"],
            row["transition_reason"],
            row["transitioned_at"],
            row["transitioned_by"],
        ] for row in detail["status_transition_rows"]],
    )
    return rows


def build_product_test_run_export_rows(database_session: Session, product_test_run_id: str) -> list[list[str]]:
    detail = get_run_detail(database_session, product_test_run_id)
    if detail is None:
        raise LookupError("Run not found.")
    rows: list[list[str]] = []
    _append_export_section(
        rows,
        "Run Summary",
        [
            "product_test_run_id",
            "product_test_release_id",
            "product_test_target_id",
            "product_test_environment_id",
            "product_test_run_status",
            "started_at",
            "started_by",
            "finished_at",
            "cancelled_at",
            "cancelled_by",
            "cancel_reason",
            "source_locked",
        ],
        [[
            detail["run"]["product_test_run_id"],
            detail["run"]["product_test_release_id"],
            detail["run"]["product_test_target_id"],
            detail["run"]["product_test_environment_id"],
            detail["run"]["status"],
            detail["run"]["started_at"],
            detail["run"]["started_by"],
            detail["run"]["finished_at"],
            detail["run"]["cancelled_at"],
            detail["run"]["cancelled_by"],
            detail["run"]["cancel_reason"],
            detail["run"]["source_locked"],
        ]],
    )
    if detail["result"]:
        _append_export_section(
            rows,
            "Result Summary",
            [
                "product_test_result_id",
                "product_test_case_id",
                "product_test_result_status",
                "actual_result",
                "judgement_reason",
                "result_judged_at",
                "result_judged_by",
            ],
            [[
                detail["result"]["product_test_result_id"],
                detail["result"]["product_test_case_id"],
                detail["result"]["status"],
                detail["result"]["actual_result"],
                detail["result"]["judgement_reason"],
                detail["result"]["result_judged_at"],
                detail["result"]["result_judged_by"],
            ]],
        )
    _append_export_section(
        rows,
        "Procedure Results",
        [
            "product_test_procedure_result_id",
            "procedure_sequence",
            "procedure_action",
            "expected_result",
            "acceptance_criteria",
            "required_evidence_type",
            "product_test_procedure_result_status",
            "actual_result",
            "judgement_reason",
            "evidence_count",
            "remark",
        ],
        [[
            row["product_test_procedure_result_id"],
            row["procedure_sequence"],
            row["procedure_action"],
            row["expected_result"],
            row["acceptance_criteria"],
            row["required_evidence_type"],
            row["status"],
            row["actual_result"],
            row["judgement_reason"],
            row["evidence_count"],
            row["remark"],
        ] for row in detail["procedure_rows"]],
    )
    _append_export_section(
        rows,
        "Evidence",
        [
            "product_test_evidence_id",
            "product_test_procedure_result_id",
            "product_test_evidence_type",
            "file_name",
            "file_path",
            "captured_at",
            "captured_by",
            "remark",
        ],
        [[
            row["product_test_evidence_id"],
            row["product_test_procedure_result_id"],
            row["product_test_evidence_type"],
            row["file_name"],
            row["file_path"],
            row["captured_at"],
            row["captured_by"],
            row["remark"],
        ] for row in detail["evidence_rows"]],
    )
    _append_export_section(
        rows,
        "Defects",
        [
            "product_test_defect_id",
            "product_test_procedure_result_id",
            "defect_title",
            "defect_severity",
            "defect_priority",
            "product_test_defect_status",
            "assigned_to",
            "retest_product_test_result_id",
            "remark",
        ],
        [[
            row["product_test_defect_id"],
            row["product_test_procedure_result_id"],
            row["defect_title"],
            row["defect_severity"],
            row["defect_priority"],
            row["status"],
            row["assigned_to"],
            row["retest_product_test_result_id"],
            row["remark"],
        ] for row in detail["defect_rows"]],
    )
    _append_export_section(
        rows,
        "Status Transition History",
        [
            "product_test_status_transition_id",
            "entity_type",
            "entity_id",
            "from_status",
            "to_status",
            "transition_reason",
            "transitioned_at",
            "transitioned_by",
        ],
        [[
            row["product_test_status_transition_id"],
            row["entity_type"],
            row["entity_id"],
            row["from_status"],
            row["to_status"],
            row["transition_reason"],
            row["transitioned_at"],
            row["transitioned_by"],
        ] for row in detail["transition_rows"]],
    )
    return rows


def get_product_test_system_check(database_session: Session) -> dict[str, Any]:
    table_names = [
        "product_test_release",
        "product_test_target_definition",
        "product_test_target",
        "product_test_environment_definition",
        "product_test_environment",
        "product_test_case",
        "product_test_procedure",
        "product_test_run",
        "product_test_result",
        "product_test_procedure_result",
        "product_test_evidence",
        "product_test_defect",
        "product_test_report",
        "product_test_status_transition",
    ]
    table_rows = []
    for table_name in table_names:
        exists_value = database_session.execute(
            text(
                """
                SELECT EXISTS(
                    SELECT 1 FROM sqlite_master
                    WHERE type='table' AND name = :table_name
                )
                """
            ),
            {"table_name": table_name},
        ).scalar()
        table_rows.append({
            "table_name": table_name,
            "exists": bool(exists_value),
        })
    unresolved_defects_count = (
        database_session.scalar(
            select(func.count()).select_from(ProductTestDefect).where(
                ProductTestDefect.product_test_defect_status.in_(["opened", "assigned", "fixed"])
            )
        )
        or 0
    )
    report_count = database_session.scalar(select(func.count()).select_from(ProductTestReport)) or 0
    approved_report_count = (
        database_session.scalar(
            select(func.count()).select_from(ProductTestReport).where(
                ProductTestReport.product_test_report_status == "APPROVED"
            )
        )
        or 0
    )
    locked_release_count = (
        database_session.scalar(
            select(func.count(func.distinct(ProductTestReport.product_test_release_id))).where(
                ProductTestReport.product_test_report_status == "APPROVED"
            )
        )
        or 0
    )
    seed_data_presence = {
        "wifi_case": database_session.get(ProductTestCase, "QA_PTCASE-WIFI-AP_CONFIG-001") is not None,
        "wifi_release": database_session.get(ProductTestRelease, "QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1") is not None,
        "wifi_run": database_session.get(ProductTestRun, "QA_PTRUN-20260504-0001") is not None,
        "wifi_result": database_session.get(ProductTestResult, "QA_PTRES-20260504-0001") is not None,
        "wifi_report": database_session.get(ProductTestReport, "QA_PTRPT-QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1-FULL-001") is not None,
    }
    return {
        "table_rows": table_rows,
        "seed_data_presence": seed_data_presence,
        "unresolved_defects_count": int(unresolved_defects_count),
        "report_count": int(report_count),
        "approved_report_count": int(approved_report_count),
        "locked_release_count": int(locked_release_count),
    }


def get_release_id_by_result_id(database_session: Session, product_test_result_id: str) -> str:
    result_row = database_session.get(ProductTestResult, product_test_result_id)
    if result_row is None:
        raise LookupError("Result not found.")
    run_row = database_session.get(ProductTestRun, result_row.product_test_run_id)
    if run_row is None:
        raise LookupError("Run not found for result.")
    return run_row.product_test_release_id


def list_running_run_options(database_session: Session) -> list[dict[str, Any]]:
    return [
        _as_dict(
            row,
            [
                "product_test_run_id",
                "product_test_release_id",
                "product_test_target_id",
                "product_test_environment_id",
                "product_test_run_status",
                "started_at",
            ],
        )
        for row in database_session.scalars(
            select(ProductTestRun)
            .where(ProductTestRun.product_test_run_status == "running")
            .order_by(ProductTestRun.started_at.desc())
        )
    ]


def get_product_test_defect_detail(database_session: Session, product_test_defect_id: str) -> dict[str, Any] | None:
    defect_row = database_session.get(ProductTestDefect, product_test_defect_id)
    if defect_row is None:
        return None
    result_row = database_session.get(ProductTestResult, defect_row.product_test_result_id)
    if result_row is None:
        raise LookupError("Original result not found.")
    run_row = database_session.get(ProductTestRun, result_row.product_test_run_id)
    procedure_result_row = None
    procedure_row = None
    if defect_row.product_test_procedure_result_id:
        procedure_result_row = database_session.get(ProductTestProcedureResult, defect_row.product_test_procedure_result_id)
        if procedure_result_row is not None:
            procedure_row = database_session.get(ProductTestProcedure, procedure_result_row.product_test_procedure_id)
    case_row = database_session.get(ProductTestCase, result_row.product_test_case_id)
    evidence_rows = [
        _as_dict(
            row,
            [
                "product_test_evidence_id",
                "product_test_result_id",
                "product_test_procedure_result_id",
                "product_test_defect_id",
                "product_test_evidence_type",
                "file_name",
                "file_path",
                "file_hash",
                "captured_at",
                "captured_by",
                "remark",
            ],
        )
        for row in database_session.scalars(
            select(ProductTestEvidence)
            .where(ProductTestEvidence.product_test_defect_id == product_test_defect_id)
            .order_by(ProductTestEvidence.captured_at.desc())
        )
    ]
    transition_rows = [
        _as_dict(
            row,
            [
                "product_test_status_transition_id",
                "entity_type",
                "entity_id",
                "from_status",
                "to_status",
                "transition_reason",
                "transitioned_at",
                "transitioned_by",
            ],
        )
        for row in database_session.scalars(
            select(ProductTestStatusTransition)
            .where(
                ProductTestStatusTransition.entity_type == "product_test_defect",
                ProductTestStatusTransition.entity_id == product_test_defect_id,
            )
            .order_by(ProductTestStatusTransition.transitioned_at.desc())
        )
    ]
    retest_result_row = None
    if defect_row.retest_product_test_result_id:
        retest_result_row = database_session.get(ProductTestResult, defect_row.retest_product_test_result_id)
    return {
        "defect": {
            **_as_dict(
                defect_row,
                [
                    "product_test_defect_id",
                    "product_test_result_id",
                    "product_test_procedure_result_id",
                    "defect_title",
                    "defect_description",
                    "defect_severity",
                    "defect_priority",
                    "assigned_to",
                    "fixed_at",
                    "fixed_by",
                    "fix_description",
                    "retest_product_test_result_id",
                    "retested_at",
                    "retested_by",
                    "closed_at",
                    "closed_by",
                    "rejection_reason",
                    "created_at",
                    "created_by",
                    "updated_at",
                    "updated_by",
                    "remark",
                ],
            ),
            "status": defect_row.product_test_defect_status,
        },
        "original_result": {
            **_as_dict(
                result_row,
                [
                    "product_test_result_id",
                    "product_test_run_id",
                    "product_test_case_id",
                    "actual_result",
                    "judgement_reason",
                    "result_judged_at",
                    "result_judged_by",
                ],
            ),
            "status": result_row.product_test_result_status,
            "product_test_case_title": case_row.product_test_case_title if case_row else "",
        },
        "original_procedure_result": (
            {
                "product_test_procedure_result_id": procedure_result_row.product_test_procedure_result_id,
                "product_test_procedure_result_status": procedure_result_row.product_test_procedure_result_status,
                "procedure_sequence": procedure_row.procedure_sequence if procedure_row else 0,
                "procedure_action": procedure_row.procedure_action if procedure_row else "",
                "expected_result": procedure_row.expected_result if procedure_row else "",
                "acceptance_criteria": procedure_row.acceptance_criteria if procedure_row else "",
                "required_evidence_type": procedure_row.required_evidence_type if procedure_row else "",
                "actual_result": procedure_result_row.actual_result or "",
                "judgement_reason": procedure_result_row.judgement_reason or "",
            }
            if procedure_result_row is not None
            else None
        ),
        "run": _as_dict(
            run_row,
            [
                "product_test_run_id",
                "product_test_release_id",
                "product_test_target_id",
                "product_test_environment_id",
                "product_test_run_status",
                "started_at",
            ],
        ) if run_row is not None else {},
        "evidence_rows": evidence_rows,
        "transition_rows": transition_rows,
        "running_run_options": list_running_run_options(database_session),
        "retest_result": (
            {
                **_as_dict(
                    retest_result_row,
                    [
                        "product_test_result_id",
                        "product_test_run_id",
                        "product_test_case_id",
                        "actual_result",
                        "judgement_reason",
                        "result_judged_at",
                        "result_judged_by",
                    ],
                ),
                "status": retest_result_row.product_test_result_status,
            }
            if retest_result_row is not None
            else None
        ),
    }


def transition_product_test_defect_to_assigned(
    database_session: Session,
    *,
    product_test_defect_id: str,
    assigned_to: str,
    transition_reason: str,
    transitioned_by: str,
) -> dict[str, Any]:
    defect_row = _ensure_defect_not_locked_for_source_mutation(
        database_session,
        product_test_defect_id=product_test_defect_id,
    )
    assigned_to_value = str(assigned_to or "").strip()
    ensure_product_test_status_transition_recorded(
        database_session,
        entity_type="product_test_defect",
        entity_id=product_test_defect_id,
        to_status="assigned",
        transition_reason=str(transition_reason or "").strip(),
        transitioned_by=transitioned_by,
        assigned_to=assigned_to_value,
    )
    defect_row.assigned_to = assigned_to_value
    defect_row.updated_at = _now_text()
    defect_row.updated_by = transitioned_by
    _commit_or_rollback(database_session)
    return {"product_test_defect_id": defect_row.product_test_defect_id, "status": defect_row.product_test_defect_status}


def transition_product_test_defect_to_fixed(
    database_session: Session,
    *,
    product_test_defect_id: str,
    fix_description: str,
    transition_reason: str,
    transitioned_by: str,
) -> dict[str, Any]:
    defect_row = _ensure_defect_not_locked_for_source_mutation(
        database_session,
        product_test_defect_id=product_test_defect_id,
    )
    now_text = _now_text()
    ensure_product_test_status_transition_recorded(
        database_session,
        entity_type="product_test_defect",
        entity_id=product_test_defect_id,
        to_status="fixed",
        transition_reason=str(transition_reason or "").strip(),
        transitioned_by=transitioned_by,
        fixed_at=now_text,
        fixed_by=transitioned_by,
        fix_description=str(fix_description or "").strip(),
    )
    defect_row.fixed_at = now_text
    defect_row.fixed_by = transitioned_by
    defect_row.fix_description = str(fix_description or "").strip()
    defect_row.updated_at = now_text
    defect_row.updated_by = transitioned_by
    _commit_or_rollback(database_session)
    return {"product_test_defect_id": defect_row.product_test_defect_id, "status": defect_row.product_test_defect_status}


def create_retest_product_test_result_from_defect(
    database_session: Session,
    *,
    product_test_defect_id: str,
    product_test_run_id: str,
    started_by: str,
) -> dict[str, Any]:
    defect_row = _ensure_defect_not_locked_for_source_mutation(
        database_session,
        product_test_defect_id=product_test_defect_id,
    )
    if defect_row.product_test_defect_status != "fixed":
        raise ValueError("Defect must be fixed before retest result creation.")
    original_result_row = database_session.get(ProductTestResult, defect_row.product_test_result_id)
    if original_result_row is None:
        raise LookupError("Original result not found.")
    target_run_row = database_session.get(ProductTestRun, str(product_test_run_id or "").strip())
    if target_run_row is None:
        raise ValueError("Unknown product_test_run_id.")
    if target_run_row.product_test_run_status != "running":
        raise ValueError("Retest requires a running Product Test Run.")
    existing_row = database_session.scalar(
        select(ProductTestResult).where(
            ProductTestResult.product_test_run_id == target_run_row.product_test_run_id,
            ProductTestResult.product_test_case_id == original_result_row.product_test_case_id,
        )
    )
    if existing_row is not None:
        raise ValueError("Selected run already has the same product_test_case_id result.")
    return start_product_test_result(
        database_session,
        product_test_run_id=target_run_row.product_test_run_id,
        product_test_case_id=original_result_row.product_test_case_id,
        started_by=started_by,
    )


def transition_product_test_defect_to_retested(
    database_session: Session,
    *,
    product_test_defect_id: str,
    retest_product_test_result_id: str,
    transition_reason: str,
    transitioned_by: str,
) -> dict[str, Any]:
    defect_row = _ensure_defect_not_locked_for_source_mutation(
        database_session,
        product_test_defect_id=product_test_defect_id,
    )
    now_text = _now_text()
    ensure_product_test_status_transition_recorded(
        database_session,
        entity_type="product_test_defect",
        entity_id=product_test_defect_id,
        to_status="retested",
        transition_reason=str(transition_reason or "").strip(),
        transitioned_by=transitioned_by,
        retest_product_test_result_id=str(retest_product_test_result_id or "").strip(),
        retested_at=now_text,
        retested_by=transitioned_by,
    )
    defect_row.retest_product_test_result_id = str(retest_product_test_result_id or "").strip()
    defect_row.retested_at = now_text
    defect_row.retested_by = transitioned_by
    defect_row.updated_at = now_text
    defect_row.updated_by = transitioned_by
    _commit_or_rollback(database_session)
    return {"product_test_defect_id": defect_row.product_test_defect_id, "status": defect_row.product_test_defect_status}


def transition_product_test_defect_to_closed(
    database_session: Session,
    *,
    product_test_defect_id: str,
    transition_reason: str,
    transitioned_by: str,
) -> dict[str, Any]:
    defect_row = _ensure_defect_not_locked_for_source_mutation(
        database_session,
        product_test_defect_id=product_test_defect_id,
    )
    now_text = _now_text()
    ensure_product_test_status_transition_recorded(
        database_session,
        entity_type="product_test_defect",
        entity_id=product_test_defect_id,
        to_status="closed",
        transition_reason=str(transition_reason or "").strip(),
        transitioned_by=transitioned_by,
        closed_at=now_text,
        closed_by=transitioned_by,
    )
    defect_row.closed_at = now_text
    defect_row.closed_by = transitioned_by
    defect_row.updated_at = now_text
    defect_row.updated_by = transitioned_by
    _commit_or_rollback(database_session)
    return {"product_test_defect_id": defect_row.product_test_defect_id, "status": defect_row.product_test_defect_status}


def transition_product_test_defect_to_rejected(
    database_session: Session,
    *,
    product_test_defect_id: str,
    rejection_reason: str,
    transition_reason: str,
    transitioned_by: str,
) -> dict[str, Any]:
    defect_row = _ensure_defect_not_locked_for_source_mutation(
        database_session,
        product_test_defect_id=product_test_defect_id,
    )
    reason_text = str(rejection_reason or "").strip()
    ensure_product_test_status_transition_recorded(
        database_session,
        entity_type="product_test_defect",
        entity_id=product_test_defect_id,
        to_status="rejected",
        transition_reason=str(transition_reason or "").strip() or reason_text,
        transitioned_by=transitioned_by,
        rejection_reason=reason_text,
    )
    defect_row.rejection_reason = reason_text
    defect_row.updated_at = _now_text()
    defect_row.updated_by = transitioned_by
    _commit_or_rollback(database_session)
    return {"product_test_defect_id": defect_row.product_test_defect_id, "status": defect_row.product_test_defect_status}
