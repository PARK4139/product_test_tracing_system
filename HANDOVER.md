# HANDOVER — 제품 시험 추적 시스템 (2026-06-08 갱신 · codex 작업지시 판)

> 이전 핸드오버는 `HANDOVER_20260604_archived.md` 로 보존.
> 이 문서는 **codex가 순서대로 실행**하도록 작성됨. **쉬운 것 → 어려운 것** 순.
> 최신 정합성 진단 근거: `docs/data_integrity_diagnosis_20260608.md`

---

## 0. 큰 그림 (caveman)

- 목표 = **시험 데이터 추적성 확보**.
- 지금 상태: **FK는 안 끊김(좋음). 근데 이름표가 엉망 + 마지막 증거가 텅 빔.**
- 그래서 순서: **(1) 진단 자동화 → (2) 스키마 정본화 → (3) 이름표 통일 → (4) 재매핑 → (5) 빈 증거 채우기(시트 탭)**.
- 이번까지는 **DB 직접 변경 없음**. 변경은 항상 **dry-run 먼저, --apply는 사람 확인 후**.

---

## 1. 프로젝트 기본 정보

| 항목 | 값 |
|---|---|
| 위치 | `C:\Users\USER\Downloads\product_test_tracing_system` |
| 스택 | FastAPI + SQLite(WAL) + Jinja2 + 순수 JS |
| 실행 | `run.cmd` (Windows 전용 venv, sandbox 실행 불가) |
| 포트 | 8000 / 8008 |
| DB | `data/product_test_tracking_system.db` |
| 로그 | `data/logs/app.log` (프런트는 `clientLog()` 필수, `console.log` 금지) |
| 백업 | 대량 변경 전 서버 중지 + DB 백업 (`backup_service` 재활용) |

---

## 2. 현재 DB 규모 (2026-06-08 진단)

| 테이블 | 건수 | | 테이블 | 건수 |
|---|---:|---|---|---:|
| release | 216 | | case | 60 |
| run | 62 | | procedure | 171 |
| result | 375 | | defect | 15 (전부 opened) |
| round | 13 | | target/def | 6 / 6 |
| **evidence** | **0** | | env/def | 6 / 6 |
| **procedure_result** | **0** | | report | 8 |
| **status_transition** | **0** | | snapshot | 0 |

---

## 3. 진단 결과 요약 (무엇을 고쳐야 하나)

| 심각도 | 문제 | 수치 |
|---|---|---|
| **P0** | 추적 증거 레벨이 텅 빔 (evidence/procedure_result/status_transition) | 0 / 0 / 0 |
| **P0** | models.py ↔ 실제 DB 스키마 불일치 | round 테이블·release 2컬럼 누락 |
| **P1** | Case ID 토폴로지 ≠ Result 실제 `[연결구성]` | 331/375 (88%) |
| **P1** | 연결구성 표기 전부 레거시 AP, ROUTER 0 | AP 372 / ROUTER 0 |
| **P1** | 비정상 Case ID | 5건 |
| **P2** | 라운드 트리 구멍 (release 없는 round / round 없는 release) | 5건 / 4건 |
| **P2** | 상태값 대소문자·어휘 제각각 | result 소문자 / release 대문자 / run 소문자 |

**좋은 점**: FK 고아 0, procedure_sequence 중복 0, 고아 Case 0. → 참조 무결성은 OK.

---

## 4. ⭐ CODEX 작업 순번 (쉬운 것부터)

> 규칙: 각 작업은 **독립 실행 가능**해야 한다. 작업마다 ① 목적 ② 대상파일 ③ 작업내용 ④ 검증 ⑤ 위험도.
> DB를 바꾸는 작업은 **무조건 dry-run 모드 먼저 제공**하고, `--apply`는 별도 플래그로만.

---

### TASK 1 — 정합성 진단 스크립트화 (read-only) 🟢위험없음
- **목적**: 매번 수동 SQL 대신, 한 번에 정합성 리포트 뽑는 스크립트.
- **대상파일**: `scripts/diagnose_integrity.py` (신규)
- **작업내용**:
  - DB를 **읽기 전용**으로 열어 아래를 출력:
    - 전 테이블 건수
    - FK 고아 검사 10종 (result→run/case, procedure→case, run→release/target/env, defect→result, release→round, target→def, env→def)
    - procedure_sequence 중복, 고아 Case
    - Case ID 첫 세그먼트 ↔ Result `[연결구성]` 불일치 건수
    - `[연결구성]` AP/ROUTER 표기 카운트
    - 비정상 Case ID 목록 (`NOT LIKE 'TEST_CASE-%'`)
    - 라운드 트리 구멍 (release 없는 round, round NULL인 release)
    - 상태값 vocab 분포
  - `--json` 옵션 시 결과를 JSON으로도 출력 (나중에 시트 탭이 소비).
- **검증**: 실행 결과가 `docs/data_integrity_diagnosis_20260608.md` 수치와 일치.
- **위험도**: 없음 (읽기 전용).

---

### TASK 2 — models.py ↔ 실제 DB 스키마 동기화 🟢코드만
- **목적**: 모델 파일이 실제 스키마를 정확히 반영하게 (drift 제거).
- **대상파일**: `app/models.py`
- **작업내용**:
  - 실제 DB에 있으나 모델에 없는 것 추가:
    - 테이블 **`product_test_round`** — 컬럼: `test_round_id`(PK), `test_round_name`, `workday`, `start_date`, `end_date`, `date_quality`, `migration_status`, `migration_note`, `project_id`, `created_at/by`, `updated_at/by`.
    - `ProductTestRelease`에 컬럼 **`release_visible`(Integer)**, **`test_round_id`(Text, FK→product_test_round)** 추가.
  - `app/db.py`의 런타임 컬럼보정 로직과 충돌 없는지 확인.
- **검증**: 앱 부팅 OK + `SELECT`로 두 컬럼/테이블 ORM 접근 성공. 스키마 비교 테스트 1개 추가(`tests/test_schema_sync.py`).
- **위험도**: 낮음 (DB 데이터 안 바꿈).

---

### TASK 3 — 상태값 정본 상수 + 뷰계층 정규화 🟢코드만
- **목적**: result/release/run 상태 대소문자·어휘 통일 (DB는 아직 안 바꿈, 표시·집계만 정규화).
- **대상파일**: `app/services/status_vocab.py` (신규), 사용처(`tracking_router.py` 등)
- **작업내용**:
  - 정본 enum 정의 (예: `PASSED/BLOCKED/TESTING/FAILED/SKIPPED/CANCELLED/APPROVED`).
  - `normalize_status(raw) -> 정본값` 함수 (소문자/대문자/별칭 흡수).
  - API 응답·집계·하이라이트에서 이 함수를 통과시키도록 교체.
  - 우선순위 정렬: `FAILED > BLOCKED > TESTING > PASSED > SKIPPED > CANCELLED`.
- **검증**: 단위 테스트 — 다양한 입력이 정본값으로 매핑.
- **위험도**: 낮음 (DB 미변경).

---

### TASK 4 — 비정상 Case ID 5건 정리 (dry-run) 🟡소량 DB
- **목적**: 규칙 위반 Case ID 5건 정상화.
- **대상파일**: `scripts/fix_abnormal_case_ids.py` (신규)
- **대상 데이터**:
  | 현재 ID | 처리안 |
  |---|---|
  | `PLACEHOLDER_EMPTY_CASE-WIFI_CONNECTIVITY_TEST_2026` (DRAFT, 절차0, Result사용중) | 정식 Case로 승격 or Result 재배정 — **사람 결정 필요** |
  | `DEPRECATED_TEST_CASE-1AP_1HDC-WIFI-DR_CONNECT_ON_DHCP-002` (ACTIVE) | status를 DEPRECATED로, 또는 정식 ID 재발급 |
  | `Wi-Fi 재ON 후 복구` / `라우터 재부팅 후 복구` / `시험대상장비 재부팅 후 복구` | `TEST_CASE-{topology}-{dut}-{scenario}-{seq}` 규칙 ID 재발급 |
- **작업내용**: PK 변경 시 **반드시** `product_test_result.product_test_case_id` + `product_test_procedure.product_test_case_id` 동시 UPDATE. 구 ID는 `remark`에 `[구 Case ID]`로 보존. dry-run / `--apply` + 자동 백업.
- **검증**: TC-PR01(Result에 쓰인 모든 case_id에 Procedure 존재) 통과, 비정상 ID 0건.
- **위험도**: 중 (FK 동시 갱신). **dry-run 먼저.**

---

### TASK 5 — AP→ROUTER 매핑 테이블 + 정규화 함수 (dry-run) 🟡정책 의존
- **선행**: 아래 §6 미결질문 1·2·5 답 확정.
- **대상파일**: `app/services/topology_normalize.py` (신규) + `scripts/preview_ap_to_router.py`
- **작업내용**:
  - 레거시 `1AP/25AP` → 정본 `1ROUTER/25ROUTER` 변환 규칙 + §5 정본 토폴로지 목록 상수화.
  - `normalize_combo(legacy) -> 정본 토폴로지` 함수 + 정본 목록에 없으면 `UNCLASSIFIED` 표시.
  - preview 스크립트: Result 375건의 `[연결구성]`을 정본으로 변환했을 때 결과를 표로 출력(미적용).
- **검증**: 375건 모두 정본 또는 UNCLASSIFIED로 분류. 매핑표가 §5 목록과 모순 없음.
- **위험도**: 중 (정책 미확정 시 보류).

---

### TASK 6 — Case ↔ 연결구성 재매핑 스크립트 (dry-run) 🔴대규모
- **선행**: TASK 4·5 + §6 미결질문 3·4 답.
- **대상파일**: `scripts/migrate_test_cases_by_topology.py` (신규)
- **작업내용**:
  - Case ID 신규 규칙: `TEST_CASE-{topology}-{dut}-{scenario_slug}-{seq}`.
  - 토폴로지 추론 우선순위: ① 같은 Run/Report 묶음 Result의 `[연결구성]` 최빈값 → ② Run→Release remark → ③ Excel Reports 텍스트 → ④ 없으면 UNCLASSIFIED.
  - Case/Procedure ID 재발급 + Result/Procedure FK 일괄 UPDATE.
  - `remark`에 `[구 Case ID]`, `[연결구성]`, `[추론 출처]` 보존.
  - dry-run / `--apply` + 자동 백업.
- **검증**: `tests/test_traceability.py` — TC-PR01/PR02/PR03/RS02 통과 + "Case ID topology ∈ 정본목록" 신규 TC. Case세그↔연결구성 불일치 88% → 0% 목표.
- **위험도**: 높음. 반드시 백업 + dry-run 리뷰 후 apply.

---

### TASK 7 — 시트 탭 백엔드 API (read-only 우선) 🟡신규기능
- **목적**: 핵심 테이블을 시트(행/열 + 검증배지)로 내려주는 API.
- **대상파일**: `app/routers/sheet_router.py` (신규), `app/services/sheet_service.py` (신규)
- **작업내용**:
  - `GET /admin/api/sheet/{table}` — case/result/release/defect/evidence 지원.
  - 각 행에 **정합성 플래그** 부여(예: `case_id_invalid`, `topology_mismatch`, `evidence_missing`).
  - 파생열 계산(절차 수, 연결 Result 수, 매칭 토폴로지 최빈값).
  - 1차는 **읽기 전용**. 편집은 TASK 9.
- **검증**: 응답 플래그 합계가 TASK 1 진단 수치와 일치.
- **위험도**: 낮음 (읽기).

---

### TASK 8 — 시트 탭 프론트 (보기 + 검증 배지) 🟡신규기능
- **대상파일**: `app/static/js/sheet-view.js` (신규), `app/templates/`에 탭 추가, `sheet.css`
- **작업내용**:
  - 스프레드시트형 렌더(고정헤더·정렬·필터).
  - 정합성 위반 색배지(규칙위반=빨강, 토폴로지불일치=주황, 증거없음=회색).
  - "문제 있는 행만 보기" 토글. 필터/정렬 상태는 `UiStatePref`에 저장.
  - 디버그 로그는 `clientLog()` 사용.
- **검증**: 불일치 행이 진단 수치만큼 배지로 표시.
- **위험도**: 낮음.

---

### TASK 9 — 시트 인라인 편집 + status_transition 자동기록 🔴추적성 핵심
- **목적**: 시트에서 직접 수정 → DB 반영 + 변경 이력 자동 적재 = 추적 기록. Evidence 빈 칸 채우기.
- **대상파일**: `sheet_router.py`(PATCH), `sheet_service.py`, `sheet-view.js`
- **작업내용**:
  - `PATCH /admin/api/sheet/{table}/{id}` — 저장 전 **diff 미리보기 필수**, 확정 시에만 반영.
  - 모든 변경을 `product_test_status_transition`에 기록(entity_type/id, from/to, by, reason).
  - Evidence 탭은 신규 행 입력 지원(file_path/hash/type) → P0 공백 해소.
  - 대량 변경 시 백업 트리거.
- **검증**: 수정 1건 → transition 1행 생성, diff와 실제 반영 일치.
- **위험도**: 높음 (쓰기). 권한·백업·dry-run diff 필수.

---

## 5. 정본 토폴로지 목록 (ROUTER 표기 — 기획 확정분)

```text
1HDC                         1HRK_1ROUTER
1HDC_1ROUTER                 1HRK_1ROUTER_1HDR
1HDR_1CABLE_1HIIS            1HRK_1ROUTER_1HTR_1HLM_4HDR
1HDR_1ROUTER                 1HRK_1ROUTER_3HDR
1HDR_1ROUTER_1HDC            1HRK_1ROUTER_4HDR
1HDR_25ROUTER                1HRK_25ROUTER
1HDR_25ROUTER_1HDC           1HRK_25ROUTER_1HDR
1HLM_1ROUTER                 1HTR_1ROUTER
1HLM_1ROUTER_1HDR            1HTR_1ROUTER_1HDR
1HLM_1ROUTER_4HDR            1HTR_1ROUTER_2HDR
1HLM_25ROUTER                1HTR_25ROUTER
1HLM_25ROUTER_1HDR           1HTR_25ROUTER_1HDR
                             2HDR_1ROUTER
                             4HDR_1ROUTER
                             4HDR_1ROUTER_1HDC
                             4HDR_1ROUTER_1HIIS
```
- 장비 순서: HRK > HTR > HLM > HDR > HDC > HIIS. ROUTER는 별도 토큰. `ALL`/`TARGET` 금지.
- `1HDC` / `1HDC_1ROUTER` 는 추후 추가(현재 Case 없음).

### 레거시 AP → ROUTER 매핑 (가설, 확정 전)
| 레거시 `[연결구성]` | ROUTER 정본 (가설) |
|---|---|
| `1AP_1HRK_4HDR` | `1HRK_1ROUTER_4HDR` |
| `1AP_1HRK_1HDR` | `1HRK_1ROUTER_1HDR` |
| `1AP_4HDR_1HDC` | `4HDR_1ROUTER_1HDC` |
| `1AP_1HDC_1HDR` | `1HDR_1ROUTER_1HDC` (확인 필요) |
| `1AP_1HRK_1HTR_1HLM_4HDR` | `1HRK_1ROUTER_1HTR_1HLM_4HDR` |
| `25AP_1HDR_1HDC` | `1HDR_25ROUTER_1HDC` |
| `25AP_1HRK_1HDR` | `1HRK_25ROUTER_1HDR` |
| `1AP_1HDC` | `1HDC_1ROUTER` 또는 `1HDC` (확인 필요) |

---

## 6. 미결 질문 (답 확정해야 TASK 5·6 착수 가능)

1. **AP→ROUTER 전역 치환** — Result/Release/구성행의 `1AP`/`25AP`를 모두 `1ROUTER`/`25ROUTER`로 바꿀지?
2. **`1HDR_1CABLE_1HIIS`** — 원문 trailing `-` 오타 맞는지(정식 ID `1HDR_1CABLE_1HIIS`).
3. **Case 복제 단위** — 동일 시나리오를 토폴로지마다 1벌인지, 토폴로지×DUT마다 1벌인지.
4. **불일치 우선순위** — Case ID 대상(예 HDC) vs Result `[연결구성]`(예 `1AP_1HRK_4HDR`)이 다를 때 어느 쪽이 정본?
5. **`1AP_1HDC` only** (13건) — 정본 `1HDC` vs `1HDC_1ROUTER` 중 어디로?

---

## 7. 데이터 계층 구조 (참고)

```
Round (13)
  └─ Release (216: device_round 12 / RC 166 / run_session 28 / TEST 6 / round_legacy 4)
       └─ Run (62)  ├─ Target(6)→TargetDef(6)
                    ├─ Environment(6)→EnvDef(6)
                    └─ Result(375) ├─ Case(60)→Procedure(171)
                                   ├─ Defect(15)
                                   ├─ ProcResult(0)  ← 비어있음
                                   └─ Evidence(0)    ← 비어있음
  Report(8) via release_id · Snapshot(0) · StatusTransition(0) ← 비어있음
```

---

## 8. 구현 위치 (파일 맵)

| 파일 | 역할 |
|---|---|
| `app/models.py` | ORM 모델 (TASK 2에서 동기화) |
| `app/db.py` | DB 초기화·런타임 컬럼 보정 |
| `app/routers/tracking_router.py` | 추적 API (releases/defects/runs/results/proc/evidence) |
| `app/static/js/tracking-*.js` | 간트·하이라이트·렌더 |
| `app/services/backup_service.py` | DB 백업 (대량 변경 전 재활용) |
| `scripts/diagnose_integrity.py` | **TASK 1 신규** |
| `app/services/status_vocab.py` | **TASK 3 신규** |
| `scripts/fix_abnormal_case_ids.py` | **TASK 4 신규** |
| `app/services/topology_normalize.py` | **TASK 5 신규** |
| `scripts/migrate_test_cases_by_topology.py` | **TASK 6 신규** |
| `app/routers/sheet_router.py` / `services/sheet_service.py` | **TASK 7/9 신규** |
| `app/static/js/sheet-view.js` | **TASK 8 신규** |
| `docs/data_integrity_diagnosis_20260608.md` | 최신 진단 근거 |

---

## 9. 편집 규칙 (반드시 준수)

1. 200줄 이상 파일은 Edit 도구 대신 python으로 처리.
2. 편집 후 항상 null 바이트 제거 + 문법 검증.
3. 프런트 디버그는 `clientLog()` 만 (`console.log` 금지).
4. DB 변경 스크립트는 **dry-run 기본**, `--apply` 별도 플래그 + 자동 백업.
5. PK 변경 시 참조 FK 전부 동시 UPDATE, 구 값은 `remark`에 보존.
6. 대량 변경 전 서버 중지 + DB 백업.

---

## 10. 다음 세션 시작점

- TASK 1 → 2 → 3 은 **위험 없음/낮음**이라 바로 착수 가능.
- TASK 4 이후는 **§6 미결질문 답 확정 후** 진행.
- 추적성 최종 목표(P0 증거 공백)는 **TASK 9**에서 해소.
