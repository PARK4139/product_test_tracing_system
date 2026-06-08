# HANDOVER 추가 — TASK 11: Environment + Environment Definition 병합 (2026-06-08)

> 본 `HANDOVER.md`의 **TASK 11**. §0-1 실수 방지 수칙·§9 편집 규칙 그대로 적용.
> 근거 스캔: 2026-06-08 DB (TASK 1~10 적용 후, 접두 `CONFIG-`/`CONFIG_DEF-` 상태).

---

## 0. 한 줄 요약 (caveman)

- `product_test_environment_definition`(정의) + `product_test_environment`(실체) = **사실상 같은 데이터, 1:1.**
- **둘을 새 통합 테이블 하나로 합침.** 커스텀 시트로 보고/편집.
- 데이터 손실 없음: 겹치는 값은 동일, def 전용 8컬럼·env 전용 1컬럼 다 살림, remark는 둘 다 보존.

---

## 1. 진단 사실 (병합 근거)

- 건수: envdef 6 / env 6, **완전 1:1** (def당 env 정확히 1개, ID도 거울: `CONFIG-X` ↔ `CONFIG_DEF-X`).
- 겹치는 데이터 컬럼 13개 중 **`remark` 빼고 전부 동일** (6쌍 중 0쌍만 차이, 대부분 NULL).
- `remark`만 6/6 다름:
  - **def.remark** = 상세 스펙(목적/시험대상/환경/Router/연동장비).
  - **env.remark** = 짧은 TODO 메모.
- def 전용 컬럼 8개: `test_country, test_city, test_company, test_building, test_floor, test_room, test_tool_name, power_condition`.
- env 전용 컬럼 1개: `captured_at`.
- `product_test_run.product_test_environment_id` → env(`CONFIG-...`) 참조. (run 62건, distinct env 4 / 미사용 env 2)

---

## TASK 11 — Environment 병합 (새 통합 테이블, dry-run) 🔴스키마 변경·파괴적

### 결정 (확정)
- **대상**: 새 통합 테이블 `product_test_environment_unified` 생성(이름은 변경 가능). 기존 env·envdef 2개는 백업 후 삭제.
- **ID**: 새 행 PK = **기존 env id(`CONFIG-...`) 그대로 재사용.** → `run.product_test_environment_id` 값 **변경 불필요**(참조 테이블만 바뀜).
- **remark**: **def 상세를 본문**, 그 뒤에 `\n[구 env 노트] {env.remark}` 덧붙여 **둘 다 보존**.
- **커스텀 시트**: 통합 테이블을 시트 탭 시스템(TASK 7~9)으로 보고/편집 가능하게 노출.

### 통합 테이블 컬럼 설계 (union, 손실 없음)
| 그룹 | 컬럼 | 출처 |
|---|---|---|
| PK | `product_test_environment_id` | env id 재사용 |
| 식별 | `product_test_environment_name`, `product_test_environment_status` | env |
| 장소(템플릿) | `test_country, test_city, test_company, test_building, test_floor, test_room` | **def 전용** |
| 네트워크/PC | `network_type, test_computer_name, operating_system_version` | env=def(동일) |
| 도구 | `test_tool_name`(def전용), `test_tool_version` | def / env |
| 전원 | `power_voltage, power_frequency, power_connector_type, power_condition`(def전용) | env=def + def |
| 실측 | `captured_at` | **env 전용** |
| 이력 | `remark`(병합), `created_at/by, updated_at/by, project_id` | 병합/공통 |

- `product_test_environment_definition_id`(연결키)·def의 중복 name/status는 **드롭**.
- 추적 보존: remark에 `[구 env id]`, `[구 def id]` 남김.

### 작업 내용 (codex)
1. **사전 스캔(read-only)**: 1:1(6:6) 유지·run FK distinct 재확인. 깨졌으면(1:N 발견) **멈추고 보고**.
2. **새 테이블 생성**: 위 컬럼 설계대로 `product_test_environment_unified`.
3. **6행 병합 이관**: env 행 기준 + 매칭 def의 전용 8컬럼 채움. remark = `def.remark` + `\n[구 env 노트] ` + `env.remark` + `\n[구 env id] {eid}\n[구 def id] {did}`.
4. **run FK 검증**: 모든 `run.product_test_environment_id`가 새 테이블에 존재(고아 0). id 재사용했으므로 run UPDATE 없음(있다면 동시 갱신).
5. **백업 후** 기존 `product_test_environment`, `product_test_environment_definition` 삭제.
6. **코드 동기화**: `models.py`(새 모델 추가·구 모델 2개 제거), `db.py` 초기화/시드, 라우터, 템플릿(`product_test_environments_admin.html` + `product_test_environment_definitions_admin.html` → **1개 관리화면으로 통합**), JS, seed 스크립트. grep: `environment_definition|product_test_environment\b`.
7. **시트 탭 노출**: TASK 7~9 시트 시스템에 통합 environment 탭 추가(보기→편집).

### 대상파일
- `scripts/migrate_merge_environment.py` (신규)
- `app/models.py`, `app/db.py`
- `app/templates/product_test_environments_admin.html`(통합), `..._definitions_admin.html`(제거)
- 관련 라우터/JS, `app/scripts/seed_*` (grep 결과)

### 검증
- 새 테이블 6행, def 전용 8컬럼·`captured_at` 값 보존, remark에 def본문+env노트 둘 다 존재.
- run FK 고아 0건(§3 검사 재실행).
- 구 테이블 2개 삭제됨, 코드/템플릿에 `environment_definition` 잔존 참조 0(grep).
- 앱 부팅 + 환경 관리화면(통합) + 추적 화면 정상.

### 위험도
**높음(파괴적·스키마+코드 동시).** 백업 + dry-run 리뷰 + 승인 후 apply. 한 트랜잭션 처리, 코드 변경은 별도 커밋 권장.

---

## 메인 HANDOVER 반영 메모
- `HANDOVER.md` §4 끝(또는 TASK 10 뒤)에 **TASK 11** 스텁 추가.
- 후속 정리정돈 대상(다음 병합 후보)이 더 있으면 TASK 12+로 같은 양식 사용.
