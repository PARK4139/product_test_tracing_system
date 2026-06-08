# Codex 작업 프롬프트 — 제품 시험 추적 시스템 정합성

아래 블록을 codex에 그대로 전달.

---

너는 이 저장소(`product_test_tracing_system`)의 정합성 개선 작업을 맡는다.

## 먼저 읽어라
1. `HANDOVER.md` — 작업 지시서. **이게 단일 진실(source of truth)**.
2. `docs/data_integrity_diagnosis_20260608.md` — 진단 근거.
특히 `HANDOVER.md`의 **§0-1 실수 방지 수칙**, **§4 TASK 순번**, **§5 정본 토폴로지**, **§6 정책 결정**을 정독하고 시작한다.

## 절대 규칙 (위반 금지)
- **한 번에 한 TASK만.** §4의 TASK 번호 순서대로(1→2→3→…) 진행. 현재 TASK의 "검증" 항목을 통과하기 전에는 다음 TASK로 넘어가지 않는다.
- **DB는 WAL 모드.** 조회 시 `.db` 단독으로 읽지 말고, `PRAGMA wal_checkpoint(TRUNCATE)` 후 읽거나 `.db`+`-wal`+`-shm`를 복사한 **읽기 전용 복사본**에서 조회한다.
- **DB를 바꾸는 작업(TASK 4 이상)은 절대 자동 실행 금지.** 항상 ① dry-run 결과만 출력 → ② 내(사용자) 승인 대기 → ③ 승인 후에만 자동 백업 + `--apply`. 승인 없이 `--apply` 실행 시 작업 실패로 간주.
- **DB가 정본, `models.py`는 따라간다.** 거꾸로 DB/`db.py`를 모델에 맞춰 바꾸지 않는다.
- **정본 토폴로지(§5)·정책(§6)은 그대로 따른다. 추측 금지.** 목록/정책에 없거나 모호하면 **멈추고 질문**한다.
- PK 변경 시 참조 FK(`result.product_test_case_id`, `procedure.product_test_case_id` 등) 동시 UPDATE, 구 값은 `remark`에 보존.
- 200줄+ 파일은 python으로 편집, 편집 후 null 바이트 제거 + 문법 검증. 프런트 디버그는 `clientLog()`만(`console.log` 금지).

## 이번에 진행할 범위
- **TASK 1 → 2 → 3 까지는 위험이 없으니 연속으로 진행**해도 된다 (각 TASK 검증 통과 확인하면서).
- **TASK 4부터는 한 TASK 끝낼 때마다 멈추고 내 승인을 받는다.** DB 변경 dry-run 결과를 보여주고 대기.

## 각 TASK 보고 형식 (TASK 끝낼 때마다)
```
[TASK N] 제목
- 변경 파일: ...
- 한 일: (요약)
- 검증 결과: (HANDOVER의 "검증" 항목 통과 여부 + 수치)
- 위험/주의: ...
- 다음: TASK N+1 진행 가능 여부 (DB 변경이면 "승인 요청")
```

## 시작
`HANDOVER.md`를 읽었음을 1줄로 확인한 뒤, **TASK 1 (정합성 진단 스크립트화)** 부터 시작하라.
