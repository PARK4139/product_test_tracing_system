# Handover — 제품 시험 추적 시스템 (2026-06-03 세션2)

## 프로젝트 개요

- **위치**: `C:\Users\USER\Downloads\product_test_tracing_system`
- **기술스택**: FastAPI + SQLite + Jinja2, 프런트엔드 순수 JS (모듈화됨)
- **실행**: `run.cmd` (Windows에서 직접 실행, venv는 Windows 전용이라 sandbox에서 실행 불가)
- **포트**: 8008 (또는 8000)
- **DB**: `data/product_test_tracking_system.db` (WAL 모드)
- **로그**: `data/logs/app.log`
- **백업**: `data/product_test_tracking_system.backup_20260603_121153.db` (구성 재편 직전 스냅샷)

---

## 데이터 계층 구조

### 구성(Topology) 기반 구조

```
시험 라운드 (예: WIFI_1ST, upstream=MULTI_PRODUCT, visible=1)
  └─ 구성행 (예: 1AP_1HRK_4HDR, visible=1)        ← 간트차트 자식 행
       └─ RC 릴리즈 (예: RC1, visible=0)            ← 결함이 실제 연결된 레벨
            └─ Run (시험 실행 세션)
                 └─ Result (case-level 결과)
                      └─ Defect (결함)
```

**구성 네이밍 규칙**: `{AP수}AP_{장비수}{장비명}_{장비수}{장비명}_...`
- 장비 순서: HRK > HTR > HLM > HDR > HDC > HIIS
- 예: `1AP_1HRK_4HDR` = AP 1대 + HRK 1대 + HDR 4대 연동 시험
- 모호한 표현(`ALL`, `TARGET` 등) 금지, 항상 장비 명시

### 전체 데이터 연결 체인

```
Release(83)
  ├─ Report(8)              via release_id
  ├─ Run(37)                via release_id
  │   ├─ Target(6)          via target_id → TargetDef(6)
  │   ├─ Environment(6)     via env_id → EnvDef(6)
  │   └─ Result(375)        via run_id
  │       ├─ Case(60)       via case_id → Procedure(171)
  │       ├─ Defect(15)     via result_id
  │       ├─ ProcResult(0)  via result_id
  │       └─ Evidence(0)    via result_id/defect_id
  └─ Snapshot(0)            via release_id
```

---

## 현재 시험 라운드 (12개)

| seq | 라운드 | alias | status |
|---|---|---|---|
| 1 | WIFI_1ST | Wi-Fi Connectivity Test 1차 | BLOCKED |
| 2 | WIFI_1ST_IMPROVE | Wi-Fi Connectivity Test 1차 개선확인 시험 | PASSED |
| 3 | WIFI_2ND | Wi-Fi Connectivity Test 2차 | BLOCKED |
| 4 | WIFI_2ND_IMPROVE | Wi-Fi Connectivity Test 2차 개선확인 시험 | TESTING |
| 5 | WIFI_DOWNGRADE | 5개 제품 Wi-Fi 기능 다운그래이드 비교 시험 | TESTING |
| 6 | WIFI_1_1_1D | HRK-9000A 1.1.1D WIFI 시험 | TESTING |
| 7 | WIFI_1_1_1D_WBS | HRK-9000A 1.1.1D WBS Test Case 시험 | PASSED |
| 8 | HDC_1_0_5A_WBS | HDC-9100 1.0.5A WBS Testcase 시험 | PASSED |
| 9 | HDC_1_0_5A_WIFI | HDC-9100 1.0.5A WIFI시험 | PASSED |
| 10 | HRK_1_1_1A_WBS | HRK-9000A 1.1.1A WBS Testcase 시험 | PASSED |
| 11 | HTR_1_1_8D_WBS | HTR-1A 1.1.8D WBS Testcase 시험 | TESTING |
| 12 | HTR_1_1_8D_WIFI | HTR-1A 1.1.8D WIFI시험 | TESTING |

seq 8~12는 이번 세션에서 신규 추가. 기간 있으면 PASSED, 진행중이면 TESTING.
WIFI_DOWNGRADE, WIFI_1_1_1D는 하위 UNCLASSIFIED(TESTING) 때문에 TESTING으로 보정됨.

---

## 이번 세션에서 완료한 작업 (2026-06-03 세션2)

### 1. 구성(Topology) 기반 Release 구조 재편

- `scripts/migrate_topology_restructure.py` 작성 및 실행
- 375건 result를 26개 구성별로 재분배
- release status를 result 집계 기반으로 자동 보정
- 기존 장비행/RC/Run 전부 삭제, 새 구성행/RC/Run 생성
- 미분류 4건은 각 라운드의 UNCLASSIFIED 구성행으로 이동
- 구 장비행 잔존 3건 추가 삭제 (WIFI_2ND, WIFI_DOWNGRADE, WIFI_1_1_1D)

### 2. docs 업데이트 (작업 A 완료)

- `docs/feature_related_data_highlight.md` — 구성 기반 용어로 전면 갱신
- Phase 1(완료)/Phase 2(미구현) 구분 명시
- 연결 키 흐름, resolve_parent_release 로직 문서화

### 3. API 확장 (작업 B 완료) — `tracking_router.py`

응답에 추가된 필드:
- `runs`: Run별 결과 집계 (total/passed/blocked/testing)
- `results_summary`: Case 단위 결과 집계 + defect_ids
- `procedure_results`: procedure별 실행 결과
- `evidence`: 증빙자료
- `active_defects`에 `run_id` 추가

### 4. UI 구현 (작업 C+D+E 완료)

**화면 순서 (현재):**
```
1. 요약 (미결결함 + 전체Result + 통과율 + 차단 + 시험중)
2. 미결 결함 현황
3. 배포 이력 타임라인 (간트) + 보기모드 버튼
4. Procedure Result (데이터 있을 때만)
5. Evidence (데이터 있을 때만)
```

**제거된 테이블:**
- Run 현황 → 요약에 핵심 숫자 병합
- Result 요약 (Case 단위) → 추적은 별도 페이지에서 가능

**하이라이트 연동:**
- 간트 ↔ 결함 ↔ ProcResult ↔ Evidence 전방위 연동
- 각 행의 실제 상태에 맞는 색상 적용 (PASSED=초록, BLOCKED=빨강, TESTING=파랑)
- 결함 테이블 hover 하이라이트 제거 (클릭만 동작)

### 5. 간트 차트 개선

- **보기모드 3단계**: 전체 / 시험중(TESTING+BLOCKED) / 중단판정(BLOCKED만)
- **보기모드 버튼**: 타임라인 섹션 우측 상단에 배치, 현재 모드 표시
- **자식 필터 보정**: 자식이 필터 통과하면 부모도 자동 포함 (고아 행 방지)
- **상태 읽기 전용**: 모든 간트 행의 상태가 readonly (하위 result 기반 자동 결정)
- **delta 일자 자동 계산**: workday 없어도 start/end 기반 `Nd` 표시
- **스크롤**: 구성행 클릭 시 결함 테이블로 스크롤

### 6. 부모 상태 논리 보정

- WIFI_DOWNGRADE: APPROVED → TESTING (하위 UNCLASSIFIED가 TESTING)
- WIFI_1_1_1D: PASSED → TESTING (하위 UNCLASSIFIED가 TESTING)

### 7. 신규 시험 라운드 5개 추가

- HDC-9100 1.0.5A WBS/WIFI, HRK-9000A 1.1.1A WBS, HTR-1A 1.1.8D WBS/WIFI

### 8. null 바이트 수정

- `admin_dashboard.html`에 trailing null 263바이트 제거

---

## 다음 작업: 전체 테이블 연쇄 하이라이트

### 목표

모든 관련 데이터 테이블이 추적 화면에 표시되고, 어느 행을 클릭하든 관련 데이터가 전부 하이라이트.

### 현재 테이블별 데이터 현황

| 테이블 | 건수 | 연결 키 | 추적 화면 표시 |
|---|---|---|---|
| Release | 83 | release_id | 간트 차트 (구현) |
| Report | 8 | release_id | **미구현** |
| Target Definition | 6 | - | **미구현** |
| Target | 6 | run.target_id | **미구현** |
| Environment Definition | 6 | - | **미구현** |
| Environment | 6 | run.env_id | **미구현** |
| Test Case | 60 | result.case_id | **미구현** |
| Procedure | 171 | case_id | **미구현** |
| Run | 37 | release_id | 요약에 집계만 (테이블 제거됨) |
| Result | 375 | run_id, case_id | 요약에 집계만 (테이블 제거됨) |
| Procedure Result | 0 | result_id | 구현됨 (데이터 없어서 미표시) |
| Evidence | 0 | result_id, defect_id | 구현됨 (데이터 없어서 미표시) |
| Defect | 15 | result_id | 구현됨 |
| Report Snapshot | 0 | release_id | **미구현** |
| Status Transition | 0 | - | **미구현** |

### 구현 순서

| 순서 | 작업 | 내용 |
|---|---|---|
| **1** | API 확장 | `/admin/api/tracking` 응답에 report, target, target_def, env, env_def, case, procedure 추가 |
| **2** | UI 테이블 렌더링 | `tracking-render.js`에 각 테이블 추가 (데이터 있을 때만 표시) |
| **3** | 하이라이트 연동 | 모든 테이블에 `data-parent-release-id` 부여, `hlAllTablesByTopo()` 확장 |
| **4** | 화면 배치 확정 | 섹션 순서 결정 |

### 하이라이트 키 매핑 설계

구성행 클릭 시 연쇄 하이라이트 경로:
```
구성행 (topology release)
  → RC release (hidden, 연결 키)
  → Report: release_id로 매칭
  → Run: release_id로 매칭
  → Target/Env: run.target_id, run.env_id로 매칭
  → Result: run_id로 매칭
  → Case/Procedure: result.case_id로 매칭
  → Defect: result_id로 매칭
  → ProcResult: result_id로 매칭
  → Evidence: result_id/defect_id로 매칭
```

**핵심**: 모든 테이블 행에 `data-parent-release-id` (구성행 ID) 부여 → `hlAllTablesByTopo(topoId)` 하나로 전체 하이라이트.

### 제안 화면 배치

```
1. 요약 (미결결함 + 통과율 + 차단 + 시험중)
2. 미결 결함 현황
3. 배포 이력 타임라인 (간트) + 보기모드
4. Report 현황
5. Target / Environment
6. Case / Procedure
7. Procedure Result (데이터 있을 때)
8. Evidence (데이터 있을 때)
```

---

## 구현 위치

| 파일 | 역할 |
|---|---|
| `app/static/js/tracking-highlight.js` | 전방위 하이라이트 로직 (gantt/defect/proc/evidence) |
| `app/static/js/tracking-gantt-chart.js` | 간트 행 렌더링 + 보기모드 필터 |
| `app/static/js/tracking-render.js` | 전체 HTML 빌더 (요약/결함/간트/proc/evidence) |
| `app/static/js/tracking-helpers.js` | badge/date 유틸 + `extractTopo()` |
| `app/static/js/tracking.js` | loadTracking + init + updateToggleLabel |
| `app/routers/tracking_router.py` | API 응답 (releases/defects/runs/results/proc/evidence) |
| `app/static/css/tracking.css` | 하이라이트 색상, 테이블 스타일 |
| `app/templates/admin_tracking_top.html` | 추적 대시보드 템플릿 (include) |

### 핵심 함수

| 함수 | 파일 | 역할 |
|---|---|---|
| `renderTracking(data)` | tracking-render.js | API 데이터 → HTML 빌드 |
| `buildDefectTable(defects)` | tracking-render.js | 결함 테이블 HTML |
| `buildGantt(releases)` | tracking-gantt-chart.js | 간트 차트 HTML |
| `bindHighlights(root)` | tracking-highlight.js | 클릭 이벤트 바인딩 |
| `hlAllTablesByTopo(topoId)` | tracking-highlight.js | 전 테이블 하이라이트 |
| `hlDefectsByTopoIds(ids)` | tracking-highlight.js | 결함 행 하이라이트 |
| `extractTopo(releaseId)` | tracking-helpers.js | release ID → 구성명 추출 |
| `resolve_parent_release()` | tracking_router.py | RC → 구성행 ID 반환 |

### resolve_parent_release 로직

```
입력: run.product_test_release_id (RC release ID)
출력: 간트에 표시되는 구성행 ID (visible=1인 상위)

경로: RC(visible=0) → 구성행(visible=1) → 라운드(visible=1)
visible=1이면서 부모도 visible=1인 행 = 구성행
```

---

## DB 현재 상태

| 항목 | 값 |
|---|---|
| 전체 릴리즈 | 83건 (라운드 12 + 구성행 29 + RC 30 + 보고서 컨테이너 + UNCLASSIFIED) |
| 미결 결함 | 15건 (전부 opened) |
| result | 375건 (26개 구성 + 3개 UNCLASSIFIED에 분배) |
| run | 37건 |
| 시험 라운드 | 12개 (seq 1~12) |

---

## 파일 편집 규칙 (반드시 준수)

1. **200줄 이상 파일 편집 시 Edit 도구 사용 금지** — python으로 직접 처리
2. **편집 후 항상 null 바이트 제거**:
   ```python
   with open(path, 'rb') as f: c = f.read()
   c = c.rstrip(b'\x00')
   with open(path, 'wb') as f: f.write(c)
   ```
3. **편집 후 항상 문법 검증**: `node -c <파일>`
4. **한글 문자열이 포함된 긴 줄은 영문으로 대체**하거나 python으로 작성
5. **admin_dashboard.html 편집 후 반드시 null 바이트 검사** (과거 trailing null 발생 이력)

---

## 미해결 항목

1. **`calcDateFromPct`의 `minD`/`totalMs` 스코프 문제** — `buildGantt` 내부 변수라 외부에서 접근 불가. 데드라인 드래그 시 날짜 계산 오류 가능성. 전역 변수화 필요
2. **HDR-7100P 장비** — 엑셀에는 있지만 별도 구성으로 분리되지 않음 (HDR 대수에 포함)
3. **UNCLASSIFIED 구성행 3개** — WIFI_2ND, WIFI_DOWNGRADE, WIFI_1_1_1D에 미분류 result 4건. combo 확정 시 적절한 구성으로 이동 필요
4. **Test Scenarios 테이블** — DB에 미생성, case remark에 텍스트로 보존 (53/60건). 별도 테이블 마이그레이션 선택적
