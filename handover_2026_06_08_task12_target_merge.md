# HANDOVER 추가 — TASK 12: Target 병합 / TASK 13: run→target 재연결 진단 (2026-06-08)

> 본 `HANDOVER.md`의 **TASK 12·13**. §0-1 실수 방지 수칙·§9 편집 규칙 그대로 적용.
> 근거 스캔: 2026-06-08 DB (TASK 1~10 적용 후, 접두 `TARGET-`/`TARGET_DEF-`).

---

## 0. 한 줄 요약 (caveman)

- `target_definition`(모델 스펙) + `target`(물리 장비 1대) = 지금 **1:1**.
- TASK 11(environment)과 같은 방식으로 **새 통합 테이블 1개로 완전 병합.**
- 단, ⚠️ run 62건이 **target 1대만** 가리키는 이상은 병합과 **분리**해 TASK 13에서 진단.

---

## 1. 진단 사실

- 건수: targetdef 6 / target 6, **완전 1:1** (def당 target 1개, ID 거울: `TARGET-{model}-{serial}` ↔ `TARGET_DEF-{model}`).
- 컬럼 성격이 **서로 다름**(env와 다른 점):
  - **def(모델)**: `product_code, manufacturer, model_name, hardware_revision, default_software_version, default_firmware_version`.
  - **target(물리장비)**: `serial_number, software_version, firmware_version, manufacture_lot`.
- 겹치는 데이터 컬럼 = **감사컬럼+remark뿐** (`created/updated_at/by, project_id`). 알맹이는 안 겹침 → 병합 시 값 충돌 없음.
- `remark`만 6쌍 중 5쌍 다름 (def=상세, target=메모).
- ⚠️ `product_test_run.product_test_target_id` **distinct = 1** : run 62건이 전부 같은 target 1대 참조. (추적성 이상 → TASK 13)

> 주의(개념): 모델↔물리장비 분리는 원래 의미 있음(한 모델에 여러 물리장비 가능). **지금 1:1이라 병합 안전**하나, 향후 "한 모델 여러 시리얼"이 필요해지면 모델 필드가 중복됨 → 그때 재분리 감수. (사용자 승인: 완전 병합)

---

## TASK 12 — Target 병합 (새 통합 테이블, dry-run) 🔴스키마 변경·파괴적

### 결정 (확정)
- **대상**: 새 통합 테이블 `product_test_target_unified`(이름 변경 가능). 기존 target·targetdef 2개는 백업 후 삭제.
- **ID**: 새 행 PK = **기존 target id(`TARGET-...`) 재사용** → `run.product_test_target_id` 값 변경 불필요.
- **remark**: def 상세 본문 + `\n[구 target 노트] {target.remark}` (둘 다 보존).
- **커스텀 시트**: 통합 테이블을 시트 탭(TASK 7~9)으로 보고/편집 노출.

### 통합 테이블 컬럼 설계 (union, 손실 없음)
| 그룹 | 컬럼 | 출처 |
|---|---|---|
| PK | `product_test_target_id` | target id 재사용 |
| 식별 | `serial_number`, `product_test_target_status` | target |
| 모델 | `product_code, manufacturer, model_name, hardware_revision, default_software_version, default_firmware_version` | **def 전용** |
| 실측(장비) | `software_version, firmware_version, manufacture_lot` | **target 전용** |
| 이력 | `remark`(병합), `created_at/by, updated_at/by, project_id` | 병합/공통 |

- `product_test_target_definition_id`(연결키)·def 중복 status는 드롭.
- 추적 보존: remark에 `[구 target id]`, `[구 def id]`.

### 작업 내용 (codex)
1. **사전 스캔(read-only)**: 1:1(6:6)·run FK 재확인. 1:N이면 **멈추고 보고**.
2. **새 테이블 생성**: 위 설계대로.
3. **6행 병합 이관**: target 행 기준 + 매칭 def의 모델 6컬럼 채움. remark 병합 + 구 id 보존.
4. **run FK 검증**: 모든 `run.product_test_target_id`가 새 테이블에 존재(고아 0). id 재사용이라 run UPDATE 없음.
5. **백업 후** 기존 `product_test_target`, `product_test_target_definition` 삭제.
6. **코드 동기화**: `models.py`(새 모델·구 2개 제거), `db.py`, 라우터, 템플릿(`product_test_targets_admin.html` + `product_test_target_definitions_admin.html` → **1개 화면 통합**), JS, seed. grep: `target_definition|product_test_target\b`.
7. **시트 탭 노출**: 통합 target 탭 추가.

### 대상파일
- `scripts/migrate_merge_target.py` (신규), `app/models.py`, `app/db.py`
- `app/templates/product_test_targets_admin.html`(통합), `..._target_definitions_admin.html`(제거), 관련 라우터/JS, seed

### 검증
- 새 테이블 6행, 모델6+실측3 컬럼 보존, remark에 def본문+target노트 둘 다.
- run FK 고아 0. 구 테이블 2개 삭제, 코드/템플릿에 `target_definition` 잔존 0(grep).
- 앱 부팅 + target 관리화면(통합) + 추적 화면 정상.

### 위험도
**높음(파괴적).** 백업+dry-run+승인 후 apply. 한 트랜잭션, 코드 변경 별도 커밋.

---

## TASK 13 — run → target 재연결 진단 (read-only) 🟢위험없음

### 목적
run 62건이 **target 1대만** 가리키는 원인 규명 + 올바른 DUT 재연결 설계. (이번엔 **진단만**, DB 변경 없음)

### ⚠️ 재연결 DUT 추론 규칙 (2026-06-09 수정 — 기존 진단 오류 정정)
**기존 진단(`run_target_relink_diagnosis_20260609.md`)은 폐기/재생성.** 원인: `[Test 대상]` 블록 첫 줄을 DUT로 봤는데, 그 블록은 **연결장비 6개 전부 나열**이라 항상 HRK가 첫 줄 → WIFI_2ND run 9건(result 57건)이 HRK로 오배정됨.

**정정 규칙 (우선순위 중요 — 2026-06-09 재정정):**
1. **1순위: `[장비] X` 태그 / run id 끝 `-X` suffix = 실제 DUT.** WIFI_1ST 분할 run은 한 토폴로지를 장비별로 쪼갠 것이라, **토폴로지 첫 장비(호스트)가 아니라 [장비] 태그가 진짜 DUT**다. 예: `RUN-...-1HDR_1ROUTER_1HDC-RC1` `[장비] HDC` → **HDC**(HDR 아님). 신뢰도 EXACT.
2. 2순위(비분할 run): 토폴로지의 `_ROUTER` 앞 토큰. 예: `1HLM_25ROUTER`→HLM, `1HTR_25ROUTER`→HTR. (WIFI_2ND처럼 [장비] 없는 run)
3. **`[Test 대상] 첫 줄 = HRK` 규칙은 폐기** (연결장비 목록이지 DUT 아님).
⚠️ **흔한 오류**: 토폴로지 첫 장비를 DUT로 쓰면 `1HRK_4HDR-...-HDR`(DUT=HDR)을 HRK로, `*_1HDC-...-HDC`(DUT=HDC)를 HDR로 오배정한다. [장비] 태그가 항상 우선.
4. **폴백: 토폴로지 없으면 release/round 모델명으로 추론.** 예: release `RELEASE-HRK_9000A_1_1_1D-RC1` / round `ROUND-HRK_9000A_*` → DUT=HRK. (legacy `RUN-TEST_REPORT_*` 3건이 여기 해당 → 전부 HRK, **UNCLASSIFIED 0 목표**)
5. 그래도 못 뽑고 result=0이면 무시. **무조건 HRK 기본값 금지**(폴백은 release 근거 있을 때만).
6. `HDR-7100P`는 보조장비(릴리즈 대상 아님) → DUT로 선택 금지.

검증: WIFI_2ND-25AP_1HDR*→HDR, -1HLM*→HLM, -1HTR*→HTR. legacy `RUN-TEST_REPORT_*` 3건(release HRK_9000A_1_1_1D/0A/1A)→**HRK**. **UNCLASSIFIED 0** (62건 전부 확정).

### 작업 내용 (codex)
1. **위 정정 규칙으로** run별 DUT 추론 → 통합 target 매핑.
2. run → (model_name·serial·sw) 매핑표 + 신뢰도(EXACT/INFER) 출력. 기존 대비 **바뀌는 run 9건/result 57건** 표시.
3. 결과를 `docs/run_target_relink_diagnosis_YYYYMMDD.md`로 **재생성**(기존 파일 대체).

### 산출물
- 진단 문서 + run→target 재연결 제안표. (실제 UPDATE는 승인 후 별도 TASK)

### 검증
- 모든 run이 후보 target에 매핑됨(또는 UNCLASSIFIED로 명시). 추정 출처 기록.

### 위험도
없음 (읽기 전용).

---

## 메인 HANDOVER 반영 메모
- `HANDOVER.md` §4에 **TASK 12·13** 스텁 추가.
- 정리정돈 양식 동일. 다음 후보(예: case/procedure, report 계열) 있으면 TASK 14+로.
