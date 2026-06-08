# 데이터 정합성 진단 + 시트 탭 설계 (2026-06-08)

> 목적: 시험 데이터의 **추적성(traceability)** 확보.
> 이번 세션: **진단 + 설계만**. DB 안 건드림.
> 진단 대상: `data/product_test_tracking_system.db` (읽기 전용 복사본 쿼리).

---

## 0. 한 줄 요약 (caveman)

- **FK 끊긴 행은 없다. 좋다.**
- **근데 "이름표"가 엉망이다.** Case ID, 연결구성, 상태값이 서로 안 맞는다.
- **추적의 마지막 증거(증빙·절차결과)가 텅 비었다.** → 지금은 "추적 가능"이 아니라 "추적 흉내"다.
- 그래서: **이름표부터 통일 → 빈 증거 채우기** 순서로 가야 한다.

---

## 1. 현재 DB 규모 (진단 시점)

| 테이블 | 건수 | 비고 |
|---|---:|---|
| product_test_release | 216 | 핸드오버(83) 대비 크게 증가 |
| product_test_run | 62 | 핸드오버(37) 대비 증가 |
| product_test_result | 375 | |
| product_test_case | 60 | |
| product_test_procedure | 171 | |
| product_test_defect | 15 | 전부 `opened` |
| product_test_round | 13 | **models.py에 없는 테이블** |
| target / target_def | 6 / 6 | |
| environment / env_def | 6 / 6 | |
| **evidence** | **0** | 추적성 공백 |
| **procedure_result** | **0** | 추적성 공백 |
| **status_transition** | **0** | 추적성 공백 |
| report / snapshot | 8 / 0 | |

---

## 2. 좋은 점 (정합성 통과)

- **FK 고아 0건.** result→run, result→case, procedure→case, run→release/target/env, defect→result, release→round, target→def, env→def **전부 0**.
- **procedure_sequence 중복 0건** (같은 case 안에서).
- **고아 Case 0건** (모든 Case가 최소 1개 Result에서 사용됨).

→ 참조 무결성(referential integrity)은 살아있다. 문제는 **의미 정합성(semantic)** 과 **표기 정합성(naming)** 이다.

---

## 3. 발견된 문제 (심각도순)

### [P0] 추적성 마지막 고리가 비어있음
- `evidence = 0`, `procedure_result = 0`, `status_transition = 0`.
- 즉 "이 결과가 왜 PASS/BLOCK인지"를 받쳐줄 **증빙 파일·절차 단위 실행기록·상태 변경 이력**이 하나도 없다.
- 추적성의 최종 목적이 여기인데, 지금은 Result까지만 있고 그 **근거 레벨이 공백**.

### [P0] ORM 모델 ↔ 실제 DB 스키마 불일치 (drift)
- 실제 DB엔 있는데 `app/models.py`엔 **없는 것**:
  - 테이블 전체: **`product_test_round`** (13건)
  - `product_test_release` 컬럼: **`release_visible`**, **`test_round_id`**
- db.py의 런타임 보정 로직이 컬럼을 추가하는 구조라, 모델 파일만 보면 실제 스키마를 오해한다. → 신규 개발자/스크립트가 틀린 가정을 하게 됨.

### [P1] Case ID 토폴로지 ↔ Result 연결구성 불일치
- Result 375건 중 **331건(88%)** 에서, 그 Result가 쓰는 **Case ID 첫 세그먼트 ≠ Result의 실제 `[연결구성]`**.
- 예: Case `1AP_1HDC` 인데 Result `[연결구성]`은 `1AP_1HDC_1HDR`.
- 원인(핸드오버 확인): Case ID 첫 세그먼트는 **토폴로지가 아니라 DUT(시험대상) 표기**. 코드가 이걸 토폴로지로 오인.

> **⚠️ 331 재현 규칙 (이 정의로만 331이 나온다 — 다르게 세지 말 것)**
> 1. **분모 = 375** : `[연결구성]`을 가진 **result 행** 단위(case별 합산). Case 단위(60)로 세지 않는다.
> 2. **caseseg 추출 정규식** : `TEST_CASE-([0-9A-Za-z_]+?)-WIFI` (비탐욕). `-WIFI`가 없는 **비정상 ID 18행은 비교 제외(=일치 취급)**.
> 3. **비교는 문자열 완전일치(`!=`)** : 부분집합/접두 비교 아님. `1AP_1HDC` vs `1AP_1HDC_1HDR` → **불일치**.
> 4. **AP→ROUTER 정규화 전, 원본 문자열로 비교.**
>
> ```python
> import sqlite3, re
> con = sqlite3.connect("data/product_test_tracking_system.db")
> con.execute("PRAGMA wal_checkpoint(TRUNCATE)")   # WAL 반영 필수
> cur = con.cursor()
> mis = tot = 0
> for (cid,) in cur.execute("SELECT product_test_case_id FROM product_test_case"):
>     rrs = cur.execute("SELECT remark FROM product_test_result "
>                       "WHERE product_test_case_id=? AND remark LIKE '%[연결구성]%'", (cid,)).fetchall()
>     if not rrs: continue
>     m = re.match(r'TEST_CASE-([0-9A-Za-z_]+?)-WIFI', cid)
>     caseseg = m.group(1) if m else None
>     for (rm,) in rrs:
>         mm = re.search(r'\[연결구성\]\s*([^\n\]]+)', rm or '')
>         rcombo = mm.group(1).strip() if mm else None
>         tot += 1
>         if caseseg and rcombo and caseseg != rcombo:
>             mis += 1
> print(tot, mis)   # -> 375 331
> ```
> 참고 분해: 분모 375 = 일치 44 + 불일치 331. caseseg 추출 실패(비교 제외) 18행은 "일치 44"에 포함.

### [P1] AP / ROUTER 표기 정책 미확정
- Result `[연결구성]` 375건 중 **AP 표기 372건, ROUTER 표기 0건**.
- 정본 목표는 `1ROUTER`/`25ROUTER` 표기인데 데이터는 전부 레거시 `1AP`/`25AP`.
- 상위 연결구성: `1AP_1HRK_4HDR`(44), `1AP_1HRK_1HDR`(43), `1AP_4HDR_1HDC`(30), `1AP_1HDC_1HDR`(29) …

### [P1] 비정상 Case ID 5건
| Case ID | 상태 | 문제 |
|---|---|---|
| `DEPRECATED_TEST_CASE-1AP_1HDC-WIFI-DR_CONNECT_ON_DHCP-002` | ACTIVE | deprecated인데 status가 ACTIVE |
| `PLACEHOLDER_EMPTY_CASE-WIFI_CONNECTIVITY_TEST_2026` | DRAFT | placeholder, **절차 0개인데 Result가 사용** (TC-PR01 위반) |
| `Wi-Fi 재ON 후 복구` | ACTIVE | 한글 자연어가 PK |
| `라우터 재부팅 후 복구` | ACTIVE | 한글 자연어가 PK |
| `시험대상장비 재부팅 후 복구` | ACTIVE | 한글 자연어가 PK |

### [P2] 라운드 트리 구멍
- `product_test_round` 13건 중 **5건은 연결된 release가 0개** (device round 12 ≠ round 13):
  `HDC_9100_1_0_5A`, `HDR_9000_1_1_7E`, `HDR_9000_1_1_8`, `HLM_9000_1_1_14B`, `HTR_1A_1_1_8`.
- `test_round_id`가 NULL인 release 4건 (라운드 미연결):
  `FALLBACK-WIFI_CONNECTIVITY_TEST_2026`, `TBD_REPORT_NO2`, `TBD_REPORT_NO4`, `TBD_REPORT_NOTBD`.
- 라운드 13건 중 **날짜 품질 EXACT는 2건뿐** (`WIFI_1ST`, `HRK_9000A_1_1_0A`), 나머지 11건은 `INFER_NEEDED`. 1건은 `ORPHAN_REVIEW_NEEDED`(`WIFI_DOWNGRADE_COMPARE_20260526`).

### [P2] 상태값(vocabulary) 표기 불일치
- result: 소문자 `passed / blocked / testing`
- release: 대문자 `TESTING / PASSED / BLOCKED / APPROVED`
- run: 소문자 `finished / running`
- → 테이블마다 대소문자·어휘가 제각각. 집계·필터·하이라이트에서 버그 유발 가능.

---

## 4. 정합성 작업 권장 순서

1. **(P0) 스키마 정본화** — models.py를 실제 DB에 맞춤(`product_test_round`, `release_visible`, `test_round_id` 반영). 정본 스키마 문서 1장.
2. **(P1) 표기 정책 확정** — AP→ROUTER 전역 치환 규칙 + Case ID 신규 규칙(`TEST_CASE-{topology}-{dut}-{scenario}-{seq}`) 확정. (핸드오버 미결질문 5건 답 필요)
3. **(P1) 비정상 Case ID 5건 정리** — placeholder/deprecated/한글 PK 처리 방침 결정.
4. **(P1) Case↔연결구성 재매핑** — Result `[연결구성]` 기준으로 Case 토폴로지 정정.
5. **(P0) 증거 레벨 채우기** — evidence / procedure_result / status_transition 입력 경로 마련(시트 탭이 여기 직접 기여).
6. **(P2) 라운드 트리·상태 vocab 정리.**

> 2~4번의 실제 DB 변경 스크립트는 **다음 세션**(이번은 설계까지만).

---

## 5. 시트 탭 기반 정합성 도구 — 설계

### 5.1 컨셉
화면 안에서 핵심 테이블을 **스프레드시트(행/열)** 로 펼쳐 보고, 셀을 직접 고치며 정합성을 맞춘다. 기존 `CustomSheetTab`(범용 JSON 시트)과 달리, 이건 **실제 도메인 테이블에 바인딩된 "정본 시트"** 다.

### 5.2 기존 자산 재활용
- `CustomSheetTab` 모델: columns_json / rows_json 범용 시트 구조 → **읽기 패턴 참고**.
- `UiStatePref`: 탭 순서·활성탭 등 화면상태 DB 저장 → 시트 필터/정렬 상태 저장에 재활용.
- `tracking_router` + `tracking-render.js`: 데이터 로딩·렌더 패턴 그대로 차용.

### 5.3 탭 구성 (정본 테이블 바인딩)
| 탭 | 바인딩 테이블 | 핵심 정합성 역할 |
|---|---|---|
| Case 시트 | product_test_case (+procedure 카운트) | 비정상 ID·placeholder 식별, 토폴로지 재매핑 |
| Result 시트 | product_test_result | `[연결구성]` ↔ Case 불일치 표시·수정 |
| Release/Round 시트 | release + round | 트리 구멍·NULL round 표시 |
| Defect 시트 | product_test_defect | result 연결·상태 확인 |
| Evidence 시트 | product_test_evidence | **빈 증거 직접 입력** |

### 5.4 정합성 기능 (시트 위에서)
- **셀 단위 검증 배지**: 행마다 정합성 위반을 색으로 표시
  (예: Case ID 규칙위반=빨강, 토폴로지 불일치=주황, 증거없음=회색).
- **불일치 필터**: "문제 있는 행만 보기" 토글.
- **인라인 수정 + diff 미리보기**: 저장 전에 바뀔 값 보여주고, 확정 시에만 DB 반영(+ status_transition 자동 기록).
- **읽기 전용 파생열**: 절차 수, 연결 Result 수, 매칭 토폴로지(다수결) 등 계산 컬럼.

### 5.5 추적성 기여
- Evidence 시트로 **증빙을 직접 채워** P0 공백 해소.
- 모든 수정이 **status_transition에 자동 적재** → 변경 이력 = 추적 기록.
- 시트의 파생열이 Case↔Result↔연결구성 체인을 한눈에 보여줌 → 불일치를 사람이 즉시 교정.

### 5.6 안전장치
- 기본 **읽기 모드**, 편집은 명시적 전환.
- 저장 전 dry-run diff 필수.
- 대량 변경 시 DB 백업 트리거(기존 `backup_service` 재활용).
- 편집 로그는 `clientLog()` 규칙(app.log) 준수.

---

## 6. 다음 세션 착수 항목
1. 핸드오버 미결질문 5건 답 확정 (AP→ROUTER, Case 복제 단위, 불일치 우선순위 등).
2. models.py ↔ DB 스키마 정본화 + 스키마 문서.
3. Case/Result 재매핑 스크립트 작성(dry-run).
4. Evidence/Result 시트 탭 프로토타입.
