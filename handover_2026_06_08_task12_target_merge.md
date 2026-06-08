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

### 작업 내용 (codex)
1. run별로 "원래 어떤 DUT였는지" 단서 수집: `run.remark`, 연결된 Result `remark`의 `[시험대상]`/`[연결구성]`, release/round의 모델 정보, Excel 원본.
2. run → 모델 추정 매핑표 출력(어느 run이 어느 model_name·serial이어야 하는지).
3. 통합 target 테이블(6대) 중 어디에 연결돼야 하는지 후보 제시 + 신뢰도(EXACT/INFER).
4. 결과를 `docs/run_target_relink_diagnosis_YYYYMMDD.md`로 저장.

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
