# HANDOVER 추가 — ID `TEST_` 접두 제거 (2026-06-08 20:15)

> 본 HANDOVER(`ai_handover/handover_main.md`)의 **TASK 10**으로 추가. §0-1 실수 방지 수칙·§9 편집 규칙 그대로 적용.
> 근거 스캔: 2026-06-08 DB(`data/product_test_tracking_system.db`, WAL checkpoint 후).

---

## 0. 한 줄 요약 (caveman)

- ID 앞에 붙은 **`TEST_`가 중복이라 보기 싫음.** `TEST_CASE-*` → `CASE-*` 처럼 떼고 싶음.
- **모든 테이블·FK까지** 같이 바꿔야 함.
- **함정**: `TEST_`가 값 **중간**에도 박혀 있음(561건). 무지성 전역 치환하면 **데이터 깨짐**.
- 그래서: **"ID 값 맨 앞의 엔티티 접두"만** 떼고, **중간 TEST_는 절대 안 건드림.**

---

## TASK 10 — ID `TEST_` 접두 제거 (DB 값 변경, dry-run) 🔴대규모·파괴적

### 목적
ID 값 시작에 붙은 엔티티 타입 접두 `TEST_`를 제거. 예) `TEST_CASE-...` → `CASE-...`. 참조 FK·하위 ID까지 일괄.

### 권장 실행 위치
- **TASK 6(Case 재매핑) 완료 후 마지막에 실행** 권장. (TASK 4·5·6이 ID를 다시 발급하므로, 그 뒤에 한 번에 접두만 떼면 재작업 없음.)
- 만약 먼저 실행하면 TASK 4·5·6의 ID 예시·생성 규칙을 새 접두로 바꿔야 함.

### 바꿀 대상 (값 **맨 앞** 엔티티 접두만)
| 구 접두 | 신 접두 | 나타나는 컬럼 (FK 포함, 전부 동시 UPDATE) |
|---|---|---|
| `TEST_CASE-` | `CASE-` | `product_test_case.product_test_case_id`, `product_test_procedure.product_test_procedure_id`(값이 `TEST_CASE-...-STEP...`), `product_test_procedure.product_test_case_id`, `product_test_result.product_test_case_id` |
| `TEST_RELEASE-` | `RELEASE-` | `product_test_release.product_test_release_id`, `product_test_release.upstream_release_id`(값이 `TEST_RELEASE-`인 것만), `product_test_report.product_test_release_id`, `product_test_run.product_test_release_id` |
| `TEST_ROUND-` | `ROUND-` | `product_test_round.test_round_id`, `product_test_release.test_round_id` |
| `TEST_CONFIG-` | `CONFIG-` | `product_test_environment.product_test_environment_id`, `product_test_run.product_test_environment_id` |
| `TEST_CONFIG_DEF-` | `CONFIG_DEF-` | `product_test_environment.product_test_environment_definition_id`, `product_test_environment_definition.product_test_environment_definition_id` |

> 참고 건수(스캔): TEST_CASE 계열 ≈ 719행, TEST_RELEASE 계열 ≈ 482행, TEST_ROUND 계열 225행, TEST_CONFIG/_DEF 계열 ≈ 86행.
> `product_test_target*`는 이미 `TARGET-`/`TARGET_DEF-` 라 **대상 아님**.

### ⛔ 절대 건드리지 말 것 (TEST_가 값 중간/단어 = 치환 지뢰, 561건)
값 맨 앞이 아닌 `TEST_`, 또는 "TEST"가 단어로 박힌 것은 **그대로 둔다**:
- `RESULT-TEST_REPORT_...` (Result ID 안에 리포트명 박힘) — **442건**
- 환경/리포트명 안 `..._TEST_CONFIG...`, `TEST_REPORT_...` — **85건**
- `DEPRECATED_TEST_CASE-...`, `PLACEHOLDER_EMPTY_CASE-...` (앞에 `DEPRECATED_`/`PLACEHOLDER_`가 더 있음) → **TASK 4에서 별도 처리** — **34건**
- `25AP_1TEST_TARGET` (Case ID 중간의 `_TEST_TARGET`)
- `WIFI_TEST_1ST`, `..._TEST_2026`, `..._TEST_260526` 등 "TEST"가 캠페인/리포트 단어인 것
- `remark` 텍스트 안의 위 참조 문자열

### 안전 치환 규칙 (이 정규식으로만)
값 전체가 아래 패턴으로 **시작**할 때만 맨 앞 `TEST_` 제거:
```
^TEST_(CASE|RELEASE|ROUND|CONFIG_DEF|CONFIG)-
```
- `CONFIG_DEF`를 `CONFIG`보다 **먼저** 매칭(순서 중요, 안 그러면 `CONFIG`가 `CONFIG_DEF`를 먼저 먹음).
- 치환은 `re.sub(r'^TEST_', '', value)` 를 **위 패턴에 매칭된 값에만** 적용.
- `remark`/`actual_result`/`test_objective` 등 **자유 텍스트 컬럼은 치환 안 함** (지뢰 다수).

### `TEST_REPORT` 는 ✅ 제외 유지 확정 (2026-06-08) — 건드리지 말 것
- **결정: TASK 10에서 `TEST_REPORT*`는 손대지 않는다. 그대로 둔다.** (codex 재질문 금지)
- 이유(깨질 위험 큼):
  1. **접두가 아니라 ID 중간 토막.** result PK 375건 전부 `RESULT-TEST_REPORT_...` 형태 — `TEST_REPORT_...`는 "원본 리포트 이름". result 진짜 접두는 `RESULT-`.
  2. **한 값에 TEST 2번**: `RESULT-TEST_REPORT_WIFI_TEST_1ST_260430` — 뒤 `WIFI_TEST_1ST`의 TEST는 "시험" 단어. 무지성 치환 시 같이 깨짐.
  3. **자유텍스트(remark) 참조는 FK cascade 불가** → PK만 바뀌면 고아 참조 발생.
  4. **이 리포트명이 엑셀 원본으로 가는 추적 링크 그 자체** → 망가뜨리면 추적성 목적 깨짐.
- 정말 바꾸려면 "리포트명 정규화"를 **별도 TASK**로, 자유텍스트까지 추적해 손봐야 함. 현재는 **진행 안 함.**

### 작업 내용 (codex)
1. **사전 스캔(read-only)**: TASK 1 진단 스크립트 방식으로, 위 5개 접두에 매칭되는 컬럼·건수를 실제로 열거해 출력. (하드코딩 말고 실제 DB로 확인)
2. **dry-run**: 각 컬럼별 `구값 → 신값` 변환 미리보기 + 충돌 검사(신 ID가 기존 다른 행과 겹치는지 PK 중복 검사).
3. **무결성 가드**: 치환 후 §3 FK 고아 검사 0건 유지되는지 dry-run에서 시뮬레이션.
4. **사용자 승인 → 백업 → `--apply`**: FK 컬럼까지 트랜잭션으로 **한 번에** UPDATE.
5. `models.py`/코드/템플릿/JS에 `TEST_CASE-` 등 **하드코딩 문자열** 있으면 같이 갱신(grep: `TEST_CASE-|TEST_RELEASE-|TEST_ROUND-|TEST_CONFIG`). 단 자유 텍스트/주석 라벨은 신중히.

### 대상파일
- `scripts/migrate_strip_test_prefix.py` (신규)
- 코드 내 하드코딩 갱신: `app/routers/*.py`, `app/static/js/tracking-*.js`, 템플릿 등 (grep 결과 기준)

### 검증
- 치환 후: 위 5개 ID 컬럼에서 `LIKE 'TEST\_%'`(시작) **0건**.
- **지뢰 보존 확인**: `RESULT-TEST_REPORT_...` 442건, `_TEST_TARGET`, `WIFI_TEST_1ST` 등 **건수 변화 없음**.
- FK 고아 0건 유지(§3 10종 검사).
- PK 중복 0건.
- 앱 부팅 + 추적 화면 정상.

### 위험도
**높음(파괴적).** PK·FK 동시 변경 + 하드코딩 의존. 반드시 백업 + dry-run 리뷰 + 승인 후 apply. 한 트랜잭션으로 처리(중간 실패 시 롤백).

---

## 메인 HANDOVER 반영 메모
- `ai_handover/handover_main.md` §4 TASK 목록 끝에 **TASK 10** 으로 편입(권장 위치: TASK 6 이후).
- §0-1 수칙 5(dry-run→승인→백업)·6(FK 동시 UPDATE)·10(파괴적 작업 금지)이 그대로 적용됨.
