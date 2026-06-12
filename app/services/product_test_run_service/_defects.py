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
    _ensure_defect_not_locked_for_source_mutation,
    _now_text,
)
from app.services.product_test_run_service._status import (
    ensure_product_test_status_transition_recorded,
)
from app.services.product_test_run_service._list_queries import (
    list_running_run_options,
)
from app.services.product_test_run_service._runs import (
    start_product_test_result,
)


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
                "test_round_id",
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
