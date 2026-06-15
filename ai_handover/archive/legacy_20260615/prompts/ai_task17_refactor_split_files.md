너는 이 저장소(`product_test_tracing_system`, FastAPI+SQLite, Windows)의 **거대 단일 파일을 기능/모듈 단위로 분할**하는 리팩토링을 한다. 목적은 AI 편집 시 불특정 줄에서 잘리는(torn-write) 사고를 줄이는 것. **동작은 100% 보존. DB 스키마/데이터 변경 없음. 순수 구조 리팩토링.**

## 배경 / 규칙
- `ai_handover/README.md` 공통규칙 6번: 파일은 함수/모듈 단위로 작게(py/js ≈400줄, 템플릿/css ≈500줄 초과 시 분할 후보).
- 분할 후 반드시 `py_compile`/`node --check` + 앱 부팅(`GET /admin` 200) + `uv run pytest tests/ -q` green 으로 **동작 보존 검증**.

## 대상 (큰 것부터, HEAD 기준 줄 수)
1. `app/services/product_test_run_service.py` (4846)
2. `app/static/js/tracking.js` (3130)
3. `app/templates/admin_dashboard.html` (2015)
4. `app/static/js/app.js` (1919)
5. `app/routers/tracking_router.py` (1448)
6. `app/static/css/app.css` (1253), `app/static/css/tracking.css` (1218)
7. `app/routers/admin_router.py` (1011)

## 분할 전략 (파일 종류별)
- **Python(서비스/라우터)**: 해당 모듈을 **패키지로** 전환. 예: `product_test_run_service.py` → `product_test_run_service/` 패키지(`__init__.py`가 공개 심볼 재export), 관심사별 서브모듈(`queries.py`, `mutations.py`, `exports.py`, `trace.py`, `rounds.py` 등)로 함수 이동. **외부 import 경로(`from app.services.product_test_run_service import X`)가 깨지지 않게** `__init__.py`에서 동일 이름 re-export. 라우터도 동일 원칙(엔드포인트 그룹별 서브라우터 분리 후 `include_router`).
- **JS**: 현재 `base.html`에서 `<script>`로 로드. 기능 그룹별 파일로 분리(예: `tracking.js` → `tracking-core.js`, `tracking-tabs.js`, `tracking-render.js`(이미 있음)…). **전역 변수/초기화 계약과 로드 순서 보존**(base.html script 순서 정확히). 전역 노출 심볼 동일 유지.
- **HTML 템플릿**: `{% include %}` 파셜/매크로로 섹션 분리(예: `admin_dashboard.html` → 탭 영역별 `_partials/`). 렌더 결과 바이트가 동일하도록(공백 포함 주의).
- **CSS**: 영역별 파일로 분리 후 base.html에서 순서대로 로드(cascade 순서 보존).

## ⚠️ 절대 규칙
1. **한 번에 한 파일만.** 한 대상 분할 → 검증(py_compile/node --check + 앱부팅 + pytest green) → **커밋** → 다음. 절대 여러 거대 파일 동시 변경 금지.
2. **NULL 바이트 고질병**: 편집 직후 `python -c "p=r'<file>';open(p,'wb').write(open(p,'rb').read().rstrip(b'\x00'))"` → 컴파일 체크 → `tail` 끝줄 확인. 분할 중 각 새 파일도 동일 검증.
3. **동작/공개 API 불변**: import 경로·전역 심볼·라우트 경로·렌더 출력·CSS cascade 모두 보존. 리네임/시그니처 변경 금지(순수 이동).
4. DB 변경 금지. 기능 추가 금지(순수 분할만). 모호하면 멈추고 질문.

## 진행 순서 (점진)
- 가장 위험하고 큰 `product_test_run_service.py`부터 하되, **먼저 분할 설계(서브모듈 경계 + 이동할 함수 목록)를 1줄~짧게 제시하고 사용자 확인** 후 실행. 이후 tracking.js → admin_dashboard.html → app.js → 라우터 → css 순.
- 각 단계: 분할 → 검증 → 커밋(`refactor: split <file> into modules (no behavior change)`).

## 검증 (각 파일 분할 후)
- `uv run pytest tests/ -q` 전체 green (회귀 0).
- 앱 부팅 `GET /admin` 200, 주요 화면(대시보드/탭/trace/in-cell 편집) 동작 동일.
- import/전역/라우트/렌더 출력 변화 없음. 새/수정 파일 NULL 0 + py_compile/node --check.

## 시작
`product_test_run_service.py` 서브모듈 경계 설계를 짧게 제시 → 사용자 확인 → 분할·검증·커밋. 한 번에 한 파일, 동작 보존, 애매하면 질문.
