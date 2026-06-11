너는 이 저장소(`product_test_tracing_system`, FastAPI+SQLite, Windows)의 v2 마이그레이션 **TASK 15-5**를 한다. 15-4까지는 이미 끝났다. 15-5는 release 테이블 폐기 + FK drift 수정 + 코드 동기화다.

## 먼저 읽어라 (정본)
1. `ai_handover/tasks/task15_v2_migration.md` — TASK 15 상세. **작업 정본.**
2. `ai_handover/master_architecture.md` 「v2 구조 결정」 + 「추가 b」.
3. `ai_handover/handover_main.md` §0-1 실수 방지 수칙 / §5 정본 토폴로지.

## 현재 상태 (apply 완료 기준 — 절대 재apply 금지)
- TASK 1~14, 11/12/12-B/13, 15-1 적용 완료.
- **15-2/15-3/15-4 apply 완료**: run/result/case/procedure 신 ID + 전 FK 일괄 갱신됨.
- **현재 DB**: integrity ok, run 41 / result 375 / case 134 / procedure 339 / defect 15 / report 8 / release 215. 고아 전부 0, AP 토큰 0.
- 백업: `data/backups/2026-06-11/product_test_tracking_system.task15_4_102809.db`, 결과: `docs/task15_4_apply_result.json`.
- ⛔ **15-2/15-3/15-4를 다시 dry-run 하거나 다시 apply 하지 마라. 재실행 시 PK 충돌·데이터 손상.** 15-5만 한다.

## ⚠️ 절대 규칙
1. **NULL 바이트 고질병**: 모든 파일 편집 직후 `python -c "p=r'<file>';open(p,'wb').write(open(p,'rb').read().rstrip(b'\x00'))"` → 시스템 python `py_compile`(JS `node --check`) → `tail` 끝줄 확인.
2. DB WAL: 조회 시 checkpoint 후 또는 복사본.
3. **dry-run → 사용자 승인 → 백업(`data/backups/`) → apply. 한 트랜잭션.** 승인 없이 apply 절대 금지.
4. 정본·정책 그대로. 모호하면 멈추고 질문. **데이터 임의 병합/삭제 금지.**

## TASK 15-5 — release 폐기 + FK drift + 코드 동기화
한 트랜잭션(DB 부분)으로:
- `product_test_release` 테이블 제거. run의 round 연결 보존(`run.test_round_id` 등 task15 문서대로). 잃을 추적단서는 run.remark `[구 release]`로 보존.
- **FK drift 수정**: `product_test_run`의 environment FK를 삭제된 `product_test_environment` → `product_test_environment_unified` 참조로 (테이블 재생성). `PRAGMA foreign_key_check` 위반 0 확인.
- 코드: models.py / routers(tracking_router 등) / templates / JS 에서 `product_test_release` 의존 제거 또는 run 기반 재작성. grep `product_test_release` 잔존 0.

### 15-5 dry-run 먼저, 보고 항목:
- release 제거 영향(참조하던 report/run 처리), run.test_round_id 보존 확인.
- FK drift 수정 후 `foreign_key_check` 위반 0 시뮬레이션.
- 코드 grep `product_test_release` 잔존 위치 목록.
- ⛔ dry-run 결과를 사용자가 검토·승인하기 전 apply 금지.

## 검증 (apply 후)
- `integrity_check` ok, `foreign_key_check` 위반 0.
- run 41 / result 375 / case 134 / procedure 339 / defect 15 유지(손실 0).
- release 테이블 제거됨, 코드 `product_test_release` 잔존참조 0.
- 앱 부팅 `GET /admin` 200. 편집 파일 NULL 0 + py_compile.

## 시작
task15 문서 읽음 1줄 확인 → **15-5 dry-run**부터. dry-run 결과 보고 후 멈춰 사용자 승인 대기. 승인 없이 apply 절대 금지. 15-2/15-3/15-4는 절대 재실행 금지.
