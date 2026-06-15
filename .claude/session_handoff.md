# Session Handoff

## Current Goal
- 

## Debugger Findings
- 원인:
- 수정 대상:
- 수정 내용:
- 주의사항:

## Tester Findings
- 재현 조건:
- 실행한 테스트:
- 결과:
- 실패 로그:
- 추가 확인 필요:

## Shared Decisions
- 테스트 실행은 항상 `run_tests.cmd --auto` 또는 `uv run python run_tests.py --auto` 사용
- 이 파일이 AI agent 간 공유 상태의 단일 소스. 세션 시작/종료 시 overwrite
- 대화 내용 공유 금지. 변경 파악은 `git diff --name-only` / `git diff --stat` 기준으로만 요약
- debugger 세션은 테스트 실행 금지. 테스트 실행은 tester 세션만 한다.

## Open Issues
- [ ] 

## Changed Files
- 

## Do Not Touch
- `app/services/product_test_field_update_service.py` — 추가 코드만 있음, 기존 로직 수정 없음
- `app/services/product_test_run_service/_trace.py` — 추가 코드만 있음, 기존 로직 수정 없음
- `tests/playwright/conftest.py` — DB 초기화 로직 정상
