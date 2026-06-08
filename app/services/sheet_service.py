from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import app_settings
from app.models import (
    ProductTestDefect,
    ProductTestEvidence,
    ProductTestProcedureResult,
    ProductTestRelease,
    ProductTestResult,
    get_utc_now_datetime,
)
from app.services.backup_service import run_backup
from app.services.product_test_run_service import (
    _ensure_defect_not_locked_for_source_mutation,
    _ensure_release_not_locked_for_source_mutation,
    _ensure_result_not_locked_for_source_mutation,
    _insert_status_transition,
    _next_prefixed_id,
    ensure_product_test_status_transition_recorded,
)
from app.services.status_vocab import normalize_status
from app.services.topology_normalize import normalize_combo

REMARK_COMBO_PATTERN = re.compile(r"\[연결구성\]\s*([^\n\]]+)")
CASE_ID_PREFIX_PATTERN = re.compile(r"^(TEST_)?CASE-")
SUPPORTED_SHEET_TABLES = {"case", "result", "release", "defect", "evidence"}
SHEET_EDIT_CONFIG: dict[str, dict[str, Any]] = {
    "case": {
        "editable_fields": [],
        "create_supported": False,
    },
    "result": {
        "entity_type": "product_test_result",
        "editable_fields": ["status", "remark"],
        "field_map": {
            "status": "product_test_result_status",
            "remark": "remark",
        },
        "create_supported": False,
    },
    "release": {
        "entity_type": "product_test_release",
        "editable_fields": ["status", "remark"],
        "field_map": {
            "status": "product_test_release_status",
            "remark": "remark",
        },
        "create_supported": False,
    },
    "defect": {
        "entity_type": "product_test_defect",
        "editable_fields": ["status", "assigned_to", "expected_resolution_date", "remark"],
        "field_map": {
            "status": "product_test_defect_status",
            "assigned_to": "assigned_to",
            "expected_resolution_date": "expected_resolution_date",
            "remark": "remark",
        },
        "create_supported": False,
    },
    "evidence": {
        "editable_fields": [],
        "create_supported": True,
        "create_fields": [
            "result_id",
            "procedure_result_id",
            "defect_id",
            "evidence_type",
            "file_name",
            "file_path",
            "file_hash",
            "captured_at",
            "remark",
        ],
    },
}
TABLE_MODEL_MAP = {
    "result": ProductTestResult,
    "release": ProductTestRelease,
    "defect": ProductTestDefect,
}


def _extract_combo(remark: str | None) -> str:
    match = REMARK_COMBO_PATTERN.search(remark or "")
    return match.group(1).strip() if match else ""


def _extract_case_topology(case_id: str | None) -> str:
    if not case_id or not CASE_ID_PREFIX_PATTERN.match(case_id):
        return ""
    parts = case_id.split("-", 3)
    return parts[1].strip() if len(parts) >= 2 else ""


def _is_comparable_case_topology(case_id: str | None, case_topology: str) -> bool:
    return bool(case_id and CASE_ID_PREFIX_PATTERN.match(case_id) and "_" in case_topology)


def _flag_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        for flag_name, flag_value in row.get("flags", {}).items():
            if flag_value:
                counts[flag_name] += 1
    return dict(sorted(counts.items()))


def _sheet_meta(table_name: str) -> dict[str, Any]:
    config = SHEET_EDIT_CONFIG[table_name]
    return {
        "editable_fields": list(config.get("editable_fields", [])),
        "create_supported": bool(config.get("create_supported")),
        "create_fields": list(config.get("create_fields", [])),
    }


def get_sheet_payload(database_session: Session, table_name: str) -> dict[str, Any]:
    normalized_name = (table_name or "").strip().lower()
    if normalized_name not in SUPPORTED_SHEET_TABLES:
        raise ValueError(f"Unsupported sheet table: {table_name}")
    if normalized_name == "case":
        return _build_case_sheet(database_session)
    if normalized_name == "result":
        return _build_result_sheet(database_session)
    if normalized_name == "release":
        return _build_release_sheet(database_session)
    if normalized_name == "defect":
        return _build_defect_sheet(database_session)
    return _build_evidence_sheet(database_session)


def _build_case_sheet(database_session: Session) -> dict[str, Any]:
    rows = []
    combo_rows = database_session.execute(
        text(
            """
            SELECT product_test_case_id, remark
            FROM product_test_result
            WHERE product_test_case_id IS NOT NULL
            ORDER BY product_test_result_id
            """
        )
    ).mappings()
    combos_by_case: dict[str, list[str]] = {}
    for combo_row in combo_rows:
        combos_by_case.setdefault(combo_row["product_test_case_id"], []).append(
            normalize_combo(_extract_combo(combo_row["remark"]))
        )
    query = text(
        """
        SELECT
            c.product_test_case_id,
            c.product_test_case_title,
            c.product_test_case_status,
            c.test_category,
            c.remark,
            COUNT(DISTINCT p.product_test_procedure_id) AS procedure_count,
            COUNT(DISTINCT r.product_test_result_id) AS result_count
        FROM product_test_case c
        LEFT JOIN product_test_procedure p ON p.product_test_case_id = c.product_test_case_id
        LEFT JOIN product_test_result r ON r.product_test_case_id = c.product_test_case_id
        GROUP BY
            c.product_test_case_id,
            c.product_test_case_title,
            c.product_test_case_status,
            c.test_category,
            c.remark
        ORDER BY c.product_test_case_id
        """
    )
    for row in database_session.execute(query).mappings():
        result_combos = combos_by_case.get(row["product_test_case_id"], [])
        combo_counts = Counter(combo for combo in result_combos if combo)
        dominant_combo = combo_counts.most_common(1)[0][0] if combo_counts else ""
        case_topology = _extract_case_topology(row["product_test_case_id"])
        flags = {
            "case_id_invalid": not bool(CASE_ID_PREFIX_PATTERN.match(row["product_test_case_id"] or "")),
            "procedure_missing": bool((row["result_count"] or 0) > 0 and (row["procedure_count"] or 0) == 0),
            "topology_mismatch": bool(case_topology and dominant_combo and case_topology != dominant_combo),
            "topology_unclassified": dominant_combo == "UNCLASSIFIED",
        }
        rows.append(
            {
                "id": row["product_test_case_id"],
                "title": row["product_test_case_title"],
                "status": normalize_status(row["product_test_case_status"]),
                "test_category": row["test_category"],
                "procedure_count": int(row["procedure_count"] or 0),
                "result_count": int(row["result_count"] or 0),
                "case_topology": case_topology,
                "dominant_result_topology": dominant_combo,
                "candidate_topologies": dict(combo_counts),
                "remark": row["remark"] or "",
                "flags": flags,
            }
        )
    return {
        "table": "case",
        "meta": _sheet_meta("case"),
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "flag_counts": _flag_counts(rows),
        },
    }


def _build_result_sheet(database_session: Session) -> dict[str, Any]:
    rows = []
    query = text(
        """
        SELECT
            r.product_test_result_id,
            r.product_test_run_id,
            r.product_test_case_id,
            r.product_test_result_status,
            r.remark,
            COUNT(DISTINCT e.product_test_evidence_id) AS evidence_count
        FROM product_test_result r
        LEFT JOIN product_test_evidence e ON e.product_test_result_id = r.product_test_result_id
        GROUP BY
            r.product_test_result_id,
            r.product_test_run_id,
            r.product_test_case_id,
            r.product_test_result_status,
            r.remark
        ORDER BY r.product_test_result_id
        """
    )
    for row in database_session.execute(query).mappings():
        combo = normalize_combo(_extract_combo(row["remark"]))
        case_topology = _extract_case_topology(row["product_test_case_id"])
        comparable_case_topology = _is_comparable_case_topology(
            row["product_test_case_id"], case_topology
        )
        flags = {
            "topology_mismatch": bool(
                combo and comparable_case_topology and case_topology != combo
            ),
            "evidence_missing": int(row["evidence_count"] or 0) == 0,
            "combo_unclassified": combo == "UNCLASSIFIED",
        }
        rows.append(
            {
                "id": row["product_test_result_id"],
                "run_id": row["product_test_run_id"],
                "case_id": row["product_test_case_id"],
                "status": normalize_status(row["product_test_result_status"]),
                "combo": combo,
                "case_topology": case_topology,
                "evidence_count": int(row["evidence_count"] or 0),
                "remark": row["remark"] or "",
                "flags": flags,
            }
        )
    return {
        "table": "result",
        "meta": _sheet_meta("result"),
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "flag_counts": _flag_counts(rows),
            "parsed_combo_count": sum(1 for row in rows if row["combo"]),
        },
    }


def _build_release_sheet(database_session: Session) -> dict[str, Any]:
    rows = []
    query = text(
        """
        SELECT
            r.product_test_release_id,
            r.upstream_release_id,
            r.release_stage,
            r.product_test_release_status,
            r.test_round_id,
            r.release_visible,
            r.remark,
            COUNT(DISTINCT run.product_test_run_id) AS run_count
        FROM product_test_release r
        LEFT JOIN product_test_run run ON run.product_test_release_id = r.product_test_release_id
        GROUP BY
            r.product_test_release_id,
            r.upstream_release_id,
            r.release_stage,
            r.product_test_release_status,
            r.test_round_id,
            r.release_visible,
            r.remark
        ORDER BY r.product_test_release_id
        """
    )
    for row in database_session.execute(query).mappings():
        flags = {
            "round_missing": row["test_round_id"] is None,
            "legacy_ap_text": "AP" in (row["product_test_release_id"] or "") or "AP" in (row["remark"] or ""),
            "orphan_visible_round": bool(
                row["release_stage"] == "device_round" and int(row["run_count"] or 0) == 0
            ),
        }
        rows.append(
            {
                "id": row["product_test_release_id"],
                "upstream_release_id": row["upstream_release_id"],
                "release_stage": row["release_stage"],
                "status": normalize_status(row["product_test_release_status"]),
                "test_round_id": row["test_round_id"] or "",
                "release_visible": int(row["release_visible"] or 0),
                "run_count": int(row["run_count"] or 0),
                "remark": row["remark"] or "",
                "flags": flags,
            }
        )
    return {
        "table": "release",
        "meta": _sheet_meta("release"),
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "flag_counts": _flag_counts(rows),
            "rounds_without_release_count": int(
                database_session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM product_test_round round
                        LEFT JOIN product_test_release rel
                          ON rel.test_round_id = round.test_round_id
                        WHERE rel.product_test_release_id IS NULL
                        """
                    )
                ).scalar_one()
                or 0
            ),
        },
    }


def _build_defect_sheet(database_session: Session) -> dict[str, Any]:
    rows = []
    query = text(
        """
        SELECT
            d.product_test_defect_id,
            d.product_test_result_id,
            d.product_test_defect_status,
            d.defect_severity,
            d.defect_priority,
            d.assigned_to,
            d.expected_resolution_date,
            res.product_test_result_status,
            d.remark
        FROM product_test_defect d
        LEFT JOIN product_test_result res ON res.product_test_result_id = d.product_test_result_id
        ORDER BY d.product_test_defect_id
        """
    )
    for row in database_session.execute(query).mappings():
        result_status = normalize_status(row["product_test_result_status"])
        defect_status = normalize_status(row["product_test_defect_status"])
        flags = {
            "opened_without_blocked_result": defect_status == "OPENED" and result_status not in {"BLOCKED", "TESTING"},
            "missing_result": not row["product_test_result_id"],
        }
        rows.append(
            {
                "id": row["product_test_defect_id"],
                "result_id": row["product_test_result_id"],
                "status": defect_status or (row["product_test_defect_status"] or ""),
                "result_status": result_status,
                "severity": row["defect_severity"],
                "priority": row["defect_priority"],
                "assigned_to": row["assigned_to"] or "",
                "expected_resolution_date": row["expected_resolution_date"] or "",
                "remark": row["remark"] or "",
                "flags": flags,
            }
        )
    return {
        "table": "defect",
        "meta": _sheet_meta("defect"),
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "flag_counts": _flag_counts(rows),
        },
    }


def _build_evidence_sheet(database_session: Session) -> dict[str, Any]:
    rows = []
    query = text(
        """
        SELECT
            e.product_test_evidence_id,
            e.product_test_result_id,
            e.product_test_procedure_result_id,
            e.product_test_defect_id,
            e.product_test_evidence_type,
            e.file_name,
            e.file_path,
            e.file_hash,
            e.captured_at,
            e.remark
        FROM product_test_evidence e
        ORDER BY e.product_test_evidence_id
        """
    )
    for row in database_session.execute(query).mappings():
        rows.append(
            {
                "id": row["product_test_evidence_id"],
                "result_id": row["product_test_result_id"],
                "procedure_result_id": row["product_test_procedure_result_id"],
                "defect_id": row["product_test_defect_id"],
                "evidence_type": row["product_test_evidence_type"],
                "file_name": row["file_name"] or "",
                "file_path": row["file_path"] or "",
                "file_hash": row["file_hash"] or "",
                "captured_at": row["captured_at"] or "",
                "remark": row["remark"] or "",
                "flags": {},
            }
        )
    missing_evidence_result_count = database_session.execute(
        text(
            """
            SELECT COUNT(*)
            FROM product_test_result r
            LEFT JOIN product_test_evidence e ON e.product_test_result_id = r.product_test_result_id
            WHERE e.product_test_evidence_id IS NULL
            """
        )
    ).scalar_one()
    return {
        "table": "evidence",
        "meta": _sheet_meta("evidence"),
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "flag_counts": _flag_counts(rows),
            "missing_evidence_result_count": int(missing_evidence_result_count or 0),
        },
    }


def _preview_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _touch_row(row: Any, updated_by: str) -> None:
    now_text = get_utc_now_datetime().astimezone().strftime("%Y-%m-%d %H:%M")
    row.updated_at = now_text
    row.updated_by = updated_by


def _normalize_sheet_status(table_name: str, value: str) -> str:
    canonical = normalize_status(value)
    if table_name in {"result", "defect"}:
        return canonical.lower()
    if table_name == "release":
        return canonical.upper()
    return str(value or "").strip()


def _normalize_text(value: Any) -> str | None:
    text_value = str(value or "").strip()
    return text_value or None


def _guard_sheet_write(database_session: Session, table_name: str, row: Any) -> None:
    if table_name == "result":
        _ensure_result_not_locked_for_source_mutation(
            database_session,
            product_test_result_id=row.product_test_result_id,
        )
    elif table_name == "release":
        _ensure_release_not_locked_for_source_mutation(
            database_session,
            product_test_release_id=row.product_test_release_id,
        )
    elif table_name == "defect":
        _ensure_defect_not_locked_for_source_mutation(
            database_session,
            product_test_defect_id=row.product_test_defect_id,
        )


def _status_attr_name(table_name: str) -> str:
    return str(SHEET_EDIT_CONFIG[table_name]["field_map"]["status"])


def _entity_identifier(table_name: str, row: Any) -> str:
    if table_name == "result":
        return row.product_test_result_id
    if table_name == "release":
        return row.product_test_release_id
    if table_name == "defect":
        return row.product_test_defect_id
    raise ValueError(f"Unsupported table for entity identifier: {table_name}")


def _get_sheet_row(database_session: Session, table_name: str, record_id: str) -> Any:
    if table_name not in TABLE_MODEL_MAP:
        raise ValueError(f"Unsupported editable table: {table_name}")
    row = database_session.get(TABLE_MODEL_MAP[table_name], record_id)
    if row is None:
        raise LookupError(f"{table_name} row not found.")
    return row


def _build_sheet_update_preview(
    database_session: Session,
    *,
    table_name: str,
    record_id: str,
    changes: dict[str, Any],
) -> dict[str, Any]:
    normalized_name = (table_name or "").strip().lower()
    if normalized_name not in SUPPORTED_SHEET_TABLES:
        raise ValueError(f"Unsupported sheet table: {table_name}")
    editable_fields = SHEET_EDIT_CONFIG[normalized_name].get("editable_fields", [])
    if not editable_fields:
        raise ValueError(f"{normalized_name} sheet is read-only.")
    row = _get_sheet_row(database_session, normalized_name, record_id)
    _guard_sheet_write(database_session, normalized_name, row)
    field_map = SHEET_EDIT_CONFIG[normalized_name]["field_map"]
    diff: list[dict[str, Any]] = []
    for public_field, raw_value in (changes or {}).items():
        if public_field not in editable_fields:
            raise ValueError(f"Field not editable: {normalized_name}.{public_field}")
        attr_name = field_map[public_field]
        current_value = getattr(row, attr_name)
        if public_field == "status":
            next_value = _normalize_sheet_status(normalized_name, str(raw_value or ""))
            current_display = normalize_status(current_value)
            next_display = normalize_status(next_value)
        else:
            next_value = _normalize_text(raw_value)
            current_display = str(current_value or "")
            next_display = str(next_value or "")
        if (current_value or "") == (next_value or ""):
            continue
        diff.append(
            {
                "field": public_field,
                "attribute": attr_name,
                "from": current_display,
                "to": next_display,
                "raw_from": current_value,
                "raw_to": next_value,
            }
        )
    preview = {
        "table": normalized_name,
        "id": record_id,
        "editable_fields": editable_fields,
        "diff": diff,
        "changed_count": len(diff),
    }
    preview["preview_hash"] = _preview_hash(
        {
            "table": preview["table"],
            "id": preview["id"],
            "diff": [
                {
                    "field": item["field"],
                    "from": item["from"],
                    "to": item["to"],
                    "raw_from": item["raw_from"],
                    "raw_to": item["raw_to"],
                }
                for item in diff
            ],
        }
    )
    return preview


def preview_sheet_update(
    database_session: Session,
    *,
    table_name: str,
    record_id: str,
    changes: dict[str, Any],
) -> dict[str, Any]:
    return _build_sheet_update_preview(
        database_session,
        table_name=table_name,
        record_id=record_id,
        changes=changes,
    )


def apply_sheet_update(
    database_session: Session,
    *,
    table_name: str,
    record_id: str,
    changes: dict[str, Any],
    preview_hash: str,
    updated_by: str,
    reason: str,
) -> dict[str, Any]:
    preview = _build_sheet_update_preview(
        database_session,
        table_name=table_name,
        record_id=record_id,
        changes=changes,
    )
    normalized_name = preview["table"]
    if preview["preview_hash"] != str(preview_hash or "").strip():
        raise RuntimeError("Preview mismatch. Refresh the diff and try again.")
    if not preview["diff"]:
        return {
            "table": normalized_name,
            "id": record_id,
            "changed_count": 0,
            "diff": [],
        }
    run_backup(app_settings.data_directory_path)
    row = _get_sheet_row(database_session, normalized_name, record_id)
    entity_type = SHEET_EDIT_CONFIG[normalized_name]["entity_type"]
    entity_id = _entity_identifier(normalized_name, row)
    current_status_attr = _status_attr_name(normalized_name)
    status_change = next((item for item in preview["diff"] if item["field"] == "status"), None)
    transition_field_updates = {
        item["attribute"]: item["raw_to"]
        for item in preview["diff"]
        if item["field"] != "status"
    }
    for item in preview["diff"]:
        if item["field"] == "status":
            ensure_product_test_status_transition_recorded(
                database_session,
                entity_type=entity_type,
                entity_id=entity_id,
                to_status=str(item["raw_to"] or ""),
                transition_reason=reason or "sheet_status_update",
                transitioned_by=updated_by,
                **transition_field_updates,
            )
            row = _get_sheet_row(database_session, normalized_name, record_id)
            continue
        setattr(row, item["attribute"], item["raw_to"])
        _touch_row(row, updated_by)
        if status_change is not None:
            continue
        current_status = str(getattr(row, current_status_attr) or "").strip()
        _insert_status_transition(
            database_session,
            entity_type=entity_type,
            entity_id=entity_id,
            from_status=current_status,
            to_status=current_status,
            transition_reason=reason or f"sheet_field_update:{item['field']}",
            transitioned_by=updated_by,
        )
    database_session.commit()
    return {
        "table": normalized_name,
        "id": record_id,
        "changed_count": preview["changed_count"],
        "diff": [
            {
                "field": item["field"],
                "from": item["from"],
                "to": item["to"],
            }
            for item in preview["diff"]
        ],
    }


def _normalize_evidence_create_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "result_id": str(payload.get("result_id") or "").strip(),
        "procedure_result_id": str(payload.get("procedure_result_id") or "").strip(),
        "defect_id": str(payload.get("defect_id") or "").strip(),
        "evidence_type": str(payload.get("evidence_type") or "").strip(),
        "file_name": str(payload.get("file_name") or "").strip(),
        "file_path": str(payload.get("file_path") or "").strip(),
        "file_hash": str(payload.get("file_hash") or "").strip(),
        "captured_at": str(payload.get("captured_at") or "").strip(),
        "remark": str(payload.get("remark") or "").strip(),
    }
    if not normalized["result_id"]:
        raise ValueError("result_id is required.")
    if not normalized["evidence_type"]:
        raise ValueError("evidence_type is required.")
    if not normalized["file_path"]:
        raise ValueError("file_path is required.")
    if not normalized["file_name"]:
        normalized["file_name"] = normalized["file_path"].rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return normalized


def _build_evidence_create_preview(
    database_session: Session,
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    normalized = _normalize_evidence_create_payload(payload)
    result_row = database_session.get(ProductTestResult, normalized["result_id"])
    if result_row is None:
        raise LookupError("result_id not found.")
    _ensure_result_not_locked_for_source_mutation(
        database_session,
        product_test_result_id=result_row.product_test_result_id,
    )
    if normalized["procedure_result_id"]:
        procedure_row = database_session.get(ProductTestProcedureResult, normalized["procedure_result_id"])
        if procedure_row is None or procedure_row.product_test_result_id != result_row.product_test_result_id:
            raise ValueError("procedure_result_id must belong to result_id.")
    if normalized["defect_id"]:
        defect_row = database_session.get(ProductTestDefect, normalized["defect_id"])
        if defect_row is None or defect_row.product_test_result_id != result_row.product_test_result_id:
            raise ValueError("defect_id must belong to result_id.")
    diff = [
        {"field": key, "from": "", "to": value}
        for key, value in normalized.items()
        if value
    ]
    preview = {
        "table": "evidence",
        "id": "__new__",
        "editable_fields": [],
        "create_fields": _sheet_meta("evidence")["create_fields"],
        "diff": diff,
        "changed_count": len(diff),
    }
    preview["preview_hash"] = _preview_hash(
        {
            "table": "evidence",
            "id": "__new__",
            "diff": diff,
        }
    )
    return preview


def preview_evidence_create(
    database_session: Session,
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _build_evidence_create_preview(database_session, payload=payload)


def apply_evidence_create(
    database_session: Session,
    *,
    payload: dict[str, Any],
    preview_hash: str,
    updated_by: str,
    reason: str,
) -> dict[str, Any]:
    preview = _build_evidence_create_preview(database_session, payload=payload)
    if preview["preview_hash"] != str(preview_hash or "").strip():
        raise RuntimeError("Preview mismatch. Refresh the diff and try again.")
    normalized = _normalize_evidence_create_payload(payload)
    result_row = database_session.get(ProductTestResult, normalized["result_id"])
    if result_row is None:
        raise LookupError("result_id not found.")
    run_backup(app_settings.data_directory_path)
    today_text = get_utc_now_datetime().astimezone().strftime("%Y%m%d")
    evidence_id = _next_prefixed_id(
        database_session,
        ProductTestEvidence,
        "product_test_evidence_id",
        f"SQA_PRODUCT_TEST_EVIDENCE_ID-{today_text}",
    )
    now_text = get_utc_now_datetime().astimezone().strftime("%Y-%m-%d %H:%M")
    row = ProductTestEvidence(
        product_test_evidence_id=evidence_id,
        product_test_result_id=normalized["result_id"],
        product_test_procedure_result_id=normalized["procedure_result_id"] or None,
        product_test_defect_id=normalized["defect_id"] or None,
        product_test_evidence_type=normalized["evidence_type"],
        file_name=normalized["file_name"] or None,
        file_path=normalized["file_path"],
        file_hash=normalized["file_hash"] or None,
        captured_at=normalized["captured_at"] or None,
        captured_by=updated_by,
        created_at=now_text,
        created_by=updated_by,
        updated_at=now_text,
        updated_by=updated_by,
        remark=normalized["remark"] or None,
    )
    database_session.add(row)
    current_status = str(result_row.product_test_result_status or "").strip()
    _insert_status_transition(
        database_session,
        entity_type="product_test_result",
        entity_id=result_row.product_test_result_id,
        from_status=current_status,
        to_status=current_status,
        transition_reason=reason or "sheet_evidence_create",
        transitioned_by=updated_by,
    )
    database_session.commit()
    return {
        "table": "evidence",
        "id": evidence_id,
        "changed_count": preview["changed_count"],
        "diff": preview["diff"],
    }
