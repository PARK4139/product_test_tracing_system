"""product_test_run_service package

각 서브모듈은 아래와 같이 분리됩니다:
  _common      — 상수·순수 헬퍼·락 가드
  _status      — 상태 전이 FSM
  _list_queries— 조회/열거 쿼리
  _master_data — 마스터 데이터 생성
  _seed        — 시드 데이터
  _runs        — 실행·결과·증거·결함 변경
  _trace       — 트레이스 뷰
  _exports     — CSV 내보내기
  _system      — 시스템 점검
  _defects     — 결함 상세·전이

외부 코드는 이 __init__.py 경로만 사용하며 실제 정의 위치는 서브모듈에 있으므로
스택 트레이스에서 정확한 파일명·줄번호를 확인할 수 있습니다.
"""
from __future__ import annotations

# ── 상수 ────────────────────────────────────────────────────────────────────
from app.services.product_test_run_service._common import (
    BLOCKED_REASON_EXAMPLES,
    DEFECT_PRIORITY_VALUES,
    DEFECT_SEVERITY_VALUES,
    DEFECT_STATUS_VALUES,
    ENTITY_TRANSITIONS,
    ENTITY_TYPE_VALUES,
    ENVIRONMENT_STATUS_VALUES,
    EVIDENCE_TYPE_VALUES,
    MASTER_ACTIVE_STATUS_VALUES,
    PROCEDURE_RESULT_STATUS_VALUES,
    PRODUCT_TEST_IDENTIFIER_GUIDES,
    PRODUCT_TEST_RELEASE_STATUS_VALUES,
    RELEASE_STAGE_VALUES,
    RESULT_STATUS_VALUES,
    RUN_STATUS_VALUES,
    SKIPPED_REASON_EXAMPLES,
    TARGET_STATUS_VALUES,
)

# ── 공개 헬퍼 ────────────────────────────────────────────────────────────────
from app.services.product_test_run_service._common import (
    build_product_code,
    get_product_test_identifier_client_rules,
    get_product_test_identifier_guides,
    _ensure_defect_not_locked_for_source_mutation,
    _ensure_result_not_locked_for_source_mutation,
    _ensure_round_not_locked_for_source_mutation,
    _next_prefixed_id,
    _now_text,
    _validate_in,
)

# ── 상태 전이 ────────────────────────────────────────────────────────────────
from app.services.product_test_run_service._status import (
    _insert_status_transition,
    ensure_product_test_status_transition_recorded,
)

# ── 조회 쿼리 ────────────────────────────────────────────────────────────────
from app.services.product_test_run_service._list_queries import (
    list_case_options,
    list_environment_options,
    list_product_test_cases,
    list_product_test_environment_definitions,
    list_product_test_environments,
    list_product_test_procedures,
    list_product_test_rounds,
    list_product_test_runs,
    list_product_test_targets,
    list_round_options,
    list_running_run_options,
    list_target_options,
)

# ── 마스터 데이터 ────────────────────────────────────────────────────────────
from app.services.product_test_run_service._master_data import (
    create_product_test_case,
    create_product_test_environment,
    create_product_test_environment_definition,
    create_product_test_procedure,
    create_product_test_target,
)

# ── 시드 ────────────────────────────────────────────────────────────────────
from app.services.product_test_run_service._seed import (
    seed_product_test_wifi_ap_configuration_sample_data,
)

# ── 실행 라이프사이클 ─────────────────────────────────────────────────────────
from app.services.product_test_run_service._runs import (
    cancel_run,
    finish_run,
    get_run_detail,
    list_runs,
    save_defect,
    save_evidence,
    save_procedure_result,
    start_product_test_result,
    start_run,
)

# ── 트레이스 ────────────────────────────────────────────────────────────────
from app.services.product_test_run_service._trace import (
    get_product_test_run_trace_view,
    get_product_test_trace_view,
    get_test_round_id_by_run_id,
)

# ── 내보내기 ────────────────────────────────────────────────────────────────
from app.services.product_test_run_service._exports import (
    build_product_test_run_export_rows,
    build_product_test_trace_export_rows,
)

# ── 시스템 ──────────────────────────────────────────────────────────────────
from app.services.product_test_run_service._system import (
    get_product_test_system_check,
    get_test_round_id_by_result_id,
)

# ── 결함 ────────────────────────────────────────────────────────────────────
from app.services.product_test_run_service._defects import (
    create_retest_product_test_result_from_defect,
    get_product_test_defect_detail,
    transition_product_test_defect_to_assigned,
    transition_product_test_defect_to_closed,
    transition_product_test_defect_to_fixed,
    transition_product_test_defect_to_rejected,
    transition_product_test_defect_to_retested,
)

__all__ = [
    # 상수
    "BLOCKED_REASON_EXAMPLES", "DEFECT_PRIORITY_VALUES", "DEFECT_SEVERITY_VALUES",
    "DEFECT_STATUS_VALUES", "ENTITY_TRANSITIONS", "ENTITY_TYPE_VALUES",
    "ENVIRONMENT_STATUS_VALUES", "EVIDENCE_TYPE_VALUES", "MASTER_ACTIVE_STATUS_VALUES",
    "PROCEDURE_RESULT_STATUS_VALUES", "PRODUCT_TEST_IDENTIFIER_GUIDES",
    "PRODUCT_TEST_RELEASE_STATUS_VALUES", "RELEASE_STAGE_VALUES",
    "RESULT_STATUS_VALUES", "RUN_STATUS_VALUES",
    "SKIPPED_REASON_EXAMPLES", "TARGET_STATUS_VALUES",
    # 헬퍼
    "build_product_code", "get_product_test_identifier_client_rules",
    "get_product_test_identifier_guides",
    "_ensure_defect_not_locked_for_source_mutation",
    "_ensure_result_not_locked_for_source_mutation",
    "_ensure_round_not_locked_for_source_mutation",
    "_next_prefixed_id", "_now_text", "_validate_in",
    # 상태
    "_insert_status_transition", "ensure_product_test_status_transition_recorded",
    # 조회
    "list_case_options", "list_environment_options", "list_product_test_cases",
    "list_product_test_environment_definitions", "list_product_test_environments",
    "list_product_test_procedures", "list_product_test_rounds", "list_product_test_runs",
    "list_product_test_targets", "list_round_options", "list_running_run_options",
    "list_target_options",
    # 마스터 데이터
    "create_product_test_case", "create_product_test_environment",
    "create_product_test_environment_definition", "create_product_test_procedure",
    "create_product_test_target",
    # 시드
    "seed_product_test_wifi_ap_configuration_sample_data",
    # 실행
    "cancel_run", "finish_run", "get_run_detail", "list_runs", "save_defect",
    "save_evidence", "save_procedure_result", "start_product_test_result", "start_run",
    # 트레이스
    "get_product_test_run_trace_view", "get_product_test_trace_view",
    "get_test_round_id_by_run_id",
    # 내보내기
    "build_product_test_run_export_rows", "build_product_test_trace_export_rows",
    # 시스템
    "get_product_test_system_check", "get_test_round_id_by_result_id",
    # 결함
    "create_retest_product_test_result_from_defect", "get_product_test_defect_detail",
    "transition_product_test_defect_to_assigned", "transition_product_test_defect_to_closed",
    "transition_product_test_defect_to_fixed", "transition_product_test_defect_to_rejected",
    "transition_product_test_defect_to_retested",
]
