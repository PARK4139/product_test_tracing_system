from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import (
    ProductTestCase,
    ProductTestDefect,
    ProductTestConfig,
    ProductTestConfigDefinition,
    ProductTestEvidence,
    ProductTestProcedure,
    ProductTestProcedureResult,
    ProductTestRound,
    ProductTestResult,
    ProductTestRun,
    ProductTestStatusTransition,
    ProductTestTargetUnified,
    get_utc_now_datetime,
)
from app.services.product_test_run_service._common import (
    _commit_or_rollback,
    _next_prefixed_id,
    _sample_product_test_case_rows,
    _sample_product_test_config_definition_rows,
    _sample_product_test_config_rows,
    _sample_product_test_procedure_rows,
    _sample_product_test_target_rows,
    _validate_in,
    _validate_product_test_identifier_format,
    _now_text,
    _as_dict,
    build_product_code,
    ENTITY_TYPE_VALUES,
)
from app.services.product_test_run_service._status import (
    _insert_status_transition,
    ensure_product_test_status_transition_recorded,
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
    date_digits = re.sub(r"\D", "", str(transitioned_at or ""))[:8]
    if len(date_digits) < 8:
        date_digits = get_utc_now_datetime().astimezone().strftime("%Y%m%d")
    transition_prefix = f"dummy_PRODUCT_TEST_STATUS_TRANSITION_ID-{date_digits}"
    row = ProductTestStatusTransition(
        product_test_status_transition_id=_next_prefixed_id(
            database_session,
            ProductTestStatusTransition,
            "product_test_status_transition_id",
            transition_prefix,
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
    database_session.flush()
    return row


def seed_product_test_wifi_ap_configuration_sample_data(database_session: Session) -> None:
    actor_name = "dummy_MASTER"
    seed_created_at = "2026-05-04 09:00"
    seed_updated_at = "2026-05-04 10:30"

    _upsert_model_row(
        database_session,
        ProductTestTargetUnified,
        "product_test_target_id",
        {
            "product_test_target_id": "dummy_PRODUCT_TEST_TARGET_ID-MERCUSYS_MR30G-SN001",
            "product_code": "MERCUSYS_MR30G",
            "manufacturer": "MERCUSYS",
            "model_name": "MR30G",
            "hardware_revision": None,
            "default_software_version": "1.0.0",
            "default_firmware_version": "1.0.3",
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
        ProductTestConfig,
        "product_test_config_id",
        {
            "product_test_config_id": "dummy_PRODUCT_TEST_ENVIRONMENT_DEFINITION_ID-HUVITZ-ANYANG-CONNECTIVITY_ROOM",
            "product_test_config_name": "Huvitz Anyang Connectivity Room Standard Environment",
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
            "product_test_config_status": "active",
            "created_at": seed_created_at,
            "created_by": actor_name,
            "updated_at": seed_updated_at,
            "updated_by": actor_name,
            "remark": None,
            "captured_at": None,
        },
    )

    database_session.flush()

    _upsert_model_row(
        database_session,
        ProductTestConfig,
        "product_test_config_id",
        {
            "product_test_config_id": "dummy_PRODUCT_TEST_ENVIRONMENT_ID-HUVITZ-ANYANG-CONNECTIVITY_ROOM-20260504-001",
            "product_test_config_name": "Huvitz Anyang Connectivity Room Snapshot 20260504",
            "test_country": "Korea",
            "test_city": "Anyang",
            "test_company": "Huvitz",
            "test_building": None,
            "test_floor": "6F",
            "test_room": "Connectivity Room",
            "test_computer_name": "SQA-PC-01",
            "operating_system_version": "Windows 10",
            "test_tool_name": "Product Test Tool",
            "test_tool_version": "1.0.0",
            "network_type": "ISOLATED_NETWORK",
            "power_voltage": "220V",
            "power_frequency": "60Hz",
            "power_connector_type": "OO_CONNECTOR",
            "power_condition": "Commercial AC power",
            "captured_at": "2026-05-04 09:00",
            "product_test_config_status": "active",
            "created_at": seed_created_at,
            "created_by": actor_name,
            "updated_at": seed_updated_at,
            "updated_by": actor_name,
            "remark": None,
        },
    )

    database_session.flush()

    _upsert_model_row(
        database_session,
        ProductTestCase,
        "product_test_case_id",
        {
            "product_test_case_id": "dummy_PRODUCT_TEST_CASE_ID-WIFI-AP_CONFIG-001",
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
            "product_test_procedure_id": "dummy_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-001",
            "procedure_sequence": 1,
            "procedure_action": "WiFi Band 분리설정 확인",
            "acceptance_criteria": "2.4GHz, 5GHz의 SSID를 분리하는 것을 권장\n[기대결과] 2.4GHz와 5GHz SSID가 분리되어 있어야 함",
            "required_evidence_type": "screenshot",
            "remark": "분리하지 않은 경우 임베디드 장비가 2.4GHz로 할당될 가능성이 높음. 원하는 SSID에 접근할 수 있도록 분리 권장.",
        },
        {
            "product_test_procedure_id": "dummy_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-002",
            "procedure_sequence": 2,
            "procedure_action": "WiFi Channel 설정 확인",
            "acceptance_criteria": "2.4GHz는 1~11번 채널 고정 사용 권장. 5GHz는 DFS 채널이 아닌 36, 40, 44, 48 채널 고정 사용 권장\n[기대결과] 2.4GHz는 1~11번 고정 채널, 5GHz는 DFS가 아닌 36, 40, 44, 48 채널이어야 함",
            "required_evidence_type": "screenshot",
            "remark": "5GHz에서 DFS 채널을 사용하는 경우 WiFi 모듈이 AP를 검색하지 못할 수 있음.",
        },
        {
            "product_test_procedure_id": "dummy_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-003",
            "procedure_sequence": 3,
            "procedure_action": "Channel Bandwidth 설정 확인",
            "acceptance_criteria": "20MHz 사용 권장\n[기대결과] Channel Bandwidth가 20MHz로 설정되어 있어야 함",
            "required_evidence_type": "screenshot",
            "remark": "WiFi 모듈 RS9116은 20MHz만 지원함.",
        },
        {
            "product_test_procedure_id": "dummy_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-004",
            "procedure_sequence": 4,
            "procedure_action": "WiFi 규격 Mode 설정 확인",
            "acceptance_criteria": "802.11 a/b/g/n, WiFi 4 권장\n[기대결과] WiFi Mode가 802.11 a/b/g/n, WiFi 4 호환 범위여야 함",
            "required_evidence_type": "screenshot",
            "remark": "일반적으로 하위 호환은 되나 WiFi 6(ax)부터 Beacon 제어 방식 차이로 AP에 따라 정상 parsing이 안 될 가능성이 있음.",
        },
        {
            "product_test_procedure_id": "dummy_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-005",
            "procedure_sequence": 5,
            "procedure_action": "WiFi Security 설정 확인",
            "acceptance_criteria": "WPA2 설정 권장\n[기대결과] AP Security가 WPA2로 설정되어 있어야 함",
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
                "product_test_case_id": "dummy_PRODUCT_TEST_CASE_ID-WIFI-AP_CONFIG-001",
                "procedure_sequence": item["procedure_sequence"],
                "procedure_action": item["procedure_action"],
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
        ProductTestRound,
        "test_round_id",
        {
            "test_round_id": "dummy_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1",
            "test_round_name": "MERCUSYS MR30G 1.0.0 RC1 Sample Round",
            "workday": None,
            "start_date": "2026-05-04",
            "end_date": None,
            "date_quality": "EXACT",
            "migration_status": "testing",
            "migration_note": "wifi ap configuration sample seed",
            "project_id": None,
            "created_at": seed_created_at,
            "created_by": actor_name,
            "updated_at": seed_updated_at,
            "updated_by": actor_name,
        },
    )

    _upsert_model_row(
        database_session,
        ProductTestRun,
        "product_test_run_id",
        {
            "product_test_run_id": "dummy_PRODUCT_TEST_RUN_ID-20260504-0001",
            "test_round_id": "dummy_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1",
            "product_test_target_id": "dummy_PRODUCT_TEST_TARGET_ID-MERCUSYS_MR30G-SN001",
            "product_test_config_id": "dummy_PRODUCT_TEST_ENVIRONMENT_ID-HUVITZ-ANYANG-CONNECTIVITY_ROOM-20260504-001",
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

    database_session.flush()

    _upsert_model_row(
        database_session,
        ProductTestResult,
        "product_test_result_id",
        {
            "product_test_result_id": "dummy_PRODUCT_TEST_RESULT_ID-20260504-0001",
            "product_test_run_id": "dummy_PRODUCT_TEST_RUN_ID-20260504-0001",
            "product_test_case_id": "dummy_PRODUCT_TEST_CASE_ID-WIFI-AP_CONFIG-001",
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

    database_session.flush()

    procedure_result_seed_rows = [
        {
            "product_test_procedure_result_id": "dummy_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0001",
            "product_test_procedure_id": "dummy_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-001",
            "product_test_procedure_result_status": "passed",
            "actual_result": "2.4GHz와 5GHz SSID가 분리되어 있음",
            "judgement_reason": None,
        },
        {
            "product_test_procedure_result_id": "dummy_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0002",
            "product_test_procedure_id": "dummy_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-002",
            "product_test_procedure_result_status": "failed",
            "actual_result": "5GHz Channel이 DFS 채널로 설정되어 있음",
            "judgement_reason": "DFS 채널 사용으로 RS9116 AP scan 실패 가능",
        },
        {
            "product_test_procedure_result_id": "dummy_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0003",
            "product_test_procedure_id": "dummy_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-003",
            "product_test_procedure_result_status": "passed",
            "actual_result": "Channel Bandwidth 20MHz 확인",
            "judgement_reason": None,
        },
        {
            "product_test_procedure_result_id": "dummy_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0004",
            "product_test_procedure_id": "dummy_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-004",
            "product_test_procedure_result_status": "passed",
            "actual_result": "WiFi Mode가 802.11 b/g/n 호환으로 설정됨",
            "judgement_reason": None,
        },
        {
            "product_test_procedure_result_id": "dummy_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0005",
            "product_test_procedure_id": "dummy_PRODUCT_TEST_PROCEDURE_ID-WIFI-AP_CONFIG-001-005",
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
                "product_test_result_id": "dummy_PRODUCT_TEST_RESULT_ID-20260504-0001",
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

    database_session.flush()

    for index, procedure_result_id in enumerate(
        [
            "dummy_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0001",
            "dummy_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0002",
            "dummy_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0003",
            "dummy_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0004",
            "dummy_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0005",
        ],
        start=1,
    ):
        _upsert_model_row(
            database_session,
            ProductTestEvidence,
            "product_test_evidence_id",
            {
                "product_test_evidence_id": f"dummy_PRODUCT_TEST_EVIDENCE_ID-20260504-{index:04d}",
                "product_test_result_id": "dummy_PRODUCT_TEST_RESULT_ID-20260504-0001",
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

    database_session.flush()

    defect_seed_rows = [
        {
            "product_test_defect_id": "dummy_PRODUCT_TEST_DEFECT_ID-20260504-0001",
            "product_test_procedure_result_id": "dummy_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0002",
            "defect_title": "5GHz DFS Channel 설정으로 RS9116 AP Scan 실패 가능",
            "defect_description": "5GHz 채널이 DFS 채널로 설정되어 있어 RS9116 WiFi 모듈이 AP를 검색하지 못할 수 있음.",
        },
        {
            "product_test_defect_id": "dummy_PRODUCT_TEST_DEFECT_ID-20260504-0002",
            "product_test_procedure_result_id": "dummy_PRODUCT_TEST_PROCEDURE_RESULT_ID-20260504-0005",
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
                "product_test_result_id": "dummy_PRODUCT_TEST_RESULT_ID-20260504-0001",
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

    transition_seed_rows = [
        ("product_test_round", "dummy_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1", None, "DRAFT", "seed_release_drafted", actor_name, "2026-05-04 09:05"),
        ("product_test_round", "dummy_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1", "DRAFT", "TESTING", "seed_release_testing", actor_name, "2026-05-04 09:10"),
        ("product_test_run", "dummy_PRODUCT_TEST_RUN_ID-20260504-0001", None, "running", "seed_run_started", "Tester-A", "2026-05-04 10:00"),
        ("product_test_run", "dummy_PRODUCT_TEST_RUN_ID-20260504-0001", "running", "finished", "seed_run_finished", "Tester-A", "2026-05-04 10:30"),
        ("product_test_result", "dummy_PRODUCT_TEST_RESULT_ID-20260504-0001", None, "testing", "seed_result_started", "Tester-A", "2026-05-04 10:00"),
        ("product_test_result", "dummy_PRODUCT_TEST_RESULT_ID-20260504-0001", "testing", "failed", "seed_result_failed", "Tester-A", "2026-05-04 10:30"),
        ("product_test_defect", "dummy_PRODUCT_TEST_DEFECT_ID-20260504-0001", None, "opened", "seed_defect_opened", "Tester-A", "2026-05-04 10:30"),
        ("product_test_defect", "dummy_PRODUCT_TEST_DEFECT_ID-20260504-0002", None, "opened", "seed_defect_opened", "Tester-A", "2026-05-04 10:30"),
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
