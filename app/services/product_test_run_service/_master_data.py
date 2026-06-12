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
from app.services.product_test_run_service._common import (
    _as_dict,
    _commit_or_rollback,
    _now_text,
    _validate_in,
    _validate_product_test_identifier_format,
    build_product_code,
    ENVIRONMENT_STATUS_VALUES,
    EVIDENCE_TYPE_VALUES,
    MASTER_ACTIVE_STATUS_VALUES,
    TARGET_STATUS_VALUES,
)


def create_product_test_target(
    database_session: Session,
    *,
    product_test_target_id: str,
    product_code: str,
    manufacturer: str,
    model_name: str,
    hardware_revision: str,
    default_software_version: str,
    default_firmware_version: str,
    serial_number: str,
    software_version: str,
    firmware_version: str,
    manufacture_lot: str,
    product_test_target_status: str,
    actor_name: str,
    remark: str,
) -> dict[str, Any]:
    target_id = _validate_product_test_identifier_format("product_test_target_id", product_test_target_id)
    manufacturer_value = str(manufacturer or "").strip()
    model_name_value = str(model_name or "").strip()
    serial_number_value = str(serial_number or "").strip()
    if not target_id or not manufacturer_value or not model_name_value or not serial_number_value:
        raise ValueError("product_test_target_id, manufacturer, model_name, serial_number are required.")
    if database_session.get(ProductTestTargetUnified, target_id) is not None:
        raise ValueError("product_test_target_id already exists.")
    status_value = _validate_in(
        str(product_test_target_status or "").strip().upper(),
        TARGET_STATUS_VALUES,
        "product_test_target_status",
    )
    now_text = _now_text()
    row = ProductTestTargetUnified(
        product_test_target_id=target_id,
        product_code=str(product_code or "").strip() or build_product_code(manufacturer_value, model_name_value),
        manufacturer=manufacturer_value,
        model_name=model_name_value,
        hardware_revision=str(hardware_revision or "").strip() or None,
        default_software_version=str(default_software_version or "").strip() or None,
        default_firmware_version=str(default_firmware_version or "").strip() or None,
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
            "product_code",
            "manufacturer",
            "model_name",
            "hardware_revision",
            "default_software_version",
            "default_firmware_version",
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
    environment_id = definition_id.replace("CONFIG_DEF-", "CONFIG-", 1) if definition_id.startswith("CONFIG_DEF-") else definition_id
    if database_session.get(ProductTestEnvironment, environment_id) is not None:
        raise ValueError("product_test_environment_definition_id already exists.")
    status_value = _validate_in(
        str(product_test_environment_definition_status or "").strip().upper(),
        MASTER_ACTIVE_STATUS_VALUES,
        "product_test_environment_definition_status",
    )
    now_text = _now_text()
    row = ProductTestEnvironment(
        product_test_environment_id=environment_id,
        product_test_environment_name=definition_name,
        product_test_environment_status=status_value,
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
        captured_at=None,
        test_tool_version=str(test_tool_version or "").strip() or None,
        power_voltage=str(power_voltage or "").strip() or None,
        power_frequency=str(power_frequency or "").strip() or None,
        power_connector_type=str(power_connector_type or "").strip() or None,
        power_condition=str(power_condition or "").strip() or None,
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
            "test_tool_name",
            "test_tool_version",
            "power_voltage",
            "power_frequency",
            "power_connector_type",
            "power_condition",
            "product_test_environment_status",
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
    product_test_environment_name: str,
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
    captured_at: str,
    product_test_environment_status: str,
    actor_name: str,
    remark: str,
) -> dict[str, Any]:
    environment_id = _validate_product_test_identifier_format("product_test_environment_id", product_test_environment_id)
    environment_name = str(product_test_environment_name or "").strip()
    if not environment_id or not environment_name:
        raise ValueError("product_test_environment_id and name are required.")
    if database_session.get(ProductTestEnvironment, environment_id) is not None:
        raise ValueError("product_test_environment_id already exists.")
    status_value = _validate_in(
        str(product_test_environment_status or "").strip().upper(),
        ENVIRONMENT_STATUS_VALUES,
        "product_test_environment_status",
    )
    now_text = _now_text()
    row = ProductTestEnvironment(
        product_test_environment_id=environment_id,
        product_test_environment_name=environment_name,
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
            "test_tool_name",
            "test_tool_version",
            "power_voltage",
            "power_frequency",
            "power_connector_type",
            "power_condition",
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
