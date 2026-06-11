너는 이 저장소(`product_test_tracing_system`, FastAPI+SQLite, Windows)의 admin 대시보드에 **Runs 테이블 탭**을 추가한다. (이후 Round Timeline 시각화의 토대가 된다.) **DB 스키마/데이터는 건드리지 않는다. 코드만.**

## 먼저 읽어라
1. `app/models.py` — `ProductTestRun`(267행~).
2. `app/services/product_test_run_service.py` — `list_product_test_rounds`(726행, 패턴 참고용), `_list_rows_as_dicts`.
3. `app/routers/admin_router.py` — admin 대시보드 컨텍스트 구성(134행 `round_rows` 부근), run trace 라우트(911행 `/admin/product-test-runs/{id}/trace`).
4. `app/templates/admin_dashboard.html` — 탭 영역(`admin_tab_region_body[data-admin-tab-region=...]`)과 탭화 패턴: 영역 안 `<section class="card" data-admin-tab-label="라벨">…</section>` 가 탭이 됨(예: "시험 추적" 탭).

## 현재 상태 (확인됨)
- **admin용 run 목록 서비스가 없다.** `round_rows`만 있고 `run_rows`는 admin 대시보드에 안 들어온다.
- `ProductTestRun` 컬럼: `product_test_run_id`(PK), `test_round_id`(FK→round), `product_test_target_id`(FK), `product_test_environment_id`(FK), `product_test_run_status`, `started_at`, `started_by`, `finished_at`, `cancelled_at/by`, `cancel_reason`, `created_at/by`, `updated_at/by`, `remark`.
- run trace 라우트 존재: `/admin/product-test-runs/{product_test_run_id}/trace`.
- 같은 시기에 별도 작업으로 **Test Round 탭**(`cursor_task16_1_test_round_tab.md`)을 같은 Tab View 영역에 넣는다. Runs 탭은 그 옆 탭으로 둔다(같은 영역, 다른 탭).

## ⚠️ 절대 규칙
1. **NULL 바이트 고질병**: 편집 직후 `python -c "p=r'<file>';open(p,'wb').write(open(p,'rb').read().rstrip(b'\x00'))"` → py_compile / `node --check` → `tail` 끝줄 확인.
2. **DB 스키마/데이터 변경 금지.** 코드만. 새 조회 함수는 읽기 전용.
3. 모호하면 멈추고 질문. 임의 삭제/병합 금지. 15-x 마이그레이션 재실행 금지.

## 할 일
1. **서비스 추가**: `product_test_run_service.py`에 `list_product_test_runs(database_session) -> list[dict]` 신설. `list_product_test_rounds`와 동일 패턴(`_list_rows_as_dicts`, model=`ProductTestRun`). 컬럼: `product_test_run_id`, `test_round_id`, `product_test_target_id`, `product_test_environment_id`, `product_test_run_status`, `started_at`, `finished_at`, `remark`. 정렬: `test_round_id` 후 `started_at`(또는 run_id).
2. **컨텍스트 주입**: `admin_router.py` 대시보드 핸들러(134행 `round_rows` 옆)에 `"run_rows": list_product_test_runs(database_session)` 추가, import 정리.
3. **탭 추가**: `admin_dashboard.html`의 Tab View 영역(Test Round 탭과 같은 `admin_tab_region_body`)에 `<section class="card" data-admin-tab-label="Runs">…</section>` 신설. 안에 읽기전용 테이블:
   - 헤더: run_id · Round · Target · Env · Status · Started · Finished · Trace · Remark
   - 본문: `{% for row in run_rows %}` … 각 셀.
   - Status는 기존 `status_badge status-{{ ...|lower }}` 패턴 사용.
4. **Trace는 새 페이지로 가면 절대 안 된다 — 현재 페이지의 탭 안에서 떠야 한다.** Trace 셀/버튼 클릭 시 페이지 이동(`<a href>` navigation) 금지. 대신 run의 trace 내용을 **현재 페이지의 탭/패널로 로드**한다(예: JS로 `/admin/product-test-runs/{id}/trace` 내용을 fetch해 Tab View 안 트레이스 탭에 표시, 또는 인페이지 트레이스 탭 활성화). 기존 trace 라우트는 데이터/프래그먼트 소스로 재사용 가능하나 결과는 탭 안에 표시.
5. 기존 탭 전환·드래그·다른 탭과 충돌 없게. run 데이터 0건이어도 헤더만 깨끗이 보이게.

## 검증
- `uv run python run.py` → `GET /admin` 200.
- 대시보드 Tab View에 **"Runs" 탭** 보이고, run 목록 렌더. Trace 클릭 시 **페이지 이동 없이 현재 페이지 탭 안**에서 트레이스 표시.
- `uv run pytest tests/ -q` 전체 green (필요 시 run 목록 회귀 테스트 1개 추가).
- 편집 파일 NULL 0 + py_compile / node --check.

## 시작
탭 구조 확인 1줄 → 서비스 → 컨텍스트 → 템플릿 탭 순. DB는 읽기만, 스키마/데이터 변경 금지.
