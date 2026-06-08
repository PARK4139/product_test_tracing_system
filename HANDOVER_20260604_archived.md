# Handover — 제품 시험 추적 시스템 (2026-06-03 세션2 · 2026-06-04 갱신)

## 프로젝트 개요

- **위치**: `C:\Users\USER\Downloads\product_test_tracing_system`
- **기술스택**: FastAPI + SQLite + Jinja2, 프런트엔드 순수 JS (모듈화됨)
- **실행**: `run.cmd` (Windows에서 직접 실행, venv는 Windows 전용이라 sandbox에서 실행 불가)
- **포트**: 8008 (또는 8000)
- **DB**: `data/product_test_tracking_system.db` (WAL 모드)
- **로그**: `data/logs/app.log`
- **백업**: `data/product_test_tracking_system.backup_20260603_121153.db` (구성 재편 직전 스냅샷)
- **DB 직접 수정**: 가능 (SQLite 로컬 파일). 대량 변경 시 서버 중지 + 백업 권장.

---

## 2026-06-04 세션 — 진행 현황 요약

### 완료

| 항목 | 내용 |
|------|------|
| Admin 뷰 분석 | `/admin` 통합 대시보드, `tracking_router` API, QC 모드, 자동제출 UX 문서화 |
| 타임라인 요구사항 정리 | 최상위 12 라운드 + 수행 기간(`remark`의 `[Workday]`/`[Start]`/`[End]`) |
| RC1 통일 방향 합의 | 구성(토폴로지)마다 RC1 하나, RC2+ Run은 RC1으로 병합 |
| 스크립트 추가 | `scripts/migrate_excel_rounds_normalize.py` (dry-run 확인, **`--apply` 미실행**) |
| 정합성 작업 순서 합의 | **Test Case → Procedure → Result → Run/Release(타임라인)** (아래부터) |
| Test Case 현황 조사 | DB 60건, ID 접두 8종; Result `[연결구성]`과 Case ID 의미 불일치 확인 |

### 미완료 (다음 담당자)

| 순서 | 작업 | 상태 |
|------|------|------|
| 1 | Test Case ID 재작성 + Procedure/Result FK 갱신 | **설계만**, 스크립트 없음 |
| 2 | ROUTER 토폴로지 정본과 DB `[연결구성]` 매핑 확정 | **질문 4건 답 대기** |
| 3 | `migrate_excel_rounds_normalize.py --apply` | 미실행 |
| 4 | 타임라인 12라운드 화면 검증 | 미실행 |
| 5 | `migrate_device_centric_rounds.py` | **WIFI 최상위 유지 시 실행 금지** |

### 타임라인 최상위 12개 (화면·기획 기준)

엑셀 마이그레이션 후 추적 화면에 나와야 할 **캠페인 라운드**(DB PK는 `TEST_RELEASE-*`, 표시는 `TEST_ROUND-*` 권장):

| # | 표시 라운드 | 설명 |
|---|-------------|------|
| 1 | TEST_ROUND-WIFI_1ST | 5개 제품 |
| 2 | TEST_ROUND-WIFI_1ST_IMPROVE | 결함 제품 개선확인 |
| 3 | TEST_ROUND-WIFI_2ND | 5개 제품 |
| 4 | TEST_ROUND-WIFI_2ND_IMPROVE | 결함 제품 개선확인 |
| 5 | TEST_ROUND-HDC_9100_1_0_5A 시험 | 단독 |
| 6 | TEST_ROUND-HDR_9000_1_1_7E 시험 | 단독 |
| 7 | TEST_ROUND-HDR_9000_1_1_8 시험 | 단독 |
| 8 | TEST_ROUND-HLM_9000_1_1_14B 시험 | 단독 |
| 9 | TEST_ROUND-HRK_9000A_1_1_0A 시험 | 단독 |
| 10 | TEST_ROUND-HRK_9000A_1_1_1A 시험 | 단독 |
| 11 | TEST_ROUND-HRK_9000A_1_1_1D 시험 | 단독 |
| 12 | TEST_ROUND-HTR_1A_1_1_8 시험 | 단독 |

수행 기간은 각 라운드 `product_test_release.remark`에 넣고, `tracking_router`가 파싱한다.

### 엑셀 마이그레이션 후 추적이 안 되는 이유

`scripts/migrate_excel_to_db.py`만 실행한 경우:

- Release ID가 `RELEASE-{엑셀 rid}` 평면 구조 (`release_stage=RC`)
- 타임라인이 기대하는 **라운드 → 구성(visible=1) → RC1(visible=0) → Run** 트리 없음
- `migrate_topology_restructure.py`는 이미 `TEST_RELEASE-*` 트리가 있을 때 동작

**권장 실행 순서** (서버 중지 + DB 백업 후):

```text
1. python scripts/migrate_excel_to_db.py [excel.xlsx]
2. python scripts/migrate_excel_rounds_normalize.py [excel.xlsx]        # dry-run
3. python scripts/migrate_excel_rounds_normalize.py [excel.xlsx] --apply
4. (Test Case 정합성 스크립트 — 작성 예정, 아래 참고)
5. /admin 추적 새로고침 · tests/test_traceability.py
```

`migrate_device_centric_rounds.py`는 최상위를 장비별로 쪼개 WIFI_1ST/2ND가 사라질 수 있어 **Case/라운드 정리 전에는 실행하지 않는다.**

### 스크립트: `migrate_excel_rounds_normalize.py`

- 12개 `TEST_RELEASE-{short}` 생성 (`upstream=MULTI_PRODUCT`, `visible=1`, 기간 remark)
- Result 기준 구성 분류 → **구성당 RC1** (`...-{combo}-RC1`)
- Run → RC1 연결, RC2+ 병합, `RELEASE-*` → `round_legacy` 숨김
- dry-run 기준: result 375건 → 약 33구성 / RC1 33개 (적용 시 백업 자동 생성)

---

## Test Case 정합성 (2026-06-04 — 진행 중)

### 문제 정의: Case ID 안의 `1AP_1HDC`는 토폴로지가 아님

예: `TEST_CASE-1AP_1HDC-WIFI-AP_AUTH-001`

| 토큰 | 잘못된 해석 (기존 코드) | 올바른 의미 |
|------|-------------------------|-------------|
| `1AP` | 토폴로지의 AP 1대 | **1ROUTER** (라우터 1대) |
| `1HDC` | 토폴로지 일부 | **시험 대상(DUT)** HDC 1대 |
| `WIFI-AP_AUTH-001` | 시나리오/절차 슬러그 | 유지 |

`migrate_topology_restructure.py`의 `extract_topo_from_case_id()`는 Case ID 첫 세그먼트를 토폴로지로 **오인**한다.  
실제 토폴로지는 **Result.remark `[연결구성]`** 또는 **Test Release.remark**(시험 대상·환경·목적)에서 추론해야 한다.

### DB 스냅샷 (조사 시점)

| 항목 | 값 |
|------|-----|
| `product_test_case` | 60건 |
| Case ID 접두 (오인 세그먼트) | `1AP_1HRK` 12, `1AP_1HTR` 12, `1AP_1HDR` 9, `1AP_1HDC` 7, `1AP_1HLM` 7, `25AP_1TEST_TARGET` 7, `20AP` 1, 비정규 한글 ID 3, 기타 |
| Result `[연결구성]` 상위 | `1AP_1HRK_4HDR` 44, `1AP_1HRK_1HDR` 43, `1AP_4HDR_1HDC` 30, `1AP_1HDC_1HDR` 29, … (레거시 **AP** 표기) |
| `product_test_procedure` | 171건 (case_id FK) |
| `product_test_procedure_result` | 0건 |

**불일치 예**: Case는 `1AP_1HDC`(대상 HDC)인데 Result는 `1AP_1HRK_4HDR`(실제 연결)인 행이 다수 → Case ID만으로 Release/구성 매칭 불가.

### 토폴로지 정본 목록 (ROUTER 표기 — 기획 확정분)

아래 목록 기준으로 **토폴로지별 Test Case 세트**를 재구성한다.  
`1HDC` / `1HDC_1ROUTER`는 HDC WBS 일부 포함·**추후 추가** — **현재 Test Case 없음**.

```text
1HDC
1HDC_1ROUTER
1HDR_1CABLE_1HIIS
1HDR_1ROUTER
1HDR_1ROUTER_1HDC
1HDR_25ROUTER
1HDR_25ROUTER_1HDC
1HLM_1ROUTER
1HLM_1ROUTER_1HDR
1HLM_1ROUTER_4HDR
1HLM_25ROUTER
1HLM_25ROUTER_1HDR
1HRK_1ROUTER
1HRK_1ROUTER_1HDR
1HRK_1ROUTER_1HTR_1HLM_4HDR
1HRK_1ROUTER_3HDR
1HRK_1ROUTER_4HDR
1HRK_25ROUTER
1HRK_25ROUTER_1HDR
1HTR_1ROUTER
1HTR_1ROUTER_1HDR
1HTR_1ROUTER_2HDR
1HTR_25ROUTER
1HTR_25ROUTER_1HDR
2HDR_1ROUTER
4HDR_1ROUTER
4HDR_1ROUTER_1HDC
4HDR_1ROUTER_1HIIS
```

(원문에 `1HDR_1CABLE_1HIIS-` trailing `-` 있음 → **미결 질문**)

### 레거시 AP 표기 → ROUTER 정본 매핑 (가설, 확정 전)

Result/Release에 남은 `1AP_*`는 **라우터+장비 수**로 읽고, 정본 토큰 순서로 변환한다.

| 레거시 `[연결구성]` (예) | ROUTER 정본 (가설) |
|------------------------|-------------------|
| `1AP_1HRK_4HDR` | `1HRK_1ROUTER_4HDR` |
| `1AP_1HRK_1HDR` | `1HRK_1ROUTER_1HDR` |
| `1AP_4HDR_1HDC` | `4HDR_1ROUTER_1HDC` |
| `1AP_1HDC_1HDR` | `1HDR_1ROUTER_1HDC` (또는 `1HDC_1ROUTER_1HDR` — **확인 필요**) |
| `1AP_1HRK_1HTR_1HLM_4HDR` | `1HRK_1ROUTER_1HTR_1HLM_4HDR` |
| `25AP_1HDR_1HDC` | `1HDR_25ROUTER_1HDC` |
| `25AP_1HRK_1HDR` | `1HRK_25ROUTER_1HDR` |
| `1AP_1HDC` | `1HDC_1ROUTER` 또는 `1HDC` (**확인 필요**) |

장비 순서 규칙(기존): HRK > HTR > HLM > HDR > HDC > HIIS — **ROUTER는 별도 토큰**으로 정본 목록에만 존재.

### 권장 Case ID 규칙 (안)

```text
TEST_CASE-{topology}-{dut}-{scenario_slug}-{seq}

예:
  TEST_CASE-1HRK_1ROUTER_4HDR-HRK-WIFI-AP_AUTH-001
  TEST_CASE-1HDC_1ROUTER-HDC-WIFI-DHCP_SELECT-001
```

- `{topology}`: 위 정본 목록 중 하나 (Release remark + Result `[연결구성]`으로 결정)
- `{dut}`: 시험 대상 장비 약어 (기존 `1AP_1HDC`의 HDC 부분)
- `{scenario_slug}`: 기존 `WIFI-*` 구간 유지
- PK 변경 시 **반드시** `product_test_result.product_test_case_id`, `product_test_procedure.product_test_case_id` 일괄 UPDATE

### 토폴로지 추론 우선순위 (안)

1. 동일 Run/Report에 묶인 Result의 `[연결구성]` (다수결 또는 최빈값)
2. Run이 연결된 Release → 상위 라운드 `remark` (시험 대상·환경·`[Test 대상]` 블록)
3. Excel Reports 시트의 시험 대상 텍스트
4. 정본 목록에 없으면 `UNCLASSIFIED` 구성 + remark에 원본 보존

### 검증 (`tests/test_traceability.py`)

Case/Procedure 단계에서 최소 통과 목표:

- **TC-PR01**: Result에 쓰인 모든 case_id에 Procedure 존재
- **TC-PR02**: Procedure → Case FK 고아 없음
- **TC-PR03**: case별 `procedure_sequence` 중복 없음
- **TC-RS02** (존재 시): Result → Case FK 고아 없음

추가 권장: “Case ID의 topology 세그먼트 ∈ 정본 목록” 커스텀 TC (신규).

### 작성 예정 스크립트

`scripts/migrate_test_cases_by_topology.py` (미작성)

- 정본 토폴로지 목록 + 레거시 AP→ROUTER 매핑 테이블 (YAML/상수)
- Result 375건 기준 (topology, dut, scenario) 그룹핑
- Case/Procedure ID 재발급 + Result/Procedure FK UPDATE
- `remark`에 `[구 Case ID]`, `[연결구성]`, `[추론 출처]` 보존
- dry-run / `--apply` + 자동 백업

---

## 미결 질문 (답변 후 Case 마이그레이션 착수)

1. **AP→ROUTER 전역 치환**  
   Result/Release/구성행의 `1AP`/`25AP`를 모두 `1ROUTER`/`25ROUTER` 규칙으로 바꿀지? (`migrate_topology_restructure.normalize_combo`도 AP 전제)

2. **`1HDR_1CABLE_1HIIS-`**  
   trailing `-` 오타인지, 정식 ID는 `1HDR_1CABLE_1HIIS`인지.

3. **Case 복제 단위**  
   동일 시나리오(`WIFI-AP_AUTH-001` 등)를 **토폴로지마다 1벌**인지, **토폴로지×DUT마다 1벌**인지  
   (예: `1HRK_1ROUTER_4HDR`에서 HRK 시험 vs HDR 시험 Case 분리 여부).

4. **불일치 시 우선순위**  
   Case ID 대상(HDC) vs Result `[연결구성]`(예: `1AP_1HRK_4HDR`)이 다를 때 **어느 쪽이 정본**인지.

5. **`1AP_1HDC` only** (연결구성 13건)  
   정본 `1HDC` vs `1HDC_1ROUTER` 중 어디에 매핑할지.

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

**구성 네이밍 (레거시 — DB/Result 다수)**: `{AP수}AP_{장비수}{장비명}_...`  
- 코드: `migrate_topology_restructure.normalize_combo`, `extract_topo_from_case_id`  
- 예: `1AP_1HRK_4HDR` — 여기서 `1AP`는 **라우터 1대** 의미이나 토큰명은 AP

**구성 네이밍 (정본 — Test Case 재구성 목표)**: `{장비}_[N]ROUTER_...`  
- 정본 목록은 위 **「Test Case 정합성」** 절 참고 (`1HRK_1ROUTER_4HDR` 등)  
- Case ID의 `1AP_1HDC`는 토폴로지가 **아님** (DUT=HDC + 라우터 표기 혼동)

공통: 장비 순서 HRK > HTR > HLM > HDR > HDC > HIIS, `ALL`/`TARGET` 금지

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

## TEST_ROUND_ID 필수 규칙 및 수정방안

### 정상 TEST_ROUND_ID 목록

타임라인의 시험 라운드 ID는 반드시 아래 `TEST_ROUND_` prefix 규칙을 따른다.
현재 DB 내부 FK가 `TEST_RELEASE-*`를 사용하더라도, view/API의 `test_round_id` 또는 화면 표시용 라운드 ID는 아래 값으로 정규화해야 한다.

| TEST_ROUND_ID | 기대 상태 |
|---|---|
| TEST_ROUND_HDC_9100_1_0_5A-WIFI_1ST | QI Team 시험중단판정 |
| TEST_ROUND_HDC_9100_1_0_5A-WIFI_2ND | QI Team 시험중 |
| TEST_ROUND_HDR_9000_1_1_7E-WIFI_1ST | QI Team 시험중단판정 |
| TEST_ROUND_HDR_9000_1_1_8-WIFI_1_1_1D | QI Team 시험중 |
| TEST_ROUND_HDR_9000_1_1_8-WIFI_2ND | QI Team 시험중 |
| TEST_ROUND_HLM_9000_1_1_14B-WIFI_1ST | QI Team 시험중단판정 |
| TEST_ROUND_HLM_9000_1_1_14B-WIFI_2ND | QI Team 시험중 |
| TEST_ROUND_HRK_9000A_1_1_0A-WIFI_DOWNGRADE | QI Team 시험중 |
| TEST_ROUND_HRK_9000A_1_1_1A-WIFI_1ST | QI Team 시험중단판정 |
| TEST_ROUND_HRK_9000A_1_1_1A-WIFI_2ND | QI Team 시험중 |
| TEST_ROUND_HTR_1A_1_1_8-WIFI_1ST | QI Team 시험중단판정 |
| TEST_ROUND_HTR_1A_1_1_8-WIFI_2ND | QI Team 시험중 |

### 현재 문제

- 일부 라운드는 화면에서 `TEST_RELEASE-*` 원본 ID 또는 prefix 없는 라운드 short id로 보인다.
- 일부 라운드는 `TEST_ROUND_` prefix가 빠져 TEST_ROUND_ID 규칙을 만족하지 않는다.
- `HDR-9000 1.1.8 WIFI 시험 (1.1.1D)`처럼 모델/SW 버전과 시험 캠페인 alias가 섞여 보이는 라운드명이 있다.
- `Target / Environment`는 실제 `product_test_target_id` 기준으로 중복 제거되어 모델/SW별 target이 1개 장비처럼 보일 수 있다.

### 수정방안

1. DB PK/FK는 당장 바꾸지 않는다.
   - `product_test_release.product_test_release_id`와 하위 FK가 이미 연결되어 있으므로 즉시 PK rename은 위험하다.
   - 대신 API/view layer에 `test_round_id`를 추가하거나 표시 ID를 정규화한다.

2. `tracking_router.py`에서 device round 응답에 정규화 ID를 내려준다.
   - 예: `TEST_RELEASE-HDC_9100_1_0_5A-WIFI_1ST` -> `TEST_ROUND_HDC_9100_1_0_5A-WIFI_1ST`
   - 변환 규칙:
     ```text
     remove_prefix("TEST_RELEASE-")
     if not startswith("TEST_ROUND_"): prepend("TEST_ROUND_")
     ```
   - 프론트는 내부 연결용 `id`는 기존 release id를 쓰고, 화면 표시/검색/복사용 ID는 `test_round_id`를 쓴다.

3. 위 정상 목록에 없는 device round를 점검한다.
   - 점검 SQL 방향:
     ```sql
     SELECT product_test_release_id, product_test_release_status, remark
     FROM product_test_release
     WHERE release_visible = 1
       AND release_stage = 'device_round'
     ORDER BY product_test_release_id;
     ```
   - 결과를 정상 TEST_ROUND_ID 목록과 비교해 누락/오타/불필요 라운드를 분류한다.

4. 라운드 alias는 모델/SW와 캠페인명을 분리한다.
   - 권장 표시:
     ```text
     TEST_ROUND_HDR_9000_1_1_8-WIFI_1_1_1D · HDR-9000 1.1.8 WIFI 시험
     ```
   - `(...1.1.1D)` 같은 캠페인 설명 괄호는 device round alias 뒤에 붙이지 않는다.
   - 캠페인 구분은 ID suffix(`WIFI_1_1_1D`)로 충분히 식별한다.

5. 상태는 하위 Result 집계 기준으로 재계산한다.
   - 우선순위: `FAILED > BLOCKED > TESTING > PASSED > SKIPPED > CANCELLED`
   - QI Team 라벨 매핑:
     - `BLOCKED` -> `QI Team 시험중단판정`
     - `TESTING` -> `QI Team 시험중`
     - `PASSED` -> `QI Team 시험합격판정`

6. `Target / Environment`는 physical target이 아니라 logical target 기준으로 보여준다.
   - logical target id 예:
     ```text
     TEST_TARGET_HDC_9100_1_0_5A-WIFI_1ST
     ```
   - 모델명/SW 버전은 라운드 ID 또는 라운드 alias에서 파생한다.
   - 물리 target id는 별도 `Physical Target ID` 컬럼으로만 보존한다.

### 검증 기준

- 타임라인 최상위 라운드 행이 위 정상 TEST_ROUND_ID 목록과 1:1로 대응해야 한다.
- 화면에 `TEST_RELEASE-HDC_...`, `HDC_9100_...`처럼 `TEST_ROUND_`가 빠진 라운드 ID가 보이면 실패.
- `HDR-9000 1.1.8 WIFI 시험 (1.1.1D)`처럼 alias에 다른 버전 괄호가 섞이면 실패.
- `Target / Environment`에 모델/SW별 logical target이 12개 라운드 기준으로 분리되어 보여야 한다.

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
| `scripts/migrate_excel_to_db.py` | Excel → DB 1차 적재 |
| `scripts/migrate_excel_rounds_normalize.py` | 12라운드 + RC1 + Run 연결 (미적용 가능) |
| `scripts/migrate_test_cases_by_topology.py` | **(예정)** Case/Procedure 토폴로지 재구성 |

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
5. **엑셀→타임라인 정규화** — `migrate_excel_rounds_normalize.py --apply` 미실행
6. **Test Case ID vs 토폴로지** — Case ID `1AP_1*` 오인, ROUTER 정본 28종으로 재구성·스크립트 미작성 (HANDOVER 「미결 질문」5건)
7. **AP vs ROUTER 표기** — Result `[연결구성]`·구성행·`normalize_combo` 전역 정책 미확정
8. **1HDC / 1HDC_1ROUTER WBS Case** — 추후 추가, 현재 없음
9. **GET 라우트 누락** — `product_test_*_admin.html` 템플릿 대비 `/admin/product-test-releases` 등 GET 일부 미구현 (E2E만 기대)
