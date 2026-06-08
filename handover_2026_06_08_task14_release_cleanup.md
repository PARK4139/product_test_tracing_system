# HANDOVER 추가 — TASK 14: release 고아/NULL-round 안전 정리 (2026-06-08)

> 본 `HANDOVER.md`의 **TASK 14**. §0-1 실수 방지 수칙·§9 편집 규칙 적용.
> 근거 스캔: 2026-06-08 DB (TASK 1~10 적용 후).

---

## 0. 한 줄 요약 (caveman)

- 처음엔 "round_legacy 4건이 죽었다" 생각했는데 **틀렸음.**
- round_legacy는 **레거시 서브트리(82 release, 그중 33건 run 보유)의 뿌리 = 살아있는 백본.** **절대 삭제 금지.**
- 진짜 안전한 정리는 딱 2개: **FALLBACK 고아 1건 삭제** + **TBD report용 release 3건에 round 채우기(삭제 아님).**

---

## 1. 진단 사실 (왜 이 범위만 안전한가)

### ⛔ round_legacy 4건 — 삭제 금지 (살아있는 백본)
`RELEASE-WIFI_1ST / WIFI_2ND / WIFI_DOWNGRADE / WIFI_1_1_1D`
- 루트 자체엔 run 0이지만, **upstream 체인으로 후손이 82 release**:
  - 구조: `round_legacy → run_session(RUN_RC*) 7 → RC 잎 66`
  - 그중 **33 release가 실제 run 보유 (라이브 데이터)**.
- 지우면 33개 run + 그 result/defect 추적이 끊김. → **건드리지 말 것.** (백본 구조 재편은 별도 대형 TASK, 이번 범위 아님)

### ✅ 안전 정리 대상 (2종)
1. **FALLBACK 고아 1건 — 삭제**
   - `RELEASE-FALLBACK-WIFI_CONNECTIVITY_TEST_2026`
   - inbound 참조 전부 0 (run 0 / report 0 / upstream 0 / snapshot 0), test_round_id NULL → **진짜 고아, 삭제 가능.**
2. **TBD report용 release 3건 — round 채우기(삭제 아님)**
   - report가 1건씩 물고 있어 삭제 불가. test_round_id만 NULL → 제목 기준 round 할당:
     | release | 연결 report 제목 | 채울 test_round_id |
     |---|---|---|
     | `RELEASE-TBD_REPORT_NO2` | Wi-Fi 1차 개선확인 시험 | `ROUND-WIFI_1ST_IMPROVE` |
     | `RELEASE-TBD_REPORT_NO4` | Wi-Fi 2차 개선확인 시험 | `ROUND-WIFI_2ND_IMPROVE` |
     | `RELEASE-TBD_REPORT_NOTBD` | HRK-9000A 1.1.1D WBS Test Case 시험 | `ROUND-HRK_9000A_1_1_1D` |
   - 세 round id 모두 `product_test_round`에 **존재 확인됨**.
- 처리 후 **test_round_id NULL release = 0** (현재 4 → 0).

---

## TASK 14 — release 고아/NULL-round 안전 정리 (dry-run) 🟡소량 DB

### 작업 내용 (codex)
1. **사전 확인(read-only)**:
   - FALLBACK의 inbound 참조 4종(run/report/upstream/snapshot) 모두 0인지 재확인. 하나라도 >0이면 **멈추고 보고**.
   - TBD 3건이 여전히 report만 물고 round=NULL인지 확인.
   - **round_legacy 4건은 손대지 않음**을 코드/쿼리에서 명시적으로 제외.
2. **dry-run 출력**: 삭제 1건 + UPDATE 3건 미리보기.
3. **승인 → 백업 → apply**:
   - `DELETE FROM product_test_release WHERE product_test_release_id='RELEASE-FALLBACK-WIFI_CONNECTIVITY_TEST_2026'` (참조 0 재확인 후).
   - 3건 `UPDATE ... SET test_round_id=? , updated_at, updated_by`, remark에 `[round 보정] 제목기준 추론` 기록.
4. **검증**: test_round_id NULL release = 0. FALLBACK 삭제됨. round_legacy 4건·그 후손 82건 **건수 변화 없음**. FK 고아 0(§3 검사).

### 대상파일
- `scripts/cleanup_orphan_releases.py` (신규)

### 위험도
낮음(소량). 단 **round_legacy 오삭제 주의** — 스크립트에 화이트리스트(FALLBACK 1 + TBD 3)만 명시, 그 외 release 절대 손대지 않게 하드코딩.

---

## 2. 남은 release 정비(이번 범위 밖, 후속 후보)
- `release_stage` 5종 vocab 표준화(RC/run_session/device_round/TEST/round_legacy) — 백본이라 대형 TASK.
- 레거시 서브트리(82) vs device_round 트리 정합 — 구조 재편, 별도 설계 필요.
- `report_type` 상수컬럼(항상 TEST_REPORT) 제거 — 소규모.
→ 필요 시 TASK 15+로.

---

## 메인 HANDOVER 반영 메모
- `HANDOVER.md` §4에 **TASK 14** 스텁 추가.
