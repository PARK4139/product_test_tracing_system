# Task 19 완료 보고 — Remove Dead Tabs & Sheet Code

## 커밋 이력

| 커밋 | 내용 |
|---|---|
| `35881f1` | chore: remove empty Tab View 2 region |
| `c7b6cdb` | chore: remove dead sheet_service code (Phase 4 remnants) |

---

## 1단계: Tab View 2 빈 섹션 제거

### 변경 파일
- `app/templates/admin_dashboard.html`
- `app/static/js/tracking.js`

### 내용
- HTML: `#admin_tab_region_primary` 섹션 통째 삭제 (Phase 4 이후 내용 0, 빈 회색 박스만 렌더됨)
- JS: `TAB_VIEW_TABLE_FOLD_META`의 `admin_primary` 항목 삭제

### 안전 근거
`tabViewRegionHasFoldableContent`이 `!shell` 가드로 DOM 없으면 `false` 반환. `attachSheetTabFoldHandlers`는 `!meta` 가드. 라인 2086 `if (foldMeta)` 가드. JS 에러 없음.

---

## 2단계: sheet_service.py 죽은 코드 제거

### 변경 파일
- `app/services/sheet_service.py`
- `app/routers/sheet_router.py`

### 삭제 목록
| 항목 | 이유 |
|---|---|
| `_REMOVED_SHEET_TABLES` | `get_sheet_payload` 제거 후 참조처 없음 |
| `get_sheet_payload` | `SUPPORTED_SHEET_TABLES == _REMOVED_SHEET_TABLES` → 항상 ValueError → 실질적 dead endpoint |
| `_build_case_sheet` | `get_sheet_payload` 통해서만 도달 가능 → unreachable |
| `_build_result_sheet` | 동일 |
| `_build_release_sheet` | 동일 |
| `_build_defect_sheet` | 동일 |
| `_build_evidence_sheet` | 동일 |
| `GET /admin/api/sheet/{table_name}` (router) | `get_sheet_payload` 삭제로 import 불가 + 항상 404였음 |

### 보존 항목
| 항목 | 이유 |
|---|---|
| `SUPPORTED_SHEET_TABLES` | `_build_sheet_update_preview` line 524에서 사용 (alive) |
| `SHEET_EDIT_CONFIG`, `TABLE_MODEL_MAP` | preview/apply 경로에서 사용 |
| `_sheet_meta` | `_build_evidence_create_preview` line 732에서 사용 |
| `preview_sheet_update`, `apply_sheet_update` | router에서 PATCH 엔드포인트 활성 사용 |
| `preview_evidence_create`, `apply_evidence_create` | router에서 활성 사용 |

### 호출처 grep 결과
```
sheet_router.py:57: payload = get_sheet_payload(...)  ← 1건 존재
```
→ 엔드포인트 자체가 항상 404 (dead route)이므로 라우터와 함께 제거.

---

## 검증 상태

- `py_compile` OK (sheet_service.py, sheet_router.py)
- `node --check` OK (tracking.js)
- NULL 바이트 제거 완료
- 앱 부팅 / 회귀 테스트 → **사용자 직접 확인 필요** (`run_tests.cmd --auto`)
