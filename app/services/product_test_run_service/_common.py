from __future__ import annotations

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
    ProductTestRound,
    ProductTestReport,
    ProductTestReportSnapshot,
    ProductTestResult,
    ProductTestRun,
    ProductTestStatusTransition,
    ProductTestTargetUnified,
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
TARGET_STATUS_VALUES = ("active", "inactive", "damaged", "returned", "archived")
ENVIRONMENT_STATUS_VALUES = ("active", "inactive", "archived")
ENTITY_TYPE_VALUES = (
    "product_test_run",
    "product_test_result",
    "product_test_procedure_result",
    "product_test_defect",
    "product_test_report",
)

ENTITY_TRANSITIONS = {
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

_sample_product_test_target_rows = [
    {
        "product_test_target_id": "SQA_PRODUCT_TEST_TARGET_ID-HRK_9000A-SN001",
        "product_code": "HRK_9000A",
        "manufacturer": "Huvitz",
        "model_name": "HRK-9000A",
        "hardware_revision": "A",
        "default_software_version": "1.0.0",
        "default_firmware_version": "1.0.0",
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
        "product_test_environment_definition_id": "SQA_PRODUCT_TEST_ENVIRONMENT_DEFINITION_ID-HUVITZ-ANYANG-CONNECTIVITY_ROOM",
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
        "product_test_environment_id": "SQA_PRODUCT_TEST_ENVIRONMENT_ID-HUVITZ-ANYANG-CONNECTIVITY_ROOM-20260504-001",
        "product_test_environment_definition_id": "SQA_PRODUCT_TEST_ENVIRONMENT_DEFINITION_ID-HUVITZ-ANYANG-CONNECTIVITY_ROOM",
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
        "product_test_case_id": "SQA_PRODUCT_TEST_CASE_ID-WIFI-AP_CONFIG-001",
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
            "product_test_procedure_id": "SQA_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-001",
            "product_test_case_id": "SQA_PRODUCT_TEST_CASE_ID-WIFI-AP_CONFIG-001",
        "procedure_sequence": 1,
        "procedure_action": "WiFi Band 분리설정 확인",
        "acceptance_criteria": "2.4GHz, 5GHz의 SSID를 분리하는 것을 권장\n[기대결과] 2.4GHz와 5GHz SSID가 분리되어 있어야 함",
        "required_evidence_type": "screenshot",
        "product_test_procedure_status": "ACTIVE",
        "created_at": "2026-05-05 08:40:00",
        "created_by": "SQA_MASTER",
        "updated_at": "2026-05-05 08:40:00",
        "updated_by": "SQA_MASTER",
        "remark": "분리하지 않은 경우 임베디드 장비가 2.4GHz로 할당될 가능성이 높음.",
    },
    {
            "product_test_procedure_id": "SQA_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-002",
            "product_test_case_id": "SQA_PRODUCT_TEST_CASE_ID-WIFI-AP_CONFIG-001",
        "procedure_sequence": 2,
        "procedure_action": "WiFi Channel 설정 확인",
        "acceptance_criteria": "2.4GHz는 1~11번 채널 고정 사용 권장. 5GHz는 DFS가 아닌 36, 40, 44, 48 채널 고정 사용 권장\n[기대결과] 2.4GHz는 1~11번 고정 채널, 5GHz는 DFS가 아닌 36, 40, 44, 48 채널이어야 함",
        "required_evidence_type": "screenshot",
        "product_test_procedure_status": "ACTIVE",
        "created_at": "2026-05-05 08:41:00",
        "created_by": "SQA_MASTER",
        "updated_at": "2026-05-05 08:41:00",
        "updated_by": "SQA_MASTER",
        "remark": "5GHz에서 DFS 채널을 사용하는 경우 WiFi 모듈이 AP를 검색하지 못할 수 있음.",
    },
    {
            "product_test_procedure_id": "SQA_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-003",
            "product_test_case_id": "SQA_PRODUCT_TEST_CASE_ID-WIFI-AP_CONFIG-001",
        "procedure_sequence": 3,
        "procedure_action": "Channel Bandwidth 설정 확인",
        "acceptance_criteria": "20MHz 사용 권장\n[기대결과] Channel Bandwidth가 20MHz로 설정되어 있어야 함",
        "required_evidence_type": "screenshot",
        "product_test_procedure_status": "active",
        "created_at": "2026-05-05 08:42:00",
        "created_by": "SQA_MASTER",
        "updated_at": "2026-05-05 08:42:00",
        "updated_by": "SQA_MASTER",
        "remark": "WiFi 모듈 RS9116은 20MHz만 지원함.",
    },
    {
            "product_test_procedure_id": "SQA_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-004",
            "product_test_case_id": "SQA_PRODUCT_TEST_CASE_ID-WIFI-AP_CONFIG-001",
        "procedure_sequence": 4,
        "procedure_action": "WiFi 규격 Mode 설정 확인",
        "acceptance_criteria": "802.11 a/b/g/n, WiFi 4 권장\n[기대결과] WiFi Mode가 802.11 a/b/g/n, WiFi 4 호환 범위여야 함",
        "required_evidence_type": "screenshot",
        "product_test_procedure_status": "active",
        "created_at": "2026-05-05 08:43:00",
        "created_by": "SQA_MASTER",
        "updated_at": "2026-05-05 08:43:00",
        "updated_by": "SQA_MASTER",
        "remark": "일반적으로 하위 호환은 되나 WiFi 6(ax)부터 Beacon 제어 방식 차이로 parsing 이 안 될 가능성이 있음.",
    },
    {
            "product_test_procedure_id": "SQA_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-005",
            "product_test_case_id": "SQA_PRODUCT_TEST_CASE_ID-WIFI-AP_CONFIG-001",
        "procedure_sequence": 5,
        "procedure_action": "WiFi Security 설정 확인",
        "acceptance_criteria": "WPA2 설정 권장\n[기대결과] AP Security가 WPA2로 설정되어 있어야 함",
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


def _parse_release_work_period_remark(remark: str) -> dict[str, str]:
    workday = ""
    start_date = ""
    end_date = ""
    for line in (remark or "").split("\n"):
        line = line.strip()
        if line.startswith("[Workday]"):
            workday = line.replace("[Workday]", "").strip()
        elif line.startswith("[Start]"):
            rest = line.replace("[Start]", "").strip()
            if "[End]" in rest:
                start_part, end_part = rest.split("[End]", 1)
                start_date = "" if start_part.strip() in ("", "None") else start_part.strip()
                end_date = "" if end_part.strip() in ("", "None") else end_part.strip()
            else:
                start_date = "" if rest in ("", "None") else rest
        elif line.startswith("[End]"):
            value = line.replace("[End]", "").strip()
            end_date = "" if value in ("", "None") else value
    return {"workday": workday, "start_date": start_date, "end_date": end_date}


def _release_work_period_remark(remark: str) -> str:
    period = _parse_release_work_period_remark(remark)
    parts = []
    if period["workday"]:
        parts.append(f"Workday: {period['workday']}")
    if period["start_date"]:
        parts.append(f"Start: {period['start_date']}")
    if period["end_date"]:
        parts.append(f"End: {period['end_date']}")
    return f"[Release Work Period] {' / '.join(parts)}" if parts else ""


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
    "test_round_id": re.compile(r"^SQA_PRODUCT_TEST_RELEASE_ID-[A-Z0-9_]+-[0-9]+(?:\.[0-9]+)*-(?:RC[0-9]+|GA|HF[0-9]+)$"),
    "product_test_target_id": re.compile(r"^SQA_PRODUCT_TEST_TARGET_ID-[A-Z0-9_]+-[A-Z0-9_]+$"),
    "product_test_environment_definition_id": re.compile(r"^SQA_PRODUCT_TEST_ENVIRONMENT_DEFINITION_ID-[A-Z0-9_]+(?:-[A-Z0-9_]+){2,}$"),
    "product_test_environment_id": re.compile(r"^SQA_PRODUCT_TEST_ENVIRONMENT_ID-[A-Z0-9_]+(?:-[A-Z0-9_]+){2,}-\d{8}-\d{3}$"),
    "product_test_case_id": re.compile(r"^SQA_PRODUCT_TEST_CASE_ID-[A-Z0-9_]+(?:-[A-Z0-9_]+)+-\d{3}$"),
    "product_test_procedure_id": re.compile(r"^SQA_PRODUCT_TEST_PROCEDURE_ID-[A-Z0-9_]+(?:-[A-Z0-9_]+)+-\d{3}$"),
}

PRODUCT_TEST_IDENTIFIER_GUIDES: dict[str, str] = {
    "test_round_id": "PRODUCT_TEST_RELEASE_ID 작성규칙위반. SQA_PRODUCT_TEST_RELEASE_ID-ITEM-1.0.0-RC1 쓰거나 SQA_PRODUCT_TEST_RELEASE_ID-ITEM-1.0.0-GA 써라.",
    "product_test_target_id": "PRODUCT_TEST_TARGET_ID 작성규칙위반. SQA_PRODUCT_TEST_TARGET_ID-HRK_9000A-SN001 써라.",
    "product_test_environment_definition_id": "PRODUCT_TEST_ENVIRONMENT_DEFINITION_ID 작성규칙위반. SQA_PRODUCT_TEST_ENVIRONMENT_DEFINITION_ID-COMPANY-CITY-ROOM 써라.",
    "product_test_environment_id": "PRODUCT_TEST_ENVIRONMENT_ID 작성규칙위반. SQA_PRODUCT_TEST_ENVIRONMENT_ID-COMPANY-CITY-ROOM-YYYYMMDD-001 써라.",
    "product_test_case_id": "PRODUCT_TEST_CASE_ID 작성규칙위반. SQA_PRODUCT_TEST_CASE_ID-WIFI-AP_CONFIG-001 써라.",
    "product_test_procedure_id": "PRODUCT_TEST_PROCEDURE_ID 작성규칙위반. SQA_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-001 써라.",
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

def _entity_model(entity_type: str):
    return {
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


def _round_is_locked(database_session: Session, test_round_id: str) -> bool:
    approved_report_count = (
        database_session.scalar(
            select(func.count()).select_from(ProductTestReport).where(
                ProductTestReport.test_round_id == test_round_id,
                ProductTestReport.product_test_report_status == "APPROVED",
            )
        )
        or 0
    )
    return int(approved_report_count) > 0


def _ensure_round_not_locked_for_source_mutation(
    database_session: Session,
    *,
    test_round_id: str,
) -> None:
    if _round_is_locked(database_session, test_round_id):
        _raise_locked_release_error()


def _ensure_run_not_locked_for_source_mutation(
    database_session: Session,
    *,
    product_test_run_id: str,
) -> ProductTestRun:
    run_row = database_session.get(ProductTestRun, product_test_run_id)
    if run_row is None:
        raise LookupError("Run not found.")
    _ensure_round_not_locked_for_source_mutation(
        database_session,
        test_round_id=run_row.test_round_id,
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
    _ensure_round_not_locked_for_source_mutation(
        database_session,
        test_round_id=run_row.test_round_id,
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

def _query_all_rows(database_session: Session, model, order_by_column: str | None = None) -> list[Any]:
    statement = select(model)
    if order_by_column:
        statement = statement.order_by(getattr(model, order_by_column))
    return list(database_session.scalars(statement))


def _list_rows_as_dicts(
    database_session: Session,
    *,
    model,
    columns: list[str],
    order_by_column: str | None = None,
) -> list[dict[str, Any]]:
    """DB에 저장된 행만 반환한다. 빈 테이블이면 빈 리스트(데모 샘플을 목록에 끼워 넣지 않음)."""
    rows = _query_all_rows(database_session, model, order_by_column)
    return [_as_dict(row, columns) for row in rows]


def _find_fallback_row(rows: list[dict[str, Any]], key_name: str, key_value: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get(key_name) == key_value:
            return dict(row)
    return None



