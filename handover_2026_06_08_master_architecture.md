# 목표 아키텍처 (MASTER) — 7 통합 탭 + Round까지 정합성 체인 (2026-06-08)

> 이 문서가 **최종 목표 구조의 정본**. 개별 TASK(11/12/14 등)는 모두 이 그림을 향한 단계다.
> 핸드오버 §0-1 수칙·§9 편집 규칙 적용.
> ⚠️ **2026-06-09: 아래 「v2 구조 결정」이 release/round/run 부분을 대체함.** v1 §1~7 중 Release 엔티티·Releases 탭 부분은 v2 기준으로 읽을 것.

---

## 0. 한 줄 요약 (caveman)

- 최종 화면 = **탭 7개**: `Configs > Targets > Cases > Procedures > Results > Releases > Rounds`.
- 탭 = 정본 테이블 1개씩. **모든 데이터가 Configs/Targets(입력)부터 최상위 Rounds까지 정합성으로 이어져야 함.**
- **Run은 탭 없음 → Results에 흡수.** Defect/Report 등은 필요한 것만 별도 탭.
- 작업도 이 순서대로: **Configs → Targets → Cases → Procedures → Results → Releases → Rounds.**

---

## 1. 7 통합 탭 정의

| 순번 | 탭명 | 정본 테이블 | 현재 테이블 | 정합성 작업 |
|---|---|---|---|---|
| 1 | **Configs** | environment(통합) | environment + environment_definition | TASK 11(병합) |
| 2 | **Targets** | target(통합) | target + target_definition | TASK 12(병합) + TASK 13(run→target 진단) |
| 3 | **Cases** | case | product_test_case | TASK 4(비정상 ID) + TASK 6(토폴로지 재매핑) |
| 4 | **Procedures** | procedure | product_test_procedure | case FK 정합(TC-PR01/02/03) |
| 5 | **Results** | result (+Run 흡수) | result + run | Run 흡수(아래 §2) + run/case/release 링크 검증 |
| 6 | **Releases** | release | product_test_release | TASK 14(고아 정리) + stage 정비(후속) |
| 7 | **Rounds** | round | product_test_round | round 정비(date_quality INFER, 고아 round) |

- 탭명은 짧게(`Configs` 등). 테이블 물리명은 `product_test_*` 유지 가능(탭 라벨만 매핑).

---

## 2. Run = Results 탭에 흡수 (탭 없음)

- Run은 Config·Target·Release를 Result에 이어주는 접합점. **별도 탭 안 만들고 Results 각 행에 컬럼으로 흡수.**
- Results 행에 표시할 흡수 컬럼(파생, run에서 조인):
  - `run_id`, `config_id`(=run.environment_id), `target_id`(=run.target_id),
    `release_id`(=run.release_id), `run_status`, `started_at/finished_at`.
- DB의 `product_test_run` 테이블은 **유지**(조인 소스). 화면 탭만 없음.

---

## 3. 보조 탭 (필요한 것만)

- **Defect**(15, 라이브): Results 하위/옆 탭으로. result_id로 연결.
- **Report**(8, 라이브): Releases/Rounds 옆 탭으로. release_id로 연결.
- Evidence / ProcedureResult / Snapshot / StatusTransition: 현재 **0건** → 데이터 생기면(TASK 9 편집·증거입력) 탭 추가.

---

## 4. 정합성 체인 (Round까지 이어지는 연결 키)

```
Configs ──(run.environment_id)──┐
Targets ──(run.target_id)───────┤
                                 Run ──(run.release_id)──→ Releases ──(test_round_id)──→ Rounds
                                  │                                          ▲(최상위)
                                  └──(result.run_id)──→ Results
Cases ──(result.case_id)──→ Results
Cases ──(case_id)──< Procedures
Defect ──(result_id)──→ Results        Report ──(release_id)──→ Releases
```

각 링크 검증 규칙(시트 정합성 배지 + 진단):
- **C1** 모든 run.environment_id ∈ Configs (고아 0)
- **C2** 모든 run.target_id ∈ Targets (고아 0) — ⚠️ 현재 run이 1개 target만 가리킴(TASK 13)
- **C3** 모든 result.run_id ∈ Run, run.release_id ∈ Releases
- **C4** 모든 result.case_id ∈ Cases, 그 case에 Procedure 존재(TC-PR01)
- **C5** 모든 release.test_round_id ∈ Rounds (NULL 0 — TASK 14에서 달성)
- **C6** Round = 최상위, 미연결 Round/Release 0

---

## 5. 작업 순서 (정합성 게이트)

순서: **Configs → Targets → Cases → Procedures → Results → Releases → Rounds.**
각 단계는 "그 탭의 정합성 작업 완료 + 위 체인 링크(Cn) 통과"를 게이트로 다음 단계 진입.

| 단계 | 게이트(통과 조건) | 선행 TASK |
|---|---|---|
| 1 Configs | 병합 완료, C1 고아 0 | TASK 11 |
| 2 Targets | 병합 완료, C2 진단(재연결은 승인 후) | TASK 12, 13 |
| 3 Cases | 비정상 ID 0, 토폴로지 정본, C4 일부 | TASK 4, 6 |
| 4 Procedures | TC-PR01/02/03 통과 | (Case 후속) |
| 5 Results | Run 흡수 컬럼, C3·C4 통과 | §2 + 시트 |
| 6 Releases | 고아 0, C5 NULL-round 0 | TASK 14 |
| 7 Rounds | 최상위 정합, C6 통과 | round 정비 |

---

## 6. 탭 구현 (시트 시스템 위에)

- 시트 탭 엔진 = **TASK 7(백엔드)·8(프론트+배지)·9(편집+status_transition)**.
- 위 7개 탭 + 보조 탭(Defect/Report)을 이 엔진으로 렌더.
- 각 탭은 자기 정본 테이블 바인딩 + 위 Cn 위반을 색배지로 표시 + 인라인 수정 시 diff·이력 기록.

---

## 7. 네이밍 규칙

- 탭 라벨: `Configs, Targets, Cases, Procedures, Results, Releases, Rounds` (복수형, 짧게).
- ID 접두: TASK 10 적용분 유지(`CASE-`, `RELEASE-`, `ROUND-`, `CONFIG-`, `TARGET-`). `TEST_REPORT*`는 손대지 않음(확정).
- 통합 테이블 물리명: `product_test_environment_unified`(Configs), `product_test_target_unified`(Targets) — 라벨과 매핑.

---

## 8. 메인 HANDOVER 반영
- `HANDOVER.md` 상단(§0 뒤)에 본 마스터 요약 + 이 파일 링크 추가.
- 개별 TASK(11/12/13/14, 7~9)는 모두 본 목표의 부분작업으로 정렬.

---

# v2 구조 결정 (2026-06-09 협의 확정)

> 박정훈님과 협의로 확정한 **계층·네이밍 정본.** 기존 release 기반 구조를 대체한다.
> 일부 "애매한 부분"은 아래 [열린 항목]에서 계속 협의.

## 계층 (Release 엔티티 폐기)

```
ROUND_{캠페인}
  └ RUN_{제품}_{버전}_{RC}_{토폴로지}
      └ RESULT_{제품}_{버전}_{RC}_{토폴로지}
          └ CASE_{캠페인}_{토폴로지}_{scenario}   (DUT는 토폴로지의 _ROUTER 앞 토큰으로 추론)
```

- **RC는 RUN id의 토큰으로만** 존재. `product_test_release` 엔티티 **폐기**(RC→RUN 흡수). → 7탭의 "Releases" 탭 사라짐.
- **라운드명엔 RC/run 같은 실행정보 금지.** ROUND = 순수 캠페인 분류.
- 제품·버전·RC·토폴로지 = **RUN/RESULT 레벨**. 캠페인 = **ROUND 레벨**.
- Run은 화면 탭 없음 → Results에 흡수(기존 결정 유지).

## ROUND 정본 분류 (캠페인)

1. `WIFI_1ST`
2. `WIFI_1ST_IMPROVE`
3. `WIFI_2ND`
4. `WIFI_2ND_IMPROVE`
5. `DOWNGRADE`
6. `WIFI_SMOKE` — 단독제품 WiFi smoke (양산)
7. `WBS` — 단독제품 + WBS (양산)
   - 차수(1차/2차…)는 **보류**: 필요해지면 RUN/날짜 또는 라운드 분리로 추후 반영.

## CASE 네이밍 (2026-06-09 변경 확정)

- `CASE_{campaign}_{topology}_{scenario}` **로 변경** (이전 {topology}_{dut}_{scenario} 폐기).
- **DUT는 별도 토큰 아님** — 토폴로지의 `_ROUTER` 바로 앞 토큰으로 추론 (예: `1HDC_1ROUTER` → DUT=HDC).
- scenario는 **Case 레벨**, Procedure는 그 Case의 실행 STEP.
- ⚠️ **함의(구현 시 처리)**: campaign이 Case에 들어가므로, 같은 scenario를 여러 캠페인에서 쓰면 **Case가 캠페인별로 복제**됨. 현재 60 case(캠페인 무관)를 campaign별로 재발급해야 함 → Case 마이그레이션 작업 필요.

## 8개 device-version 라운드 처리 (확정)

- `ROUND-HDC_9100_1_0_5A / HDR_9000_1_1_7E / HDR_9000_1_1_8 / HLM_9000_1_1_14B / HRK_9000A_1_1_0A / 1_1_1A / 1_1_1D / HTR_1A_1_1_8`
- 5개는 실데이터 0(빈 shell). 실제 device 시험은 캠페인 라운드(WIFI_1ST 5, WIFI_2ND 5, DOWNGRADE 1, HRK_1_1_1D 1) 밑 device_round에 있음.
- **결정(2026-06-09, 해석 A): 8개 device-version 라운드는 v2 위배(제품·버전은 ROUND 아닌 RUN). → 삭제하고 양산 캠페인 라운드 2개(`ROUND-WIFI_SMOKE`, `ROUND-WBS`)로 대체.**
- 단독제품 양산 데이터는 앞으로 `RUN_{제품}_{버전}_{RC}_{토폴로지}` 형태로 양산 라운드 밑에 채움. 제품·버전은 RUN 토큰으로만.
- ⚠️ 현재 양산/WBS/SMOKE 실데이터 거의 없음(빈 shell + WBS 2건/SMOKE case 1건) → 이번은 **정의/네이밍**이지 데이터 마이그레이션 아님.

## 진단으로 드러난 정리 대상 (배경)

- `RELEASE-HDR_9000_1_1_8-WIFI_1_1_1D` = 잘못 라벨된 빈 device_round (DUT는 HRK-9000A 1.1.1D, HDR은 보조장비). 
- `ROUND-HRK_9000A_1_1_1D` 안에 같은 캠페인이 3중 중복(device_round 빈 것 / WIFI_1_1_1D legacy / HRK_1_1_1D-RC1).
- → v2 구조로 재구성 시 자연 해소(제품·버전은 RUN으로, 캠페인은 ROUND로).

## [열린 항목] (계속 협의)

1. ✅ **[해결 2026-06-09] 양산 라운드 = 캠페인 2개** `ROUND-WIFI_SMOKE`, `ROUND-WBS`. 8개 device shell 삭제, 제품·버전은 RUN으로. 차수는 보류.
   - **[해결 2026-06-09] `WIFI_1_1_1D` 계열(HRK 1.1.1D) 캠페인 매핑**: WIFI 시험 → **`WIFI_SMOKE`**, WBS 변형(`WIFI_1_1_1D_WBS`) → **`WBS`**. 빈 잘못라벨 `HDR_9000_1_1_8-WIFI_1_1_1D` 트리 4건은 WIFI_SMOKE로 임시 remap 후 15-4에서 삭제. → 15-1 UNMAPPED 0.
2. ✅ **[설계완료 → TASK 15] release→run v2 마이그레이션.** 상세: `handover_2026_06_09_task15_v2_migration.md`. 선행: TASK 13 ✅완료. **AP→ROUTER는 result `[연결구성]` 레벨에서 이미 충족(TASK 6) → STEP D(run-PK 치환) 생략 확정(2026-06-09).** TASK 15가 토폴로지를 result `[연결구성]`(ROUTER 정본)에서 뽑아 run/result ID 전체 재작성.
3. ✅ **[해결 2026-06-09] RC = S/W 버전 풀네임의 일부** (별도 날짜 컬럼/정규화 X). 소프트웨어 풀네임 = `{버전} RC{n}` 한 문자열(예: `1.1.8D RC1`). 회사가 RC가 아니라 BUILD DATE로 관리하므로, RUN id의 version 토막에 **풀네임 문자열 그대로** 넣음. 원본 회차 유지·재번호 X.
4. ✅ **[해결 2026-06-09] WIFI_2ST = WIFI_2ND 오타 확정.** 정본 토큰은 `WIFI_2ND`.

## 다음 작업 (제안)
- 위 [열린 항목] 합의 → v2 마이그레이션 TASK 작성(dry-run) → codex.
- 그 전엔 기존 release 기반 데이터 **건드리지 않음**.


---

# v2 구조 결정 추가 (2026-06-09 b)

## RUN/RESULT id — version = S/W 풀네임
- RUN id = `RUN_{제품}_{S/W풀네임}_{토폴로지}`. **S/W풀네임 = 버전+RC를 한 덩어리**(예: `1_1_8D_RC1`).
- RC는 별도 토큰·날짜 컬럼 아님 — **풀네임 문자열의 일부**. (회사 S/W는 BUILD DATE로 관리 → 풀네임에 흡수)
- RESULT id = RUN 미러.

## RESULT 하위 연결 (확정)
```
RESULT_{제품}_{S/W풀네임}_{RC}_{토폴로지}
  ├ CASE      = result.case_id  (CASE_{campaign}_{topology}_{scenario}, DUT=ROUTER앞 토큰 추론)
  ├ CONFIG    = run.environment_id (Configs/환경)
  └ DEFECT    = defect.result_id
```
- **VALIDATION 엔티티 배제(확정).** 결함 개선 추적은 **기존 Defect 필드로 충분**:
  `result(결함발견) → defect(fixed_*/fix_description) → retest_product_test_result_id(재시험 결과) → closed_*`.
  (현재 retest_result_id 0/15 채워짐 → 채우는 건 데이터 작업, 스키마 변경 불필요)

## CASE 네이밍 — 최종 변경 (2026-06-09)
- **최종: `CASE_{campaign}_{topology}_{scenario}`** (예: `CASE_WIFI_1ST_1HDC_1ROUTER_AP_AUTH`).
- DUT는 토폴로지 `_ROUTER` 앞 토큰으로 추론 → DUT 토큰 불필요.
- (이전 {topology}_{dut}_{scenario} 결정은 이걸로 대체됨.)
