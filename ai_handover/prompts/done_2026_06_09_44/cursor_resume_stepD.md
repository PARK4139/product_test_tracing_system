# Cursor 작업 프롬프트 — STEP D부터 (v2 경로 이어받기)

아래 "---" 블록을 Cursor 채팅에 그대로 붙여넣어라.

---

너는 이 저장소(`product_test_tracing_system`, FastAPI+SQLite, Windows)의 v2 구조 전환을 **STEP D부터** 이어서 한다. 지금까지 TASK 1~13 + STEP B/C는 완료됐다.

## 먼저 읽어라 (정본 순서)
1. `ai_handover/master_architecture.md` — **최종 목표 구조 정본**. 「v2 구조 결정」 + 「v2 구조 결정 추가(b)」 포함. (release 엔티티 폐기 → ROUND→RUN→RESULT→CASE)
2. `ai_handover/handover_main.md` — §0-0 목표, §0-1 실수 방지 수칙, §4 TASK, §5 정본 토폴로지, §6 정책.
3. `ai_handover/tasks/task12_13_target_merge.md` — TASK 13 규칙(완료, 참고).
4. `ai_handover/tasks/task15_v2_migration.md` — TASK 15(다음 큰 단계) 설계.

## 현재 상태 (완료분)
- TASK 1~10 적용 완료(접두 정리: CASE-/RELEASE-/ROUND-/CONFIG-/TARGET-, TEST_REPORT는 손대지 않음).
- TASK 11(Configs 병합)·12+12-B(Targets 병합 `product_test_target_unified`, 구 테이블 DROP)·13(run→target 재연결) 완료.
- 현재 run.target 분포 = HDC6/HDR18/HLM11/HRK16/HTR11, FK 고아 0, result-bearing run의 target==[장비]태그 불일치 0.

## ⚠️ 절대 규칙 (이 저장소 고질병 포함)
1. **이 저장소는 편집 후 파일 끝에 NULL 바이트가 붙는 사고가 반복됨.** 모든 파일 편집 직후 반드시:
   - trailing NULL 제거: `python -c "p=r'<file>';d=open(p,'rb').read();open(p,'wb').write(d.rstrip(b'\x00'))"`
   - `python -m py_compile <file>` (또는 `node --check` for JS) + `tail`로 끝줄 확인.
2. **DB는 WAL 모드.** 조회 시 `PRAGMA wal_checkpoint(TRUNCATE)` 후 또는 `.db`+`-wal`+`-shm` 복사본(읽기전용)에서.
3. **DB 변경은 항상: dry-run 출력 → 사용자 승인 → 자동 백업(`data/backups/`) → apply.** 승인 없이 apply 금지. 한 트랜잭션.
4. **정본 토폴로지(§5)·정책(§6)·마스터 구조 그대로.** 모호하면 멈추고 질문. 추측 금지.
5. 한 STEP씩. 검증 통과 못 하면 다음으로 안 넘어감.

## STEP D — run/result 토폴로지 AP→ROUTER 정규화 (지금 할 것)
- 대상: run id·result `[연결구성]`·관련 텍스트의 `{N}AP` → `{N}ROUTER`. (마스터 §5·§6, TASK 5 규칙)
- 규칙: 장비순서 HRK>HTR>HLM>HDR>HDC>HIIS, ROUTER 별도 토큰. `1AP_1HDC` only → `1HDC_1ROUTER`. 정본 목록(§5)에 없으면 UNCLASSIFIED로 두고 보고.
- 구 값은 remark `[구 연결구성]`로 보존(이미 일부 존재 → 중복 보존 주의).
- **dry-run**: 치환 영향 건수(run id / result remark 각각) + 치환 후 정본목록 매칭/UNCLASSIFIED 수 출력 → **사용자 승인 대기(멈춤)**.
- 승인 후: 백업 → apply.
- 검증: 치환 후 `[연결구성]`·run/result id에 `AP` 토큰 0(보조장비명 등 정당한 예외 제외), FK 고아 0(run→target_unified, result→run), 앱 부팅 `GET /admin` 200.

## STEP E — TASK 15 v2 마이그레이션 (STEP D 승인 후, 별도)
- `ai_handover/tasks/task15_v2_migration.md` 전체 따라. release 엔티티 폐기 → ROUND→RUN→RESULT.
- RUN id=`RUN_{제품}_{S/W풀네임}_{토폴로지}`(S/W풀네임=버전+RC 한 덩어리), RESULT 미러, CASE=`CASE_{campaign}_{topology}_{scenario}`(DUT=ROUTER앞 토큰 추론, campaign별 Case 복제), Defect FK 동시 갱신, report 재연결.
- 최고 위험. 반드시 dry-run 충분 리뷰 + 승인 + 백업.

## 보고 형식 (STEP마다)
```
[STEP X] 제목
- 한 일 / 변경 파일 / 검증 결과(수치) / 위험·주의 / 다음(승인요청 여부)
```

## 시작
master 문서 읽음 1줄 확인 → **STEP D dry-run** 부터. dry-run 결과(영향 건수 + UNCLASSIFIED 수) 내고 멈춰서 사용자 검토 요청.
---
