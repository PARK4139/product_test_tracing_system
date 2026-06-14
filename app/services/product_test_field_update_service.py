from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import (
    ProductTestCase,
    ProductTestRun,
    ProductTestDefect,
    ProductTestEnvironment,
    ProductTestProcedure,
    ProductTestProcedureResult,
    ProductTestRound,
    ProductTestTargetUnified,
)
from app.services.product_test_run_service import (
    DEFECT_PRIORITY_VALUES,
    DEFECT_SEVERITY_VALUES,
    ENVIRONMENT_STATUS_VALUES,
    MASTER_ACTIVE_STATUS_VALUES,
    PROCEDURE_RESULT_STATUS_VALUES,
    PRODUCT_TEST_RELEASE_STATUS_VALUES,
    TARGET_STATUS_VALUES,
    _ensure_defect_not_locked_for_source_mutation,
    _ensure_round_not_locked_for_source_mutation,
    _ensure_result_not_locked_for_source_mutation,
    _now_text,
    _validate_in,
    ensure_product_test_status_transition_recorded,
    save_procedure_result,
)

RELEASE_STATUS_EDIT_VALUES = tuple(
    {
        *PRODUCT_TEST_RELEASE_STATUS_VALUES,
        "QI_TEAM_RELEASED",
        "QI_TEAM_REVIEWED",
        "BLOCKED",
        "PASSED",
        "DONE",
    }
)

ENTITY_MODEL_MAP = {
    "product_test_round": ProductTestRound,
    "product_test_run": ProductTestRun,
    "product_test_target": ProductTestTargetUnified,
    "product_test_environment": ProductTestEnvironment,
    "product_test_case": ProductTestCase,
    "product_test_procedure": ProductTestProcedure,
    "product_test_procedure_result": ProductTestProcedureResult,
    "product_test_defect": ProductTestDefect,
}

FIELD_WHITELIST: dict[str, frozenset[str]] = {
    "product_test_round": frozenset(
        {
            "test_round_id",
            "test_round_name",
            "workday",
            "start_date",
            "end_date",
            "migration_status",
        }
    ),
    "product_test_run": frozenset(
        {
            "product_test_run_id",
            "product_test_run_status",
            "started_at",
            "finished_at",
            "remark",
        }
    ),
    "product_test_target": frozenset(
        {
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
            "remark",
        }
    ),
    "product_test_environment": frozenset(
        {
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
            "remark",
        }
    ),
    "product_test_case": frozenset(
        {
            "product_test_case_id",
            "product_test_case_title",
            "test_category",
            "test_objective",
            "precondition",
            "expected_result",
            "product_test_case_status",
            "remark",
        }
    ),
    "product_test_procedure": frozenset(
        {
            "product_test_procedure_id",
            "procedure_action",
            "acceptance_criteria",
            "required_evidence_type",
            "product_test_procedure_status",
            "remark",
        }
    ),
    "product_test_procedure_result": frozenset(
        {
            "actual_result",
            "judgement_reason",
            "product_test_procedure_result_status",
            "remark",
        }
    ),
    "product_test_defect": frozenset(
        {
            "defect_title",
            "defect_description",
            "defect_severity",
            "defect_priority",
            "assigned_to",
            "expected_resolution_date",
            "remark",
        }
    ),
}

STATUS_FIELD_VALIDATORS: dict[tuple[str, str], tuple[str, ...]] = {
    ("product_test_target", "product_test_target_status"): TARGET_STATUS_VALUES,
    ("product_test_environment", "product_test_environment_status"): ENVIRONMENT_STATUS_VALUES,
    ("product_test_case", "product_test_case_status"): MASTER_ACTIVE_STATUS_VALUES,
    ("product_test_procedure", "product_test_procedure_status"): MASTER_ACTIVE_STATUS_VALUES,
    ("product_test_procedure_result", "product_test_procedure_result_status"): PROCEDURE_RESULT_STATUS_VALUES,
}

REQUIRED_TEXT_FIELDS = frozenset(
    {
        "upstream_release_id",
        "upstream_release_system",
        "product_code",
        "manufacturer",
        "model_name",
        "defect_title",
        "product_test_case_title",
        "procedure_action",
        "acceptance_criteria",
        "product_test_environment_name",
        "test_category",
        "serial_number",
    }
)


def _normalize_optional_text(value: str) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_defect_severity(value: str) -> str:
    raw = str(value or "").strip().upper()
    mapped = {
        "S": "critical",
        "A": "major",
        "B": "minor",
        "C": "trivial",
        "CRITICAL": "critical",
        "BLOCKER": "critical",
        "HIGH": "major",
        "MAJOR": "major",
        "MEDIUM": "minor",
        "NORMAL": "minor",
        "MODERATE": "minor",
        "LOW": "trivial",
        "MINOR": "trivial",
        "TRIVIAL": "trivial",
    }.get(raw, str(value or "").strip().lower())
    return _validate_in(mapped, DEFECT_SEVERITY_VALUES, "defect_severity")


def _normalize_defect_priority(value: str) -> str:
    raw = str(value or "").strip().upper()
    mapped = {
        "S": "high",
        "A": "high",
        "B": "medium",
        "C": "low",
        "CRITICAL": "high",
        "HIGH": "high",
        "MEDIUM": "medium",
        "LOW": "low",
    }.get(raw, str(value or "").strip().lower())
    return _validate_in(mapped, DEFECT_PRIORITY_VALUES, "defect_priority")


def _coerce_field_value(entity_type: str, field_name: str, value: str) -> Any:
    if field_name == "defect_severity":
        return _normalize_defect_severity(value)
    if field_name == "defect_priority":
        return _normalize_defect_priority(value)

    status_key = (entity_type, field_name)
    if status_key in STATUS_FIELD_VALIDATORS:
        normalized = str(value or "").strip()
        if field_name in {"migration_status"}:
            normalized = normalized.upper()
        else:
            normalized = normalized.lower()
        return _validate_in(normalized, STATUS_FIELD_VALIDATORS[status_key], field_name)

    text = str(value or "").strip()
    if field_name in REQUIRED_TEXT_FIELDS and not text:
        raise ValueError(f"{field_name} is required.")
    if field_name in {
        "remark",
        "test_objective",
        "precondition",
        "expected_result",
        "defect_description",
        "actual_result",
        "judgement_reason",
        "assigned_to",
        "expected_resolution_date",
        "required_evidence_type",
        "hardware_revision",
        "default_software_version",
        "default_firmware_version",
        "software_version",
        "firmware_version",
        "manufacture_lot",
        "captured_at",
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
    }:
        return _normalize_optional_text(value)
    return text


def _touch_row(row: Any, updated_by: str) -> None:
    now_text = _now_text()
    row.updated_at = now_text
    row.updated_by = updated_by


def _save_procedure_result_row(
    database_session: Session,
    *,
    entity_id: str,
    field_name: str,
    coerced_value: Any,
    updated_by: str,
) -> None:
    row = database_session.get(ProductTestProcedureResult, entity_id)
    if row is None:
        raise LookupError("procedure result not found.")
    _ensure_result_not_locked_for_source_mutation(
        database_session,
        product_test_result_id=row.product_test_result_id,
    )
    save_procedure_result(
        database_session,
        product_test_result_id=row.product_test_result_id,
        product_test_procedure_result_id=entity_id,
        next_status=coerced_value
        if field_name == "product_test_procedure_result_status"
        else row.product_test_procedure_result_status,
        actual_result=coerced_value if field_name == "actual_result" else (row.actual_result or ""),
        judgement_reason=coerced_value if field_name == "judgement_reason" else (row.judgement_reason or ""),
        remark=coerced_value if field_name == "remark" else (row.remark or ""),
        updated_by=updated_by,
    )


def _apply_status_update(
    database_session: Session,
    *,
    entity_type: str,
    entity_id: str,
    field_name: str,
    coerced_value: str,
    updated_by: str,
) -> None:
    if entity_type == "product_test_procedure_result":
        _save_procedure_result_row(
            database_session,
            entity_id=entity_id,
            field_name=field_name,
            coerced_value=coerced_value,
            updated_by=updated_by,
        )
        return

    model = ENTITY_MODEL_MAP[entity_type]
    try:
        ensure_product_test_status_transition_recorded(
            database_session,
            entity_type=entity_type,
            entity_id=entity_id,
            to_status=coerced_value,
            transition_reason="table_cell_edit",
            transitioned_by=updated_by,
        )
        row = database_session.get(model, entity_id)
        if row is not None:
            _touch_row(row, updated_by)
    except (ValueError, KeyError):
        # KeyError: entity_type이 status-transition 시스템 미지원 (예: product_test_target)
        row = database_session.get(model, entity_id)
        if row is None:
            raise LookupError(f"{entity_type} not found.")
        setattr(row, field_name, coerced_value)
        _touch_row(row, updated_by)


def _apply_single_update(
    database_session: Session,
    *,
    entity_type: str,
    entity_id: str,
    field_name: str,
    value: str,
    updated_by: str,
) -> None:
    entity_type_value = str(entity_type or "").strip()
    entity_id_value = str(entity_id or "").strip()
    field_name_value = str(field_name or "").strip()
    if not entity_type_value or not entity_id_value or not field_name_value:
        raise ValueError("entity_type, entity_id, field_name are required.")

    if entity_type_value not in ENTITY_MODEL_MAP:
        raise ValueError(f"Unsupported entity_type: {entity_type_value}")

    allowed_fields = FIELD_WHITELIST.get(entity_type_value, frozenset())
    if field_name_value not in allowed_fields:
        raise ValueError(f"Field not allowed for update: {entity_type_value}.{field_name_value}")

    coerced_value = _coerce_field_value(entity_type_value, field_name_value, value)

    if entity_type_value == "product_test_defect":
        _ensure_defect_not_locked_for_source_mutation(
            database_session,
            product_test_defect_id=entity_id_value,
        )

    if field_name_value.endswith("_status"):
        _apply_status_update(
            database_session,
            entity_type=entity_type_value,
            entity_id=entity_id_value,
            field_name=field_name_value,
            coerced_value=coerced_value,
            updated_by=updated_by,
        )
        return

    if entity_type_value == "product_test_procedure_result":
        _save_procedure_result_row(
            database_session,
            entity_id=entity_id_value,
            field_name=field_name_value,
            coerced_value=coerced_value,
            updated_by=updated_by,
        )
        return

    # product_test_run_id PK cascade rename
    if entity_type_value == "product_test_run" and field_name_value == "product_test_run_id":
        old_id = entity_id_value
        new_id = str(coerced_value)
        if old_id != new_id:
            database_session.execute(text("PRAGMA foreign_keys = OFF"))
            for fk_table in ("product_test_result",):
                database_session.execute(
                    text(f"UPDATE {fk_table} SET product_test_run_id = :new WHERE product_test_run_id = :old"),
                    {"new": new_id, "old": old_id},
                )
            database_session.execute(
                text("UPDATE product_test_run SET product_test_run_id = :new WHERE product_test_run_id = :old"),
                {"new": new_id, "old": old_id},
            )
            database_session.flush()
            database_session.execute(text("PRAGMA foreign_keys = ON"))
        return

    # product_test_target_id PK cascade rename
    if entity_type_value == "product_test_target" and field_name_value == "product_test_target_id":
        old_id = entity_id_value
        new_id = str(coerced_value)
        if old_id != new_id:
            database_session.execute(text("PRAGMA foreign_keys = OFF"))
            for fk_table in ("product_test_run",):
                database_session.execute(
                    text(f"UPDATE {fk_table} SET product_test_target_id = :new WHERE product_test_target_id = :old"),
                    {"new": new_id, "old": old_id},
                )
            database_session.execute(
                text("UPDATE product_test_target_unified SET product_test_target_id = :new WHERE product_test_target_id = :old"),
                {"new": new_id, "old": old_id},
            )
            database_session.flush()
            database_session.execute(text("PRAGMA foreign_keys = ON"))
        return

    # product_test_case_id PK cascade rename
    if entity_type_value == "product_test_case" and field_name_value == "product_test_case_id":
        old_id = entity_id_value
        new_id = str(coerced_value)
        if old_id != new_id:
            database_session.execute(text("PRAGMA foreign_keys = OFF"))
            for fk_table in ("product_test_procedure", "product_test_result"):
                database_session.execute(
                    text(f"UPDATE {fk_table} SET product_test_case_id = :new WHERE product_test_case_id = :old"),
                    {"new": new_id, "old": old_id},
                )
            database_session.execute(
                text("UPDATE product_test_case SET product_test_case_id = :new WHERE product_test_case_id = :old"),
                {"new": new_id, "old": old_id},
            )
            database_session.flush()
            database_session.execute(text("PRAGMA foreign_keys = ON"))
        return

    # product_test_procedure_id PK cascade rename
    if entity_type_value == "product_test_procedure" and field_name_value == "product_test_procedure_id":
        old_id = entity_id_value
        new_id = str(coerced_value)
        if old_id != new_id:
            database_session.execute(text("PRAGMA foreign_keys = OFF"))
            for fk_table in ("product_test_procedure_result",):
                database_session.execute(
                    text(f"UPDATE {fk_table} SET product_test_procedure_id = :new WHERE product_test_procedure_id = :old"),
                    {"new": new_id, "old": old_id},
                )
            database_session.execute(
                text("UPDATE product_test_procedure SET product_test_procedure_id = :new WHERE product_test_procedure_id = :old"),
                {"new": new_id, "old": old_id},
            )
            database_session.flush()
            database_session.execute(text("PRAGMA foreign_keys = ON"))
        return

    # test_round_id PK cascade rename
    if entity_type_value == "product_test_round" and field_name_value == "test_round_id":
        old_id = entity_id_value
        new_id = str(coerced_value)
        if old_id != new_id:
            # FK 체크 일시 중단: new_id가 PK에 없는 상태에서 FK 업데이트 시 IntegrityError 방지
            database_session.execute(text("PRAGMA foreign_keys = OFF"))
            for fk_table in ("product_test_run",):
                database_session.execute(
                    text(f"UPDATE {fk_table} SET test_round_id = :new WHERE test_round_id = :old"),
                    {"new": new_id, "old": old_id},
                )
            database_session.execute(
                text("UPDATE product_test_round SET test_round_id = :new WHERE test_round_id = :old"),
                {"new": new_id, "old": old_id},
            )
            database_session.flush()
            database_session.execute(text("PRAGMA foreign_keys = ON"))
        return

    model = ENTITY_MODEL_MAP[entity_type_value]
    row = database_session.get(model, entity_id_value)
    if row is None:
        raise LookupError(f"{entity_type_value} not found.")

    setattr(row, field_name_value, coerced_value)
    _touch_row(row, updated_by)


def bulk_update_product_test_fields(
    database_session: Session,
    *,
    updates: list[dict[str, str]],
    updated_by: str,
) -> dict[str, Any]:
    if not updates:
        return {"updated": 0, "skipped": 0}

    deduped: dict[tuple[str, str, str], str] = {}
    for item in updates:
        key = (
            str(item.get("entity_type") or "").strip(),
            str(item.get("entity_id") or "").strip(),
            str(item.get("field_name") or "").strip(),
        )
        if not key[0] or not key[1] or not key[2]:
            continue
        deduped[key] = str(item.get("value") if item.get("value") is not None else "")

    updated_count = 0
    for (entity_type, entity_id, field_name), raw_value in deduped.items():
        _apply_single_update(
            database_session,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            value=raw_value,
            updated_by=updated_by,
        )
        updated_count += 1

    database_session.commit()
    return {"updated": updated_count, "skipped": max(0, len(updates) - len(deduped))}


# entity_type → cascade DELETE 문 목록 (실행 순서: 자식 → 부모)
# 파라미터: :id = 삭제 대상 PK 값
_CASCADE_DELETE_SQLS: dict[str, list[str]] = {
    "product_test_round": [
        # 런 자식들 (evidence → result → run 경로)
        "DELETE FROM product_test_evidence WHERE product_test_result_id IN (SELECT product_test_result_id FROM product_test_result WHERE product_test_run_id IN (SELECT product_test_run_id FROM product_test_run WHERE test_round_id=:id))",
        "DELETE FROM product_test_procedure_result WHERE product_test_result_id IN (SELECT product_test_result_id FROM product_test_result WHERE product_test_run_id IN (SELECT product_test_run_id FROM product_test_run WHERE test_round_id=:id))",
        "DELETE FROM product_test_result WHERE product_test_run_id IN (SELECT product_test_run_id FROM product_test_run WHERE test_round_id=:id)",
        "DELETE FROM product_test_status_transition WHERE entity_id IN (SELECT product_test_run_id FROM product_test_run WHERE test_round_id=:id)",
        "DELETE FROM product_test_run WHERE test_round_id=:id",
        # 라운드 자체
        "DELETE FROM product_test_status_transition WHERE entity_id=:id",
        "DELETE FROM product_test_round WHERE test_round_id=:id",
    ],
    "product_test_run": [
        "DELETE FROM product_test_evidence WHERE product_test_result_id IN (SELECT product_test_result_id FROM product_test_result WHERE product_test_run_id=:id)",
        "DELETE FROM product_test_procedure_result WHERE product_test_result_id IN (SELECT product_test_result_id FROM product_test_result WHERE product_test_run_id=:id)",
        "DELETE FROM product_test_result WHERE product_test_run_id=:id",
        "DELETE FROM product_test_status_transition WHERE entity_id=:id",
        "DELETE FROM product_test_run WHERE product_test_run_id=:id",
    ],
    "product_test_case": [
        "DELETE FROM product_test_evidence WHERE product_test_procedure_result_id IN (SELECT product_test_procedure_result_id FROM product_test_procedure_result WHERE product_test_procedure_id IN (SELECT product_test_procedure_id FROM product_test_procedure WHERE product_test_case_id=:id))",
        "DELETE FROM product_test_evidence WHERE product_test_result_id IN (SELECT product_test_result_id FROM product_test_result WHERE product_test_case_id=:id)",
        "DELETE FROM product_test_procedure_result WHERE product_test_procedure_id IN (SELECT product_test_procedure_id FROM product_test_procedure WHERE product_test_case_id=:id)",
        "DELETE FROM product_test_procedure_result WHERE product_test_result_id IN (SELECT product_test_result_id FROM product_test_result WHERE product_test_case_id=:id)",
        "DELETE FROM product_test_result WHERE product_test_case_id=:id",
        "DELETE FROM product_test_procedure WHERE product_test_case_id=:id",
        "DELETE FROM product_test_case WHERE product_test_case_id=:id",
    ],
    "product_test_procedure": [
        "DELETE FROM product_test_evidence WHERE product_test_procedure_result_id IN (SELECT product_test_procedure_result_id FROM product_test_procedure_result WHERE product_test_procedure_id=:id)",
        "DELETE FROM product_test_procedure_result WHERE product_test_procedure_id=:id",
        "DELETE FROM product_test_procedure WHERE product_test_procedure_id=:id",
    ],
    "product_test_target": [
        "DELETE FROM product_test_target_unified WHERE product_test_target_id=:id",
    ],
    "product_test_environment": [
        "DELETE FROM product_test_environment_unified WHERE product_test_environment_id=:id",
    ],
    "product_test_defect": [
        "UPDATE product_test_evidence SET product_test_defect_id=NULL WHERE product_test_defect_id=:id",
        "DELETE FROM product_test_defect WHERE product_test_defect_id=:id",
    ],
    "product_test_procedure_result": [
        "UPDATE product_test_evidence SET product_test_procedure_result_id=NULL WHERE product_test_procedure_result_id=:id",
        "DELETE FROM product_test_procedure_result WHERE product_test_procedure_result_id=:id",
    ],
}


def bulk_delete_product_test_entities(
    database_session: Session,
    *,
    entity_type: str,
    entity_ids: list[str],
) -> dict[str, Any]:
    entity_type_value = str(entity_type or "").strip()
    if entity_type_value not in ENTITY_MODEL_MAP:
        raise ValueError(f"Unsupported entity_type: {entity_type_value}")

    deduped_ids = []
    seen_ids = set()
    for raw_id in entity_ids:
        entity_id = str(raw_id or "").strip()
        if not entity_id or entity_id in seen_ids:
            continue
        seen_ids.add(entity_id)
        deduped_ids.append(entity_id)

    if not deduped_ids:
        return {"deleted": 0, "skipped": len(entity_ids)}

    cascade_sqls = _CASCADE_DELETE_SQLS.get(entity_type_value)
    deleted_count = 0

    if cascade_sqls:
        # FK 제약 OFF → cascade 순서대로 삭제 → FK 제약 ON
        database_session.execute(text("PRAGMA foreign_keys=OFF"))
        for entity_id in deduped_ids:
            for stmt in cascade_sqls:
                database_session.execute(text(stmt), {"id": entity_id})
            deleted_count += 1
        database_session.execute(text("PRAGMA foreign_keys=ON"))
    else:
        # cascade 정의 없는 entity는 ORM delete (FK 제약 있을 경우 에러 반환)
        model = ENTITY_MODEL_MAP[entity_type_value]
        for entity_id in deduped_ids:
            row = database_session.get(model, entity_id)
            if row is None:
                raise LookupError(f"{entity_type_value} not found: {entity_id}")
            database_session.delete(row)
            deleted_count += 1

    database_session.commit()
    return {"deleted": deleted_count, "skipped": max(0, len(entity_ids) - len(deduped_ids))}
