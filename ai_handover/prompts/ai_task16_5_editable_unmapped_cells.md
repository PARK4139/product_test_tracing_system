너는 이 저장소(`product_test_tracing_system`, FastAPI+SQLite, Windows)의 in-cell 편집을 **필드 차단 없이 자유 편집**으로 바꾼다. 사용자가 데이터 orphan 위험을 감수하기로 했다. 어떤 실제 컬럼 셀이든 클릭해서 수정·저장할 수 있어야 한다. **코드만(서비스/라우트/템플릿/JS/CSS). DB 스키마/데이터 마이그레이션은 없음.**

## 현재 메커니즘 (확인됨)
- 저장 단위 = `{entity_type, entity_id, field_name, value}` (`app/routers/admin_router.py`).
- `app/services/product_test_field_update_service.py`:
  - `ENTITY_MODEL_MAP`(46행) — entity_type→모델.
  - `_apply_single_update`(356행)가 **`FIELD_WHITELIST`** 로 `field_name not in 허용목록`이면 `Field not allowed for update`로 거부 → **이게 자유편집을 막는 핵심.**
  - `_coerce_field_value`(타입 변환), `_apply_status_update`(_status 특수 처리) 등.
- `app/static/js/admin-incell-edit.js` — 셀이 `entity_type/entity_id/field_name` 매핑을 들고 있어야 편집됨.

## 목표 — 차단 제거 + 매핑 보강
1. **필드 화이트리스트 차단 제거**: `_apply_single_update`에서 `FIELD_WHITELIST` 거부 로직을 없앤다(또는 "해당 엔티티의 실제 컬럼이면 모두 허용"으로 대체). **PK/FK/ID 포함 모든 실제 컬럼 편집 허용** — orphan/정합성 위험은 사용자가 감수.
   - 단, 쓰기 대상은 **그 엔티티의 실제 컬럼(`model.__table__.columns`)** 으로 한정한다. 존재하지 않는 속성에 setattr 하지 않도록 컬럼 존재만 확인(없는 컬럼이면 명확한 에러).
   - 타입 변환(`_coerce_field_value`)은 유지(정수/날짜 등 깨짐 방지). NOT NULL 위반 등 DB 에러는 그대로 사용자에게 메시지로 노출.
2. **셀 매핑 보강**: 각 admin 데이터 표/탭의 모든 데이터 컬럼 셀이 자기 `entity_type/entity_id/field_name`(= 그 컬럼) 매핑을 갖도록 템플릿 정비. 매핑만 있으면 JS가 편집 가능하게 함.
3. **계산/파생 셀**(예: RUN 개수, 집계 — 대응 DB 컬럼 없음): 저장 대상이 없으므로 편집 불가(읽기전용으로 표시). 이건 "차단"이 아니라 쓸 컬럼 자체가 없는 것.
4. JS: 실제 컬럼 매핑이 있는 셀은 전부 편집 진입 가능. 매핑 없는(파생) 셀만 읽기전용 표시.

## ⚠️ 규칙
- **NULL 바이트 고질병**: 편집 직후 `python -c "p=r'<file>';open(p,'wb').write(open(p,'rb').read().rstrip(b'\x00'))"` → py_compile/`node --check` → `tail` 확인.
- DB 스키마/데이터 마이그레이션 금지(코드만). 저장은 기존 bulk-update 경로 사용.
- Trace는 새 페이지 금지 — 현재 페이지 탭 안에서.
- 자유 편집이 목적이므로 임의로 새 차단을 만들지 말 것. 단 PK 변경이 같은 트랜잭션에서 SQLAlchemy identity와 충돌하면(예: PK setattr 후 flush 실패) 동작 방식을 사용자에게 보고하고 멈춰 확인.

## 검증
- 임의의 데이터 컬럼 셀(텍스트/상태/날짜, **PK/FK 포함**) 클릭 → 편집 → 저장 시 DB 반영, 새로고침 유지.
- 화이트리스트 거부 메시지(`Field not allowed for update`)가 더 이상 안 뜸.
- 파생/계산 셀은 읽기전용.
- `uv run pytest tests/ -q` — 기존 화이트리스트 의존 테스트가 있으면 자유편집 정책에 맞게 갱신, 전체 green.
- 편집 파일 NULL 0 + py_compile/node --check.

## 시작
`FIELD_WHITELIST` 차단 제거(컬럼 존재 검증으로 대체) → 셀 매핑 보강 → 표 하나씩 검증. PK setattr/flush 충돌 시 멈추고 보고.
