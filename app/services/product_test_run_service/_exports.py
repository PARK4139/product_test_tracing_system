from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.product_test_run_service._runs import get_run_detail
from app.services.product_test_run_service._trace import get_product_test_trace_view


def _append_export_section(rows: list[list[str]], title: str, header: list[str], body_rows: list[list[Any]]) -> None:
    rows.append([title])
    rows.append(header)
    for body_row in body_rows:
        rows.append(["" if value is None else str(value) for value in body_row])
    rows.append([])


def build_product_test_trace_export_rows(
    database_session: Session,
    *,
    test_round_id: str,
    product_test_target_id: str = "",
    product_test_config_id: str = "",
    product_test_case_id: str = "",
    result_status: str = "",
    defect_status: str = "",
) -> list[list[str]]:
    detail = get_product_test_trace_view(
        database_session,
        test_round_id=test_round_id,
        product_test_target_id=product_test_target_id,
        product_test_config_id=product_test_config_id,
        product_test_case_id=product_test_case_id,
        result_status=result_status,
        defect_status=defect_status,
    )
    rows: list[list[str]] = []
    _append_export_section(
        rows,
        "Round",
        [
            "test_round_id",
            "test_round_name",
            "workday",
            "start_date",
            "end_date",
            "migration_status",
        ],
        [[
            detail["round"].get("test_round_id"),
            detail["round"].get("test_round_name"),
            detail["round"].get("workday"),
            detail["round"].get("start_date"),
            detail["round"].get("end_date"),
            detail["round"].get("migration_status"),
        ]],
    )
    run_rows: list[list[Any]] = []
    procedure_rows: list[list[Any]] = []
    evidence_rows: list[list[Any]] = []
    defect_rows: list[list[Any]] = []
    for run in detail["run_trace_rows"]:
        run_rows.append([
            run["product_test_run_id"],
            run["product_test_run_status"],
            run["target_summary"].get("product_test_target_id"),
            run["target_summary"].get("serial_number"),
            run["config_summary"].get("product_test_config_id"),
            run["config_summary"].get("product_test_config_name"),
        ])
        for result in run["result_rows"]:
            for procedure in result["procedure_rows"]:
                procedure_rows.append([
                    run["product_test_run_id"],
                    result["product_test_result_id"],
                    result["product_test_case_id"],
                    result["product_test_result_status"],
                    procedure["product_test_procedure_result_id"],
                    procedure["procedure_sequence"],
                    procedure["procedure_action"],
                    procedure["product_test_procedure_result_status"],
                    procedure["actual_result"],
                    procedure["judgement_reason"],
                ])
                for evidence in procedure["evidence_rows"]:
                    evidence_rows.append([
                        result["product_test_result_id"],
                        procedure["product_test_procedure_result_id"],
                        evidence["product_test_evidence_id"],
                        evidence["product_test_evidence_type"],
                        evidence["file_name"],
                        evidence["file_path"],
                        evidence["captured_at"],
                    ])
            for defect in result["defect_rows"]:
                defect_rows.append([
                    result["product_test_result_id"],
                    defect["product_test_defect_id"],
                    defect["defect_title"],
                    defect["defect_severity"],
                    defect["defect_priority"],
                    defect["status"],
                    defect["assigned_to"],
                    defect["retest_product_test_result_id"],
                ])
    _append_export_section(
        rows,
        "Runs",
        [
            "product_test_run_id",
            "product_test_run_status",
            "product_test_target_id",
            "serial_number",
            "product_test_config_id",
            "product_test_config_name",
        ],
        run_rows,
    )
    _append_export_section(
        rows,
        "Procedure Results",
        [
            "product_test_run_id",
            "product_test_result_id",
            "product_test_case_id",
            "product_test_result_status",
            "product_test_procedure_result_id",
            "procedure_sequence",
            "procedure_action",
            "product_test_procedure_result_status",
            "actual_result",
            "judgement_reason",
        ],
        procedure_rows,
    )
    _append_export_section(
        rows,
        "Evidence",
        [
            "product_test_result_id",
            "product_test_procedure_result_id",
            "product_test_evidence_id",
            "product_test_evidence_type",
            "file_name",
            "file_path",
            "captured_at",
        ],
        evidence_rows,
    )
    _append_export_section(
        rows,
        "Defects",
        [
            "product_test_result_id",
            "product_test_defect_id",
            "defect_title",
            "defect_severity",
            "defect_priority",
            "product_test_defect_status",
            "assigned_to",
            "retest_product_test_result_id",
        ],
        defect_rows,
    )
    _append_export_section(
        rows,
        "Status Transitions",
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
        [[
            row["product_test_status_transition_id"],
            row["entity_type"],
            row["entity_id"],
            row["from_status"],
            row["to_status"],
            row["transition_reason"],
            row["transitioned_at"],
            row["transitioned_by"],
        ] for row in detail["status_transition_rows"]],
    )
    return rows


def build_product_test_run_export_rows(database_session: Session, product_test_run_id: str) -> list[list[str]]:
    detail = get_run_detail(database_session, product_test_run_id)
    if detail is None:
        raise LookupError("Run not found.")
    rows: list[list[str]] = []
    _append_export_section(
        rows,
        "Run Summary",
        [
            "product_test_run_id",
            "test_round_id",
            "product_test_target_id",
            "product_test_config_id",
            "product_test_run_status",
            "started_at",
            "started_by",
            "finished_at",
            "cancelled_at",
            "cancelled_by",
            "cancel_reason",
            "source_locked",
        ],
        [[
            detail["run"]["product_test_run_id"],
            detail["run"]["test_round_id"],
            detail["run"]["product_test_target_id"],
            detail["run"]["product_test_config_id"],
            detail["run"]["status"],
            detail["run"]["started_at"],
            detail["run"]["started_by"],
            detail["run"]["finished_at"],
            detail["run"]["cancelled_at"],
            detail["run"]["cancelled_by"],
            detail["run"]["cancel_reason"],
            detail["run"]["source_locked"],
        ]],
    )
    if detail["result"]:
        _append_export_section(
            rows,
            "Result Summary",
            [
                "product_test_result_id",
                "product_test_case_id",
                "product_test_result_status",
                "actual_result",
                "judgement_reason",
                "result_judged_at",
                "result_judged_by",
            ],
            [[
                detail["result"]["product_test_result_id"],
                detail["result"]["product_test_case_id"],
                detail["result"]["status"],
                detail["result"]["actual_result"],
                detail["result"]["judgement_reason"],
                detail["result"]["result_judged_at"],
                detail["result"]["result_judged_by"],
            ]],
        )
    _append_export_section(
        rows,
        "Procedure Results",
        [
            "product_test_procedure_result_id",
            "procedure_sequence",
            "procedure_action",
            "acceptance_criteria",
            "required_evidence_type",
            "product_test_procedure_result_status",
            "actual_result",
            "judgement_reason",
            "evidence_count",
            "remark",
        ],
        [[
            row["product_test_procedure_result_id"],
            row["procedure_sequence"],
            row["procedure_action"],
            row["acceptance_criteria"],
            row["required_evidence_type"],
            row["status"],
            row["actual_result"],
            row["judgement_reason"],
            row["evidence_count"],
            row["remark"],
        ] for row in detail["procedure_rows"]],
    )
    _append_export_section(
        rows,
        "Evidence",
        [
            "product_test_evidence_id",
            "product_test_procedure_result_id",
            "product_test_evidence_type",
            "file_name",
            "file_path",
            "captured_at",
            "captured_by",
            "remark",
        ],
        [[
            row["product_test_evidence_id"],
            row["product_test_procedure_result_id"],
            row["product_test_evidence_type"],
            row["file_name"],
            row["file_path"],
            row["captured_at"],
            row["captured_by"],
            row["remark"],
        ] for row in detail["evidence_rows"]],
    )
    _append_export_section(
        rows,
        "Defects",
        [
            "product_test_defect_id",
            "product_test_procedure_result_id",
            "defect_title",
            "defect_severity",
            "defect_priority",
            "product_test_defect_status",
            "assigned_to",
            "retest_product_test_result_id",
            "remark",
        ],
        [[
            row["product_test_defect_id"],
            row["product_test_procedure_result_id"],
            row["defect_title"],
            row["defect_severity"],
            row["defect_priority"],
            row["status"],
            row["assigned_to"],
            row["retest_product_test_result_id"],
            row["remark"],
        ] for row in detail["defect_rows"]],
    )
    _append_export_section(
        rows,
        "Status Transition History",
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
        [[
            row["product_test_status_transition_id"],
            row["entity_type"],
            row["entity_id"],
            row["from_status"],
            row["to_status"],
            row["transition_reason"],
            row["transitioned_at"],
            row["transitioned_by"],
        ] for row in detail["transition_rows"]],
    )
    return rows
