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

## 0-0. 🎯 목표 아키텍처 (MASTER — 모든 TASK가 이걸 향함)

- 최종 화면 = **탭 7개**: `Configs > Targets > Cases > Procedures > Results > Releases > Rounds`.
- 탭 = 정본 테이블 1개씩. **Configs/Targets(입력)부터 최상위 Rounds까지 정합성으로 이어져야 함.**
- **Run은 탭 없음 → Results에 흡수**(run/config/target/release 컬럼). Defect/Report 등은 필요 시 보조 탭.
- 작업 순서도 동일: **Configs → Targets → Cases → Procedures → Results → Releases → Rounds** (각 단계 정합성 게이트 통과 후 진행).
- 탭↔테이블↔TASK 매핑, 연결키 체인(C1~C6), 게이트 조건은 **`handover_2026_06_08_master_architecture.md` 참조 (정본).**

| 탭 | 정본 테이블 | 관련 TASK |
|---|---|---|
| Configs | environment(통합) | TASK 11 |
| Targets | target(통합) | TASK 12, 13 |
| Cases | case | TASK 4, 6 |
| Procedures | procedure | TC-PR01/02/03 |
| Results (+Run 흡수) | result | 시트 §2 |
| Releases | release | TASK 14 |
| Rounds | round | round 정비 |

---

## 0-1. ⚠️ CODEX 실수 방지 수칙 (작업 전 필독)

1. **DB는 WAL 모드.** 진단 수치 재현/조회 시 `.db` 단독으로 읽으면 최신값 누락된다. 읽기 전 `PRAGMA wal_checkpoint(TRUNCATE)` 하거나, `.db`+`.db-wal`+`.db-shm`를 통째로 복사해 **읽기 전용 복사본**에서 작업하라. (이 핸드오버의 모든 수치는 checkpoint 후 기준.)
2. **DB가 정본, models.py는 따라간다.** TASK 2는 실제 DB 스키마에 모델을 맞추는 것. **거꾸로 db.py/DB를 모델에 맞춰 바꾸지 마라.**
3. **`[연결구성]`은 `product_test_result.remark` 안의 텍스트.** 별도 컬럼 아님. 파싱 패턴: 정규식 `\[연결구성\]\s*([^\n\]]+)`.
4. **상태값은 테이블마다 대소문자/어휘가 다르다** (result 소문자 / release 대문자 / run 소문자). 비교·집계 전 반드시 `normalize_status()`(TASK 3) 통과. 생짜 문자열 비교 금지.
5. **DB를 바꾸는 모든 작업은: ① dry-run 먼저 출력 → ② 사람 승인 → ③ 자동 백업 후 `--apply`.** 승인 없이 `--apply` 절대 금지.
6. **PK 변경 시 참조 FK 전부 동시 UPDATE.** Case ID 바꾸면 `product_test_result.product_test_case_id` + `product_test_procedure.product_test_case_id` 같이 갱신. 구 값은 `remark`에 보존.
7. **정본 토폴로지 목록은 §5, 정책 결정은 §6에서만 가져온다. 추측 금지.** 목록에 없으면 `UNCLASSIFIED`로 두고 멈춰서 질문하라.
8. **한 번에 한 TASK.** 검증(④) 통과 못 하면 다음 TASK로 넘어가지 마라. 막히면 추측해서 진행하지 말고 보고.
9. 200줄+ 파일은 Edit 대신 python으로 처리, 편집 후 null 바이트 제거 + 문법 검증. 프런트 디버그는 `clientLog()`만(`console.log` 금지).
10. **파괴적 작업 금지 목록**: 기존 테이블/행 DROP·DELETE, PK 일괄 변경, AP→ROUTER 치환 등은 **반드시 백업 + dry-run + 승인** 없이는 실행하지 않는다.

---

## 1. 프로젝트 기본 정보

| 항목 | 값 |
|---|---|
| 위치 | **이 `HANDOVER.md`가 있는 폴더가 프로젝트 루트** (경로 하드코딩 금지) |
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
  - **불일치 331 재현은 역산 금지.** 진단 문서의 "⚠️ 331 재현 규칙" 4가지(분모=375 result행 단위 / `TEST_CASE-(...)-WIFI` 비탐욕 / 문자열 완전일치 / 정규화 전 비교)와 거기 첨부된 코드 스니펫을 **그대로** 써라. 다른 기준으로 세면 수치가 어긋난다.
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

### TASK 5 — AP→ROUTER 전역 치환 (DB 값 변경, dry-run) 🟡정책 확정됨
- **정책(확정)**: Q1 = **DB 값 전부 치환**. `1AP→1ROUTER`, `25AP→25ROUTER`. 표시만이 아니라 실제 UPDATE.
- **대상파일**: `app/services/topology_normalize.py` (신규) + `scripts/migrate_ap_to_router.py`
- **작업내용**:
  - 레거시 `{N}AP` → 정본 `{N}ROUTER` 치환 + 장비순서 규칙(HRK>HTR>HLM>HDR>HDC>HIIS, ROUTER 별도 토큰)으로 토큰 재정렬.
  - `normalize_combo(legacy) -> 정본 토폴로지` 함수 + 정본 목록(§5)에 없으면 `UNCLASSIFIED`.
  - **`1AP_1HDC` only(13건) → `1HDC_1ROUTER`** (Q5 확정, Q1 일관성).
  - 치환 대상: Result `[연결구성]`(remark), 구성행 release ID/표시, 관련 텍스트 전부.
  - 구 값은 remark에 `[구 연결구성]`으로 보존. dry-run / `--apply` + 자동 백업.
- **검증**: 치환 후 `[연결구성]`에 `AP` 토큰 0건, 375건 모두 정본 또는 UNCLASSIFIED.
- **위험도**: 중 (DB 텍스트 대량 변경). dry-run 먼저.

---

### TASK 6 — Case ↔ 연결구성 재매핑 스크립트 (dry-run) 🔴대규모
- **선행**: TASK 4·5 완료. (§6 정책 확정됨)
- **정책(확정)**:
  - **Q3 = Case ID는 토폴로지 유지** (일단). Case ID 규칙: `TEST_CASE-{topology}-{dut}-{scenario_slug}-{seq}`.
  - **Q4 = "더 긴 연결구성이 정본".** Case의 topology는 그 Case를 쓰는 Result들의 `[연결구성]` 중 **가장 긴(토큰 많은) 것**으로 확정. Case ID 대상(DUT)과 충돌해도 **긴 연결구성 우선**. 진짜 충돌(DUT가 연결구성에 없음)은 현재 0건.
  - 한 Case가 여러 연결구성에서 쓰이는 경우(60개 중 52개): **가장 긴 연결구성**을 그 Case의 정본 topology로 삼고, 나머지는 일단 그대로 둠. **추후 데이터 분리/수정은 사용자가 감수**(별도 작업).
- **대상파일**: `scripts/migrate_test_cases_by_topology.py` (신규)
- **작업내용**:
  - 각 Case별로 Result `[연결구성]`(TASK 5에서 ROUTER 정본화된 값) 수집 → **최장 연결구성 선택** → 그게 topology.
  - DUT는 기존 Case ID의 대상 토큰(예 HDC) 유지.
  - Case ID 재발급 = `TEST_CASE-{최장topology}-{dut}-{scenario}-{seq}`.
  - Case/Procedure ID 재발급 + Result/Procedure FK 일괄 UPDATE.
  - `remark`에 `[구 Case ID]`, `[선택 연결구성]`, `[후보 연결구성 목록]`, `[추론 출처]` 보존.
  - dry-run / `--apply` + 자동 백업.
- **검증**: `tests/test_traceability.py` — TC-PR01/PR02/PR03/RS02 통과 + "Case ID topology ∈ 정본목록(§5)" 신규 TC. 모든 Case의 topology가 정본 목록 또는 UNCLASSIFIED.
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

### TASK 10 — ID `TEST_` 접두 제거 (DB 값 변경, dry-run) 🔴파괴적
- **상세 스펙은 별도 파일 `handover_2026_06_08_20_15.md` 참조.**
- 요지: ID 값 **맨 앞 엔티티 접두만** 제거 — `TEST_CASE-→CASE-`, `TEST_RELEASE-→RELEASE-`, `TEST_ROUND-→ROUND-`, `TEST_CONFIG-→CONFIG-`, `TEST_CONFIG_DEF-→CONFIG_DEF-`. FK 컬럼 전부 동시 UPDATE.
- **함정**: `TEST_`가 값 중간/단어로 박힌 561건(`RESULT-TEST_REPORT_...`, `25AP_1TEST_TARGET`, `WIFI_TEST_1ST` 등)은 **절대 안 건드림**. 안전 규칙: `^TEST_(CASE|RELEASE|ROUND|CONFIG_DEF|CONFIG)-` 매칭 값만.
- **`TEST_REPORT*`는 ✅ 제외 유지 확정(2026-06-08), 건드리지 말 것** (재질문 금지 — 사유는 별도 파일 참조).
- **권장 위치**: TASK 6 이후 마지막. 위험도 높음(백업+dry-run+승인 필수).

### TASK 11 — Environment + Environment Definition 병합 (스키마 변경, dry-run) 🔴파괴적
- **상세 스펙은 별도 파일 `handover_2026_06_08_task11_env_merge.md` 참조.**
- 요지: envdef·env가 **완전 1:1·값 거의 동일** → **새 통합 테이블 `product_test_environment_unified`** 하나로 병합. 커스텀 시트로 보고/편집.
- ID는 기존 env `CONFIG-...` 재사용 → `run.environment_id` 값 변경 불필요.
- remark = **def 상세 + `[구 env 노트]` 덧붙임**(둘 다 보존). def 전용 8컬럼·env `captured_at` 살림.
- 구 테이블 2개·관리화면 2개는 삭제/통합. 위험도 높음(백업+dry-run+승인 필수).

### TASK 12 — Target + Target Definition 병합 (스키마 변경, dry-run) 🔴파괴적
- **상세 스펙은 별도 파일 `handover_2026_06_08_task12_target_merge.md` 참조.**
- 요지: targetdef(모델)·target(물리장비) 1:1 → **새 통합 테이블 `product_test_target_unified`**. 커스텀 시트로 노출.
- ID는 기존 target `TARGET-...` 재사용 → `run.target_id` 값 변경 불필요. remark = def 상세 + `[구 target 노트]`.
- 모델6컬럼·실측3컬럼 다 보존. 구 테이블·관리화면 2개 삭제/통합. 위험도 높음(백업+dry-run+승인).

### TASK 12-B — Target 병합 마무리 + 회귀 점검 (코드+소량 DB) 🟡
- **상세 스펙은 별도 파일 `handover_2026_06_08_task12b_finalize.md` 참조.**
- 요지: target 데이터는 `product_test_target_unified`로 옮겨졌으나 **models.py·구 테이블·화면 연결이 옛것** → 마무리.
- models.py에 `ProductTestTargetUnified` 추가·구 클래스 2개 제거, 서비스/대시보드 repoint, 구 빈 테이블 DROP, 화면 1개로 통합.
- ⚠️ 회귀: `GET /admin` 404(라우트 누락+파일 잘림) → **조치 완료**. 재발 방지: 큰 파일 편집 후 `py_compile`+`tail` 끝줄 확인 필수.

### TASK 13 — run → target 재연결 진단 (read-only) 🟢위험없음
- **상세 스펙은 `handover_2026_06_08_task12_target_merge.md` 참조.**
- 요지: run 62건이 target 1대만 가리키는 이상 원인 규명 + 올바른 DUT 재연결 **제안표만** 작성(`docs/run_target_relink_diagnosis_*.md`). 실제 UPDATE는 승인 후 별도.

### TASK 14 — release 고아/NULL-round 안전 정리 (dry-run) 🟡소량
- **상세 스펙은 별도 파일 `handover_2026_06_08_task14_release_cleanup.md` 참조.**
- 요지: **FALLBACK 고아 1건 삭제** + **TBD report용 release 3건에 round 채우기(삭제 아님)** → NULL-round release 0.
- ⛔ **round_legacy 4건은 절대 삭제 금지** — 후손 82 release(33건 run 보유)의 살아있는 백본. 스크립트에 화이트리스트(FALLBACK 1 + TBD 3)만 명시.

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

## 6. 정책 결정 (2026-06-08 확정 ✅)

| # | 질문 | 결정 |
|---|---|---|
| Q1 | AP→ROUTER 전역 치환 | ✅ **DB 값 전부 치환** (`1AP→1ROUTER`, `25AP→25ROUTER`) |
| Q2 | `1HDR_1CABLE_1HIIS-` 대시 | ✅ **오타.** 정식 = `1HDR_1CABLE_1HIIS` (대시 없음) |
| Q3 | Case 복제 단위 | ✅ **Case ID는 토폴로지 유지(일단).** `TEST_CASE-{topology}-{dut}-{scenario}-{seq}` |
| Q4 | 불일치 정본 기준 | ✅ **더 긴 연결구성이 정본.** Result `[연결구성]` 중 최장값을 채택. 추후 데이터 수정은 사용자 감수 |
| Q5 | `1AP_1HDC` only (13건) | ✅ **`1HDC_1ROUTER`** (Q1 일관성) |

**진단 보강 사실**: Case ID DUT 장비가 Result 연결구성에 아예 없는 **진짜 충돌은 0건**.
88% "불일치"는 Case ID가 짧은 토폴로지(예 `1AP_1HDC`)를 쓰고 Result가 더 긴 것(예 `1AP_1HDC_1HDR`)을 쓰는 **부분집합 관계**였음. → Q4 "긴 쪽 채택"으로 일괄 해소 가능.
한 Case가 2종+ 연결구성에서 쓰이는 경우 60개 중 **52개** (예: `25AP_1TEST_TARGET` Case 하나가 8종 연결구성에서 사용).

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
- §6 정책 5건 **모두 확정 완료** → TASK 4·5·6 착수 가능.
- TASK 5·6 핵심 규칙: **AP→ROUTER 전부 치환**, **Case topology = 그 Case Result들의 최장 연결구성**.
- 추적성 최종 목표(P0 증거 공백)는 **TASK 9**에서 해소.
