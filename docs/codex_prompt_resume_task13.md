# Codex 실행 프롬프트 — TASK 13 재생성부터 (v2 경로)

아래 "---" 블록을 codex에 그대로 전달.

---

너는 이 저장소(`product_test_tracing_system`)의 v2 구조 전환 작업을 이어서 한다. **TASK 13 진단 재생성부터.**

## 먼저 읽어라 (정본 순서)
1. `handover_2026_06_08_master_architecture.md` — **최종 목표 구조 정본.** 특히 「v2 구조 결정」 + 「v2 구조 결정 추가(b)」. (Release 엔티티 폐기 → ROUND→RUN→RESULT, CASE/RC/양산 규칙)
2. `HANDOVER.md` — §0-0 목표, §0-1 실수 방지 수칙, §4 TASK, §5 정본 토폴로지, §6 정책.
3. `handover_2026_06_08_task12_target_merge.md` — **TASK 13 정정 규칙(필독)**.
4. `handover_2026_06_09_task15_v2_migration.md` — TASK 15(최종 목표) 설계.

## 절대 규칙
- **한 번에 한 단계.** 각 단계 검증 통과 전 다음 금지.
- **DB는 WAL.** 조회 시 `PRAGMA wal_checkpoint(TRUNCATE)` 후 또는 읽기전용 복사본.
- **DB 변경은 dry-run → 사용자 승인 → 백업 → apply.** 승인 없이 apply 금지.
- **이 마운트에서 Edit 도구가 파일 끝을 자르는 사고 이력 있음.** 200줄+ 파일 수정은 python으로, **저장 후 즉시 `py_compile`/`node --check` + `tail`로 끝줄 확인.**
- 모호하면 멈추고 질문. 추측 금지.

## 단계별 작업

### STEP A — TASK 13 진단 **재생성** (read-only, 지금 실행)
- 기존 `docs/run_target_relink_diagnosis_20260609.md`는 **폐기됨**(DUT 규칙 오류). 재생성한다.
- **정정 규칙(필수, `..._task12_target_merge.md` TASK 13)**: **DUT = 토폴로지의 `_ROUTER` 바로 앞 토큰.**
  - `[구성]`/`[연결구성]`/run id에서 `{N}{MODEL}_{N}ROUTER` → ROUTER 앞 MODEL = DUT. (1HLM_25ROUTER→HLM 등)
  - `[Test 대상] 첫 줄=HRK` 규칙은 **쓰지 마라**(연결장비 목록임).
  - DUT 못 뽑고 result=0이면 무시. **HRK 기본값 금지.** HDR-7100P는 보조장비.
- 산출: run→target 매핑표(model/serial/sw, EXACT/INFER) + **기존 대비 바뀌는 run 표시**.
- **검증**: WIFI_2ND-25AP_1HDR*→HDR, -1HLM*→HLM, -1HTR*→HTR로 바뀌고, HRK는 1HRK_* run만. (대략 9 run/57 result가 HRK→타모델로 정정되어야 함)
- 결과를 새 `docs/run_target_relink_diagnosis_<오늘날짜>.md`로 저장하고 **사용자 검토 대기(멈춤).**

### STEP B — TASK 12-B 마무리 (선행 정리)
- `handover_2026_06_08_task12b_finalize.md` 따라: models.py에 `ProductTestTargetUnified` 추가·구 클래스 2개 제거, 서비스/대시보드 repoint, 구 빈 테이블 DROP, 화면 통합. dry-run→승인→apply.

### STEP C — TASK 13 **적용** (승인 후)
- STEP A 매핑표 사용자 승인 후, `run.product_test_target_id`를 정정 target으로 UPDATE. dry-run→승인→백업→apply.
- 검증: run.target_id distinct ≥ 5(HDC/HDR/HLM/HRK/HTR), FK 고아 0.

### STEP D — AP→ROUTER (run/result 토폴로지)
- run id·result `[연결구성]`의 `1AP/25AP` → `1ROUTER/25ROUTER` 정규화(§5·§6 규칙). dry-run→승인→apply.

### STEP E — TASK 15 v2 마이그레이션
- `handover_2026_06_09_task15_v2_migration.md` 전체 따라 실행. (release 폐기 → ROUND→RUN→RESULT, RUN id=`RUN_{제품}_{S/W풀네임}_{토폴로지}`, CASE=`CASE_{campaign}_{topology}_{scenario}` 재발급 포함)
- 최고 위험. 백업+dry-run 충분 리뷰+승인 필수.

## 보고 형식 (단계마다)
```
[STEP X] 제목
- 한 일 / 변경 파일 / 검증 결과(수치) / 위험·주의 / 다음(승인요청 여부)
```

## 시작
master 문서 읽음 1줄 확인 → **STEP A(TASK 13 재생성)** 부터. STEP A 끝나면 멈추고 검토 요청.
---
