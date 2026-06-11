너는 이 저장소(`product_test_tracing_system`, FastAPI+SQLite, Windows)의 **Procedures 개편**을 한다. 두 단계다: (A) DB 데이터+스키마 정리, (B) UI 개편. **(A)는 DB 변경이므로 dry-run→사용자 승인→백업→apply 절차를 반드시 지킨다.**

## 먼저 읽어라
1. `ai_handover/tasks/task15_v2_migration.md`, `ai_handover/handover_main.md` §0-1 — 규칙/정책.
2. `app/models.py` — `ProductTestProcedure`(236행~), `ProductTestCase`(211행~).
3. `app/templates/product_test_procedures_admin.html` — Procedures 등록폼(5행)·목록(6행).
4. `app/routers/admin_router.py` (procedure create/update: 588/602/622~639행), `app/routers/tracking_router.py` (procedure 조회: 768/780행대), `app/services/*`.

## 현재 구조 (확인됨)
- `product_test_procedure` 필드: `procedure_sequence`, `procedure_action`(수행절차, NOT NULL), `expected_result`(기대결과, nullable), `acceptance_criteria`(합격기준, NOT NULL), …
- 목록 컬럼(6행): ID · Case ID · Seq · Action · **Expected Result** · Acceptance Criteria · Evidence · Status · Remark
- ⚠️ **함정**: `expected_result`는 `ProductTestProcedure`(256행)와 `ProductTestCase`(227행) **둘 다** 있다. 이번 작업은 **`product_test_procedure.expected_result`만** 대상. **`product_test_case.expected_result`는 절대 건드리지 마라.**

## ⚠️ 절대 규칙
1. **NULL 바이트 고질병**: 파일 편집 직후 `python -c "p=r'<file>';open(p,'wb').write(open(p,'rb').read().rstrip(b'\x00'))"` → py_compile / `node --check` → `tail` 끝줄 확인.
2. **DB 변경 = dry-run → 사용자 승인 → 백업(`data/backups/`) → apply. 한 트랜잭션.** 승인 없이 apply 금지.
3. DB WAL: 조회 시 체크포인트 후 또는 복사본.
4. 모호하면 멈추고 질문. 임의 삭제/병합 금지. 15-x 마이그레이션 재실행 금지.

## 단계 A — DB 데이터+스키마 정리 (procedure만)
목표: `expected_result`를 `acceptance_criteria`로 병합 후 `product_test_procedure.expected_result` 컬럼 제거.
- 병합 규칙: `expected_result`가 NULL/빈값이면 **acceptance_criteria 그대로(작성 불필요)**. 값이 있으면 acceptance_criteria에 기대결과 내용을 포함시킨다(이미 포함돼 있으면 중복 추가 금지). 정확한 결합 포맷은 dry-run 샘플로 제시해 사용자 승인받는다.
- 그 후 `product_test_procedure`에서 `expected_result` 컬럼 제거(SQLite: 테이블 재생성 또는 DROP COLUMN). FK·인덱스 보존.
- **dry-run 보고**: 영향 row 수, 병합 예정 값 샘플 10건(전/후), NULL이라 변경 없는 수, 컬럼 제거 계획. → **멈추고 사용자 승인 대기.** 승인 시 백업 → 한 트랜잭션 apply → integrity_check ok / procedure 수 보존 검증.
- 코드 동기화: 모델에서 procedure `expected_result` 제거, 등록폼(5행)·라우터(admin create/update)·tracking_router 조회·서비스·테스트에서 procedure expected_result 참조 제거/정리. (case expected_result 참조는 유지.)

## 단계 B — Procedures UI 개편 (`product_test_procedures_admin.html` 및 관련 뷰)
- **Expected Result 컬럼 제거** (목록 6행에서). acceptance_criteria만 남김.
- **Action 컬럼 축약**: `procedure_action`의 하위절차 개수만 `1, 2, 3, 4 …` 식으로 셀에 간략 표시(전체 텍스트 X). 하위절차 구분 기준은 실제 데이터로 확인(개행/번호 등); 애매하면 멈추고 질문.
- **클릭 시 편집 팝업**: 축약 셀(또는 행) 클릭 → 별도 수정 팝업(Text Editor Area/textarea)이 뜬다. 팝업에서는 **하위 수행절차가 각 줄로 개행되어** 보이고 편집 가능. 저장 시 `procedure_action` 갱신(기존 저장 포맷 유지).
- 등록/수정 흐름·기존 편집(`table-cell-f2-edit.js` 등)과 충돌 없게. 팝업은 모달로.

## 검증
- 단계 A: `integrity_check` ok, procedure 수 보존, `product_test_procedure.expected_result` 컬럼 없음, `product_test_case.expected_result`는 그대로 존재.
- `grep -rn "expected_result" app/` 에서 **procedure 관련 잔존 0** (case 관련만 남음).
- 단계 B: `/admin` 또는 procedures 화면에서 Expected Result 컬럼 없음, Action 축약 표시(1,2,3,4), 클릭 시 팝업 뜨고 하위절차 개행 표시·편집·저장 동작.
- `uv run pytest tests/ -q` 전체 green, `GET /admin` 200.
- 편집 파일 NULL 0 + py_compile/node --check.

## 시작
문서 읽음 1줄 확인 → **단계 A dry-run부터**(병합 샘플 제시) → 사용자 승인 대기. 승인 후 백업·apply, 그다음 단계 B. case expected_result는 절대 건드리지 말 것.
