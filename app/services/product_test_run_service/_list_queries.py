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
    _find_fallback_row,
    _list_rows_as_dicts,
    _query_all_rows,
)


def list_product_test_rounds(database_session: Session) -> list[dict[str, Any]]:
    return _list_rows_as_dicts(
        database_session,
        model=ProductTestRound,
        columns=[
            "test_round_id",
            "test_round_name",
            "workday",
            "start_date",
            "end_date",
            "date_quality",
            "migration_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
        ],
        order_by_column="test_round_id",
    )


def list_product_test_runs(database_session: Session) -> list[dict[str, Any]]:
    rows = _list_rows_as_dicts(
        database_session,
        model=ProductTestRun,
        columns=[
            "product_test_run_id",
            "test_round_id",
            "product_test_target_id",
            "product_test_environment_id",
            "product_test_run_status",
            "started_at",
            "finished_at",
            "remark",
        ],
        order_by_column="test_round_id",
    )
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("test_round_id") or ""),
            str(row.get("started_at") or ""),
            str(row.get("product_test_run_id") or ""),
        ),
    )


def list_product_test_targets(database_session: Session) -> list[dict[str, Any]]:
    return _list_rows_as_dicts(
        database_session,
        model=ProductTestTargetUnified,
        columns=[
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
        order_by_column="created_at",
    )


def list_product_test_environment_definitions(database_session: Session) -> list[dict[str, Any]]:
    return _list_rows_as_dicts(
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
            "product_test_environment_status",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "remark",
        ],
        order_by_column="created_at",
    )


def list_product_test_environments(database_session: Session) -> list[dict[str, Any]]:
    return _list_rows_as_dicts(
        database_session,
        model=ProductTestEnvironment,
        columns=[
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
        order_by_column="created_at",
    )


def list_product_test_cases(database_session: Session) -> list[dict[str, Any]]:
    return _list_rows_as_dicts(
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
        order_by_column="created_at",
    )


def list_product_test_procedures(database_session: Session) -> list[dict[str, Any]]:
    return _list_rows_as_dicts(
        database_session,
        model=ProductTestProcedure,
        columns=[
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
        order_by_column="product_test_case_id",
    )


def list_round_options(database_session: Session) -> list[dict[str, Any]]:
    return list_product_test_rounds(database_session)


def list_target_options(database_session: Session) -> list[dict[str, Any]]:
    return list_product_test_targets(database_session)


def list_environment_options(database_session: Session) -> list[dict[str, Any]]:
    return list_product_test_environments(database_session)


def list_case_options(database_session: Session) -> list[dict[str, Any]]:
    return list_product_test_cases(database_session)

def _target_summary(database_session: Session, product_test_target_id: str) -> dict[str, Any]:
    target_row = database_session.get(ProductTestTargetUnified, product_test_target_id)
    if target_row is None:
        fallback = _find_fallback_row(_sample_product_test_target_rows, "product_test_target_id", product_test_target_id) or {}
        return {
            "product_test_target_id": product_test_target_id,
            "product_code": fallback.get("product_code", ""),
            "manufacturer": fallback.get("manufacturer", ""),
            "model_name": fallback.get("model_name", ""),
            "serial_number": fallback.get("serial_number", ""),
            "software_version": fallback.get("software_version", ""),
            "firmware_version": fallback.get("firmware_version", ""),
            "manufacture_lot": fallback.get("manufacture_lot", ""),
        }
    return {
        "product_test_target_id": target_row.product_test_target_id,
        "product_code": target_row.product_code or "",
        "manufacturer": target_row.manufacturer or "",
        "model_name": target_row.model_name or "",
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
    return {
        "product_test_environment_id": environment_row.product_test_environment_id,
        "product_test_environment_name": environment_row.product_test_environment_name,
        "test_country": environment_row.test_country or "",
        "test_city": environment_row.test_city or "",
        "test_company": environment_row.test_company or "",
        "test_building": environment_row.test_building or "",
        "test_floor": environment_row.test_floor or "",
        "test_room": environment_row.test_room or "",
        "network_type": environment_row.network_type or "",
        "test_computer_name": environment_row.test_computer_name or "",
        "operating_system_version": environment_row.operating_system_version or "",
        "test_tool_version": environment_row.test_tool_version or "",
        "power_voltage": environment_row.power_voltage or "",
        "power_frequency": environment_row.power_frequency or "",
        "power_connector_type": environment_row.power_connector_type or "",
        "power_condition": environment_row.power_condition or "",
    }

def list_running_run_options(database_session: Session) -> list[dict[str, Any]]:
    return [
        _as_dict(
            row,
            [
                "product_test_run_id",
                "test_round_id",
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
