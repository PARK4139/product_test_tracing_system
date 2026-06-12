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
    _ensure_round_not_locked_for_source_mutation,
    _ensure_result_not_locked_for_source_mutation,
    _ensure_run_not_locked_for_source_mutation,
    _next_prefixed_id,
    _now_text,
    _validate_in,
    DEFECT_PRIORITY_VALUES,
    DEFECT_SEVERITY_VALUES,
    EVIDENCE_TYPE_VALUES,
    PROCEDURE_RESULT_STATUS_VALUES,
    _query_all_rows,
)
from app.services.product_test_run_service._status import (
    _insert_status_transition,
    ensure_product_test_status_transition_recorded,
)
from app.services.product_test_run_service._list_queries import (
    list_case_options,
    list_environment_options,
    list_round_options,
    list_target_options,
    _target_summary,
    _environment_summary,
)


def list_runs(database_session: Session) -> list[dict[str, Any]]:
    rows = _query_all_rows(database_session, ProductTestRun, "started_at")
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
    test_round_id: str,
    product_test_target_id: str,
    product_test_environment_id: str,
    started_by: str,
) -> dict[str, Any]:
    round_row = database_session.get(ProductTestRound, str(test_round_id or "").strip())
    target = database_session.get(ProductTestTargetUnified, str(product_test_target_id or "").strip())
    environment = database_session.get(ProductTestEnvironment, str(product_test_environment_id or "").strip())
    if round_row is None:
        raise ValueError("Unknown test_round_id.")
    if target is None:
        raise ValueError("Unknown product_test_target_id.")
    if environment is None:
        raise ValueError("Unknown product_test_environment_id.")
    _ensure_round_not_locked_for_source_mutation(
        database_session,
        test_round_id=round_row.test_round_id,
    )
    run_id = _next_prefixed_id(database_session, ProductTestRun, "product_test_run_id", "SQA_PRODUCT_TEST_RUN_ID")
    now_text = _now_text()
    round_remark_parts = [
        f"[Workday] {round_row.workday}" if round_row.workday else "",
        f"[Start] {round_row.start_date}" if round_row.start_date else "",
        f"[End] {round_row.end_date}" if round_row.end_date else "",
    ]
    round_remark = "\n".join(part for part in round_remark_parts if part).strip() or None
    row = ProductTestRun(
        product_test_run_id=run_id,
        test_round_id=round_row.test_round_id,
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
        remark=round_remark,
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
            "test_round_id",
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
    result_id = _next_prefixed_id(database_session, ProductTestResult, "product_test_result_id", "SQA_PRODUCT_TEST_RESULT_ID")
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
            "SQA_PRODUCT_TEST_PROCEDURE_RESULT_ID",
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
    evidence_id = _next_prefixed_id(database_session, ProductTestEvidence, "product_test_evidence_id", "SQA_PRODUCT_TEST_EVIDENCE_ID")
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
    defect_id = _next_prefixed_id(database_session, ProductTestDefect, "product_test_defect_id", "SQA_PRODUCT_TEST_DEFECT_ID")
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
                ProductTestReport.test_round_id == run_row.test_round_id,
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
                    "test_round_id",
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
        "round_summary": _as_dict(
            database_session.get(ProductTestRound, run_row.test_round_id),
            [
                "test_round_id",
                "test_round_name",
                "workday",
                "start_date",
                "end_date",
                "migration_status",
            ],
        ),
        "target_summary": _target_summary(database_session, run_row.product_test_target_id),
        "environment_summary": _environment_summary(database_session, run_row.product_test_environment_id),
        "round_options": list_round_options(database_session),
        "target_options": list_target_options(database_session),
        "environment_options": list_environment_options(database_session),
        "case_options": list_case_options(database_session),
    }
