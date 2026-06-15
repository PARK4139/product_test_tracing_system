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
    ENTITY_TRANSITIONS,
    ENTITY_TYPE_VALUES,
    _entity_model,
    _load_entity_row,
    _next_prefixed_id,
    _now_text,
    _validate_in,
)


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
        f"SQA_PRODUCT_TEST_STATUS_TRANSITION_ID-{today_text}",
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
        "product_test_run": "product_test_run_status",
        "product_test_result": "product_test_result_status",
        "product_test_procedure_result": "product_test_procedure_result_status",
        "product_test_defect": "product_test_defect_status",
    }[entity_type]

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
