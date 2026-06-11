# HANDOVER 추가 — TASK 12-B: Target 병합 마무리 + 회귀 점검 (2026-06-09)

> TASK 12(Targets 병합)가 **데이터는 옮겼으나 코드/스키마 마무리가 덜 됨.** 그 잔여 + 회귀 점검.
> §0-1 수칙·§9 편집 규칙 적용. DB 변경은 dry-run→승인→백업.

---

## 0. 한 줄 요약 (caveman)

- target 데이터는 `product_test_target_unified`로 옮겨졌음(6행, FK 고아 0). 👍
- 근데 **models.py·구 테이블·화면 연결이 옛것 그대로** → 마무리 필요.
- 덤으로 **admin_router.py가 잘렸던 회귀**가 있었음(아래 4) — 같은 잘림 재발 주의.

---

## 1. 현재 진단 사실 (2026-06-09)

| 항목 | 상태 |
|---|---|
| `product_test_target_unified` | ✅ 6행, 모델6+실측3 컬럼, run FK 고아 0 |
| 구 `product_test_target` / `_definition` 테이블 | ⚠️ **빈 채로 남아있음(0행, 삭제 안 됨)** |
| `models.py` | ⚠️ 구 클래스 2개(`ProductTestTargetDefinition`,`ProductTestTarget`) 남음, **`*_unified` 모델 없음** |
| 화면 컨텍스트 | ⚠️ `list_product_test_target_definitions`/`list_product_test_targets`가 **구 빈 테이블** 조회 → 대시보드 target 비어 보임 |
| env 병합(TASK 11) | ✅ 완료(참고 모범: `ProductTestEnvironment`→`product_test_environment_unified`) |

---

## TASK 12-B — Target 병합 마무리 🟡코드+소량 DB

### 작업 내용 (codex)
1. **models.py 정합**:
   - `ProductTestTargetUnified` 모델 추가 → `__tablename__="product_test_target_unified"` (컬럼: product_test_target_id PK, product_code, manufacturer, model_name, hardware_revision, default_software_version, default_firmware_version, serial_number, software_version, firmware_version, manufacture_lot, product_test_target_status, project_id, remark, created_at/by, updated_at/by).
   - 구 클래스 `ProductTestTargetDefinition`, `ProductTestTarget` **제거**.
   - (env 모델이 이미 이 패턴 → 그대로 따라 하면 됨)
2. **서비스/화면 repoint**:
   - `list_product_test_targets` 등 target 조회 함수가 **`product_test_target_unified`** 를 보게 수정(`product_test_run_service.py`).
   - 대시보드 컨텍스트(`_admin_dashboard_product_tracing_template_context`)의 `target_definition_rows`/`target_rows`를 **통합 1종(`target_rows`)** 으로 정리(목표 아키텍처 = Targets 단일 탭).
   - 템플릿 `product_test_targets_admin.html` + `product_test_target_definitions_admin.html` → **1개 화면 통합**, 구 화면 제거. grep: `target_definition`.
3. **구 빈 테이블 삭제(dry-run→승인→백업)**:
   - `product_test_target`, `product_test_target_definition` DROP. (0행 확인 후)
4. **검증**:
   - 앱 부팅 + `GET /admin` 200 + target 행이 unified에서 6건 보임.
   - `grep -rn target_definition app/` 잔존 0(주석/라벨 제외).
   - FK 고아 0(run→target_unified). py_compile 전 파일 통과.

### 대상파일
- `app/models.py`, `app/services/product_test_run_service.py`, `app/routers/admin_router.py`
- `app/templates/product_test_targets_admin.html`(통합), `..._target_definitions_admin.html`(제거)
- `scripts/drop_old_target_tables.py`(신규, dry-run)

---

## 2. ⚠️ 회귀 점검 (이미 1건 터짐)

### 2-1. admin_router.py 잘림 사고 (조치 완료, 재발 주의)
- 증상: `GET /admin` → `{"detail":"Not Found"}` 404.
- 원인 2개:
  1. 리팩토링 커밋에서 **`GET /admin` 대시보드 라우트가 통째로 누락**(report 진입 불가).
  2. 작업 도중 `admin_router.py` 파일이 **`status_code = 200 if o`에서 잘려** 저장됨(끝부분 db-truncate 라우트 유실, CRLF).
- 조치: git HEAD 완전본 복원 + `@admin_router.get("")` 대시보드 라우트 추가(아래). py_compile 통과 확인.
- **재발 방지**: 200줄+ 파일은 python으로 편집, **저장 후 즉시 `python -m py_compile` + `tail`로 끝줄 확인**(§9 규칙). 부분 Edit 후 파일 끝이 잘렸는지 항상 점검.

추가된 라우트(복원본):
```python
@admin_router.get("")
def render_admin_dashboard(request, database_session, current_role_name):
    _ensure_admin_role(current_role_name)
    context = _admin_dashboard_product_tracing_template_context(database_session=database_session)
    return _render_admin_shell_template(
        request=request, database_session=database_session,
        current_role_name=current_role_name,
        template_name="admin_dashboard.html",
        page_title="Product Test Data Tracing System",
        extra_context=context)
```

### 2-2. 기타
- `.git/index.lock` 잔존(권한 잠김) → Windows에서 `del .git\index.lock` 후 git 사용.
- codex 임시 폴더(`diag_*` 등) 권한 잠김 → `.gitignore`엔 추가됨, Windows에서 takeown 후 삭제.

---

## 메인 HANDOVER 반영
- §4에 **TASK 12-B** 스텁 추가. TASK 13(run 21건 재연결)·시트(7~9)는 그대로 후속.
