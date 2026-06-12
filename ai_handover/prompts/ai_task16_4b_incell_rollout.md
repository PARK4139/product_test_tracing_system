너는 이 저장소(`product_test_tracing_system`, FastAPI+SQLite, Windows)의 in-cell 편집을 **나머지 admin 데이터 표 전체로 롤아웃**한다. Phase A(레퍼런스)는 이미 끝났고, 이제 같은 패턴을 남은 탭/표에 동일 적용한다. **코드(템플릿/JS/CSS/라우트)만. DB 스키마/데이터 변경 없음.**

## 기준 = 이미 완성된 Phase A 패턴 (그대로 재사용)
- `app/static/js/admin-incell-edit.js` — 셀 클릭 편집, Enter/blur 저장, Esc 취소, "+ 행 추가" 인라인 생성. **이걸 공통 모듈로 재사용/일반화한다.**
- `app/templates/product_test_cases_admin.html` — 별도 Create form 제거, 목록을 in-cell 편집 + "+ 행 추가" 단일 테이블로 구성한 **레퍼런스 구현**.
- 저장 경로: 기존 행 수정 = `POST /admin/api/product-test/fields/bulk-update`, 신규 = 각 엔티티 `/create` POST.

## 할 일 — 위 패턴을 아래 표/탭에 동일 적용
별도 "등록 / Create" 입력폼/입력 테이블을 **제거**하고, 목록 표를 **in-cell 편집 + "+ 행 추가"** 단일 표로 바꾼다. 사용자 화면에서 입력 전용 테이블이 남으면 안 된다.
1. `app/templates/product_test_procedures_admin.html` (Procedures) — 단, `procedure_action`은 16-2의 모달 편집(축약 1,2,3 + 모달) 유지하면서 나머지 셀은 in-cell.
2. `app/templates/product_test_targets_admin.html` (Targets)
3. `app/templates/product_test_reports_admin.html` (Reports)
4. `app/templates/product_test_environments_admin.html` (Environments)
5. `app/templates/test_config_admin.html` (Configs)
6. **근무 캘린더** 탭 — 해당 렌더링 위치/데이터를 찾아 적용. 단 표준 엔티티 CRUD 표가 아니면(달력 위젯 등 특수 UI) **멈추고 사용자에게 확인.**
7. admin 대시보드 탭들 중 아직 입력 테이블을 쓰는 곳이 있으면 동일 전환.

## ⚠️ 절대 규칙
1. **NULL 바이트 고질병**: 파일 편집 직후 `python -c "p=r'<file>';open(p,'wb').write(open(p,'rb').read().rstrip(b'\x00'))"` → py_compile/`node --check` → `tail` 끝줄 확인.
2. DB 스키마/데이터 변경 금지. 저장은 기존 bulk-update(수정)/`/create`(생성) 재사용.
3. **Trace는 새 페이지 금지 — 현재 페이지 탭 안에서.**
4. 표마다 하나씩 적용·검증하고, 공통 로직은 `admin-incell-edit.js`로 일반화해 중복 최소화. 애매하면 멈추고 질문. 15-x·16-2 마이그레이션 재실행 금지.

## 검증 (각 표)
- 해당 `/admin/...` 200, 대시보드 탭 정상.
- 기존 행: 셀 클릭/F2 → 편집 → 저장 시 DB 반영, 새로고침 후 유지.
- 신규: "+ 행 추가" → 빈 행 → 입력 → 저장 시 `/create` 생성, 목록 반영.
- 별도 "등록 / Create" 입력폼/입력 테이블 **없음**(인라인 대체).
- `uv run pytest tests/ -q` 전체 green, 편집 파일 NULL 0 + py_compile/node --check.

## 시작
Phase A 패턴 확인 1줄 → 표 하나씩(Procedures부터) 전환·검증. 근무 캘린더가 특수 UI면 멈추고 질문. Trace는 인페이지 탭, DB는 읽기/기존경로만.
