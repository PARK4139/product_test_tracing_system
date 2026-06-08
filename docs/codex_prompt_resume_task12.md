# Codex 실행 프롬프트 — TASK 12부터 재개

아래 "---" 블록을 codex에 그대로 전달. (TASK 1~11은 완료 가정)

---

너는 이 저장소(`product_test_tracing_system`)의 정합성/구조 정돈 작업을 **TASK 12부터** 이어서 한다.

## 먼저 읽어라 (정본 순서)
1. `handover_2026_06_08_master_architecture.md` — **최종 목표 구조(7 통합 탭 + Round까지 정합성 체인). 모든 작업이 이걸 향함.**
2. `HANDOVER.md` — §0-0 목표요약, §0-1 실수 방지 수칙, §4 TASK 순번, §5 정본 토폴로지, §6 정책.
3. 개별 스펙: `handover_2026_06_08_task12_target_merge.md`(TASK 12·13), `handover_2026_06_08_task14_release_cleanup.md`(TASK 14).

## 진행 상태
- TASK 1~10: 완료.
- TASK 11(Configs 병합): 사용자가 진행함. **단 실제 DB에 반영됐는지 먼저 확인**(아래 0번). 안 됐으면 보고하고 멈춰라.
- 이번에 할 것: **TASK 12 → 13 → 14**, 그다음 시트 시스템 **TASK 7 → 8 → 9**.

## 절대 규칙 (위반 금지)
- **한 번에 한 TASK.** §4 순서대로. 현재 TASK의 "검증"을 통과하기 전 다음으로 넘어가지 않는다.
- **DB는 WAL 모드.** 조회 시 `PRAGMA wal_checkpoint(TRUNCATE)` 후 읽거나 `.db`+`-wal`+`-shm` 복사본(읽기 전용)에서 한다.
- **DB 변경(TASK 12·14)은 절대 자동 실행 금지.** ① dry-run 출력 → ② 사용자 승인 → ③ 승인 후 자동 백업 + `--apply`. 승인 없이 apply = 실패.
- **PK 변경/병합 시 참조 FK 동시 처리.** 병합은 기존 ID 재사용(run FK 값 유지) 원칙.
- **파괴적 작업 화이트리스트로만.** TASK 14는 FALLBACK 1 + TBD 3만, ⛔ **round_legacy 4건 절대 삭제 금지**(살아있는 백본).
- **정본 토폴로지(§5)·정책(§6)·목표구조(master) 그대로 따른다. 추측 금지.** 모호하면 멈추고 질문.
- 200줄+ 파일은 python으로, 편집 후 null 바이트 제거 + 문법 검증. 프런트 디버그는 `clientLog()`만.

## 0. 시작 전 상태 확인 (read-only, 필수)
- TASK 11 반영 여부: `product_test_environment` 통합/`_definition` 제거(또는 `product_test_environment_unified` 존재) 확인.
  - **반영 안 됐으면**(environment + environment_definition 둘 다 존재) → "TASK 11 미반영" 보고하고 멈춤. 사용자 지시 대기.
- TASK 12 대상 확인: target/targetdef 1:1(6:6), `run.target_id` distinct. (distinct=1 이상은 **정상 예상** → TASK 13에서 처리)

## 이번 범위 & 게이트
- **TASK 12** Targets 병합(파괴적) → dry-run → 승인 → apply. 게이트: run FK 고아 0, 모델6+실측3 보존.
- **TASK 13** run→target 재연결 **진단만**(read-only). 산출물 `docs/run_target_relink_diagnosis_*.md`. (실제 UPDATE는 승인 후 별도)
- **TASK 14** release 고아/NULL-round 안전 정리(소량) → dry-run → 승인 → apply. 게이트: NULL-round 0, round_legacy 무손상.
- 이후 **TASK 7→8→9** 시트 시스템(7 통합 탭 + Defect/Report 보조 탭, Run은 Results에 흡수).

## TASK 보고 형식 (끝낼 때마다)
```
[TASK N] 제목
- 변경 파일 / 한 일 / 검증 결과(수치) / 위험·주의 / 다음(승인요청 여부)
```

## 시작
master 문서를 읽었음을 1줄 확인 → **0번 상태 확인** → 이상 없으면 **TASK 12** 부터.
---
