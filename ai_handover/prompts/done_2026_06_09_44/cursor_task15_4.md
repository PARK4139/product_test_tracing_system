너는 이 저장소(`product_test_tracing_system`, FastAPI+SQLite, Windows)의 v2 마이그레이션 **TASK 15-4(일괄 apply)부터** 한다. 이건 전체 여정 중 **가장 위험한 단계**다.

## 먼저 읽어라 (정본)
1. `ai_handover/tasks/task15_v2_migration.md` — TASK 15 상세 + 15-2/15-3 해소 규칙(seq 항상 부착, PLACEHOLDER TC-PR01 화이트리스트, RC1/RC1_2, legacy UNCLASSIFIED 유지). **작업 정본.**
2. `ai_handover/master_architecture.md` 「v2 구조 결정」 + 「추가 b」.
3. `ai_handover/handover_main.md` §0-1 실수 방지 수칙 / §5 정본 토폴로지.
4. dry-run 산출물: `docs/task15_2_dryrun.json`, `docs/task15_3_dryrun.json`.

## 현재 상태 (적용 완료/확정)
- TASK 1~14, 11/12/12-B/13 완료.
- **15-1 적용 완료**: round 7개(WIFI_1ST/1ST_IMPROVE/2ND/2ND_IMPROVE/DOWNGRADE/WIFI_SMOKE/WBS), release.test_round_id remap, integrity ok.
- **15-2 확정(dry-run)**: RUN/RESULT 신 ID. 충돌 0, 매핑 41 + MIGRATE_DROP 21, RESULT 375. RC1/RC1_2 분리, legacy 3건 UNCLASSIFIED 유지.
- **15-3 확정(dry-run)**: CASE 재발급. 충돌 0, case 60→134, procedure 171→339, 고아 0, TC-PR01 1건(placeholder 화이트리스트).
- DB 현재: integrity ok, round 7 / release 215 / run 62 / result 375 / case 60 / procedure 171 / defect 15.

## ⚠️ 절대 규칙
1. **NULL 바이트 고질병**: 모든 파일 편집 직후 `python -c "p=r'<file>';open(p,'wb').write(open(p,'rb').read().rstrip(b'\x00'))"` → 시스템 python `py_compile`(JS `node --check`) → `tail` 끝줄 확인.
2. DB WAL: 조회 시 checkpoint 후 또는 복사본.
3. **dry-run → 사용자 승인 → 백업(`data/backups/`) → apply. 한 트랜잭션.** 승인 없이 apply 절대 금지.
4. 정본·정책·해소 규칙 그대로. 모호하면 멈추고 질문. **데이터 임의 병합/삭제 금지.**

## TASK 15-4 — 일괄 apply (run/result/case/procedure 신 ID + 전 FK + MIGRATE_DROP)
한 트랜잭션으로:
- run/result/case/procedure PK를 15-2·15-3 매핑표대로 신 ID로 UPDATE.
- **모든 참조 FK 동시 갱신**: `result.product_test_run_id`, `result.product_test_case_id`, `procedure.product_test_case_id`, **`defect.product_test_result_id`**(+ retest_product_test_result_id), `evidence.*`(0건이나 확인), `report` 연결.
- **MIGRATE_DROP 21**: result 0인 빈 base run 삭제 (result 손실 0 확인 — 이 run들엔 result 없음).
- 신 case remark에 PLACEHOLDER TC-PR01 예외 기록.
- 구 ID는 remark에 `[구 run id]`/`[구 result id]`/`[구 case id]` 보존.

### 15-4 dry-run 먼저, 보고 항목(정확한 수치):
- 변경 run/result/case/procedure 수, MIGRATE_DROP 21.
- **고아 검사(apply 시뮬레이션 후 전부 0)**: result→run, result→case, procedure→case, **defect→result**, report→(round/run).
- result 375 **손실 0**, case 134, procedure 339, defect 15 전부 신 result로 재연결.
- 신 ID PK 충돌 0, AP 토큰 0.
- **⛔ dry-run 결과를 사용자가 검토·승인하기 전 apply 금지.** (사용자가 별도 검증 게이트를 둘 수 있음 — 승인 받고 진행)

## TASK 15-5 — release 폐기 + 코드 동기화 (15-4 apply 성공 후, 별도 승인)
- `product_test_release` 테이블 제거. run에 round 연결 보존(`run.test_round_id` 등 task15 문서대로), 잃을 추적단서는 run.remark `[구 release]`로.
- **FK drift 수정**: `product_test_run`의 environment FK를 삭제된 `product_test_environment` → `product_test_environment_unified` 참조로 (테이블 재생성). `PRAGMA foreign_key_check` 위반 0 확인.
- 코드: models.py / routers(tracking_router 등) / templates / JS 에서 `product_test_release` 의존 제거 또는 run 기반 재작성. grep `product_test_release` 잔존 0.

## 검증 (apply 후)
- `integrity_check` ok, `foreign_key_check` 위반 0.
- 고아 전부 0(위 목록), result 375 / case 134 / procedure 339 / defect 15 유지.
- RUN/RESULT/CASE id 규칙 100%, AP 토큰 0.
- release 테이블 제거, 코드 `product_test_release` 잔존참조 0.
- 앱 부팅 `GET /admin` 200. 편집 파일 NULL 0 + py_compile.

## 시작
task15 문서 읽음 1줄 확인 → **15-4 dry-run**부터. dry-run 결과(특히 고아 0·defect 15 재연결·result 손실 0) 보고 후 멈춰 사용자 승인 대기. 15-4가 최고 위험이니 승인 없이 apply 절대 금지.
