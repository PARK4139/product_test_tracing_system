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
    _next_prefixed_id,
    _now_text,
    _round_is_locked,
    _validate_in,
    REPORT_TYPE_VALUES,
    SNAPSHOT_TYPE_VALUES,
    _query_all_rows,
)
from app.services.product_test_run_service._status import (
    _insert_status_transition,
    ensure_product_test_status_transition_recorded,
)
from app.services.product_test_run_service._list_queries import (
    list_round_options,
    _target_summary,
    _environment_summary,
)


def list_report_round_options(database_session: Session) -> list[dict[str, Any]]:
    return list_round_options(database_session)


def list_product_test_reports(database_session: Session) -> list[dict[str, Any]]:
    from app.services.product_test_run_service._common import _query_all_rows
    rows = _query_all_rows(database_session, ProductTestReport, "created_at")
    return [
        _as_dict(
            row,
            [
                "product_test_report_id",
                "test_round_id",
                "product_test_report_type",
                "product_test_report_status",
                "product_test_report_title",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
                "approved_at",
                "approved_by",
                "rejected_at",
                "rejected_by",
                "rejection_reason",
                "remark",
            ],
        )
        for row in rows
    ]


def list_product_test_report_snapshots(database_session: Session) -> list[dict[str, Any]]:
    from app.services.product_test_run_service._common import _query_all_rows
    rows = _query_all_rows(database_session, ProductTestReportSnapshot, "created_at")
    return [
        _as_dict(
            row,
            [
                "product_test_report_snapshot_id",
                "product_test_report_id",
                "test_round_id",
                "snapshot_type",
                "snapshot_format",
                "snapshot_hash",
                "source_data_locked",
                "created_at",
                "created_by",
                "remark",
            ],
        )
        for row in rows
    ]


def get_product_test_report_snapshot_detail(
    database_session: Session,
    product_test_report_snapshot_id: str,
) -> dict[str, Any] | None:
    row = database_session.get(ProductTestReportSnapshot, product_test_report_snapshot_id)
    if row is None:
        return None
    payload_object = json.loads(row.snapshot_payload)
    return {
        "snapshot": _as_dict(
            row,
            [
                "product_test_report_snapshot_id",
                "product_test_report_id",
                "test_round_id",
                "snapshot_type",
                "snapshot_format",
                "snapshot_payload",
                "snapshot_hash",
                "source_data_locked",
                "created_at",
                "created_by",
                "remark",
            ],
        ),
        "snapshot_payload_pretty": json.dumps(payload_object, ensure_ascii=False, indent=2, sort_keys=True),
        "snapshot_payload_object": payload_object,
    }


def create_product_test_report(
    database_session: Session,
    *,
    test_round_id: str,
    product_test_report_type: str,
    product_test_report_title: str,
    created_by: str,
    remark: str,
) -> dict[str, Any]:
    release_id = str(test_round_id or "").strip()
    report_type_value = _validate_in(str(product_test_report_type or "").strip().upper(), REPORT_TYPE_VALUES, "product_test_report_type")
    title = str(product_test_report_title or "").strip()
    if not release_id or not title:
        raise ValueError("test_round_id and product_test_report_title are required.")
    if database_session.get(ProductTestRound, release_id) is None:
        raise ValueError("Unknown test_round_id.")
    report_id = _next_prefixed_id(database_session, ProductTestReport, "product_test_report_id", "SQA_PRODUCT_TEST_REPORT_ID")
    now_text = _now_text()
    row = ProductTestReport(
        product_test_report_id=report_id,
        test_round_id=release_id,
        product_test_report_type=report_type_value,
        product_test_report_status="DRAFT",
        product_test_report_title=title,
        created_at=now_text,
        created_by=created_by,
        updated_at=now_text,
        updated_by=created_by,
        approved_at=None,
        approved_by=None,
        rejected_at=None,
        rejected_by=None,
        rejection_reason=None,
        remark=str(remark or "").strip() or None,
    )
    database_session.add(row)
    _insert_status_transition(
        database_session,
        entity_type="product_test_report",
        entity_id=report_id,
        from_status=None,
        to_status="DRAFT",
        transition_reason="create_report",
        transitioned_by=created_by,
    )
    _commit_or_rollback(database_session)
    return _as_dict(
        row,
        [
            "product_test_report_id",
            "test_round_id",
            "product_test_report_type",
            "product_test_report_status",
            "product_test_report_title",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "approved_at",
            "approved_by",
            "rejected_at",
            "rejected_by",
            "rejection_reason",
            "remark",
        ],
    )


def _build_product_test_report_snapshot_payload(detail: dict[str, Any]) -> dict[str, Any]:
    flat_result_rows = []
    flat_procedure_result_rows = []
    flat_defect_rows = []
    flat_evidence_rows = []
    for result in detail["result_details"]:
        flat_result_rows.append(
            {
                "product_test_result_id": result["product_test_result_id"],
                "product_test_run_id": result["product_test_run_id"],
                "product_test_case_id": result["product_test_case_id"],
                "product_test_case_title": result["product_test_case_title"],
                "product_test_result_status": result["product_test_result_status"],
                "actual_result": result["actual_result"],
                "judgement_reason": result["judgement_reason"],
                "result_judged_at": result["result_judged_at"],
                "result_judged_by": result["result_judged_by"],
            }
        )
        flat_defect_rows.extend(result["defect_rows"])
        flat_evidence_rows.extend(result["evidence_rows"])
        for procedure in result["procedure_rows"]:
            flat_procedure_result_rows.append(
                {
                    "product_test_result_id": result["product_test_result_id"],
                    "product_test_procedure_result_id": procedure.get("product_test_procedure_result_id", ""),
                    "product_test_procedure_id": procedure.get("product_test_procedure_id", ""),
                    "procedure_sequence": procedure["procedure_sequence"],
                    "procedure_action": procedure["procedure_action"],
                    "acceptance_criteria": procedure["acceptance_criteria"],
                    "required_evidence_type": procedure["required_evidence_type"],
                    "product_test_procedure_result_status": procedure["product_test_procedure_result_status"],
                    "actual_result": procedure["actual_result"],
                    "judgement_reason": procedure["judgement_reason"],
                    "evidence_count": procedure["evidence_count"],
                }
            )
            flat_defect_rows.extend(procedure["defect_rows"])
            flat_evidence_rows.extend(procedure["evidence_rows"])
    dedup_defects = {row["product_test_defect_id"]: row for row in flat_defect_rows if row.get("product_test_defect_id")}
    dedup_evidences = {row["product_test_evidence_id"]: row for row in flat_evidence_rows if row.get("product_test_evidence_id")}
    return {
        "report_header": detail["report"],
        "round_summary": detail["round_summary"],
        "run_summaries": detail["run_summaries"],
        "result_summary": detail["result_summary"],
        "result_details": detail["result_details"],
        "product_test_results": flat_result_rows,
        "product_test_procedure_results": flat_procedure_result_rows,
        "product_test_defects": list(dedup_defects.values()),
        "product_test_evidences": list(dedup_evidences.values()),
        "product_test_status_transitions": detail["status_transitions"],
    }


def create_product_test_report_snapshot(
    database_session: Session,
    product_test_report_id: str,
    snapshot_type: str,
    created_by: str,
    remark: str | None = None,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    report_row = database_session.get(ProductTestReport, str(product_test_report_id or "").strip())
    if report_row is None:
        raise LookupError("Report not found.")
    snapshot_type_value = _validate_in(str(snapshot_type or "").strip(), SNAPSHOT_TYPE_VALUES, "snapshot_type")
    detail = get_product_test_report_detail(database_session, report_row.product_test_report_id)
    if detail is None:
        raise LookupError("Report detail not found.")
    payload_object = _build_product_test_report_snapshot_payload(detail)
    snapshot_payload = json.dumps(payload_object, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    snapshot_hash = hashlib.sha256(snapshot_payload.encode("utf-8")).hexdigest()
    today_text = get_utc_now_datetime().astimezone().strftime("%Y%m%d")
    snapshot_id = _next_prefixed_id(
        database_session,
        ProductTestReportSnapshot,
        "product_test_report_snapshot_id",
        f"SQA_PRODUCT_TEST_REPORT_SNAPSHOT_ID-{today_text}",
    )
    now_text = _now_text()
    source_data_locked = 1 if snapshot_type_value == "approval" or _round_is_locked(database_session, report_row.test_round_id) else 0
    row = ProductTestReportSnapshot(
        product_test_report_snapshot_id=snapshot_id,
        product_test_report_id=report_row.product_test_report_id,
        test_round_id=report_row.test_round_id,
        snapshot_type=snapshot_type_value,
        snapshot_format="json",
        snapshot_payload=snapshot_payload,
        snapshot_hash=snapshot_hash,
        source_data_locked=source_data_locked,
        created_at=now_text,
        created_by=created_by,
        remark=str(remark or "").strip() or None,
    )
    database_session.add(row)
    if commit:
        _commit_or_rollback(database_session)
    return _as_dict(
        row,
        [
            "product_test_report_snapshot_id",
            "product_test_report_id",
            "test_round_id",
            "snapshot_type",
            "snapshot_format",
            "snapshot_hash",
            "source_data_locked",
            "created_at",
            "created_by",
            "remark",
        ],
    )


def _collect_round_graph(database_session: Session, test_round_id: str) -> dict[str, Any]:
    round_row = database_session.get(ProductTestRound, test_round_id)
    run_rows = list(
        database_session.scalars(
            select(ProductTestRun)
            .where(ProductTestRun.test_round_id == test_round_id)
            .order_by(ProductTestRun.started_at.desc())
        )
    )
    run_ids = [row.product_test_run_id for row in run_rows]
    result_rows = []
    procedure_result_rows = []
    evidence_rows = []
    defect_rows = []
    if run_ids:
        result_rows = list(
            database_session.scalars(
                select(ProductTestResult)
                .where(ProductTestResult.product_test_run_id.in_(run_ids))
                .order_by(ProductTestResult.created_at.desc())
            )
        )
    result_ids = [row.product_test_result_id for row in result_rows]
    if result_ids:
        procedure_result_rows = list(
            database_session.scalars(
                select(ProductTestProcedureResult).where(
                    ProductTestProcedureResult.product_test_result_id.in_(result_ids)
                )
            )
        )
        evidence_rows = list(
            database_session.scalars(
                select(ProductTestEvidence).where(ProductTestEvidence.product_test_result_id.in_(result_ids))
            )
        )
        defect_rows = list(
            database_session.scalars(
                select(ProductTestDefect).where(ProductTestDefect.product_test_result_id.in_(result_ids))
            )
        )
    report_rows = list(
        database_session.scalars(
            select(ProductTestReport)
            .where(ProductTestReport.test_round_id == test_round_id)
            .order_by(ProductTestReport.created_at.desc())
        )
    )
    entity_ids = set(run_ids + result_ids + [row.product_test_procedure_result_id for row in procedure_result_rows] + [row.product_test_defect_id for row in defect_rows] + [row.product_test_report_id for row in report_rows])
    status_transitions = []
    if entity_ids:
        status_transitions = list(
            database_session.scalars(
                select(ProductTestStatusTransition)
                .where(ProductTestStatusTransition.entity_id.in_(entity_ids))
                .order_by(ProductTestStatusTransition.transitioned_at.desc())
            )
        )
    return {
        "round": round_row,
        "runs": run_rows,
        "results": result_rows,
        "procedure_results": procedure_result_rows,
        "evidences": evidence_rows,
        "defects": defect_rows,
        "reports": report_rows,
        "status_transitions": status_transitions,
    }


def approve_product_test_report(database_session: Session, *, product_test_report_id: str, approved_by: str) -> dict[str, Any]:
    report_row = database_session.get(ProductTestReport, product_test_report_id)
    if report_row is None:
        raise LookupError("Report not found.")
    graph = _collect_round_graph(database_session, report_row.test_round_id)
    if any(row.product_test_defect_status in {"opened", "assigned", "fixed", "retested"} for row in graph["defects"]):
        raise ValueError("Open defects exist for this release. Approval is blocked.")
    create_product_test_report_snapshot(
        database_session,
        product_test_report_id=product_test_report_id,
        snapshot_type="approval",
        created_by=approved_by,
        remark="auto snapshot before approval",
        commit=False,
    )
    ensure_product_test_status_transition_recorded(
        database_session,
        entity_type="product_test_report",
        entity_id=product_test_report_id,
        to_status="APPROVED",
        transition_reason="approve_report",
        transitioned_by=approved_by,
        approved_at=_now_text(),
        approved_by=approved_by,
    )
    now_text = _now_text()
    report_row.approved_at = now_text
    report_row.approved_by = approved_by
    report_row.updated_at = now_text
    report_row.updated_by = approved_by
    _commit_or_rollback(database_session)
    return _as_dict(report_row, ["product_test_report_id", "product_test_report_status", "approved_at", "approved_by"])


def reject_product_test_report(database_session: Session, *, product_test_report_id: str, rejected_by: str, rejection_reason: str) -> dict[str, Any]:
    report_row = database_session.get(ProductTestReport, product_test_report_id)
    if report_row is None:
        raise LookupError("Report not found.")
    reason_text = str(rejection_reason or "").strip()
    if not reason_text:
        raise ValueError("rejection_reason is required.")
    ensure_product_test_status_transition_recorded(
        database_session,
        entity_type="product_test_report",
        entity_id=product_test_report_id,
        to_status="REJECTED",
        transition_reason=reason_text,
        transitioned_by=rejected_by,
        rejected_at=_now_text(),
        rejected_by=rejected_by,
    )
    now_text = _now_text()
    report_row.rejected_at = now_text
    report_row.rejected_by = rejected_by
    report_row.rejection_reason = reason_text
    report_row.updated_at = now_text
    report_row.updated_by = rejected_by
    _commit_or_rollback(database_session)
    return _as_dict(report_row, ["product_test_report_id", "product_test_report_status", "rejected_at", "rejected_by", "rejection_reason"])


def get_product_test_report_detail(database_session: Session, product_test_report_id: str) -> dict[str, Any] | None:
    report_row = database_session.get(ProductTestReport, product_test_report_id)
    if report_row is None:
        return None
    graph = _collect_round_graph(database_session, report_row.test_round_id)
    result_rows = graph["results"]
    procedure_rows = graph["procedure_results"]
    evidence_rows = graph["evidences"]
    defect_rows = graph["defects"]
    case_map = {
        row.product_test_case_id: row
        for row in database_session.scalars(select(ProductTestCase))
    }
    procedure_map = {
        row.product_test_procedure_id: row
        for row in database_session.scalars(select(ProductTestProcedure))
    }
    result_details = []
    for result_row in result_rows:
        scoped_procedure_rows = [
            row for row in procedure_rows
            if row.product_test_result_id == result_row.product_test_result_id
        ]
        procedure_detail_rows = []
        for procedure_result_row in scoped_procedure_rows:
            procedure_row = procedure_map.get(procedure_result_row.product_test_procedure_id)
            scoped_evidence_rows = [
                row for row in evidence_rows
                if row.product_test_procedure_result_id == procedure_result_row.product_test_procedure_result_id
            ]
            scoped_defect_rows = [
                row for row in defect_rows
                if row.product_test_procedure_result_id == procedure_result_row.product_test_procedure_result_id
            ]
            procedure_detail_rows.append(
                {
                    "product_test_procedure_result_id": procedure_result_row.product_test_procedure_result_id,
                    "product_test_procedure_id": procedure_result_row.product_test_procedure_id,
                    "procedure_sequence": procedure_row.procedure_sequence if procedure_row else 0,
                    "procedure_action": procedure_row.procedure_action if procedure_row else "",
                    "acceptance_criteria": procedure_row.acceptance_criteria if procedure_row else "",
                    "required_evidence_type": procedure_row.required_evidence_type if procedure_row else "",
                    "product_test_procedure_result_status": procedure_result_row.product_test_procedure_result_status,
                    "actual_result": procedure_result_row.actual_result or "",
                    "judgement_reason": procedure_result_row.judgement_reason or "",
                    "evidence_count": len(scoped_evidence_rows),
                    "evidence_rows": [
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
                        for row in scoped_evidence_rows
                    ],
                    "defect_rows": [
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
                                    "fix_description",
                                    "retest_product_test_result_id",
                                    "rejection_reason",
                                ],
                            ),
                            "product_test_defect_status": row.product_test_defect_status,
                        }
                        for row in scoped_defect_rows
                    ],
                }
            )
        case_row = case_map.get(result_row.product_test_case_id)
        result_details.append(
            {
                "product_test_result_id": result_row.product_test_result_id,
                "product_test_run_id": result_row.product_test_run_id,
                "product_test_case_id": result_row.product_test_case_id,
                "product_test_case_title": case_row.product_test_case_title if case_row else "",
                "product_test_result_status": result_row.product_test_result_status,
                "actual_result": result_row.actual_result or "",
                "judgement_reason": result_row.judgement_reason or "",
                "result_judged_at": result_row.result_judged_at or "",
                "result_judged_by": result_row.result_judged_by or "",
                "procedure_rows": procedure_detail_rows,
                "defect_rows": [
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
                                "fix_description",
                                "retest_product_test_result_id",
                                "rejection_reason",
                            ],
                        ),
                        "status": row.product_test_defect_status,
                    }
                    for row in defect_rows
                    if row.product_test_result_id == result_row.product_test_result_id
                ],
                "evidence_rows": [
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
                    for row in evidence_rows
                    if row.product_test_result_id == result_row.product_test_result_id
                ],
            }
        )
    open_defect_count = len([row for row in defect_rows if row.product_test_defect_status in {"opened", "assigned", "fixed", "retested"}])
    procedure_failed_count = len(
        [row for row in procedure_rows if row.product_test_procedure_result_status == "failed"]
    )
    return {
        "report": _as_dict(
            report_row,
            [
                "product_test_report_id",
                "test_round_id",
                "product_test_report_type",
                "product_test_report_status",
                "product_test_report_title",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
                "approved_at",
                "approved_by",
                "rejected_at",
                "rejected_by",
                "rejection_reason",
                "remark",
            ],
        ),
        "round_summary": _as_dict(
            graph["round"],
            [
                "test_round_id",
                "test_round_name",
                "workday",
                "start_date",
                "end_date",
                "migration_status",
            ],
        ) if graph["round"] else {"test_round_id": report_row.test_round_id},
        "run_summaries": [
            {
                "product_test_run_id": row.product_test_run_id,
                "product_test_target_id": row.product_test_target_id,
                "product_test_environment_id": row.product_test_environment_id,
                "product_test_run_status": row.product_test_run_status,
                "started_at": row.started_at,
                "started_by": row.started_by,
                "finished_at": row.finished_at or "",
                "target_summary": _target_summary(database_session, row.product_test_target_id),
                "environment_summary": _environment_summary(database_session, row.product_test_environment_id),
            }
            for row in graph["runs"]
        ],
        "result_summary": {
            "total_result_count": len(result_rows),
            "passed_count": len([row for row in result_rows if row.product_test_result_status == "passed"]),
            "failed_count": len([row for row in result_rows if row.product_test_result_status == "failed"]),
            "blocked_count": len([row for row in result_rows if row.product_test_result_status == "blocked"]),
            "skipped_count": len([row for row in result_rows if row.product_test_result_status == "skipped"]),
            "procedure_result_count": len(procedure_rows),
            "procedure_failed_count": procedure_failed_count,
            "defect_count": len(defect_rows),
            "open_defect_count": open_defect_count,
            "unresolved_defect_count": open_defect_count,
            "evidence_count": len(evidence_rows),
        },
        "result_details": result_details,
        "status_transitions": [
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
                    "created_at",
                    "created_by",
                    "remark",
                ],
            )
            for row in graph["status_transitions"]
        ],
        "approval_blocked": open_defect_count > 0,
    }


def compare_product_test_report_snapshots(
    database_session: Session,
    left_snapshot_id: str,
    right_snapshot_id: str,
) -> dict[str, Any]:
    left_row = database_session.get(ProductTestReportSnapshot, str(left_snapshot_id or "").strip())
    right_row = database_session.get(ProductTestReportSnapshot, str(right_snapshot_id or "").strip())
    if left_row is None or right_row is None:
        raise LookupError("Both snapshot IDs must exist.")
    if left_row.snapshot_format != "json" or right_row.snapshot_format != "json":
        raise ValueError("Both snapshots must use json format.")
    warnings: list[str] = []
    if left_row.test_round_id != right_row.test_round_id:
        warnings.append("Snapshots belong to different test_round_id values.")
    for row in (left_row, right_row):
        if not re.fullmatch(r"[0-9a-f]{64}", str(row.snapshot_hash or "")):
            warnings.append(f"Snapshot hash invalid: {row.product_test_report_snapshot_id}")
    left_payload = json.loads(left_row.snapshot_payload)
    right_payload = json.loads(right_row.snapshot_payload)
    left_results = {row["product_test_result_id"]: row for row in left_payload.get("product_test_results", [])}
    right_results = {row["product_test_result_id"]: row for row in right_payload.get("product_test_results", [])}
    left_cases = {row["product_test_case_id"] for row in left_results.values() if row.get("product_test_case_id")}
    right_cases = {row["product_test_case_id"] for row in right_results.values() if row.get("product_test_case_id")}
    left_procedures = {
        row["product_test_procedure_result_id"]: row
        for row in left_payload.get("product_test_procedure_results", [])
        if row.get("product_test_procedure_result_id")
    }
    right_procedures = {
        row["product_test_procedure_result_id"]: row
        for row in right_payload.get("product_test_procedure_results", [])
        if row.get("product_test_procedure_result_id")
    }
    left_defects = {row["product_test_defect_id"]: row for row in left_payload.get("product_test_defects", []) if row.get("product_test_defect_id")}
    right_defects = {row["product_test_defect_id"]: row for row in right_payload.get("product_test_defects", []) if row.get("product_test_defect_id")}
    left_evidences = {row["product_test_evidence_id"]: row for row in left_payload.get("product_test_evidences", []) if row.get("product_test_evidence_id")}
    right_evidences = {row["product_test_evidence_id"]: row for row in right_payload.get("product_test_evidences", []) if row.get("product_test_evidence_id")}
    changed_result_statuses = []
    for result_id in sorted(set(left_results) & set(right_results)):
        if left_results[result_id].get("product_test_result_status") != right_results[result_id].get("product_test_result_status"):
            changed_result_statuses.append(
                {
                    "product_test_result_id": result_id,
                    "product_test_case_id": right_results[result_id].get("product_test_case_id") or left_results[result_id].get("product_test_case_id"),
                    "left_status": left_results[result_id].get("product_test_result_status"),
                    "right_status": right_results[result_id].get("product_test_result_status"),
                }
            )
    changed_procedure_statuses = []
    for procedure_result_id in sorted(set(left_procedures) & set(right_procedures)):
        if left_procedures[procedure_result_id].get("product_test_procedure_result_status") != right_procedures[procedure_result_id].get("product_test_procedure_result_status"):
            changed_procedure_statuses.append(
                {
                    "product_test_procedure_result_id": procedure_result_id,
                    "product_test_procedure_id": right_procedures[procedure_result_id].get("product_test_procedure_id") or left_procedures[procedure_result_id].get("product_test_procedure_id"),
                    "left_status": left_procedures[procedure_result_id].get("product_test_procedure_result_status"),
                    "right_status": right_procedures[procedure_result_id].get("product_test_procedure_result_status"),
                }
            )
    changed_defect_statuses = []
    for defect_id in sorted(set(left_defects) & set(right_defects)):
        left_status = left_defects[defect_id].get("status") or left_defects[defect_id].get("product_test_defect_status")
        right_status = right_defects[defect_id].get("status") or right_defects[defect_id].get("product_test_defect_status")
        if left_status != right_status:
            changed_defect_statuses.append(
                {
                    "product_test_defect_id": defect_id,
                    "left_status": left_status,
                    "right_status": right_status,
                }
            )
    changed_evidence_hashes = []
    for evidence_id in sorted(set(left_evidences) & set(right_evidences)):
        if (left_evidences[evidence_id].get("file_hash") or "") != (right_evidences[evidence_id].get("file_hash") or ""):
            changed_evidence_hashes.append(
                {
                    "product_test_evidence_id": evidence_id,
                    "left_file_hash": left_evidences[evidence_id].get("file_hash") or "",
                    "right_file_hash": right_evidences[evidence_id].get("file_hash") or "",
                }
            )
    return {
        "left_snapshot": _as_dict(left_row, ["product_test_report_snapshot_id", "product_test_report_id", "test_round_id", "snapshot_type", "snapshot_hash"]),
        "right_snapshot": _as_dict(right_row, ["product_test_report_snapshot_id", "product_test_report_id", "test_round_id", "snapshot_type", "snapshot_hash"]),
        "warnings": warnings,
        "added_product_test_case_ids": sorted(right_cases - left_cases),
        "removed_product_test_case_ids": sorted(left_cases - right_cases),
        "changed_product_test_result_statuses": changed_result_statuses,
        "changed_product_test_procedure_result_statuses": changed_procedure_statuses,
        "added_defect_ids": sorted(set(right_defects) - set(left_defects)),
        "removed_defect_ids": sorted(set(left_defects) - set(right_defects)),
        "changed_defect_statuses": changed_defect_statuses,
        "added_evidence_ids": sorted(set(right_evidences) - set(left_evidences)),
        "removed_evidence_ids": sorted(set(left_evidences) - set(right_evidences)),
        "changed_evidence_hashes": changed_evidence_hashes,
    }
