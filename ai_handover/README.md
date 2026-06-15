# ai_handover — AI 협업 (역할 기반)

AI 에이전트(claude/codex/cursor)가 이 저장소 작업을 이어가기 위한 **역할별 규칙(.rule) + 결과(.log)** 모음.

## 구조

```
ai_handover/
├─ README.md                ← (이 파일) 인덱스
├─ session/
│  ├─ session.rule          ← 공통 세션 규칙 (모든 역할 선행) + 역할 정의 + 안전 수칙
│  └─ session.log           ← 세션 진행상황 + 정본 포인터
├─ planner/   planner.rule  + planner.log    ← 계획
├─ upserter/     upserter.rule    + upserter.log       ← 구현 (★Claude 기본 역할)
├─ tester/    tester.rule   + tester.log      ← 검증 (★사용자 담당, Claude 아님)
├─ debugger/  debugger.rule + debugger.log    ← 디버그
├─ master_architecture.md   ← 목표 구조 정본 (참조)
├─ tasks/                    ← 개별 TASK 상세 스펙 (참조)
└─ archive/                  ← 구 문서 보존
```

## 사용법

- **규칙(.rule)** = 역할에게 주는 지시(입력). 새 AI에 해당 `.rule` 본문을 전달.
- **결과(.log)** = 역할이 남기는 보고(출력). 최신순 누적.
- 워크플로: **planner → upserter → tester → debugger** (디버그 결과는 다시 upserter).
- 시작 전 반드시 `session/session.rule` 먼저 읽을 것.

## 핵심 규칙 (요약, 전체는 session.rule)

- 편집 직후 NULL 제거 + `py_compile`/`node --check`.
- DB 변경 = dry-run → 승인 → 백업 → apply.
- 테스트는 **`run_tests.cmd --auto`** 만. **Claude는 테스트 실행 안 함 — 사용자(tester) 담당.**
- 최소 수정, 기존 구조 유지, 모호하면 질문.
