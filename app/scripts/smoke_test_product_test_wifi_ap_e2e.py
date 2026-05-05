from __future__ import annotations

import json

from sqlalchemy import func, select, text

from app.db import engine, initialize_database, session_local
from app.models import (
    ProductTestDefect,
    ProductTestEvidence,
    ProductTestProcedureResult,
    ProductTestReport,
    ProductTestResult,
    ProductTestRun,
    ProductTestTargetDefinition,
)
from app.services.product_test_run_service import (
    approve_product_test_report,
    get_product_test_report_detail,
    seed_product_test_wifi_ap_configuration_sample_data,
)


SEEDED_TARGET_DEFINITION_IDS = [
    "PTTGTDEF-HUVITZ_HRK_9000A",
    "PTTGTDEF-HUVITZ_HLM_9000",
    "PTTGTDEF-HUVITZ_HTR_TBD",
    "PTTGTDEF-HUVITZ_HDR_9000_OP",
    "PTTGTDEF-HUVITZ_HDR_9000_JUNCTION_BOX",
    "PTTGTDEF-HUVITZ_HDR_9000_UNKNOWN",
    "PTTGTDEF-HUVITZ_HDC_9100",
    "PTTGTDEF-MERCUSYS_MR30G",
    "PTTGTDEF-TBD_LENS",
    "PTTGTDEF-TBD_MODELAI",
    "PTTGTDEF-TBD_JUNCTION_BOX_POWER_CABLE",
    "PTTGTDEF-TBD_HDC_POWER_CABLE",
    "PTTGTDEF-TBD_HLM_POWER_CABLE_L_FORM_POWER_CABLE",
    "PTTGTDEF-TBD_OP_SIGNAL_AND_POWER_CABLE",
    "PTTGTDEF-TBD_HDR_SIGNAL_AND_POWER_CABLE",
]


def _assert_seed_is_idempotent() -> None:
    with session_local() as database_session:
        seed_product_test_wifi_ap_configuration_sample_data(database_session)
        first_counts = {
            "target_definition_count": database_session.scalar(
                select(func.count()).select_from(ProductTestTargetDefinition).where(
                    ProductTestTargetDefinition.product_test_target_definition_id.in_(
                        SEEDED_TARGET_DEFINITION_IDS
                    )
                )
            ),
            "run_count": database_session.scalar(
                select(func.count()).select_from(ProductTestRun).where(
                    ProductTestRun.product_test_run_id == "PTRUN-20260504-0001"
                )
            ),
            "result_count": database_session.scalar(
                select(func.count()).select_from(ProductTestResult).where(
                    ProductTestResult.product_test_result_id == "PTRES-20260504-0001"
                )
            ),
            "procedure_result_count": database_session.scalar(
                select(func.count()).select_from(ProductTestProcedureResult).where(
                    ProductTestProcedureResult.product_test_result_id == "PTRES-20260504-0001"
                )
            ),
            "evidence_count": database_session.scalar(
                select(func.count()).select_from(ProductTestEvidence).where(
                    ProductTestEvidence.product_test_result_id == "PTRES-20260504-0001"
                )
            ),
            "defect_count": database_session.scalar(
                select(func.count()).select_from(ProductTestDefect).where(
                    ProductTestDefect.product_test_result_id == "PTRES-20260504-0001"
                )
            ),
            "report_count": database_session.scalar(
                select(func.count()).select_from(ProductTestReport).where(
                    ProductTestReport.product_test_report_id
                    == "PTRPT-PTREL-MERCUSYS_MR30G-1.0.0-RC1-FULL-001"
                )
            ),
        }
        seed_product_test_wifi_ap_configuration_sample_data(database_session)
        second_counts = {
            "target_definition_count": database_session.scalar(
                select(func.count()).select_from(ProductTestTargetDefinition).where(
                    ProductTestTargetDefinition.product_test_target_definition_id.in_(
                        SEEDED_TARGET_DEFINITION_IDS
                    )
                )
            ),
            "run_count": database_session.scalar(
                select(func.count()).select_from(ProductTestRun).where(
                    ProductTestRun.product_test_run_id == "PTRUN-20260504-0001"
                )
            ),
            "result_count": database_session.scalar(
                select(func.count()).select_from(ProductTestResult).where(
                    ProductTestResult.product_test_result_id == "PTRES-20260504-0001"
                )
            ),
            "procedure_result_count": database_session.scalar(
                select(func.count()).select_from(ProductTestProcedureResult).where(
                    ProductTestProcedureResult.product_test_result_id == "PTRES-20260504-0001"
                )
            ),
            "evidence_count": database_session.scalar(
                select(func.count()).select_from(ProductTestEvidence).where(
                    ProductTestEvidence.product_test_result_id == "PTRES-20260504-0001"
                )
            ),
            "defect_count": database_session.scalar(
                select(func.count()).select_from(ProductTestDefect).where(
                    ProductTestDefect.product_test_result_id == "PTRES-20260504-0001"
                )
            ),
            "report_count": database_session.scalar(
                select(func.count()).select_from(ProductTestReport).where(
                    ProductTestReport.product_test_report_id
                    == "PTRPT-PTREL-MERCUSYS_MR30G-1.0.0-RC1-FULL-001"
                )
            ),
        }
    assert first_counts == second_counts, (first_counts, second_counts)


def _assert_report_detail_and_approval_guard() -> dict[str, object]:
    with session_local() as database_session:
        detail = get_product_test_report_detail(
            database_session,
            "PTRPT-PTREL-MERCUSYS_MR30G-1.0.0-RC1-FULL-001",
        )
        assert detail is not None
        summary = detail["result_summary"]
        assert summary["total_result_count"] == 1
        assert summary["failed_count"] == 1
        assert summary["procedure_result_count"] == 5
        assert summary["procedure_failed_count"] == 2
        assert summary["evidence_count"] >= 5
        assert summary["unresolved_defect_count"] >= 1
        approval_blocked = False
        approval_error = ""
        try:
            approve_product_test_report(
                database_session,
                product_test_report_id="PTRPT-PTREL-MERCUSYS_MR30G-1.0.0-RC1-FULL-001",
                approved_by="SQA_MASTER",
            )
        except ValueError as exc:
            approval_blocked = True
            approval_error = str(exc)
        assert approval_blocked, "Report approval must be blocked while opened defects exist."
        return {
            "summary": summary,
            "approval_error": approval_error,
        }


def _assert_product_test_report_item_absent() -> None:
    with engine.begin() as connection:
        row = connection.execute(
            text(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table' AND name='product_test_report_item'
                """
            )
        ).fetchone()
    assert row is None, "product_test_report_item table must not exist."


def main() -> None:
    initialize_database()
    _assert_seed_is_idempotent()
    report_payload = _assert_report_detail_and_approval_guard()
    _assert_product_test_report_item_absent()
    print(
        json.dumps(
            {
                "status": "ok",
                "expected_summary": report_payload["summary"],
                "approval_guard": report_payload["approval_error"],
                "product_test_report_item": "not added",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
