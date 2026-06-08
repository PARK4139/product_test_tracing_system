# 목표 아키텍처 (MASTER) — 7 통합 탭 + Round까지 정합성 체인 (2026-06-08)

> 이 문서가 **최종 목표 구조의 정본**. 개별 TASK(11/12/14 등)는 모두 이 그림을 향한 단계다.
> 핸드오버 §0-1 수칙·§9 편집 규칙 적용.

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
