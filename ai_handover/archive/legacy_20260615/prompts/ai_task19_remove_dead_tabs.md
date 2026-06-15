너는 이 저장소(`product_test_tracing_system`, FastAPI+SQLite, Windows)의 **관리자 대시보드 빈 탭 영역 + 죽은 시트 코드 정리**를 한다. 목적은 화면에 보이는 빈 껍데기 제거와 도달 불가 죽은 코드 삭제. **동작은 100% 보존(살아있는 탭/기능 불변). DB 스키마/데이터 변경 없음.**

## 배경 / 점검 결과
- 조사 대상: `app/templates/admin_dashboard.html` 의 Tab View 5 — Entity Sheets.
- Tab View 5(`#admin_tab_region_entity`, line 77-104)에는 탭 2개뿐: **Test Round**, **Runs**. 둘 다 실데이터 + 인라인 편집 + 하이라이트 살아있음 → **유지(삭제 금지)**.
- 사용자 "+" 커스텀 시트 탭은 localStorage/DB 저장 → 템플릿에 안 보임. 코드 판단 불가 → 손대지 않음.
- 진짜 빈 껍데기/죽은 코드는 Tab View 5 밖에 있음(아래).

## 삭제 대상

### 1. Tab View 2 빈 섹션 (확정, 안전)
- `app/templates/admin_dashboard.html` line 13-20 `#admin_tab_region_primary`.
- 내용 0개. Phase 4 주석만 있고 카드 없음 → 탭바도 안 생기고 빈 회색 박스만 렌더됨.
- **섹션(`<section class="card admin_tab_region_shell" id="admin_tab_region_primary">` ~ 닫는 `</section>`) 통째 삭제.**
- ⚠️ 삭제 전 확인: `tracking.js`에서 `admin_primary` / `tabview_2` / `admin_tab_region_primary` 참조(예: line 914 `admin_primary: {...}` 매핑, region refresh 로직)가 빈 영역 제거 후에도 에러 없이 동작하는지. 참조가 빈 DOM을 전제로 죽으면 해당 매핑 항목도 같이 정리.

### 2. sheet_service.py 죽은 코드 (선택, 별도 커밋)
- `app/services/sheet_service.py`.
- `SUPPORTED_SHEET_TABLES`(line 35) == `_REMOVED_SHEET_TABLES`(line 127) — 둘 다 `{case, result, release, defect, evidence}` 동일.
- 결과: `get_sheet_payload()`(line 130)는 모든 입력에서 항상 `ValueError` raise. `_build_case_sheet` / `_build_result_sheet` / `_build_release_sheet` / `_build_defect_sheet` / `_build_evidence_sheet` 5개 함수 전부 도달 불가.
- ⚠️ 단, 같은 파일의 `preview_sheet_update` / `apply_sheet_update` / `preview_evidence_create` / `apply_evidence_create` 는 별개 경로 — **이게 라우터/UI에서 아직 쓰이는지 먼저 grep 확인 후** 죽은 부분만 제거. 살아있으면 보존.
- 삭제 전 `get_sheet_payload` 호출처 grep → 호출 0건이면 함수+빌더 5개 제거. 1건이라도 있으면 멈추고 질문.

## ⚠️ 절대 규칙
1. **한 번에 한 가지.** Tab View 2 제거 → 검증 → 커밋 → 그다음 sheet_service 정리. 동시 변경 금지.
2. **살아있는 탭/기능 불변**: Test Round, Runs, 근무 캘린더(Tab View 3), 시험 추적(Tab View 4) 모두 동작 동일해야 함.
3. **NULL 바이트 고질병**: 편집 직후 `python -c "p=r'<file>';open(p,'wb').write(open(p,'rb').read().rstrip(b'\x00'))"` → 컴파일/`node --check` → `tail` 끝줄 확인.
4. DB 변경 금지. 기능 추가 금지. 모호하면 멈추고 질문.

## 검증 (각 단계 후)
- 앱 부팅 `GET /admin` 200. 대시보드 탭(2/3/4/5) 렌더 정상, 빈 Tab View 2만 사라짐.
- Test Round/Runs 인라인 편집·하이라이트 동작 동일.
- `run_tests.cmd --auto` 전체 green (회귀 0). ※ bare cmd는 대화형 프롬프트에서 멈춤 — 반드시 `--auto`.
- 수정 파일 NULL 0 + py_compile/node --check.

## 시작
1단계 Tab View 2 빈 섹션 제거부터. `tracking.js` 참조 영향 짧게 점검 → 제거 → 검증 → 커밋(`chore: remove empty Tab View 2 region`). 이후 2단계 sheet_service 죽은 코드는 호출처 grep 결과 보고 후 진행. 한 번에 하나, 동작 보존, 애매하면 질문.
