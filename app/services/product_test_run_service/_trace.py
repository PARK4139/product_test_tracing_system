from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ProductTestCase,
    ProductTestDefect,
    ProductTestEvidence,
    ProductTestProcedure,
    ProductTestProcedureResult,
    ProductTestResult,
    ProductTestRound,
    ProductTestRun,
    ProductTestStatusTransition,
)
from app.services.product_test_run_service._common import (
    _as_dict,
)
from app.services.product_test_run_service._list_queries import (
    _config_summary,
    _target_summary,
    list_case_options,
    list_config_options,
    list_round_options,
    list_target_options,
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
    entity_ids = set(
        run_ids
        + result_ids
        + [row.product_test_procedure_result_id for row in procedure_result_rows]
        + [row.product_test_defect_id for row in defect_rows]
    )
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
        "status_transitions": status_transitions,
    }


def get_product_test_trace_view(
    database_session: Session,
    *,
    test_round_id: str,
    product_test_target_id: str = "",
    product_test_config_id: str = "",
    product_test_case_id: str = "",
    result_status: str = "",
    defect_status: str = "",
) -> dict[str, Any]:
    graph = _collect_round_graph(database_session, test_round_id)
    target_id = str(product_test_target_id or "").strip()
    config_id = str(product_test_config_id or "").strip()
    case_id = str(product_test_case_id or "").strip()
    result_status_value = str(result_status or "").strip()
    defect_status_value = str(defect_status or "").strip()
    case_map = {
        row.product_test_case_id: row
        for row in database_session.scalars(select(ProductTestCase))
    }
    procedure_map = {
        row.product_test_procedure_id: row
        for row in database_session.scalars(select(ProductTestProcedure))
    }
    run_trace_rows = []
    for run_row in graph["runs"]:
        if target_id and run_row.product_test_target_id != target_id:
            continue
        if config_id and run_row.product_test_config_id != config_id:
            continue
        result_rows = []
        scoped_result_rows = [
            row for row in graph["results"]
            if row.product_test_run_id == run_row.product_test_run_id
        ]
        for result_row in scoped_result_rows:
            if case_id and result_row.product_test_case_id != case_id:
                continue
            if result_status_value and result_row.product_test_result_status != result_status_value:
                continue
            procedure_rows = []
            scoped_procedure_rows = [
                row for row in graph["procedure_results"]
                if row.product_test_result_id == result_row.product_test_result_id
            ]
            for procedure_result_row in scoped_procedure_rows:
                procedure_row = procedure_map.get(procedure_result_row.product_test_procedure_id)
                procedure_rows.append(
                    {
                        "product_test_procedure_result_id": procedure_result_row.product_test_procedure_result_id,
                        "product_test_procedure_result_status": procedure_result_row.product_test_procedure_result_status,
                        "procedure_sequence": procedure_row.procedure_sequence if procedure_row else 0,
                        "procedure_action": procedure_row.procedure_action if procedure_row else "",
                        "acceptance_criteria": procedure_row.acceptance_criteria if procedure_row else "",
                        "required_evidence_type": procedure_row.required_evidence_type if procedure_row else "",
                        "actual_result": procedure_result_row.actual_result or "",
                        "judgement_reason": procedure_result_row.judgement_reason or "",
                        "evidence_rows": [
                            _as_dict(
                                row,
                                [
                                    "product_test_evidence_id",
                                    "product_test_evidence_type",
                                    "file_name",
                                    "file_path",
                                    "file_hash",
                                    "captured_at",
                                    "captured_by",
                                    "remark",
                                ],
                            )
                            for row in graph["evidences"]
                            if row.product_test_procedure_result_id == procedure_result_row.product_test_procedure_result_id
                        ],
                    }
                )
            scoped_defect_rows = [
                row for row in graph["defects"]
                if row.product_test_result_id == result_row.product_test_result_id
            ]
            if defect_status_value:
                scoped_defect_rows = [
                    row for row in scoped_defect_rows
                    if row.product_test_defect_status == defect_status_value
                ]
            result_rows.append(
                {
                    "product_test_result_id": result_row.product_test_result_id,
                    "product_test_result_status": result_row.product_test_result_status,
                    "product_test_case_id": result_row.product_test_case_id,
                    "case_row": case_map.get(result_row.product_test_case_id),
                    "procedure_rows": procedure_rows,
                    "defect_rows": [
                        {
                            **_as_dict(
                                row,
                                [
                                    "product_test_defect_id",
                                    "defect_title",
                                    "defect_severity",
                                    "defect_priority",
                                    "assigned_to",
                                    "retest_product_test_result_id",
                                ],
                            ),
                            "status": row.product_test_defect_status,
                        }
                        for row in scoped_defect_rows
                    ],
                }
            )
        run_trace_rows.append(
            {
                "product_test_run_id": run_row.product_test_run_id,
                "product_test_run_status": run_row.product_test_run_status,
                "target_summary": _target_summary(database_session, run_row.product_test_target_id),
                "config_summary": _config_summary(database_session, run_row.product_test_config_id),
                "result_rows": result_rows,
            }
        )
    return {
        "round": _as_dict(
            graph["round"],
            [
                "test_round_id",
                "test_round_name",
                "workday",
                "start_date",
                "end_date",
                "migration_status",
            ],
        ) if graph["round"] else {"test_round_id": test_round_id},
        "filters": {
            "test_round_id": test_round_id,
            "product_test_target_id": target_id,
            "product_test_config_id": config_id,
            "product_test_case_id": case_id,
            "result_status": result_status_value,
            "defect_status": defect_status_value,
        },
        "run_trace_rows": run_trace_rows,
        "status_transition_rows": [
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
            for row in graph["status_transitions"]
        ],
        "round_options": list_round_options(database_session),
        "target_options": list_target_options(database_session),
        "config_options": list_config_options(database_session),
        "case_options": list_case_options(database_session),
    }


def get_test_round_id_by_run_id(database_session: Session, product_test_run_id: str) -> str:
    run_row = database_session.get(ProductTestRun, product_test_run_id)
    if run_row is None:
        raise LookupError("Run not found.")
    return run_row.test_round_id


def get_product_test_run_trace_view(database_session: Session, product_test_run_id: str) -> dict[str, Any]:
    run_row = database_session.get(ProductTestRun, product_test_run_id)
    if run_row is None:
        raise LookupError("Run not found.")
    trace_detail = get_product_test_trace_view(
        database_session,
        test_round_id=run_row.test_round_id,
        product_test_target_id=run_row.product_test_target_id,
        product_test_config_id=run_row.product_test_config_id,
    )
    run_trace = next(
        (row for row in trace_detail["run_trace_rows"] if row["product_test_run_id"] == product_test_run_id),
        None,
    )
    if run_trace is None:
        raise LookupError("Run trace not found.")

    trace_entity_ids = {product_test_run_id}
    for result_row in run_trace["result_rows"]:
        trace_entity_ids.add(result_row["product_test_result_id"])
        trace_entity_ids.update(
            procedure_row["product_test_procedure_result_id"]
            for procedure_row in result_row["procedure_rows"]
        )
        trace_entity_ids.update(
            defect_row["product_test_defect_id"]
            for defect_row in result_row["defect_rows"]
        )

    return {
        "round": trace_detail["round"],
        "run_trace": run_trace,
        "status_transition_rows": [
            row
            for row in trace_detail["status_transition_rows"]
            if row["entity_id"] in trace_entity_ids
        ],
    }
