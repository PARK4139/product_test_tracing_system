"""Phase 2 — custom_sheet_tab 기반 추적성 쿼리 헬퍼.

원본 관계형 테이블을 쓰지 않고 custom_sheet_tab.rows_json 위에서
json_extract / json_each 로 동일한 추적 체인을 재현한다.

검증 규칙:
  - 이 모듈의 쿼리 결과는 원본 관계형 쿼리와 행 수/샘플이 일치해야 한다.
  - 불일치 발견 시 즉시 LookupError 를 올린다.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# 내부 헬퍼 — json_each 기반 행 추출
# ---------------------------------------------------------------------------

_SQL_ROWS_BY_FIELD = """
SELECT r.value AS row_json
FROM custom_sheet_tab cs, json_each(cs.rows_json) r
WHERE cs.region_key = :region_key
  AND json_extract(r.value, :field_path) = :field_value
"""

_SQL_ALL_ROWS = """
SELECT r.value AS row_json
FROM custom_sheet_tab cs, json_each(cs.rows_json) r
WHERE cs.region_key = :region_key
"""

_SQL_ROWS_IN_SET = """
SELECT r.value AS row_json
FROM custom_sheet_tab cs, json_each(cs.rows_json) r
WHERE cs.region_key = :region_key
  AND json_extract(r.value, :field_path) IN ({placeholders})
"""


def _rows(db: Session, region_key: str) -> list[dict[str, Any]]:
    """region_key 의 모든 rows_json 행을 dict 리스트로 반환."""
    import json as _json
    result = db.execute(text(_SQL_ALL_ROWS), {"region_key": region_key})
    return [_json.loads(row[0]) for row in result]


def _rows_where(
    db: Session,
    region_key: str,
    field: str,
    value: str,
) -> list[dict[str, Any]]:
    """특정 필드 값으로 필터링된 rows_json 행 반환."""
    import json as _json
    result = db.execute(
        text(_SQL_ROWS_BY_FIELD),
        {"region_key": region_key, "field_path": f"$.{field}", "field_value": value},
    )
    return [_json.loads(row[0]) for row in result]


def _rows_where_in(
    db: Session,
    region_key: str,
    field: str,
    values: list[str],
) -> list[dict[str, Any]]:
    """IN 필터로 rows_json 행 반환 (값 목록이 빈 경우 빈 리스트)."""
    if not values:
        return []
    import json as _json
    placeholders = ",".join(f":v{i}" for i in range(len(values)))
    sql = _SQL_ROWS_IN_SET.format(placeholders=placeholders)
    params: dict[str, Any] = {
        "region_key": region_key,
        "field_path": f"$.{field}",
    }
    params.update({f"v{i}": v for i, v in enumerate(values)})
    result = db.execute(text(sql), params)
    return [_json.loads(row[0]) for row in result]


# ---------------------------------------------------------------------------
# Public API — Round 중심 추적 그래프
# ---------------------------------------------------------------------------

def collect_round_graph_cs(
    db: Session,
    test_round_id: str,
) -> dict[str, Any]:
    """custom_sheet_tab 에서 Round 를 루트로 한 전체 추적 그래프 수집.

    반환 구조:
      round          : dict | None
      runs           : list[dict]
      results        : list[dict]
      procedure_results: list[dict]
      evidences      : list[dict]
      defects        : list[dict]
      status_transitions: list[dict]
    """
    round_rows = _rows_where(db, "entity/round", "test_round_id", test_round_id)
    round_row = round_rows[0] if round_rows else None

    run_rows = _rows_where(db, "entity/run", "test_round_id", test_round_id)
    run_ids = [r["product_test_run_id"] for r in run_rows]

    result_rows = _rows_where_in(db, "entity/result", "product_test_run_id", run_ids)
    result_ids = [r["product_test_result_id"] for r in result_rows]

    procedure_result_rows = _rows_where_in(
        db, "entity/proc_result", "product_test_result_id", result_ids
    )
    evidence_rows = _rows_where_in(
        db, "entity/evidence", "product_test_result_id", result_ids
    )
    defect_rows = _rows_where_in(
        db, "entity/defect", "product_test_result_id", result_ids
    )

    entity_ids = (
        set(run_ids)
        | set(result_ids)
        | {r["product_test_procedure_result_id"] for r in procedure_result_rows}
        | {r["product_test_defect_id"] for r in defect_rows}
    )

    all_transitions = _rows(db, "entity/status_log")
    status_transitions = [
        t for t in all_transitions
        if t.get("entity_id") in entity_ids
    ]

    return {
        "round": round_row,
        "runs": run_rows,
        "results": result_rows,
        "procedure_results": procedure_result_rows,
        "evidences": evidence_rows,
        "defects": defect_rows,
        "status_transitions": status_transitions,
    }


# ---------------------------------------------------------------------------
# Public API — 집계
# ---------------------------------------------------------------------------

def get_round_summary_cs(db: Session, test_round_id: str) -> dict[str, Any]:
    """Round 별 run / result / defect 카운트 집계."""
    graph = collect_round_graph_cs(db, test_round_id)
    return {
        "test_round_id": test_round_id,
        "run_count": len(graph["runs"]),
        "result_count": len(graph["results"]),
        "defect_count": len(graph["defects"]),
        "evidence_count": len(graph["evidences"]),
        "status_transitions_count": len(graph["status_transitions"]),
    }


def get_all_rounds_summary_cs(db: Session) -> list[dict[str, Any]]:
    """모든 Round 의 집계를 리스트로 반환."""
    round_rows = _rows(db, "entity/round")
    summaries = []
    for rnd in round_rows:
        rid = rnd.get("test_round_id", "")
        s = get_round_summary_cs(db, rid)
        s.update({
            "test_round_name": rnd.get("test_round_name", ""),
            "migration_status": rnd.get("migration_status", ""),
            "start_date": rnd.get("start_date", ""),
            "end_date": rnd.get("end_date", ""),
        })
        summaries.append(s)
    return summaries


def get_defects_for_result_cs(db: Session, product_test_result_id: str) -> list[dict[str, Any]]:
    """result_id 에 연결된 defect 행 목록."""
    return _rows_where(db, "entity/defect", "product_test_result_id", product_test_result_id)


def get_results_for_run_cs(db: Session, product_test_run_id: str) -> list[dict[str, Any]]:
    """run_id 에 연결된 result 행 목록."""
    return _rows_where(db, "entity/result", "product_test_run_id", product_test_run_id)


def get_case_row_cs(db: Session, product_test_case_id: str) -> dict[str, Any] | None:
    """case_id 로 케이스 행 조회."""
    rows = _rows_where(db, "entity/case", "product_test_case_id", product_test_case_id)
    return rows[0] if rows else None


def get_run_row_cs(db: Session, product_test_run_id: str) -> dict[str, Any] | None:
    rows = _rows_where(db, "entity/run", "product_test_run_id", product_test_run_id)
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Public API — 전체 엔티티 목록 옵션
# ---------------------------------------------------------------------------

def list_round_options_cs(db: Session) -> list[dict[str, str]]:
    rows = _rows(db, "entity/round")
    return [
        {"value": r.get("test_round_id", ""), "label": r.get("test_round_name", "") or r.get("test_round_id", "")}
        for r in rows
    ]


def list_target_options_cs(db: Session) -> list[dict[str, str]]:
    rows = _rows(db, "entity/target")
    return [
        {
            "value": r.get("product_test_target_id", ""),
            "label": " / ".join(filter(None, [
                r.get("product_code", ""),
                r.get("model_name", ""),
                r.get("serial_number", ""),
            ])),
        }
        for r in rows
    ]


def list_config_options_cs(db: Session) -> list[dict[str, str]]:
    rows = _rows(db, "entity/environment")
    return [
        {
            "value": r.get("product_test_config_id", ""),
            "label": r.get("product_test_config_name", "") or r.get("product_test_config_id", ""),
        }
        for r in rows
    ]


def list_case_options_cs(db: Session) -> list[dict[str, str]]:
    rows = _rows(db, "entity/case")
    return [
        {
            "value": r.get("product_test_case_id", ""),
            "label": r.get("product_test_case_title", "") or r.get("product_test_case_id", ""),
        }
        for r in rows
    ]
