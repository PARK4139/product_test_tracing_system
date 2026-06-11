# ai_handover — AI 작업 핸드오버 / 프롬프트 인덱스

이 디렉토리는 **AI 에이전트(codex / cursor / claude)** 가 이 저장소의 정합성·v2 마이그레이션 작업을 이어가기 위한 **정본 문서 + 킥오프 프롬프트** 모음이다.
사람이 작업을 새 AI에게 넘길 때, 아래 "지금 무엇을 줄까"를 보고 해당 프롬프트 파일의 본문을 그대로 전달하면 된다.

---

## 📁 구조

```
ai_handover/
├─ README.md                  ← (이 파일) 인덱스 + 현재 진행상황
├─ handover_main.md           ← 메인 핸드오버 (TASK 1~15 색인 + §0-1 실수 방지 수칙)
├─ master_architecture.md     ← 목표 구조 정본 (7탭 + v2: ROUND→RUN→RESULT, 네이밍/정책 확정)
├─ tasks/                     ← 개별 TASK 상세 스펙
│   ├─ task10b_strip_test_prefix.md   (TEST_ 접두 제거, TEST_REPORT 제외 확정)
│   ├─ task11_env_merge.md
│   ├─ task12_13_target_merge.md      (Target 병합 + run→target 재연결 진단 규칙)
│   ├─ task12b_finalize.md
│   ├─ task14_release_cleanup.md
│   └─ task15_v2_migration.md         (release 폐기 → ROUND→RUN→RESULT, 15-1~15-5)
├─ prompts/                   ← AI 에이전트 킥오프 프롬프트 (본문을 그대로 전달)
│   ├─ cursor_task15_4.md              ← ▶ 활성: TASK 15-4 일괄 apply부터
│   └─ done_2026_06_09_44/            ← 소임 끝난 프롬프트 보관
│       ├─ codex_task1_start.md            (TASK 1부터)
│       ├─ codex_resume_task12.md
│       ├─ codex_resume_task13.md
│       ├─ codex_resume_task15_3.md        (15-3 dry-run 확정 완료)
│       ├─ cursor_resume_stepD.md
│       └─ cursor_task15.md
└─ archive/
    └─ HANDOVER_20260604.md            (구 핸드오버, 보존용)
```

> **진단/dry-run 산출물은 `docs/`에 유지**: `docs/data_integrity_diagnosis_20260608.md`, `docs/run_target_relink_diagnosis_20260609.md`, `docs/task15_*_dryrun.json`.
> (스크립트가 `docs/`에 생성하므로 위치를 옮기지 않는다. 프롬프트/핸드오버가 이 경로로 참조함.)

---

## 🔖 AI 에이전트 공통 규칙 (모든 프롬프트에 반복됨)

1. **NULL 바이트 고질병**: 파일 편집 직후 trailing NULL 제거 + 시스템 python `py_compile`/`node --check` + `tail` 끝줄 확인.
2. **DB는 WAL**: 조회 시 `PRAGMA wal_checkpoint(TRUNCATE)` 후 또는 복사본(읽기전용).
3. **DB 변경 = dry-run → 사용자 승인 → 백업(`data/backups/`) → apply. 한 트랜잭션.** 승인 없이 apply 금지.
4. **정본은 `master_architecture.md` + 해당 `tasks/` 문서.** 모호하면 멈추고 질문. 데이터 임의 병합/삭제 금지.
5. PK 변경 시 참조 FK 동시 갱신. 구 값은 remark에 보존.

---

## ▶ 현재 진행상황 (2026-06-11 기준)

| 단계 | 상태 |
|---|---|
| TASK 1~14 | ✅ 적용 완료 |
| TASK 11/12/12-B/13 (Configs·Targets 병합, run→target 재연결) | ✅ 적용 완료 |
| TASK 15-1 (round 13→7 캠페인) | ✅ 적용 완료 |
| TASK 15-2 (RUN/RESULT 신 ID 매핑) | ✅ 적용 완료 (15-4에 포함) |
| TASK 15-3 (CASE 재발급) | ✅ 적용 완료 (15-4에 포함, case 60→134) |
| TASK 15-4 (일괄 apply) | ✅ **적용 완료** (2026-06-11). run 41 / result 375(손실0) / case 134 / procedure 339 / defect 15, integrity ok, 고아 0 |
| TASK 15-5 (release 폐기 + 코드 동기화 + FK drift 수정) | ✅ **적용 완료** (2026-06-11). release 테이블 제거, run FK→`product_test_environment_unified`, fk_check 0, integrity ok |
| TASK 15-6 (15-5 코드/테스트 동기화 마무리) | ✅ **완료** (2026-06-11, 코드/테스트만). release UI→round 전환, 고아 템플릿·옛 경로 제거, traceability 스크립트 v2화. `pytest 73 passed`, `GET /admin` 200, `product_test_release` 잔존 0 |

> ✅ **v2 마이그레이션 + 코드/테스트 동기화(15-1~15-6) 전부 완료.** 활성 프롬프트 없음. 백업: 15-4 `...task15_4_102809.db`, 15-5 `...task15_5_133636.db`.
> ⛔ 15-2/15-3/15-4/15-5 모두 apply 완료됨. **재 dry-run·재 apply 금지** (PK 충돌·손상 위험).

---

## ⚠️ 미해결/주의

- **FK drift**: `product_test_run`이 삭제된 `product_test_environment`를 FK로 선언(데이터 고아 아님). → TASK 15-5에서 `product_test_environment_unified` 참조로 수정.
- **마운트 읽기 불안정**: 일부 환경에서 live `data/*.db`가 torn-read로 malformed처럼 보일 수 있음(실제 손상 아님). 의심 시 `PRAGMA integrity_check` + 최신 백업과 대조.
- **15-4는 최고 위험 단계**: defect 15건의 result_id 재연결·result 375 손실 0·고아 0을 apply 전에 반드시 검증.
