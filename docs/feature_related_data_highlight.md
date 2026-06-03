# 연관 데이터 하이라이트 기능

## 개요

**연관 데이터 하이라이트**는 제품 시험 및 개선 추적 현황 화면의 핵심 기능이다.

간트차트(시험 타임라인)와 미결 결함 테이블 간의 연관 관계를, 행(row)을 클릭하는 것만으로 시각적으로 즉시 파악할 수 있게 한다. 시험 중 결함 발생 지점부터 개선 완료까지의 추적성(traceability)을 한 화면에서 그려내는 것이 목적이다.

---

## 데이터 계층 구조

### 구성(Topology) 기반 (2026-06-03~)

```
시험 라운드 (예: Wi-Fi 1차 시험)
  └─ 구성행 (예: 1AP_1HRK_4HDR)             ← 간트차트 자식 행
       └─ RC 릴리즈 (예: RC1, hidden)        ← 결함이 실제 연결된 레벨
            └─ Run (시험 실행 세션)
                 └─ Result (case-level 결과)
                      └─ Defect (결함)        ← 미결 결함 테이블 행
```

구성 = 시험 시 AP와 장비의 물리적 연결 조합.
- `1AP_1HRK_4HDR` = AP 1대 + HRK 1대 + HDR 4대 연동
- `25AP_1HDR_1HDC` = AP 25대 + HDR 1대 + HDC 1대

### 구성 네이밍 규칙

```
{AP수}AP_{장비수}{장비명}_{장비수}{장비명}_...
```

- 장비 순서: HRK > HTR > HLM > HDR > HDC > HIIS
- 같은 장비 복수 대수는 합산 표기 (예: `4HDR`)
- 모호한 표현(`ALL`, `TARGET` 등) 금지, 항상 장비를 명시

`parent_release_id` 필드가 결함 행과 간트 구성행을 연결하는 키다.

---

## 현재 구현 상태

### Phase 1: 간트 ↔ 결함 (구현 완료)

간트차트와 미결 결함 테이블 2개 영역 간 양방향 하이라이트.

### Phase 2: 전체 테이블 연쇄 하이라이트 (미구현)

```
결함 클릭
  → 간트 구성행 하이라이트         ← Phase 1 (완료)
  → 해당 Run 하이라이트           ← Phase 2 (미구현, 테이블 없음)
  → 해당 Result 하이라이트        ← Phase 2 (미구현, 테이블 없음)
  → 해당 Case/Procedure 하이라이트 ← Phase 2 (미구현)
  → 해당 Evidence 하이라이트      ← Phase 2 (미구현, 데이터 없음)
```

Phase 2 구현을 위한 선행 작업:
1. API에 runs/results_summary 추가 (`tracking_router.py`)
2. Run/Result 요약 테이블 UI 렌더링 (`tracking-render.js`)
3. 연쇄 하이라이트 로직 구현 (`tracking-highlight.js`)

---

## 클릭 시나리오별 동작 (Phase 1)

### 1. 간트 라운드 행 클릭 (예: "Wi-Fi 1차 시험")

- 해당 라운드의 **모든 자식 구성행** 하이라이트
- 그 구성들과 연결된 **모든 결함 행** 하이라이트 (빨간색)
- 같은 행을 다시 클릭하면 하이라이트 해제

### 2. 간트 구성행 클릭 (예: "1AP_1HRK_4HDR")

- 해당 **구성행** 하이라이트
- 해당 구성과 연결된 **결함 행** 하이라이트 (빨간색)
- 결함 행으로 자동 스크롤

### 3. 결함 테이블 행 클릭

- 해당 **결함 행** 하이라이트 (빨간색)
- 결함이 발생한 **간트 구성행** 하이라이트 (빨간색)
- 간트 해당 구성행으로 자동 스크롤
- 부모 라운드행은 하이라이트하지 않음 (결함이 속한 구성행만 강조)

---

## 하이라이트 색상

| 상태 | CSS 클래스 | 색상 의미 |
|---|---|---|
| `TESTING` | `hl-testing` | 파랑 — 현재 시험 진행 중 |
| `BLOCKED` | `hl-blocked` | 빨강 — 시험 중단/결함 존재 |
| `PASSED` / `APPROVED` | `hl-passed` | 초록 — 시험 합격 |
| 기본 | `hl-default` | 노랑 |

결함 행과 결함 클릭 시 간트 구성행은 항상 `hl-blocked`(빨간색)으로 하이라이트된다.

---

## 추적성 시나리오 예시

### "1차 시험에서 HLM+HDR 연동이 BLOCKED됐는데, 관련 결함이 뭐야?"

1. 간트에서 `1AP_1HLM_4HDR` 구성행 클릭
2. 미결 결함 테이블에서 해당 결함들이 빨간색으로 하이라이트
3. 결함 ID, 심각도, 예상 해결일 즉시 확인 가능

### "이 결함이 어느 시험 구성에서 나온 거야?"

1. 결함 행 클릭 (예: `DEFECT-SQA_ISSUE_20260518_001`)
2. 간트에서 `1AP_1HLM_4HDR` 구성행이 빨간색으로 하이라이트
3. 시험 일정과 상태 즉시 파악 가능

### Phase 2 시나리오 (목표)

**"이 결함이 어느 Test Case의 어떤 Result에서 나왔어?"**

1. 결함 행 클릭
2. 간트 구성행 하이라이트
3. Run 테이블에서 해당 Run 행 하이라이트
4. Result 테이블에서 해당 Result 행 하이라이트
5. Case, Procedure, Evidence까지 연쇄 하이라이트

---

## 구현 위치

| 파일 | 역할 |
|---|---|
| `app/static/js/tracking-highlight.js` | 하이라이트 이벤트 바인딩 전체 로직 |
| `app/static/js/tracking-gantt-chart.js` | 간트 행 렌더링 (`data-row-id`, `data-parent-id` 속성) |
| `app/static/js/tracking-render.js` | 결함 행 렌더링 (`data-parent-release-id` 속성) |
| `app/routers/tracking_router.py` | `resolve_parent_release` 계산 |
| `app/static/css/tracking.css` | 하이라이트 색상 스타일 정의 |

### 핵심 데이터 속성

```html
<!-- 간트 라운드행 (부모) -->
<div class="gantt_row"
     data-row-id="TEST_RELEASE-WIFI_1ST"
     data-status="BLOCKED">

<!-- 간트 구성행 (자식) -->
<div class="gantt_row gantt_row_child"
     data-row-id="TEST_RELEASE-WIFI_1ST-1AP_1HRK_4HDR"
     data-parent-id="TEST_RELEASE-WIFI_1ST"
     data-status="BLOCKED">

<!-- 결함 행 -->
<tr data-release-id="TEST_RELEASE-WIFI_1ST-1AP_1HRK_4HDR-RC2"
    data-parent-release-id="TEST_RELEASE-WIFI_1ST-1AP_1HRK_4HDR"
    data-defect-id="DEFECT-SQA_ISSUE_20260507_004-RNO00157-01">
```

### 연결 키 흐름

```
결함 행.data-parent-release-id
  ↕ 매칭
간트 구성행.data-row-id

결함 행.data-release-id  →  RC release  →  run  →  result
  (Phase 2에서 활용)
```

### `resolve_parent_release` 로직 (`tracking_router.py`)

```
입력: run.product_test_release_id (RC release ID)
출력: 간트에 표시되는 구성행 ID (visible=1인 상위)

경로: RC(visible=0) → 구성행(visible=1) → 라운드(visible=1)
      resolve_parent_release는 구성행(visible=1이면서 부모도 visible=1인 행)을 반환
```

---

## 주의 사항

- RC 릴리즈(`release_visible=0`)는 간트에 표시되지 않으며, 하이라이트 매칭의 중간 키 역할만 한다.
- 새로운 결함을 추가할 때 `product_test_run.product_test_release_id`가 반드시 RC 릴리즈 ID를 가리켜야 연동이 정상 동작한다.
- RC 릴리즈가 `product_test_release` 테이블에 등록되어 있어야 `resolve_parent_release`가 구성행 ID를 올바르게 반환한다.
- 구성행의 `status`는 하위 RC의 result 집계로 자동 결정된다 (`tracking_router.py`의 부모 상태 자동결정 로직).
