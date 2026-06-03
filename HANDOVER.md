# Handover — 제품 시험 추적 시스템 (2026-06-03)

## 프로젝트 개요

- **위치**: `C:\Users\USER\Downloads\product_test_tracing_system`
- **기술스택**: FastAPI + SQLite + Jinja2, 프런트엔드 순수 JS (모듈화됨)
- **실행**: `run.cmd` (Windows에서 직접 실행, venv는 Windows 전용이라 sandbox에서 실행 불가)
- **포트**: 8008 (또는 8000)
- **DB**: `data/product_test_tracking_system.db` (WAL 모드)
- **로그**: `data/logs/app.log`
- **백업**: `data/product_test_tracking_system.backup_20260603_121153.db` (구성 재편 직전 스냅샷)

---

## 데이터 계층 구조 (2026-06-03 현재)

### 구성(Topology) 기반 구조

2026-06-03에 장비 중심에서 **시험 구성(topology) 중심**으로 전환 완료.

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
- 예: `25AP_1HDR_1HDC` = AP 25대 + HDR 1대 + HDC 1대

### 변경 이전 구조 (참고용)

```
시험 라운드 (WIFI_1ST)
  └─ 장비행 (WIFI_1ST-HRK_9000A_1_1_1A)   ← 모든 result가 HRK에 몰려있었음
       └─ RC 릴리즈 (HRK_9000A_1_1_1A-RC1)
```

**변경 이유**: 1개 Run에 5개 장비(HRK/HTR/HLM/HDR/HDC) 결과가 혼재되어 있었고, 모든 result가 HRK release에만 연결되어 HDR/HLM/HTR/HDC 장비행은 result=0이었음. 결함 하이라이트도 실제 시험 구성과 무관하게 HRK로만 연결됨.

### 마이그레이션 결과

| 항목 | 전 | 후 |
|---|---|---|
| result | 375 | 375 (전량 보존) |
| defect | 15 | 15 (경로 무결성 15/15) |
| release | 40 | 78 (+26 topology, +30 RC, -18 old) |
| run | 9 | 37 (+34 new, -6 old empty) |
| 구성 수 | 5 (장비행) | 26 (topology행) |

마이그레이션 스크립트: `scripts/migrate_topology_restructure.py`

### 미분류 result 4건

testing(시험 미완료) 상태로 원래 위치 유지:
- TBD 2건 (case/combo 미정)
- `25AP_` 1건 (장비 미입력)
- `VARIOUS_CONNECTIONS` 1건 (20AP 스모크 테스트)

---

## 현재 구성별 분포

### WIFI_1ST (1차 시험)

| 구성 | status | result 수 |
|---|---|---|
| 1AP_1HRK_4HDR | BLOCKED | 44 |
| 1AP_1HRK_1HDR | PASSED | 43 |
| 1AP_4HDR_1HDC | BLOCKED | 30 |
| 1AP_1HDR_1HDC | BLOCKED | 29 |
| 1AP_1HTR_2HDR | BLOCKED | 26 |
| 1AP_1HTR_1HDR | PASSED | 24 |
| 1AP_2HDR | PASSED | 23 |
| 1AP_1HLM_4HDR | BLOCKED | 20 |
| 1AP_1HLM_1HDR | PASSED | 19 |
| 1AP_1HDC | PASSED | 13 |
| 1AP_1HRK | PASSED | 6 |
| 1AP_4HDR | BLOCKED | 5 |
| 1AP_1HLM | PASSED | 4 |
| 1AP_1HTR | PASSED | 4 |
| 1AP_1HRK_1HTR_1HLM_4HDR | BLOCKED | 4 |
| 1AP_1HDR | PASSED | 2 |
| 1AP_4HDR_1HIIS | TESTING | 1 |

### WIFI_2ND (2차 시험)

| 구성 | status | result 수 |
|---|---|---|
| 25AP_1HDR_1HDC | BLOCKED | 22 |
| 25AP_1HRK_1HDR | BLOCKED | 13 |
| 25AP_1HTR_1HDR | BLOCKED | 13 |
| 25AP_1HLM_1HDR | BLOCKED | 13 |
| 25AP_1HDR | BLOCKED | 6 |
| 25AP_1HTR | BLOCKED | 2 |
| 25AP_1HRK | BLOCKED | 1 |
| 25AP_1HLM | BLOCKED | 1 |

### 기타 라운드

| 라운드 | 구성 | result 수 |
|---|---|---|
| WIFI_1_1_1D | 1AP_1HRK_3HDR | 3 |
| WIFI_DOWNGRADE | (미분류, 1건) | 1 |

---

## 이번 세션에서 완료한 작업 (2026-06-03)

### 1. 구성(Topology) 기반 Release 구조 재편

- `scripts/migrate_topology_restructure.py` 작성 및 실행
- 375건 result를 26개 구성별로 재분배
- release status를 result 집계 기반으로 자동 보정 (blocked > 0 → BLOCKED)
- 기존 장비행/RC/Run 삭제, 새 구성행/RC/Run 생성

### 2. 하이라이트 버그 수정

**`tracking-highlight.js`**:
- 결함 클릭 시 간트 구성행을 `hl-blocked`(빨간색)으로 하이라이트
- 부모 라운드행 하이라이트 제거 (결함이 속한 구성행만 강조)

**`tracking_router.py`** — `resolve_parent_release` 개선:
- 기존: if/else 양쪽 동일 값 반환 (dead code)
- 수정: `release_visible` 맵을 활용하여 visible=1인 구성행을 정확히 탐색

### 3. 문제 분석 완료

- **Run→Release 1:1 매핑 문제**: 1개 Run에 5개 장비 결과 혼재 → 구성별 분리로 해결
- **Release status 불일치**: RC가 PASSED인데 opened defect 있음 → result 집계 기반 자동 보정
- **Test Scenarios 시트**: DB에 별도 테이블 없음, case remark에 텍스트로 보존 (53/60건)

---

## 연관 데이터 하이라이트 — 현재 상태와 목표

### 현재 구현 (간트 ↔ 결함 2영역)

| 클릭 대상 | 동작 |
|---|---|
| 간트 라운드행 | 자식 구성행 + 연결된 결함 행 하이라이트 |
| 간트 구성행 | 해당 구성의 결함 행 하이라이트 |
| 결함 행 | 해당 구성행 하이라이트 (빨간색) |

### 구현 위치

| 파일 | 역할 |
|---|---|
| `app/static/js/tracking-highlight.js` | 하이라이트 이벤트 바인딩 전체 로직 |
| `app/static/js/tracking-gantt-chart.js` | 간트 행 렌더링 (`data-row-id`, `data-parent-id`) |
| `app/static/js/tracking-render.js` | 결함 행 렌더링 (`data-parent-release-id`) |
| `app/routers/tracking_router.py` | `resolve_parent_release` — RC → 구성행 ID 반환 |

### 핵심 데이터 속성 (구성 기반)

```html
<!-- 간트 구성행 -->
<div class="gantt_row gantt_row_child"
     data-row-id="TEST_RELEASE-WIFI_1ST-1AP_1HRK_4HDR"
     data-parent-id="TEST_RELEASE-WIFI_1ST"
     data-status="BLOCKED">

<!-- 결함 행 -->
<tr data-release-id="TEST_RELEASE-WIFI_1ST-1AP_1HRK_4HDR-RC2"
    data-parent-release-id="TEST_RELEASE-WIFI_1ST-1AP_1HRK_4HDR">
```

`data-parent-release-id` = RC의 upstream (visible=1인 구성행 ID)

### 궁극적 목표: 전체 테이블 연쇄 하이라이트

결함 하나를 클릭하면 관련된 **모든 데이터가 연쇄적으로 하이라이트**:

```
결함 클릭
  → 간트 구성행 하이라이트
  → 해당 Run 하이라이트          ← 미구현 (테이블 없음)
  → 해당 Result 하이라이트       ← 미구현 (테이블 없음)
  → 해당 Case/Procedure 하이라이트 ← 미구현
  → 해당 Evidence 하이라이트     ← 미구현 (데이터 없음)
```

---

## 다음 작업 계획 (순서대로)

### A. docs 업데이트

`docs/feature_related_data_highlight.md` 갱신:
- "장비행" → "구성행" 용어 전환
- 구성 기반 data 속성 예시 반영
- 전체 테이블 연쇄 하이라이트 목표 아키텍처 추가

### B. API 확장 (`tracking_router.py`)

`/admin/api/tracking` 응답에 추가:
```python
{
    "releases": [...],
    "active_defects": [...],
    "runs": [...],              # 신규: 구성별 Run 목록
    "results_summary": [...],   # 신규: 구성별 result 집계 (pass/block/test)
}
```

### C. Run/Result 요약 테이블 UI 렌더링

`tracking-render.js`에 추가:
- Run 테이블: run_id, 구성, status, 시작/종료
- Result 요약 테이블: case별 pass/block/test 집계

### D. 연쇄 하이라이트 로직 구현

`tracking-highlight.js` 확장:
- 결함 → Result → Run → 구성행 연쇄 하이라이트
- 구성행 → Run → Result → Defect 역방향 하이라이트
- 각 테이블 행에 `data-*` 속성 연결 키 부여

### E. procedure_result/evidence 연동 (운영 데이터 축적 후)

현재 `product_test_procedure_result`=0건, `product_test_evidence`=0건.
운영 중 데이터가 쌓이면 하이라이트 연동 추가.

### F. Test Scenarios 테이블 마이그레이션 (선택)

`product_test_scenario` 테이블 DDL 추가 + 엑셀 81건 삽입.
현재 case remark에 텍스트로 보존되어 있어 급하지 않음.

---

## JS 모듈 구조

| 파일 | 내용 | 줄수 |
|---|---|---|
| `tracking-client-log.js` | `window.clientLog()` 유틸 | 11 |
| `tracking-helpers.js` | badge, date 유틸 | 84 |
| `tracking-gantt-chart.js` | buildGantt (바 렌더링) | 162 |
| `tracking-gantt-resize.js` | 컬럼 리사이즈 + 데드라인 드래그 | 69 |
| `tracking-gantt-fold.js` | 간트 접기/펼치기 | 24 |
| `tracking-col-drag.js` | 컬럼 드래그&드롭 순서 저장 | 57 |
| `tracking-status.js` | 상태 드롭다운 + 통계 클릭 | 78 |
| `tracking-highlight.js` | 간트↔결함 하이라이트 연동 | 81 |
| `tracking-defect.js` | 결함 이미지 팝업, 컬럼 리사이즈 | 74 |
| `tracking-render.js` | renderTracking (HTML 빌더) | 128 |
| `tracking.js` | loadTracking + init | 66 |

---

## DB 현재 상태

| 항목 | 값 |
|---|---|
| 전체 릴리즈 | 78건 |
| visible=1 (간트 표시) | 37건 (라운드 + 구성행 + 보고서 컨테이너) |
| visible=0 (RC, 간트 숨김) | 30건 (구성별 RC) |
| 미결 결함 | 15건 (전부 opened) |
| result | 375건 (26개 구성에 분배) |
| run | 37건 (34개 구성별 + 3개 TBD) |

### DB 테이블별 마이그레이션 데이터 현황

| 테이블 | 건수 | 비고 |
|---|---|---|
| product_test_result | 375 | 엑셀 전량 마이그레이션, 구성별 재배치 완료 |
| product_test_defect | 15 | opened만 (엑셀 이슈ID 기반) |
| product_test_case | 60 | 55 unique + 5 skeleton/placeholder |
| product_test_procedure | 171 | case별 step |
| product_test_procedure_result | 0 | 운영 시 축적 |
| product_test_evidence | 0 | 운영 시 축적 |
| product_test_status_transition | 0 | 운영 시 축적 |
| product_test_scenario | 없음 | 테이블 미생성 (case remark에 보존) |

### created_by 별 release 분포

| created_by | 건수 | 내용 |
|---|---|---|
| topology_restructure_v1 | 56 | 구성행 26 + RC 30 |
| restructure | 10 | 라운드 등 기존 구조 (보존됨) |
| migration | 3 | 기존 (보존됨) |
| migration_script_v1 | 9 | 보고서 컨테이너 등 (보존됨) |

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

---

## DB 수정 주의사항

WAL 파일 문제로 직접 바이너리 쓰기 후 WAL을 truncate해야 함:
```python
conn = sqlite3.connect('/tmp/work.db')  # 복사본에서 작업
# ... 수정 ...
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.commit(); conn.close()

db_path = '...product_test_tracking_system.db'
wal_path = db_path + '-wal'
with open('/tmp/work.db', 'rb') as f: data = f.read()
with open(db_path, 'r+b') as f: f.write(data); f.truncate()
with open(wal_path, 'r+b') as f: f.seek(0); f.truncate(0)
```

---

## 미해결 항목

1. **`calcDateFromPct`의 `minD`/`totalMs` 스코프 문제** — `buildGantt` 내부 변수라 외부에서 접근 불가. 데드라인 드래그 시 날짜 계산 오류 가능성. 전역 변수화 필요
2. **타임라인 라벨 표현 개선** — "배포 이력 타임라인" → 더 적합한 이름 검토
3. **HDR-7100P 장비** — 엑셀에는 있지만 별도 구성으로 분리되지 않음 (HDR 대수에 포함)
4. **WIFI_DOWNGRADE 라운드** — 미분류 result 1건 (VARIOUS_CONNECTIONS, 스모크 테스트)
5. **`feature_related_data_highlight.md`** — 장비행 용어가 아직 구성행으로 갱신되지 않음 (작업 A)
