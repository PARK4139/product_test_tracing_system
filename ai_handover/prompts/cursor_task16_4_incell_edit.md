너는 이 저장소(`product_test_tracing_system`, FastAPI+SQLite, Windows)의 admin 데이터 표 편집 방식을 **셀 직접(in-cell) 편집으로 통일**한다. 별도 입력 테이블/등록폼이 아니라 셀 안에서 바로 편집하고, 신규 행은 "+"로 인라인 추가한다. **이 작업은 코드(템플릿/JS/라우트)만. DB 스키마/데이터 변경 없음.**

## 먼저 읽어라
1. `app/static/js/table-cell-f2-edit.js` — 기존 셀 선택+F2 멀티편집, 저장 `POST /admin/api/product-test/fields/bulk-update`.
2. `app/routers/admin_router.py` — `bulk-update`(332행, **수정 전용**), 각 엔티티 `/create` POST 핸들러(case 등록 등).
3. `app/services/product_test_field_update_service.py` — `bulk_update_product_test_fields`(416행).
4. `app/static/js/tracking.js` 2116행~ — "+" 커스텀 탭 생성 UX(버튼 모양/동작 참고용. 단 그건 custom-sheets 시스템이고 엔티티 표와는 별개).
5. `ai_handover/handover_main.md` §0-1 수칙.

## 현재 상태 (확인됨)
- admin CRUD 표는 "**등록 / Create** 입력폼" + "**목록 / List** (plain 텍스트, 편집 불가)" 2단 구조다. 대상 템플릿:
  - `product_test_cases_admin.html`
  - `product_test_procedures_admin.html`
  - `product_test_environments_admin.html`
  - `product_test_targets_admin.html`
  - `product_test_reports_admin.html`
  - (+ admin 대시보드 시트형 탭들: rounds/runs/reports 등)
- `bulk-update`는 **기존 행 필드 수정만** 한다(신규 생성 아님). 신규 생성은 엔티티별 `/create` POST가 따로 있다.

## 목표 동작
1. **기존 행 = 셀에서 바로 편집**: 목록 표의 데이터 셀을 편집 가능하게(F2/클릭 → 인라인 편집 → blur/Enter 저장). 기존 `table-cell-f2-edit.js` + `bulk-update` 인프라 재사용. 별도 입력행 테이블 만들지 말 것.
2. **신규 행 = "+" 인라인 추가**: 기존 "+" 탭추가 버튼과 **UI 일관**되게, 표에 "+ 행 추가" affordance를 둔다. 누르면 **빈 편집행**이 표에 생기고, 셀을 채워 저장하면 해당 엔티티 `/create`로 생성된다. 별도 "등록 / Create" 폼 섹션은 제거.
3. PK/필수값 검증, 상태(select)·badge 셀은 기존 패턴 유지. 저장 실패 시 행 강조+메시지.
4. **Trace는 새 페이지 금지 — 현재 페이지 탭 안에서**(이 프로젝트 표준). 표에 Trace가 있으면 인페이지 탭 로드.

## 진행 방식 (중요 — 한 번에 다 하지 말 것)
- **A. 레퍼런스 먼저**: `product_test_cases_admin.html` 한 표에 위 동작(셀편집 + "+"인라인생성, 등록폼 제거)을 **완성**한다. 재사용 가능한 JS/매크로로 만든다.
- **B. 롤아웃**: 검증 후 동일 패턴을 procedures/environments/targets/reports + 대시보드 탭에 **동일하게** 적용.
- 각 단계마다 멈춰 검증. 매크로/JS 공통화로 중복 최소화. 애매하면 멈추고 질문.

## ⚠️ 절대 규칙
1. **NULL 바이트 고질병**: 편집 직후 `python -c "p=r'<file>';open(p,'wb').write(open(p,'rb').read().rstrip(b'\x00'))"` → py_compile/`node --check` → `tail` 끝줄 확인.
2. DB 스키마/데이터 변경 금지. 저장은 기존 bulk-update(수정)·/create(생성) 경로 재사용.
3. 기존 F2/선택/드래그/탭 동작과 충돌 없게. 모호하면 멈추고 질문. 15-x·16-2 마이그레이션 재실행 금지.

## 검증 (각 표)
- `GET /admin` 및 각 `/admin/product-test-*` 200.
- 기존 행: 셀 클릭/F2 → 편집 → 저장 시 DB 반영(bulk-update). 새로고침 후 유지.
- 신규: "+" → 빈 행 → 입력 → 저장 시 `/create`로 생성, 목록에 반영.
- 별도 "등록 / Create" 폼 섹션 없음(인라인으로 대체).
- `uv run pytest tests/ -q` 전체 green(필요 시 회귀 테스트 갱신/추가).
- 편집 파일 NULL 0 + py_compile/node --check.

## 시작
구조 확인 1줄 → **A(case 레퍼런스)부터**. 완성·검증 후 B 롤아웃. Trace는 인페이지 탭. DB는 읽기/기존경로만.
