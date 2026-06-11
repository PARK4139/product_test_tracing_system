너는 이 저장소(`product_test_tracing_system`, FastAPI+SQLite, Windows)의 **admin 대시보드 UI 작업**을 한다. Test Round를 독립 섹션에서 기존 Tab View 탭으로 옮긴다. **DB 스키마/데이터는 건드리지 않는다. 코드(템플릿/JS)만.**

## 먼저 읽어라
1. `app/templates/admin_dashboard.html` — 대시보드 본체(약 1991줄).
2. `app/static/js/tracking.js` — 탭 영역 로직(`admin_tab_region`, `data-admin-tab-region`, `data-admin-tab-label`, 탭 변환/드래그).
3. `ai_handover/handover_main.md` §0-1 실수 방지 수칙.

## 현재 구조 (확인됨)
- **Test Round는 독립 `<section>`** 이다: `admin_dashboard.html` 113행 부근, `<h3>Test Round</h3>` + "Trace 보기" 버튼 + 읽기전용 테이블(`{% for row in round_rows %}` … `test_round_id/test_round_name/workday/start_date/end_date/migration_status/Trace`). 즉 탭이 아니라 카드 섹션으로 떠 있다.
- **Tab View 영역들**: `admin_tab_region_shell` + `admin_tab_region_body[data-admin-tab-region=...]`
  - Tab View 2 = `#admin_tab_region_primary` (primary)
  - Tab View 3 = `#admin_tab_region_secondary` (secondary)
  - Tab View 4 = `#admin_tab_region_quaternary` (quaternary)
- **탭화 패턴(정본)**: tab region body 안에 `<section class="card" data-admin-tab-label="라벨">…</section>` 를 넣으면 그 섹션이 "라벨" 탭이 된다. 예: 321행 `<section class="card" data-admin-tab-label="시험 추적">` 가 Tab View 4의 탭.

## 할 일
1. 현재 독립 Test Round 섹션 전체(헤더+가이드+테이블, 113행 부근 `<section>…</section>`)를 **잘라낸다(독립 섹션 제거).**
2. 그것을 **Tab View 2(`#admin_tab_region_primary`)의 `admin_tab_region_body` 안에** `<section class="card" data-admin-tab-label="Test Round">…</section>` 형태로 넣어, 그 영역의 다른 탭들과 동일한 패턴으로 **"Test Round" 탭**이 되게 한다.
   - (Tab View 2가 부적절하면 3/4 중 적절한 곳에. 단 한 곳에만. 어디 둘지 애매하면 멈추고 사용자에게 1줄로 확인.)
3. 기능 보존: `round_rows` 렌더, 읽기전용 테이블 그대로. 그 영역 탭 전환·드래그 동작과 충돌 없게.
   - ⚠️ **Trace는 새 페이지로 가면 절대 안 된다 — 현재 페이지의 탭 안에서 떠야 한다.** 기존 "Trace 보기"/행별 Trace가 `/admin/product-test-trace`·`/admin/product-test-rounds/{id}/trace`로 **페이지 이동**한다면, 이를 **인페이지 탭 로드 방식으로 전환**한다(JS로 trace 내용을 fetch해 Tab View 안 트레이스 탭에 표시). 기존 라우트는 데이터/프래그먼트 소스로 재사용 가능하나 결과는 탭 안에 표시.
4. 중복 제거: 옮긴 뒤 Test Round가 두 곳에 나오지 않게(원래 섹션은 완전히 제거).

## ⚠️ 절대 규칙
1. **NULL 바이트 고질병**: 편집 직후 `python -c "p=r'<file>';open(p,'wb').write(open(p,'rb').read().rstrip(b'\x00'))"` → 끝줄 `tail` 확인. JS는 `node --check`.
2. DB 스키마/데이터 변경 금지. 라우트/데이터 소스(`round_rows`) 변경 금지 — 위치만 옮긴다.
3. 모호하면 멈추고 질문. 임의 삭제/병합 금지.

## 검증
- `uv run python run.py` → `GET /admin` 200.
- 대시보드에서 Tab View 2(또는 선택한 영역)에 **"Test Round" 탭**이 보이고, round 목록 정상 렌더. Trace는 **페이지 이동 없이 현재 페이지 탭 안**에서 표시.
- 독립 Test Round 섹션은 더 이상 없음(중복 0).
- `uv run pytest tests/ -q` 전체 green 유지.
- 편집 파일 NULL 0 + (해당 시) `node --check` 통과.

## 시작
admin_dashboard 탭 구조 확인 1줄 → Test Round 섹션을 Tab View 2 탭으로 이동. 위치 애매하면 사용자에게 어느 Tab View인지 확인 후 진행.
