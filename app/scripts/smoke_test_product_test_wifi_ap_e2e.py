from __future__ import annotations

import json

from sqlalchemy import func, select, text

from app.db import engine, initialize_database, session_local
from app.models import (
    ProductTestDefect,
    ProductTestEvidence,
    ProductTestProcedureResult,
    ProductTestReport,
    ProductTestReportSnapshot,
    ProductTestResult,
    ProductTestRun,
    ProductTestTargetDefinition,
)
from app.services.product_test_run_service import (
    approve_product_test_report,
    compare_product_test_report_snapshots,
    create_product_test_report_snapshot,
    get_product_test_report_detail,
    seed_product_test_wifi_ap_configuration_sample_data,
    transition_product_test_defect_to_rejected,
)


SEEDED_TARGET_DEFINITION_IDS = [
    "QA_PTTGTDEF-HRK_9000A",
    "QA_PTTGTDEF-HUVITZ_HLM_9000",
    "QA_PTTGTDEF-HUVITZ_HTR_TBD",
    "QA_PTTGTDEF-HUVITZ_HDR_9000_OP",
    "QA_PTTGTDEF-HUVITZ_HDR_9000_JUNCTION_BOX",
    "QA_PTTGTDEF-HUVITZ_HDR_9000_UNKNOWN",
    "QA_PTTGTDEF-HUVITZ_HDC_9100",
    "QA_PTTGTDEF-MERCUSYS_MR30G",
    "QA_PTTGTDEF-TBD_LENS",
    "QA_PTTGTDEF-TBD_MODELAI",
    "QA_PTTGTDEF-TBD_JUNCTION_BOX_POWER_CABLE",
    "QA_PTTGTDEF-TBD_HDC_POWER_CABLE",
    "QA_PTTGTDEF-TBD_HLM_POWER_CABLE_L_FORM_POWER_CABLE",
    "QA_PTTGTDEF-TBD_OP_SIGNAL_AND_POWER_CABLE",
    "QA_PTTGTDEF-TBD_HDR_SIGNAL_AND_POWER_CABLE",
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
                    ProductTestRun.product_test_run_id == "QA_PTRUN-20260504-0001"
                )
            ),
            "result_count": database_session.scalar(
                select(func.count()).select_from(ProductTestResult).where(
                    ProductTestResult.product_test_result_id == "QA_PTRES-20260504-0001"
                )
            ),
            "procedure_result_count": database_session.scalar(
                select(func.count()).select_from(ProductTestProcedureResult).where(
                    ProductTestProcedureResult.product_test_result_id == "QA_PTRES-20260504-0001"
                )
            ),
            "evidence_count": database_session.scalar(
                select(func.count()).select_from(ProductTestEvidence).where(
                    ProductTestEvidence.product_test_result_id == "QA_PTRES-20260504-0001"
                )
            ),
            "defect_count": database_session.scalar(
                select(func.count()).select_from(ProductTestDefect).where(
                    ProductTestDefect.product_test_result_id == "QA_PTRES-20260504-0001"
                )
            ),
            "report_count": database_session.scalar(
                select(func.count()).select_from(ProductTestReport).where(
                    ProductTestReport.product_test_report_id
                    == "QA_PTRPT-QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1-FULL-001"
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
                    ProductTestRun.product_test_run_id == "QA_PTRUN-20260504-0001"
                )
            ),
            "result_count": database_session.scalar(
                select(func.count()).select_from(ProductTestResult).where(
                    ProductTestResult.product_test_result_id == "QA_PTRES-20260504-0001"
                )
            ),
            "procedure_result_count": database_session.scalar(
                select(func.count()).select_from(ProductTestProcedureResult).where(
                    ProductTestProcedureResult.product_test_result_id == "QA_PTRES-20260504-0001"
                )
            ),
            "evidence_count": database_session.scalar(
                select(func.count()).select_from(ProductTestEvidence).where(
                    ProductTestEvidence.product_test_result_id == "QA_PTRES-20260504-0001"
                )
            ),
            "defect_count": database_session.scalar(
                select(func.count()).select_from(ProductTestDefect).where(
                    ProductTestDefect.product_test_result_id == "QA_PTRES-20260504-0001"
                )
            ),
            "report_count": database_session.scalar(
                select(func.count()).select_from(ProductTestReport).where(
                    ProductTestReport.product_test_report_id
                    == "QA_PTRPT-QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1-FULL-001"
                )
            ),
        }
    assert first_counts == second_counts, (first_counts, second_counts)


def _assert_report_detail_and_approval_guard() -> dict[str, object]:
    with session_local() as database_session:
        detail = get_product_test_report_detail(
            database_session,
            "QA_PTRPT-QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1-FULL-001",
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
                product_test_report_id="QA_PTRPT-QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1-FULL-001",
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


def _assert_snapshot_flow() -> dict[str, object]:
    with session_local() as database_session:
        manual_snapshot = create_product_test_report_snapshot(
            database_session,
            product_test_report_id="QA_PTRPT-QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1-FULL-001",
            snapshot_type="manual",
            created_by="SQA_MASTER",
            remark="smoke manual snapshot",
        )
        manual_snapshot_row = database_session.get(
            ProductTestReportSnapshot,
            manual_snapshot["product_test_report_snapshot_id"],
        )
        assert manual_snapshot_row is not None
        payload = json.loads(manual_snapshot_row.snapshot_payload)
        assert payload["product_test_results"], "snapshot must include product_test_results."
        assert payload["product_test_procedure_results"], "snapshot must include product_test_procedure_results."
        assert payload["product_test_evidences"], "snapshot must include product_test_evidences."
        assert payload["product_test_defects"], "snapshot must include product_test_defects."
        assert manual_snapshot_row.snapshot_hash

        transition_product_test_defect_to_rejected(
            database_session,
            product_test_defect_id="QA_PTDEF-20260504-0001",
            rejection_reason="smoke reject",
            transition_reason="smoke reject for approval snapshot",
            transitioned_by="SQA_MASTER",
        )
        transition_product_test_defect_to_rejected(
            database_session,
            product_test_defect_id="QA_PTDEF-20260504-0002",
            rejection_reason="smoke reject",
            transition_reason="smoke reject for approval snapshot",
            transitioned_by="SQA_MASTER",
        )
        approve_product_test_report(
            database_session,
            product_test_report_id="QA_PTRPT-QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1-FULL-001",
            approved_by="SQA_MASTER",
        )
        approval_snapshot_row = database_session.scalar(
            select(ProductTestReportSnapshot)
            .where(
                ProductTestReportSnapshot.product_test_report_id == "QA_PTRPT-QA_PTREL-MERCUSYS_MR30G-1.0.0-RC1-FULL-001",
                ProductTestReportSnapshot.snapshot_type == "approval",
            )
            .order_by(ProductTestReportSnapshot.created_at.desc())
        )
        assert approval_snapshot_row is not None, "approval must create approval snapshot."
        diff_result = compare_product_test_report_snapshots(
            database_session,
            left_snapshot_id=manual_snapshot_row.product_test_report_snapshot_id,
            right_snapshot_id=approval_snapshot_row.product_test_report_snapshot_id,
        )
        assert isinstance(diff_result["added_product_test_case_ids"], list)
        assert isinstance(diff_result["changed_product_test_result_statuses"], list)
        return {
            "manual_snapshot_id": manual_snapshot_row.product_test_report_snapshot_id,
            "approval_snapshot_id": approval_snapshot_row.product_test_report_snapshot_id,
            "diff_warning_count": len(diff_result["warnings"]),
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


def _assert_product_test_report_snapshot_exists() -> None:
    with engine.begin() as connection:
        row = connection.execute(
            text(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table' AND name='product_test_report_snapshot'
                """
            )
        ).fetchone()
    assert row is not None, "product_test_report_snapshot table must exist."


def main() -> None:
    initialize_database()
    _assert_seed_is_idempotent()
    report_payload = _assert_report_detail_and_approval_guard()
    _assert_product_test_report_snapshot_exists()
    _assert_product_test_report_item_absent()
    snapshot_payload = _assert_snapshot_flow()
    print(
        json.dumps(
            {
                "status": "ok",
                "expected_summary": report_payload["summary"],
                "approval_guard": report_payload["approval_error"],
                "snapshot": snapshot_payload,
                "product_test_report_item": "not added",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
