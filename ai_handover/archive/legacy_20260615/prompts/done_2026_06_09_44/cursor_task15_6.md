너는 이 저장소(`product_test_tracing_system`, FastAPI+SQLite, Windows)의 **TASK 15-6 — 15-5 코드/테스트 동기화 마무리**를 한다. DB 마이그레이션(15-1~15-5)은 이미 끝났다. 이건 release 폐기 후 코드·테스트에 남은 잔재를 정리하는 작업이며 **DB 스키마는 건드리지 않는다.**

## 먼저 읽어라 (정본)
1. `ai_handover/tasks/task15_v2_migration.md` — TASK 15 상세. **작업 정본.**
2. `ai_handover/master_architecture.md` 「v2 구조 결정」.
3. `ai_handover/handover_main.md` §0-1 실수 방지 수칙.
4. 참고 산출: `docs/task15_5_apply_result.json`, `scripts/task15_5_code_sync.py`(미완성 — 무엇을 하려 했는지 확인).

## 현재 상태 (DB 적용 완료 — 절대 재apply 금지)
- 15-1~15-5 DB apply 완료. 현재 DB: integrity ok, run 41 / result 375 / case 134 / procedure 339 / defect 15 / report 8.
- **`product_test_release` 테이블은 폐기됨.** run은 `test_round_id`로 round에 연결. environment FK는 `product_test_environment_unified`.
- ⛔ **15-2/15-3/15-4/15-5 dry-run·apply를 다시 실행하지 마라.** DB 스키마/데이터는 이미 정답 상태다. 이번 작업은 **코드·테스트 파일만** 고친다.

## 문제 (release 폐기 후 코드/테스트 잔재 — git 기준 확인됨)
1. **`tests/test_traceability.py`** — pytest용이 아닌 CLI 스크립트인데 `tests/`에 있어 수집됨. 모듈 레벨에서 폐기된 `product_test_release`를 조회하고 실패 시 `sys.exit(2)` → **pytest 전체 수집이 죽는다(최우선 블로커).**
2. **`app/services/admin_product_test_ui_service.py`, `app/services/admin_qc_e2e_service.py`** — 옛 경로 `/admin/product-test-releases` 참조.
3. **테스트 4개** — 옛 경로 `/admin/product-test-releases` 호출: `tests/e2e_api/test_extra_regression_scenarios.py`, `tests/e2e_api/test_product_tracing_http_flows.py`, `tests/e2e_api/test_qc_db_truncate.py`, `tests/unit/test_admin_product_test_ui_service.py`.
4. **`app/templates/product_test_releases_admin.html`** — 렌더하는 코드 0인 고아 템플릿.
5. `scripts/task15_5_code_sync.py`는 `/admin/product-test-releases` → `/admin/product-test-rounds` 치환을 의도했으나 **라우터에 rounds 경로가 실제로 안 생겼다.** 라우트·템플릿·서비스·테스트가 서로 불일치.

## ⚠️ 절대 규칙
1. **NULL 바이트 고질병**: 모든 파일 편집 직후 `python -c "p=r'<file>';open(p,'wb').write(open(p,'rb').read().rstrip(b'\x00'))"` → 시스템 python `py_compile`(JS `node --check`) → `tail` 끝줄 확인.
2. **DB 스키마/데이터 변경 금지.** 이번 작업은 코드·테스트만. 굳이 DB를 읽어야 하면 복사본/체크포인트 후.
3. 정본 그대로. 모호하면 멈추고 질문. 데이터 임의 병합/삭제 금지.
4. 큰 코드 변경 전 어떤 방향(release UI를 round 기반으로 살릴지 vs 완전 제거할지)을 task15 문서로 정하고, 불명확하면 사용자에게 확인.

## TASK 15-6 — 할 일
먼저 방향 결정(정본 기준): release 화면/라우트를 **round 기반으로 전환**할지, **완전 제거**할지. task15 문서가 "release 폐기"이므로 기본은 제거 또는 round 기반 전환. 그에 맞춰 일관되게:
- **블로커 우선**: `tests/test_traceability.py`가 pytest를 죽이지 않게 한다. 폐기 테이블 조회를 ROUND→RUN→RESULT 체인으로 갱신하고, pytest 수집 대상에서 빼거나(예: `__main__` 가드, 파일명 변경, `tests/` 밖으로 이동, 또는 pytest ignore 설정) 모듈 레벨 `sys.exit` 제거.
- `app/services/admin_product_test_ui_service.py`, `admin_qc_e2e_service.py`의 `/admin/product-test-releases` 참조를 새 경로/로직으로 정리.
- 옛 경로를 쓰는 테스트 4개를 새 경로·새 기대값으로 갱신(또는 제거).
- `product_test_releases_admin.html`: 렌더처가 없으면 제거, round 기반으로 살릴 거면 라우트+템플릿+테스트를 일관되게 연결.
- 라우트/템플릿/서비스/테스트 사이의 release↔round 불일치를 전부 해소.

## 검증 (전부 통과해야 함)
- `uv run pytest tests/ -q` **전체 green** (`--ignore` 없이, 수집 에러 0).
- 앱 부팅 `uv run python run.py` → `GET /admin` 200.
- `grep -rn "product_test_release" app/` 잔존 0 (단, round의 `upstream_release_id`/`release_sequence`/`release_stage` 등 메타데이터는 정상이므로 제외).
- 옛 경로 `/admin/product-test-releases` 잔존 0 (의도적으로 남길 경우 사유 명시).
- 편집한 파일 NULL 0 + py_compile/node --check 통과.

## 시작
task15 문서 읽음 1줄 확인 → 방향(제거 vs round 전환) 1줄 제안 후 진행. 블로커(`test_traceability.py`)부터 잡아 pytest 수집이 되게 만들고, 전체 green까지. DB는 절대 재apply/스키마 변경 금지.
