# Cursor 작업 프롬프트 — TASK 15 (v2 마이그레이션) 이어받기

아래 "---" 블록을 Cursor 채팅에 붙여넣어라.

---

너는 이 저장소(`product_test_tracing_system`)의 v2 전환 **TASK 15(최종 대규모 마이그레이션)**를 한다. STEP D는 **생략 확정**(아래 이유).

## 먼저 읽어라
1. `handover_2026_06_08_master_architecture.md` — 최종 구조 정본(「v2 구조 결정」+「추가(b)」).
2. `handover_2026_06_09_task15_v2_migration.md` — **TASK 15 상세 설계(이걸 따른다)**.
3. `HANDOVER.md` §0-1 수칙 / §5 정본 토폴로지 / §6 정책.

## 현재 상태 (완료분)
- TASK 1~14, TASK 11/12/12-B/13 완료.
- run.target 재연결 완료: 분포 HDC6/HDR18/HLM11/HRK16/HTR11, FK 고아 0, result-bearing run의 target==[장비]태그 불일치 0.
- **result `[연결구성]`은 이미 ROUTER 정본(AP 0건, TASK 6).**
- ⛔ **STEP D(run-PK AP→ROUTER 치환)는 생략 확정** — TASK 15가 run/result ID를 새 포맷으로 전부 재작성하므로 throwaway. 토폴로지는 result `[연결구성]`에서 뽑는다(run id 아님).

## ⚠️ 절대 규칙
1. **NULL 바이트 고질병**: 모든 파일 편집 직후 `python -c "p=r'<file>';open(p,'wb').write(open(p,'rb').read().rstrip(b'\x00'))"` + `python -m py_compile`(또는 `node --check`) + `tail` 끝줄 확인.
2. DB WAL: 조회 시 checkpoint 후 또는 복사본.
3. **DB 변경 = dry-run → 사용자 승인 → 백업(`data/backups/`) → apply. 한 트랜잭션.** 승인 없이 apply 금지.
4. 정본(§5)·정책(§6)·마스터 그대로. 모호하면 멈추고 질문.

## TASK 15 — release→run v2 구조 마이그레이션 (최고 위험)
목표: `product_test_release` 엔티티 폐기 → **ROUND→RUN→RESULT** + CASE 재네이밍.

핵심 규칙(상세는 task15 문서):
- **RUN id** = `RUN_{제품}_{S/W풀네임}_{토폴로지}`. 제품=재연결된 target(TASK 13), S/W풀네임=버전+RC 한 덩어리, **토폴로지=result `[연결구성]`(ROUTER 정본)**.
- **RESULT id** = RUN 미러.
- **CASE** = `CASE_{campaign}_{topology}_{scenario}` (DUT=토폴로지 `_ROUTER` 앞 토큰 추론). campaign 들어가므로 campaign별 Case 복제 필요(현 60 case 재발급). result.case_id FK 동시 갱신.
- **release 폐기**: run에 round 연결 보존(run.test_round_id), 나머지 추적단서는 remark `[구 release]`. report는 round/run으로 재연결(8건). defect.result_id FK 동시 갱신(result id 바뀌므로).
- 빈 base run(result 0)·legacy UNCLASSIFIED는 마이그레이션 제외/정리(보고).

## 진행 방식 (반드시 단계 분할 — 한 번에 다 하지 말 것)
TASK 15는 크니까 **서브스텝으로 쪼개서 각각 dry-run→승인→apply**:
- **15-1** round 테이블 7 캠페인 정본화(WIFI_1ST/1ST_IMPROVE/2ND/2ND_IMPROVE/DOWNGRADE/WIFI_SMOKE/WBS) + 8 device shell 처리.
- **15-2** RUN/RESULT 신 ID 매핑표 생성(dry-run, 변경 건수·UNCLASSIFIED) → 검토.
- **15-3** CASE campaign별 재발급 매핑(dry-run).
- **15-4** 일괄 apply(run/result/case ID + 모든 FK: result.run_id, result.case_id, procedure.case_id, defect.result_id, report) 한 트랜잭션.
- **15-5** release 테이블 폐기 + 코드(models/router/tracking/templates/JS) release 의존 제거.
각 서브스텝 끝에 보고+멈춤.

## 검증 (apply 후)
- 모든 result.run_id ∈ 새 RUN(고아 0), defect.result_id 고아 0, result.case_id ∈ 새 Case.
- RUN id 규칙 100% 충족, AP 토큰 0.
- run.test_round_id ∈ 7 캠페인 round.
- release 테이블 제거됨, 코드 `product_test_release` 잔존참조 0(grep).
- 앱 부팅 `GET /admin` 200 + 추적/시트 화면 정상.
- 편집 파일 NULL 0 + py_compile 통과.

## 시작
master+task15 문서 읽음 1줄 확인 → **15-1 dry-run**부터. 각 서브스텝 dry-run 결과 내고 멈춰서 사용자 승인 대기.
---
