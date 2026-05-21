# Product Test Tracing System

Product Test 데이터 입력, 검토, 승인, 내보내기를 위한 FastAPI 기반 내부 시스템이다.

이 프로젝트는 ELT TEST 추적 시스템을 기반으로 가져왔고, 현재는 Product Test 기준으로 운영 문구와 흐름을 정리한 상태다. MVP 전제가 아니라 실제 운영 프로덕트 기준으로 유지보수하는 것을 목표로 한다.

## 핵심 특징

- QC_MODE 실행 시 로그인 화면 없이 `master_admin` 권한으로 바로 관리자 화면 진입
- 사용자 입력 화면과 관리자 검토 화면 분리
- SQLite 기반 로컬 데이터 저장
- 제출 단위(`form_submission`)와 행 단위(`test_result`) 분리 관리
- 저온/고온 시험 시작, 종료, 소요시간 자동 계산
- 관리자 검토완료 처리, 제출 승인, 엑셀 내보내기 지원
- 드롭다운 옵션 및 사용자 계정 관리 기능 포함

## 기술 스택

- Python 3.12+
- FastAPI
- SQLAlchemy
- Jinja2
- SQLite
- OpenPyXL
- Uvicorn
- Watchdog

## 디렉터리 구조

```text
product_test_tracing_system/
├─ app/
│  ├─ routers/        # 인증, 관리자, 사용자, 제출, 내보내기 라우터
│  ├─ services/       # 도메인 서비스, 엑셀 처리, 드롭다운 관리
│  ├─ templates/      # Jinja2 HTML 템플릿
│  ├─ static/         # CSS, JS, 이미지
│  ├─ models.py       # ORM 모델
│  ├─ db.py           # DB 초기화 및 마이그레이션성 보정
│  └─ config.py       # 앱 설정 및 DB 파일 경로
├─ data/              # SQLite DB 파일 저장 위치
├─ docs/
├─ run.py             # 실행 진입점
├─ run.cmd            # Windows 실행 스크립트
├─ pyproject.toml
└─ README.md
```

## 실행 방법

### 1. 의존성 설치

```powershell
uv sync
uv sync --group dev
```

테스트 실행:

```powershell
.\test.cmd
```

또는

```powershell
uv run python test.py
```

(`test.py`는 `tests/unit`, `tests/e2e_api`, `tests/integration` 아래 모든 `test_*.py`를 순서대로 실행한다.)

```powershell
uv run pytest
```

### 2. 실행

```powershell
.\run.cmd
```

또는

```powershell
uv run python run.py
```

## 실행 모드

이 프로젝트는 상위 디렉터리의 `.env` 파일을 읽는다.

기본값:

```env
QC_MODE=True
KIOSK_MODE=True
```

### QC_MODE=True

- 브라우저를 자동 실행한다.
- 시작 URL은 `http://127.0.0.1:8000/admin` 이다.
- `/`, `/login`, `/logout` 접근 시 모두 `master_admin` 쿠키를 세팅하고 관리자 화면으로 이동한다.
- 파일 변경 감지 후 브라우저 새로고침 또는 서버 재시작을 수행한다.

### QC_MODE=False

- 일반 FastAPI 서버로 실행된다.
- 로그인 페이지를 통해 역할별 접근을 사용한다.

## 기본 URL

- 관리자 화면: [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin)
- 사용자 화면: [http://127.0.0.1:8000/user](http://127.0.0.1:8000/user)
- 로그인 화면: [http://127.0.0.1:8000/login](http://127.0.0.1:8000/login)

단, QC_MODE에서는 로그인 화면을 실질적으로 사용하지 않는다.

## 데이터 저장소

- SQLite 파일 경로: `data/product_test_tracking_system.db`
- 앱 시작 시 테이블 생성 및 스키마 보정 로직이 자동 실행된다.

초기화 로직은 다음을 포함한다.

- 누락 컬럼 보정
- 기존 `test_result` 스키마를 4-key 구조로 보정
- `form_submission` 백필
- 기본 드롭다운 옵션 생성
- UI 샘플 프로필 생성

## 주요 도메인 모델

### `user_account`

- 사용자 계정
- 역할: `tester`, `admin`, `master_admin`

### `form_submission`

- 제출 단위 엔티티
- 상태: `draft`, 제출 이후 상태

### `test_result`

- 실제 Product Test 행 데이터
- 자연키:
  - `key_1`: 업체명
  - `key_2`: 양식제출자
  - `key_3`: 모델명
  - `key_4`: 공정번호

### `dropdown_option`

- 드롭다운 항목 관리

## 주요 기능

### 사용자 화면

- 제출 생성
- 행 추가, 수정, 삭제
- 저온/고온 시험 시간 기록
- 제출 저장 및 제출 완료

### 관리자 화면

- 최근 입력 데이터 검토
- 검토완료/검토대기 전환
- 제출 승인 및 삭제
- 관리자 계정 생성
- 업체 사용자 생성 및 가입 승인
- 드롭다운 옵션 추가/삭제
- 엑셀 다운로드
- 기존 엑셀 파일에 데이터 append

## 엑셀 내보내기

관리자 화면에서 두 가지 방식 지원:

- 현재 데이터 새 엑셀 다운로드
- 기존 엑셀 파일 특정 시트에 현재 데이터 append

다운로드 파일명 형식:

```text
product_test_data_YYMMDD.xlsx
```

## 개발 메모

### 1. QC_MODE는 운영 편의용 강제 관리자 진입 모드

현재 QC_MODE에서는 인증 흐름보다 관리자 검토 작업 우선이다. 일반 사용자 플로우 검증이 필요하면 `QC_MODE=False` 로 실행해야 한다.

### 2. 브라우저 자동 제어 포함

`run.py` 는 Windows 환경에서 Chrome을 찾고, 전용 프로필 디렉터리(`.chrome_qc_profile`)로 실행한다.

### 3. DB 파일명 변경

기존 ELT 기준 DB 파일명이 아니라 현재는 아래 경로를 사용한다.

```text
data/product_test_tracking_system.db
```

기존 `elt_test_tracking_system.db` 데이터를 계속 써야 하면 별도 마이그레이션 또는 파일 이관이 필요하다.

## 빠른 점검 명령

문법 확인:

```powershell
python -m py_compile .\app\routers\auth_router.py .\app\routers\admin_router.py .\app\routers\tester_router.py .\app\routers\export_router.py .\run.py
```

ELT 문구 잔존 검색:

```powershell
rg -n -i "elt" .
```

## 후속 권장 작업

- Product Test 도메인 용어에 맞게 `low_test` / `high_test` 내부 필드명 재정의 여부 결정
- 실제 운영 계정 정책과 QC_MODE 강제 admin 모드 분리
- API/화면 테스트 추가
- 기존 ELT 데이터 이관 정책 확정
