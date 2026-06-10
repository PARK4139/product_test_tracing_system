# Codex 작업 프롬프트 — TASK 15-3부터 (v2 마이그레이션 이어받기)

아래 "---" 블록을 codex에 그대로 전달. (15-1·15-2 적용 완료, 15-3 충돌로 멈춤 상태)

---

너는 이 저장소(`product_test_tracing_system`, FastAPI+SQLite, Windows)의 v2 마이그레이션 **TASK 15-3부터** 이어서 한다.

## 먼저 읽어라 (정본 순서)
1. `handover_2026_06_08_master_architecture.md` — 최종 구조 정본(「v2 구조 결정」+「추가 b」). 특히 **§맨 끝 「15-2 충돌/legacy 해결 규칙」, 「15-3 충돌/TC-PR01 해소 규칙」**.
   (주의: 이 파일이 너무 길면, v2 관련 핵심은 `handover_2026_06_09_task15_v2_migration.md`에 다 정리돼 있다.)
2. `handover_2026_06_09_task15_v2_migration.md` — **TASK 15 상세 + 15-2/15-3 해소 규칙**. 이게 작업 정본.
3. `HANDOVER.md` §0-1 실수 방지 수칙 / §5 정본 토폴로지.

## 현재 상태 (적용 완료)
- TASK 1~14, TASK 11/12/12-B/13 완료.
- **TASK 15-1 적용 완료**: round 13→7 (`WIFI_1ST/WIFI_1ST_IMPROVE/WIFI_2ND/WIFI_2ND_IMPROVE/DOWNGRADE/WIFI_SMOKE/WBS`), release.test_round_id remap 25, 고아/NULL 0, integrity ok.
- **TASK 15-2 적용 안 함(dry-run만 확정)**: RUN/RESULT 신 ID 매핑 규칙 확정 — 충돌 0, 매핑 41 + MIGRATE_DROP 21, RESULT 375. (`docs/task15_2_dryrun.json`)
- **TASK 15-3 멈춤**: CASE 재발급 dry-run에서 신 case id 충돌 2건 + TC-PR01 1건 → **해소 규칙은 아래 §해소 확정에 있음.**
- DB 현재: integrity ok, round 7, release 215 / run 62 / result 375.

## ⚠️ 절대 규칙
1. **이 저장소는 편집 후 파일 끝에 NULL 바이트가 붙는 사고가 반복됨.** 모든 파일 편집 직후: `python -c "p=r'<file>';open(p,'wb').write(open(p,'rb').read().rstrip(b'\x00'))"` → `python -m py_compile <file>`(JS는 `node --check`) → `tail` 끝줄 확인. **시스템 python으로** 검증.
2. DB는 WAL. 조회 시 `PRAGMA wal_checkpoint(TRUNCATE)` 후 또는 `.db`+`-wal`+`-shm` 복사본(읽기전용).
3. **DB 변경 = dry-run 출력 → 사용자 승인 → 백업(`data/backups/`) → apply. 한 트랜잭션.** 승인 없이 apply 금지.
4. 정본(§5)·정책·마스터 그대로. 모호하면 멈추고 질문. 추측으로 데이터 합치거나 버리지 마라.
5. 각 서브스텝 끝에 정확한 수치 보고 + 멈춤(사용자 승인 대기).

## 해소 확정 (15-3 재개용)
### CASE 충돌 → 신 case id 끝에 **원본 seq 항상 부착**
- 신 case id = `CASE_{campaign}_{topology}_{scenario}_{seq}` (예: `CASE_WIFI_1ST_1HTR_1ROUTER_2HDR_WIFI_SERVER_RECONNECT_RECOVERY_002`).
- seq는 구 case id의 끝 번호(001/002…). **충돌 case 병합 금지**(절차 다른 별개 case다).
- procedure id = `{신_case_id}_STEP_{seq:03d}`. 신 case별 복제 유지.
### PLACEHOLDER TC-PR01 → 알려진 예외, 절차 날조 금지
- `PLACEHOLDER_EMPTY_CASE-WIFI_CONNECTIVITY_TEST_2026`(procedure 0, result 2)는 가짜 procedure 만들지 말고 유지.
- 신 case remark에 `[TC-PR01 예외: legacy placeholder, 절차 미정의]` 기록. 검증에서 이 1건은 화이트리스트.

## 서브스텝 (각각 dry-run → 승인 → apply)
- **15-3 재 dry-run**: 위 해소 규칙 반영 → 신 case id 충돌 **0** 확인. 보고: case 60→132, procedure 171→339, result.case_id/procedure.case_id 고아 0, TC-PR01 위반=1(placeholder 예외). → 승인 후 **15-3은 단독 apply 안 하고 15-4와 함께 일괄 apply**(아래).
- **15-4 일괄 apply (최고 위험)**: run/result/case/procedure 신 ID + **모든 FK 동시 갱신**(result.run_id, result.case_id, procedure.case_id, defect.result_id, report.release_id 등) + MIGRATE_DROP(빈 base run 21) 처리. 한 트랜잭션. ⛔ **dry-run 결과를 사용자가 검토·승인하기 전 절대 apply 금지.**
- **15-5 release 폐기 + 코드 동기화**: `product_test_release` 테이블 제거(run에 round 연결 보존 등 task15 문서대로), models.py/router/tracking/templates/JS에서 release 의존 제거. **FK drift도 함께 수정**: run의 environment FK를 `product_test_environment_unified` 참조로(현재 삭제된 `product_test_environment` 가리킴 — `foreign_key_check`로 확인).

## 검증 (15-4/15-5 apply 후)
- integrity_check ok, foreign_key_check 위반 0(FK drift 수정 포함).
- 모든 result.run_id ∈ 새 RUN, result.case_id ∈ 새 case, procedure.case_id ∈ 새 case, defect.result_id ∈ 새 result (고아 전부 0).
- RUN/RESULT/CASE id 규칙 100% 충족, AP 토큰 0.
- release 테이블 제거됨, 코드 `product_test_release` 잔존참조 0(grep).
- 건수: result 375 유지(MIGRATE_DROP은 빈 run만, result 손실 0), case 132, procedure 339.
- 앱 부팅 `GET /admin` 200.
- 편집 파일 NULL 0 + py_compile.

## 시작
task15 문서 읽음 1줄 확인 → **15-3 재 dry-run**(해소 규칙 반영, 충돌 0)부터. 결과 보고 후 멈춰 승인 대기. 15-4는 최고 위험이니 dry-run 결과를 반드시 사용자 검토 후 apply.
---
