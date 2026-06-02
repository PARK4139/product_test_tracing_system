# 연관 데이터 하이라이트 기능

## 개요

**연관 데이터 하이라이트**는 제품 시험 및 개선 추적 현황 화면의 핵심 기능이다.

간트차트(시험 타임라인)와 미결 결함 테이블 간의 연관 관계를, 행(row)을 클릭하는 것만으로 시각적으로 즉시 파악할 수 있게 한다. 시험 중 결함 발생 지점부터 개선 완료까지의 추적성(traceability)을 한 화면에서 그려내는 것이 목적이다.

---

## 동작 방식

### 데이터 계층 구조

```
시험 라운드 (예: Wi-Fi 2차 시험)
  └─ 장비행 (예: HDR-9000 1.1.8)          ← 간트차트 자식 행
       └─ RC 릴리즈 (예: RC3, hidden)      ← 결함이 실제 연결된 레벨
            └─ 결함 (예: SQA_ISSUE_20260519_001)  ← 미결 결함 테이블 행
```

`parent_release_id` 필드가 결함 행과 간트 장비행을 연결하는 키다.

---

## 클릭 시나리오별 동작

### 1. 간트 라운드 행 클릭 (예: "Wi-Fi 2차 시험")

- 해당 라운드의 **모든 자식 장비행** 하이라이트
- 그 장비들과 연결된 **모든 결함 행** 하이라이트
- 같은 행을 다시 클릭하면 하이라이트 해제

### 2. 간트 장비행 클릭 (예: "HRK-9000A 1.1.1A")

- 해당 **장비행** 하이라이트
- 해당 장비와 연결된 **결함 행** 하이라이트
- 결함 행으로 자동 스크롤

### 3. 결함 테이블 행 클릭

- 해당 **결함 행** 하이라이트
- 결함이 발생한 **간트 장비행** 하이라이트
- 해당 장비행의 상위 **라운드 행** 도 함께 하이라이트
- 간트 해당 장비행으로 자동 스크롤

---

## 하이라이트 색상

| 상태 | 색상 의미 |
|---|---|
| `TESTING` | 파랑 — 현재 시험 진행 중 |
| `BLOCKED` | 빨강 — 시험 중단/결함 존재 |
| `PASSED` / `APPROVED` | 초록 — 시험 합격 |
| 기본 | 회색 |

결함 행은 항상 `BLOCKED` 색상(빨강)으로 하이라이트된다.

---

## 추적성 시나리오 예시

**"2차 시험에서 HDR이 BLOCKED됐는데, 관련 결함이 뭐야?"**

→ 간트에서 `HDR-9000 1.1.8` 장비행 클릭  
→ 미결 결함 테이블에서 해당 결함들이 빨간색으로 하이라이트  
→ 결함 ID, 심각도, 예상 해결일 즉시 확인 가능

**"이 결함이 어느 시험 라운드에서 나온 거야?"**

→ 결함 행 클릭  
→ 간트에서 시험 라운드(예: WIFI_2ND)와 장비행(HRK-9000A)이 동시에 하이라이트  
→ 시험 일정과 상태 즉시 파악 가능

---

## 구현 위치

| 파일 | 역할 |
|---|---|
| `app/static/js/tracking-highlight.js` | 하이라이트 이벤트 바인딩 전체 로직 |
| `app/static/js/tracking-gantt-chart.js` | 간트 행 렌더링 (`data-row-id`, `data-parent-id` 속성) |
| `app/static/js/tracking-render.js` | 결함 행 렌더링 (`data-parent-release-id` 속성) |
| `app/routers/tracking_router.py` | `parent_release_id` 계산 (`resolve_parent_release`) |

### 핵심 데이터 속성

```html
<!-- 간트 장비행 -->
<div class="gantt_row gantt_row_child"
     data-row-id="TEST_RELEASE-WIFI_2ND-HRK_9000A_1_1_1A"
     data-parent-id="TEST_RELEASE-WIFI_2ND"
     data-status="BLOCKED">

<!-- 결함 행 -->
<tr data-release-id="TEST_RELEASE-HRK_9000A_1_1_1A-RC3"
    data-parent-release-id="TEST_RELEASE-WIFI_2ND-HRK_9000A_1_1_1A">
```

`data-parent-release-id` = 결함의 RC 릴리즈가 속한 **간트 장비행 ID**  
이 값이 간트 `data-row-id`와 매칭되어 하이라이트가 연동된다.

---

## 주의 사항

- RC 릴리즈(`release_visible=false`)는 간트에 표시되지 않으며, 하이라이트 매칭의 중간 키 역할만 한다.
- 새로운 결함을 추가할 때 `product_test_run.product_test_release_id`가 반드시 RC 릴리즈 ID를 가리켜야 연동이 정상 동작한다.
- RC 릴리즈가 `product_test_release` 테이블에 등록되어 있어야 `resolve_parent_release`가 장비행 ID를 올바르게 반환한다.
