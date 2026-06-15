# Upserter 작업 보고 (add session)

## 커밋 이력

| 커밋 | 내용 |
|---|---|
| `35881f1` | chore: remove empty Tab View 2 region |
| `c7b6cdb` | chore: remove dead sheet_service code (Phase 4 remnants) |
| `3137aed` | feat: rename Environment → Config across codebase + DB migration |

---

## Task 19: Remove Dead Tabs & Sheet Code

### 1단계: Tab View 2 빈 섹션 제거
- `admin_dashboard.html`: `#admin_tab_region_primary` 섹션 삭제
- `tracking.js`: `TAB_VIEW_TABLE_FOLD_META`의 `admin_primary` 항목 삭제
- **근거**: `tabViewRegionHasFoldableContent`의 `!shell` 가드 → DOM 없어도 에러 없음

### 2단계: sheet_service.py 죽은 코드 제거
- `sheet_service.py`: `_REMOVED_SHEET_TABLES`, `get_sheet_payload`, `_build_*` 5개 삭제 (939라인)
- `sheet_router.py`: `GET /admin/api/sheet/{table_name}` 엔드포인트 삭제 (항상 404)
- **근거**: `SUPPORTED_SHEET_TABLES == _REMOVED_SHEET_TABLES` → 모든 입력 ValueError

---

## Environment → Config 전체 리네임

### DB 마이그레이션 (앱 시작 시 자동 실행)
- `_migrate_environment_to_config()` 함수 추가 (`db.py`)
- `initialize_database()` 에서 `create_all` 직전 호출 (idempotent)
- `_get_or_create_project_engine()` 에도 적용

**DB 변경:**
| 변경 전 | 변경 후 |
|---|---|
| 테이블 `product_test_environment_unified` | `product_test_config_unified` |
| 컬럼 `product_test_environment_id` | `product_test_config_id` |
| 컬럼 `product_test_environment_name` | `product_test_config_name` |
| 컬럼 `product_test_environment_status` | `product_test_config_status` |
| `product_test_run.product_test_environment_id` | `product_test_run.product_test_config_id` |
| 뷰 `product_test_environment` | `product_test_config` |
| 뷰 `product_test_environment_definition` | `product_test_config_definition` |

### 코드 변경 (26개 파일)
- `ProductTestEnvironment` → `ProductTestConfig`
- `ENVIRONMENT_STATUS_VALUES` → `CONFIG_STATUS_VALUES`
- `/product-test-environments` → `/product-test-configs`
- `trk_test_environment_table` → `trk_test_config_table`
- UI: "Environment" → "Config", "Test Environment" → "Test Config"

### 변경하지 않은 것 (데이터 값 / 저장된 키)
| 항목 | 이유 |
|---|---|
| `SQA_PRODUCT_TEST_ENVIRONMENT_ID-*` | DB 저장 ID 포맷 |
| `"environment_issue"` | DB에 저장된 status 코드 |
| `"entity/environment"` | custom_sheet_trace DB region_key |
| custom_sheet JSON 필드 `environment_name` | DB 저장 JSON 키 |

---

## 검증 상태
- `py_compile` OK (19개 Python 파일)
- `node --check` OK (3개 JS 파일)
- 앱 부팅 / DB migration / 회귀 테스트 → **사용자 직접 확인 필요**
