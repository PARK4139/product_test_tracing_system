너는 이 저장소(`product_test_tracing_system`, FastAPI+SQLite, Windows)의 **모든 엔티티 테이블을 custom-sheet 저장소로 이전**하고, 그 위에 **쿼리 기반 추적성**을 재구현한다. 사용자가 "정합성·추적성을 일시적으로 파괴하더라도 진행, 이후 custom-sheet 쿼리로 추적성 재구현"을 명시적으로 선택했다. 매우 큰 비가역 변경이므로 **원본 관계형 테이블은 검증 끝나기 전까지 절대 삭제하지 말고 보존**한다.

## 배경 (확인됨)
- `CustomSheetTab`(models.py 529행): `region_key`, `tab_label`, `columns_json`(`[{key,label,type}]`), `rows_json`(`[{col:value}]`), `sort_order`. SQLite `json_extract`/`json_each`로 집계·조인 가능.
- API: `GET/POST /admin/api/custom-sheets`, `PATCH/DELETE /admin/api/custom-sheets/{id}`, `POST .../compute` (tracking_router 1044행~). 서비스 `app/services/sheet_service.py`.
- 이전 대상 엔티티 테이블: `product_test_round`, `product_test_target_unified`, `product_test_environment_unified`, `product_test_case`, `product_test_procedure`, `product_test_run`, `product_test_result`, `product_test_procedure_result`, `product_test_defect`, `product_test_evidence`, `product_test_status_transition`, `work_calendar`. (인프라 테이블 `project/user_account/project_membership/custom_sheet_tab/ui_state_pref/form_submission`은 제외.)

## ⚠️ 절대 안전 규칙
1. **DB 변경 = dry-run → 사용자 승인 → 백업(`data/backups/`) → 한 트랜잭션 apply.** 승인 없이 apply 금지.
2. **원본 관계형 테이블 보존.** custom-sheet로 복제 이전만 하고, 원본은 Phase 4 검증 통과 + 별도 승인 전까지 DROP 금지(롤백·검증 소스).
3. **NULL 바이트 고질병**: 편집 직후 trailing NULL 제거 → py_compile/`node --check` → `tail` 확인.
4. 한 번에 한 엔티티/단계. 매 단계 검증·커밋. 모호하면 멈추고 질문.

## Phase 0 — 설계 + 복원점
- 풀 백업 + git 커밋/태그로 복원점 생성.
- **시트 매핑 설계**(엔티티→탭, `columns_json`=해당 모델 컬럼(FK 컬럼도 **값으로** 보존해 관계 단서 유지), 타입 매핑, region/sort 배치)를 **짧게 제시 → 사용자 승인.**

## Phase 1 — 데이터 이전 (dry-run → 승인 → apply)
- 엔티티별로 `custom_sheet_tab` 행 생성: `columns_json`=컬럼 정의, `rows_json`=전체 행(FK 값 포함). 멱등·재실행 안전.
- dry-run: 엔티티별 행 수, 생성될 탭/컬럼, 누락/타입이슈 보고 → 승인 → 백업 → 한 트랜잭션 apply.
- **원본 테이블은 그대로 둔다.**

## Phase 2 — 쿼리 기반 추적성 재구현
- custom-sheet JSON 위에서 `json_extract`/`json_each`로 추적 체인 재구현: result→run→round, result→case, procedure→case, defect→result(+retest), round→run 집계.
- Round Timeline·trace 화면이 쓰던 읽기 로직을 custom-sheet 쿼리로 대체하는 헬퍼/서비스 작성.
- **검증**: 같은 추적 결과가 (아직 살아있는) 원본 관계형 쿼리와 **동일함을 비교**(행수·샘플 대조). 불일치 시 멈추고 보고.

## Phase 3 — UI 전환
- 엔티티 표/탭을 custom-sheet 데이터 기반 렌더·편집으로 전환(custom-sheet PATCH 자동저장 또는 기존 경로 재사용). in-cell 편집·Ctrl+H 전역치환·Trace 인페이지 탭 등 기존 기능 보존.

## Phase 4 — 검증 후 정리 (별도 승인)
- 행수 일치, 추적성 쿼리 결과가 원본과 동일함을 **입증한 뒤에만**, 원본 관계형 테이블 폐기 여부를 사용자에게 별도 승인받아 진행. 그 전까지 보존.

## 검증 (각 단계)
- `uv run pytest tests/ -q` green(정책 변경에 맞게 테스트 갱신), 앱 부팅 `GET /admin` 200.
- Phase별 산출물 JSON(이전 결과·대조 결과)을 `docs/`에 남김.
- 편집 파일 NULL 0 + py_compile/node --check.

## 시작
Phase 0 설계(시트 매핑)부터 짧게 제시 → 사용자 승인 → Phase 1 dry-run. 원본 테이블 보존, 단계별 승인·검증, 애매하면 질문.
