# Handover — 제품 시험 추적 시스템 (2026-06-02)

## 프로젝트 개요

- **위치**: `C:\Users\USER\Downloads\product_test_tracing_system`
- **기술스택**: FastAPI + SQLite + Jinja2, 프런트엔드 순수 JS (모듈화됨)
- **실행**: `run.cmd` (Windows에서 직접 실행, venv는 Windows 전용이라 sandbox에서 실행 불가)
- **포트**: 8008 (또는 8000)
- **DB**: `data/product_test_tracking_system.db` (WAL 모드)
- **로그**: `data/logs/app.log`

---

## 이번 세션에서 완료한 작업

### 1. JS 모듈화 (`tracking.js` → 10개 파일)
원래 800줄 단일 파일이 Edit 도구 한계(~200줄 이상 편집 시 파일 끝 잘림)로 반복 손상되어 분리.

| 파일 | 내용 | 줄수 |
|---|---|---|
| `tracking-client-log.js` | `window.clientLog()` 유틸 | 11 |
| `tracking-helpers.js` | badge, date 유틸 | 84 |
| `tracking-gantt-chart.js` | buildGantt (바 렌더링) | 162 |
| `tracking-gantt-resize.js` | 컬럼 리사이즈 + 데드라인 드래그 + initDeadlineDrag | 69 |
| `tracking-gantt-fold.js` | 간트 접기/펼치기 | 24 |
| `tracking-col-drag.js` | 컬럼 드래그&드롭 순서 저장 | 57 |
| `tracking-status.js` | 상태 드롭다운 + 통계 클릭 | 78 |
| `tracking-highlight.js` | 간트↔결함 하이라이트 연동 | 81 |
| `tracking-defect.js` | 결함 이미지 팝업, 컬럼 리사이즈 | 74 |
| `tracking-render.js` | renderTracking (HTML 빌더) | 128 |
| `tracking.js` | loadTracking + init | 66 |

**중요**: 파일 편집 시 Edit 도구 대신 `python3`으로 직접 문자열 교체할 것 (한글 포함 긴 줄 잘림 방지).

### 2. 데이터 계층 정합성 수정

**RC 릴리즈 구조 신규 추가**:
```
시험 라운드 (WIFI_1ST)
  └─ 장비행 (WIFI_1ST-HRK_9000A_1_1_1A)  ← 간트 표시, visible=1
       └─ RC 릴리즈 (HRK_9000A_1_1_1A-RC1)  ← 간트 숨김, visible=0
            └─ 결함 (SQA_ISSUE_20260507_003)
```

RC 릴리즈 5건 (`product_test_release` 테이블, `release_visible=0`):
- `TEST_RELEASE-HRK_9000A_1_1_1A-RC1` → `WIFI_1ST-HRK_9000A_1_1_1A`
- `TEST_RELEASE-HRK_9000A_1_1_1A-RC2` → `WIFI_1ST-HRK_9000A_1_1_1A`
- `TEST_RELEASE-HRK_9000A_1_1_1A-RC3` → `WIFI_2ND-HRK_9000A_1_1_1A`
- `TEST_RELEASE-HRK_9000A_1_1_0A-RC1` → `WIFI_DOWNGRADE-HRK_9000A_1_1_0A`
- `TEST_RELEASE-HRK_9000A_1_1_1D-RC1` → `WIFI_1_1_1D-HRK_9000A_1_1_1D`

**`resolve_parent_release`** (`tracking_router.py`): `run.release_id`(RC) → 장비행 ID 반환.  
**`data-parent-release-id`**: 결함 테이블 행에 붙는 속성 = 장비행 ID.

### 3. 연관 데이터 하이라이트 (핵심 기능)

클릭 시 동작:
- 간트 라운드 행 클릭 → 자식 장비행 + 연결된 결함 행 하이라이트
- 간트 장비행 클릭 → 해당 결함 행 하이라이트
- 결함 행 클릭 → 간트 장비행 + 라운드 행 하이라이트

**현재 미해결**: 결함 클릭 시 간트 하이라이트 안 되는 버그.  
디버그 로그 추가됨 (`clientLog` → `data/logs/app.log`).  
서버 재시작 후 결함 클릭 → 로그 확인 필요:
```
grep "\[frontend\].*\[HL\]" data/logs/app.log | tail -5
```
- `parentReleaseId`가 빈 값이면 → `resolve_parent_release` 문제
- `deviceRow NOT FOUND`이면 → 간트 DOM에 해당 행 없음 (필터 문제)
- ID 정상이면 → CSS `gantt_hl` 스타일 확인

### 4. 기타 수정 사항

- 수정 우선순위: S/A → "필수수정", B → "차순위", C → "후순위"
- 요약 테이블: 통과율·블록된항목 제거, 미결 결함만 표시 (`defects.length` 기준)
- 2차 개선확인시험 HDC_9100 장비행 삭제 (2차 시험에서 PASSED였으므로 부적절)
- `wifi_release_id` → `parent_release_id` 전체 리네임
- 데드라인 선: 헤더에 드래그 가능, localStorage 저장 (`gantt_deadline_pct`)
- 오늘날짜 표시선: 헤더에만 라벨 표시

### 5. 개발 규칙 (README.md에 추가됨)

**프런트엔드 디버그 로그는 반드시 `clientLog()` 사용**:
```js
clientLog("메시지", {data: value});        // info
clientLog("에러", errorObj, "error");      // error
// console.log 금지
```

---

## DB 현재 상태

| 항목 | 값 |
|---|---|
| 전체 릴리즈 | 40건 |
| visible=1 (간트 표시) | 35건 |
| visible=0 (RC, 간트 숨김) | 5건 |
| 미결 결함 | 15건 |

**DB 수정 주의사항**: WAL 파일 문제로 직접 바이너리 쓰기 후 WAL을 truncate해야 함.
```python
# DB 수정 패턴
conn = sqlite3.connect('/tmp/work.db')  # 복사본에서 작업
# ... 수정 ...
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.commit(); conn.close()

db_path = '...product_test_tracking_system.db'
wal_path = db_path + '-wal'
with open('/tmp/work.db', 'rb') as f: data = f.read()
with open(db_path, 'r+b') as f: f.write(data); f.truncate()
with open(wal_path, 'r+b') as f: f.seek(0); f.truncate(0)  # WAL 초기화
```

---

## 다음 작업 후보

1. **결함 클릭 하이라이트 버그 수정** — 로그 확인 후 원인 파악
2. **`calcDateFromPct`의 `minD`/`totalMs` 스코프 문제** — `buildGantt` 내부 변수라 외부에서 접근 불가. 데드라인 드래그 시 날짜 계산 오류 가능성 있음. 전역 변수화 또는 모듈 구조 개선 필요
3. **타임라인 라벨 표현 개선** — "배포 이력 타임라인" → 더 적합한 이름 검토
4. **HDR-7100P 장비** — 엑셀에는 있지만 간트에 없음. 추가 여부 확인 필요

---

## 파일 편집 규칙 (반드시 준수)

1. **200줄 이상 파일 편집 시 Edit 도구 사용 금지** — python으로 직접 처리
2. **편집 후 항상 null 바이트 제거**:
   ```python
   with open(path, 'rb') as f: c = f.read()
   c = c.rstrip(b'\x00')
   with open(path, 'wb') as f: f.write(c)
   ```
3. **편집 후 항상 문법 검증**: `node -c <파일>`
4. **한글 문자열이 포함된 긴 줄은 영문으로 대체**하거나 python으로 작성
