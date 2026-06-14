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
    _query_all_rows,
)
from app.services.product_test_run_service._list_queries import (
    list_product_test_rounds,
    list_product_test_runs,
    list_product_test_targets,
    list_product_test_environments,
    list_product_test_cases,
    list_product_test_procedures,
)


def get_product_test_system_check(database_session: Session) -> dict[str, Any]:
    table_names = [
        "product_test_round",
        "product_test_target_unified",
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
    locked_round_count = (
        database_session.scalar(
            select(func.count(func.distinct(ProductTestReport.test_round_id))).where(
                ProductTestReport.product_test_report_status == "APPROVED"
            )
        )
        or 0
    )
    seed_data_presence = {
        "wifi_case": database_session.get(ProductTestCase, "dummy_PRODUCT_TEST_CASE_ID-WIFI-AP_CONFIG-001") is not None,
        "wifi_round": database_session.get(ProductTestRound, "ROUND-WIFI_1ST") is not None,
        "wifi_run": database_session.get(ProductTestRun, "dummy_PRODUCT_TEST_RUN_ID-20260504-0001") is not None,
        "wifi_result": database_session.get(ProductTestResult, "dummy_PRODUCT_TEST_RESULT_ID-20260504-0001") is not None,
        "wifi_report": database_session.get(ProductTestReport, "dummy_PRODUCT_TEST_REPORT_ID-dummy_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1-FULL-001") is not None,
    }
    return {
        "table_rows": table_rows,
        "seed_data_presence": seed_data_presence,
        "unresolved_defects_count": int(unresolved_defects_count),
        "report_count": int(report_count),
        "approved_report_count": int(approved_report_count),
        "locked_round_count": int(locked_round_count),
    }


def get_test_round_id_by_result_id(database_session: Session, product_test_result_id: str) -> str:
    result_row = database_session.get(ProductTestResult, product_test_result_id)
    if result_row is None:
        raise LookupError("Result not found.")
    run_row = database_session.get(ProductTestRun, result_row.product_test_run_id)
    if run_row is None:
        raise LookupError("Run not found for result.")
    return run_row.test_round_id
