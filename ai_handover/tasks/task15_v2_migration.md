# HANDOVER 추가 — TASK 15: release→run v2 구조 마이그레이션 설계 (2026-06-09)

> 마스터 `ai_handover/master_architecture.md` 「v2 구조 결정」의 [열린 항목 2] 구현 설계.
> §0-1 수칙·§9 편집 규칙. **대규모·파괴적 — dry-run→승인→백업 필수.**


> 🔧 **[발견 2026-06-11] FK drift**: `product_test_run`이 삭제된 `product_test_environment`를 FK로 선언(선언만 dangling, 데이터 고아는 아님 — run.env_id는 unified에 다 존재). TASK 11 env 병합 때 누락. **15-5 스키마 동기화에서 run 테이블 재구성 시 `product_test_environment_unified` 참조로 수정.** `foreign_key_check`로 검증.
> 🔁 2026-06-09 b 보강(마스터 참조): RUN id의 version 토막 = **S/W 풀네임(버전+RC 한 덩어리)**. RESULT 하위 = CASE/CONFIG/DEFECT(**VALIDATION 배제** — 결함개선 추적은 기존 Defect.retest_product_test_result_id 체인으로).

---

## 0. 한 줄 요약 (caveman)

- 목표: `product_test_release` 엔티티 폐기 → **ROUND→RUN→RESULT** 모델로 전환.
- RUN id = `RUN_{제품}_{버전}_{RC}_{토폴로지}`.
- **막힌 곳: 제품·버전이 0/62.** 모든 run이 단일 target만 가리켜서, **TASK 13 재연결 적용 전엔 RUN id 못 만듦.**
- 그래서 TASK 15는 **선행(TASK 13 적용 + AP→ROUTER) 끝난 뒤** 실행.

---

## 1. 현재 상태 진단 (2026-06-09)

| 항목 | 값 |
|---|---|
| release | 215 (RC 166 / run_session 28 / device_round 12 / TEST 5 / round_legacy 4) |
| run | 62 (clean `RUN-{camp}-{topo}-RC` 59 / legacy `RUN-TEST_REPORT...` 3) |
| result | 375 |
| round | 13 (→ 7 캠페인 정본으로 정리 예정) |

v2 RUN id 4토막 가용성:
- campaign 62/62 ✓ (run→release→round)
- topology 62/62 ✓ (단 **AP→ROUTER 정규화 필요** — run id 아직 `1AP/25AP`)
- RC 59/62 (legacy TEST_REPORT run 3개 예외)
- **product/version 0/62** ⚠️ (전부 `TARGET-HRK_9000A-9HA09A24I0014` 단일 → TASK 13 의존)

---

## 2. ⛔ 선행 조건 (이거 없이는 TASK 15 시작 금지)

1. **TASK 13 실제 적용** — run 62건을 올바른 target(제품·버전)으로 재연결.
   - 현재 진단만 됨(`docs/run_target_relink_diagnosis_20260609.md`, EXACT25/INFER37). UPDATE 미적용.
   - 이게 돼야 RUN id의 `{제품}_{버전}` 토막이 나옴.
2. ✅ **AP→ROUTER 이미 충족** — result `[연결구성]`은 TASK 6에서 ROUTER화 완료(AP 0건). **STEP D(run-PK 치환) 생략**. run id의 AP는 TASK 15가 ID를 새로 쓰므로 무관.
3. (권장) TASK 12-B 마무리 — target_unified 모델/구테이블 정리(제품·버전 조회 안정화).

---

## TASK 15 — v2 구조 마이그레이션 🔴초대규모·파괴적

### 변환 규칙
1. **ROUND**: round 테이블을 7 캠페인 정본으로 정리(WIFI_1ST/1ST_IMPROVE/2ND/2ND_IMPROVE/DOWNGRADE/WIFI_SMOKE/WBS). 8개 device-version 라운드 삭제(마스터 확정).
2. **RUN** (release의 run_session/RC/device_round 흡수):
   - 새 id `RUN_{제품}_{버전}_{RC}_{토폴로지}`.
   - 제품·버전 = TASK 13 재연결된 target에서.
   - RC = 현재 run id의 RC 토큰 **원본 유지**(마스터 [해결3]). `RUN_RC`/`RC` 이중용법은 RC잎 번호로 단일화.
   - 토폴로지 = **result `[연결구성]`(ROUTER 정본)에서 추출** (run id 아님). 한 run의 result들이 같은 `[연결구성]` 가짐. result 없는 빈 base run은 마이그레이션 제외/정리.
   - run.test_round_id(캠페인)로 ROUND 직접 연결(중간 release 제거).
3. **RESULT**: `RESULT_{제품}_{버전}_{RC}_{토폴로지}` (RUN 미러) + result 고유(case_id, status, [연결구성]). result.run_id는 새 RUN id로 갱신.
4. **CASE**: 네이밍 변경 `CASE_{campaign}_{topology}_{scenario}` (DUT=토폴로지 _ROUTER 앞 토큰 추론). campaign이 들어가므로 **캠페인별 Case 복제 필요**(현 60건 campaign-무관 → campaign별 재발급). result.case_id FK 동시 갱신. ⚠️ 별도 Case 마이그레이션 sub-step.
5. **release 엔티티 폐기**: `product_test_release` 테이블 제거. run이 보존하던 release_id/upstream 트리 정보 중 필요한 것(round 연결)은 run.test_round_id로 이관, 나머지(remark의 추적 단서)는 run.remark에 `[구 release]`로 보존.

### 엣지 케이스
- **legacy TEST_REPORT run 3개**: RC/topology 파싱 불가 → 개별 처리(remark의 CFG/리포트명에서 추출 시도, 안되면 UNCLASSIFIED + 보고).
- **HRK_9000A_1_1_1D 3중 중복**(device_round 빈 것/WIFI_1_1_1D legacy/HRK_1_1_1D-RC1): v2 전환 시 RUN 2건(실데이터)만 남고 빈 구조 자연 소멸.
- **report.release_id**: release 폐기되므로 report를 round 또는 run으로 재연결(8건). 매핑 규칙 필요.
- **defect.result_id**: result id가 바뀌면 defect FK 동시 갱신(15건).

### 작업 순서 (codex)
1. 선행조건 3개 충족 확인 — 안 되면 멈추고 보고.
2. read-only: 62 run × (제품·버전·RC·토폴로지) 매핑표 dry-run 출력. UNCLASSIFIED 0 목표.
3. 신 RUN/RESULT id 생성 + FK(result.run_id, defect.result_id, report) 동시 갱신 미리보기.
4. 승인 → 백업 → apply (한 트랜잭션). release 테이블 제거는 **맨 마지막**.
5. 코드 동기화: models.py(release 모델 제거, run에 test_round_id), tracking_router/서비스/템플릿/JS에서 release 의존 제거 또는 run 기반 재작성. grep: `product_test_release`.

### 검증
- 모든 result.run_id ∈ 새 RUN (고아 0), defect.result_id 고아 0.
- 모든 run.test_round_id ∈ 7 캠페인 round.
- RUN id가 `RUN_{제품}_{버전}_{RC}_{토폴로지}` 규칙 100% 충족, AP 토큰 0.
- release 테이블 제거됨, 코드에 release 잔존참조 0.
- 앱 부팅 + 추적/시트 화면 정상.

### 위험도
**최고(파괴적·광범위).** 백업 필수, dry-run 충분히 리뷰, 한 트랜잭션, 코드 변경 별도 커밋. 실패 시 롤백.

---

## 3. 마스터 [열린 항목] 상태
- 1 ✅ 양산 라운드 / 2 (본 문서=설계 완료, 선행 의존) / 3 ✅ RC 원본유지 / 4 ✅ 2ND 오타.
- **TASK 15는 TASK 13 적용·AP→ROUTER 후 실행.** 그 전엔 release 데이터 건드리지 않음.

---

## 15-2 충돌/legacy 해결 규칙 (2026-06-11 확정)

### PK 충돌 (4건) → 재시행 표시 보존
- 원인: WIFI_2ND의 `-RC1`와 `-RC1-2`(같은 구성 재시행, 둘 다 result 보유: 8/14, 6/7 등)가 같은 신 RUN id로 수렴.
- 해결: **RC 토큰에 재시행 표시 보존**. 구 run id의 RC 토막 그대로 → `RC1` / `RC1-2`를 ID용으로 `RC1` / `RC1_2`(대시→언더스코어)로. 신 RUN id가 유일해짐.
- 즉 RC 토큰 = 구 run id에서 토폴로지 뒤 전체(`RC1`, `RC1_2`, `RC2`, `RC5`…). 원본 회차+재시행 모두 보존.

### legacy TEST_REPORT 3건 (4 result) → 유지
- 토폴로지 UNCLASSIFIED(`TBD`/`VARIOUS_CONNECTIONS`/`25AP_` → 정본 파싱 불가), RC 토큰 없음.
- **유지 확정**: 신 ID 생성하되
  - **버전 = round에서** (target sw 아님): `ROUND-WIFI_SMOKE`였던 HRK_1_1_1D→`1_1_1D`, DOWNGRADE(HRK_1_1_0A)→`1_1_0A`, WIFI_2ND(HRK_1_1_1A)→`1_1_1A`. (target_unified엔 HRK가 1.1.1A 하나뿐이라 target sw 쓰면 틀림)
  - **RC = `RC1` 합성**, **토폴로지 = `UNCLASSIFIED`**.
  - 예: `RUN_HRK_9000A_1_1_1D_RC1_UNCLASSIFIED`. 4 result 보존, 나중에 수동 분류.

### 버전 소스 일반 규칙 (명확화)
- 일반 run: 버전 = `target_unified.software_version` (DUT 실측 sw. campaign run은 이게 round 버전과 일치).
- **예외(legacy 3건)**: round가 버전을 인코딩하고 target sw와 다르면 → **round 버전 우선**.

---

## 15-3 충돌/TC-PR01 해소 규칙 (2026-06-11 확정)

### CASE 충돌 (2건) → 신 case id에 원본 seq 보존
- 원인: 신 ID `CASE_{campaign}_{topology}_{scenario}`에서 **seq(001/002)와 DUT가 빠져**, 같은 campaign·topology·scenario인데 seq만 다른 두 case가 수렴.
  - 예: `CASE-1HTR_1ROUTER_2HDR-HTR-WIFI_SERVER_RECONNECT_RECOVERY-001` / `-002` (절차 내용 다름, 별개 case).
- **해결: 신 case id 끝에 원본 seq 유지** → `CASE_{campaign}_{topology}_{scenario}_{seq}` (예: `..._RECOVERY_001`, `..._RECOVERY_002`).
  - 충돌 시에만이 아니라 **항상 seq 부착**(결정적·단순). procedure도 신 case별 복제 유지.
  - **병합 금지** — 절차가 다른 별개 case다.

### PLACEHOLDER TC-PR01 (1건) → 알려진 예외, 절차 날조 금지
- `PLACEHOLDER_EMPTY_CASE-WIFI_CONNECTIVITY_TEST_2026`: procedure 0, legacy result 2.
- **해결: 가짜 procedure 만들지 않는다.** 신 case(`CASE_WIFI_SMOKE_UNCLASSIFIED_WIFI_CONNECTIVITY_TEST_2026`) 유지, result 2건 보존.
- TC-PR01 위반 1건은 **이 placeholder에 한해 알려진 예외로 수용**(remark에 `[TC-PR01 예외: legacy placeholder, 절차 미정의]` 기록). 검증에서 이 1건은 화이트리스트 처리.

### 결과(예상) — 충돌 0
- 신 case 수: seq 부착으로 132 유지(충돌 0). procedure 339.
- result.case_id / procedure.case_id 고아 0. TC-PR01 위반 = 1(placeholder, 예외 허용).
