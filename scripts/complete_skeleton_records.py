#!/usr/bin/env python3
"""
skeleton 레코드 보완 스크립트
================================================================================
마이그레이션 후 DRAFT/SKELETON 상태로 남은 레코드들을 원본 Excel 분석을 토대로
최대한 보완합니다.

실행 방법 (프로젝트 루트에서):
  python scripts/complete_skeleton_records.py

보완 대상:
  1. TEST_CASE-20AP-SMOKE_TEST-001
     → 20AP 환경 다운그레이드 비교 시험 Smoke Test
  2. Wi-Fi 재ON 후 복구
     → 기존 TEST_CASE-1AP_1HRK-WIFI-라우터_재부팅_후_복구-001 패턴 기반 보완
  3. 라우터 재부팅 후 복구
     → 기존 TEST_CASE-1AP_1HRK-WIFI-라우터_재부팅_후_복구-001 패턴 기반 보완
  4. 시험대상장비 재부팅 후 복구
     → 기존 TEST_CASE-1AP_1HRK-WIFI-시험대상_장비_재부팅_후_복구-001 패턴 기반 보완
  5. PLACEHOLDER_EMPTY_CASE
     → 미입력 예정 항목 (no=382, 383): 향후 채워야 함 표시
  6. skeleton env: TEST_CONFIG-5GHz_연결성-20AP_4HDR 다운그레이드 시험
     → Report 정보에서 파악한 환경 정보로 보완
================================================================================
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
MAIN_DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"

PROJECT_ID = "WIFI_CONNECTIVITY_TEST_2026"
UPDBY      = "complete_skeleton_v1"
NOW        = datetime.now(timezone.utc).isoformat()


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def update_case(conn: sqlite3.Connection, case_id: str, title: str,
                objective: str, precondition: str, expected: str,
                status: str, remark: str) -> None:
    conn.execute("""
        UPDATE product_test_case SET
            product_test_case_title  = ?,
            test_objective           = ?,
            precondition             = ?,
            expected_result          = ?,
            product_test_case_status = ?,
            updated_at               = ?,
            updated_by               = ?,
            remark                   = ?
        WHERE product_test_case_id = ? AND project_id = ?
    """, (title, objective, precondition, expected, status,
          NOW, UPDBY, remark, case_id, PROJECT_ID))


def add_procedure(conn: sqlite3.Connection, case_id: str,
                  seq: int, action: str, criteria: str,
                  remark: str | None = None) -> None:
    proc_id = f"{case_id}_STEP_{seq:03d}"
    existing = conn.execute(
        "SELECT 1 FROM product_test_procedure WHERE product_test_procedure_id=?",
        (proc_id,)
    ).fetchone()
    if not existing:
        conn.execute("""
            INSERT INTO product_test_procedure
              (product_test_procedure_id, project_id, product_test_case_id,
               procedure_sequence, procedure_action, acceptance_criteria,
               product_test_procedure_status,
               created_at, created_by, updated_at, updated_by, remark)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (proc_id, PROJECT_ID, case_id, seq, action, criteria,
              "ACTIVE", NOW, UPDBY, NOW, UPDBY, remark))


def update_env_def(conn: sqlite3.Connection, env_def_id: str, name: str,
                   test_room: str, network_type: str, remark: str) -> None:
    conn.execute("""
        UPDATE product_test_environment_definition SET
            product_test_environment_definition_name   = ?,
            test_company                               = 'Huvitz',
            test_room                                  = ?,
            network_type                               = ?,
            product_test_environment_definition_status = 'ACTIVE',
            updated_at = ?, updated_by = ?,
            remark     = ?
        WHERE product_test_environment_definition_id = ? AND project_id = ?
    """, (name, test_room, network_type, NOW, UPDBY, remark,
          env_def_id, PROJECT_ID))


def update_env(conn: sqlite3.Connection, env_id: str, name: str,
               network_type: str, remark: str) -> None:
    conn.execute("""
        UPDATE product_test_environment SET
            product_test_environment_name   = ?,
            network_type                    = ?,
            product_test_environment_status = 'ACTIVE',
            updated_at = ?, updated_by = ?,
            remark     = ?
        WHERE product_test_environment_id = ? AND project_id = ?
    """, (name, network_type, NOW, UPDBY, remark, env_id, PROJECT_ID))


def main() -> None:
    if not MAIN_DB_PATH.exists():
        sys.exit(f"[ERROR] DB 없음: {MAIN_DB_PATH}\n"
                 "먼저 migrate_excel_to_db.py 를 실행하세요.")

    conn = open_db(MAIN_DB_PATH)
    print("=" * 65)
    print("  skeleton 레코드 보완 시작")
    print("=" * 65)

    # ──────────────────────────────────────────────────────────────────────────
    # 1. TEST_CASE-20AP-SMOKE_TEST-001
    #    - 다운그레이드 비교 시험에서 20AP 환경 전체 연결 smoke test
    #    - 결과 status=None (시험 미완료 또는 기록 미입력)
    #    - combo=VARIOUS_CONNECTIONS → 5개 제품 각각의 연결 상태 전수 확인
    # ──────────────────────────────────────────────────────────────────────────
    cid = "TEST_CASE-20AP-SMOKE_TEST-001"
    update_case(conn, cid,
        title      = "20AP 환경 Wi-Fi 연결 Smoke Test (다운그레이드 비교)",
        objective  = "5개 제품(HRK·HLM·HTR·HDR·HDC)이 20AP(연결할AP 1대 + 주변AP 19대) 환경에서 "
                     "구버전 S/W로 다운그레이드한 뒤에도 Wi-Fi 연결이 정상 동작하는지 전반 확인",
        precondition = (
            "1. 연결할AP: MERCUSYS MR30G 1대 (5GHz, SSID 설정완료)\n"
            "2. 주변AP: 5GHz AP 19대 전원 ON (RSSI 강함 모의)\n"
            "3. 시험대상 5개 제품 각각 구버전 S/W 다운그레이드 완료\n"
            "   - HRK-9000A 1.1.0A / HLM-9000 1.1.13B / HTR-1A 1.1.8B\n"
            "   - HDR-9000 1.1.7A / HDC-9100 1.0.4A\n"
            "4. OP 장비와 동일 네트워크 연결 확인"
        ),
        expected   = "5개 제품 모두 연결할AP에 정상 연결되고 데이터 송수신 이상 없음",
        status     = "ACTIVE",
        remark     = (
            "[보완근거] TEST_REPORT_WIFI_DOWNGRADE_TEST_260526_1454 리포트에서 참조됨\n"
            "[연결구성] VARIOUS_CONNECTIONS (20AP 환경, 5개 제품)\n"
            "[원본 결과] status=None (시험 기록 미입력 — 별도 확인 필요)\n"
            "[Config] TEST_CONFIG-5GHz_연결성-20AP_4HDR-TARGET_Wi-Fi_기능_다운그래이드_비교_시험-20260526-001"
        ),
    )
    # Procedure 추가
    add_procedure(conn, cid, 1,
        action   = "5개 시험대상 제품 각각 SETUP MODE → WIFI 탭으로 이동 후 SCAN 실행",
        criteria = "연결할AP SSID가 AP List에 표시되는지 확인")
    add_procedure(conn, cid, 2,
        action   = "연결할AP SSID 선택 후 인증 진행",
        criteria = "5개 제품 모두 연결할AP에 정상 연결됨 확인 (Wi-Fi 아이콘 연결상태)")
    add_procedure(conn, cid, 3,
        action   = "각 제품에서 측정/데이터 전송 동작 수행",
        criteria = "측정 데이터 정상 전송 및 OP 화면 수신 확인")
    add_procedure(conn, cid, 4,
        action   = "20AP 환경에서 3분간 연결 유지 모니터링",
        criteria = "연결 끊김 없이 3분 유지 확인")
    print(f"  [1/6] {cid} 보완 완료")

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Wi-Fi 재ON 후 복구
    #    - HRK-9000A 1.1.1D 시험 (1AP_1HRK_3HDR 구성), PASSED(OO)
    #    - OO = 양쪽 눈 데이터 모두 정상
    #    - 기존 패턴 참조: TEST_CASE-1AP_1HRK-WIFI-라우터_재부팅_후_복구-001
    #    ※ 이 Case ID는 비정규 형식(한글)으로 Test Cases 시트에서 누락된 것
    #      → 새 정규 ID 없이 원본 그대로 유지하며 내용만 보완
    # ──────────────────────────────────────────────────────────────────────────
    cid = "Wi-Fi 재ON 후 복구"
    update_case(conn, cid,
        title      = "Wi-Fi 재ON 후 연결 복구 확인 (1AP_1HRK_3HDR)",
        objective  = "HRK가 Wi-Fi를 OFF → ON 했을 때 AP 재연결 및 HDR 데이터 송수신이 "
                     "정상 복구되는지 확인",
        precondition = (
            "1. 연결구성: 1AP_1HRK_3HDR (AP 1대, HRK 1대, HDR 3대)\n"
            "2. HRK-9000A 1.1.1D, HDR-9000 1.1.8, HDR-7100P 1.1.7i 연결 완료\n"
            "3. REF/KER 측정 MODE 화면에서 정상 측정 상태 확인 후 시험 시작"
        ),
        expected   = "Wi-Fi 재ON 후 AP 자동 재연결 및 HDR 데이터 정상 수신 (OO: 양쪽 눈 정상)",
        status     = "ACTIVE",
        remark     = (
            "[보완근거] TEST_REPORT_HRK_9000A_1_1_1D_WIFI_TEST_260526, no=379, PASSED(OO)\n"
            "[연결구성] 1AP_1HRK_3HDR\n"
            "[원본 Case ID] 비정규 한글 ID — Test Cases 시트에 미등록\n"
            "[유사 정규 Case] TEST_CASE-1AP_1HRK-WIFI-라우터_재부팅_후_복구-001 패턴 참조\n"
            "[향후 조치] 정규 Case ID로 재등록 후 이 레코드를 deprecated 처리 권장"
        ),
    )
    add_procedure(conn, cid, 1,
        action   = "HRK SETUP MODE → WIFI 탭에서 Wi-Fi OFF 설정",
        criteria = "측정화면 우측상단 Wi-Fi 아이콘이 미연결 상태(회색)로 변경 확인")
    add_procedure(conn, cid, 2,
        action   = "30초 대기 후 HRK Wi-Fi ON 설정",
        criteria = "Wi-Fi 아이콘이 재연결 시도 상태(RSSI 신호세기 표기) 확인")
    add_procedure(conn, cid, 3,
        action   = "AP 재연결 완료 대기 (최대 1분)",
        criteria = "측정화면 우측상단 Wi-Fi & HDR 정상연결 상태 확인\n"
                   "· Wi-Fi 아이콘: 연결상태 (신호강도 색상)\n"
                   "· HDR 아이콘: 연결상태")
    add_procedure(conn, cid, 4,
        action   = "REF/KER 측정 수행 후 OP 화면과 데이터 비교",
        criteria = "측정화면 좌우 R, L 데이터와 OP Basic Operation 화면 데이터 일치 확인 (OO 기준)")
    print(f"  [2/6] '{cid}' 보완 완료")

    # ──────────────────────────────────────────────────────────────────────────
    # 3. 라우터 재부팅 후 복구
    #    - HRK-9000A 1.1.1D 시험 (1AP_1HRK_3HDR 구성), PASSED(XO)
    #    - XO = 한쪽 눈만 데이터 정상 (단안 측정 케이스)
    #    - 기존 TEST_CASE-1AP_1HRK-WIFI-라우터_재부팅_후_복구-001 과 동일 시나리오
    #      → 해당 정규 케이스의 비정규 alias로 추정
    # ──────────────────────────────────────────────────────────────────────────
    cid = "라우터 재부팅 후 복구"
    update_case(conn, cid,
        title      = "라우터(AP) 재부팅 후 Wi-Fi 연결 복구 확인 (1AP_1HRK_3HDR)",
        objective  = "연결 중인 AP(라우터)가 재부팅될 때 HRK가 자동으로 재연결되고 "
                     "HDR 데이터 송수신이 정상 복구되는지 확인",
        precondition = (
            "1. 연결구성: 1AP_1HRK_3HDR (AP 1대, HRK 1대, HDR 3대)\n"
            "2. HRK-9000A 1.1.1D 측정 중 정상 연결 상태\n"
            "3. AP: MERCUSYS MR30G 전원 ON 상태"
        ),
        expected   = "AP 재부팅 완료 후 HRK 자동 재연결 및 측정 데이터 정상 복구 (XO: 단안 측정 기준)",
        status     = "ACTIVE",
        remark     = (
            "[보완근거] TEST_REPORT_HRK_9000A_1_1_1D_WIFI_TEST_260526, no=380, PASSED(XO)\n"
            "[연결구성] 1AP_1HRK_3HDR\n"
            "[원본 Case ID] 비정규 한글 ID — Test Cases 시트에 미등록\n"
            "[동일 정규 Case] TEST_CASE-1AP_1HRK-WIFI-라우터_재부팅_후_복구-001 과 동일 시나리오\n"
            "[향후 조치] 정규 Case ID로 통합 권장"
        ),
    )
    add_procedure(conn, cid, 1,
        action   = "HRK가 AP에 연결된 상태에서 AP(라우터) 전원 OFF",
        criteria = "홈 화면 우측상단 Wi-Fi 아이콘이 미연결 상태 확인 (범례와 다른 상태)")
    add_procedure(conn, cid, 2,
        action   = "AP 재부팅 완료 대기 (약 1~2분) 후 전원 ON 확인",
        criteria = "AP 부팅 완료 후 SSID 브로드캐스트 정상 확인")
    add_procedure(conn, cid, 3,
        action   = "HRK 자동 재연결 대기 (최대 2분)",
        criteria = "홈 화면 우측상단 Wi-Fi 아이콘이 연결 상태 확인 (범례와 같은 상태)")
    add_procedure(conn, cid, 4,
        action   = "REF/KER 측정 수행 (단안 XO 기준)",
        criteria = "측정화면 우측상단 Wi-Fi & HDR 정상연결 상태 확인\n"
                   "측정 데이터 OP 화면과 일치 확인")
    print(f"  [3/6] '{cid}' 보완 완료")

    # ──────────────────────────────────────────────────────────────────────────
    # 4. 시험대상장비 재부팅 후 복구
    #    - HRK-9000A 1.1.1D 시험 (1AP_1HRK_3HDR 구성), PASSED(OO)
    #    - 기존 TEST_CASE-1AP_1HRK-WIFI-시험대상_장비_재부팅_후_복구-001 패턴 기반
    # ──────────────────────────────────────────────────────────────────────────
    cid = "시험대상장비 재부팅 후 복구"
    update_case(conn, cid,
        title      = "시험대상 장비 재부팅 후 Wi-Fi 연결 복구 확인 (1AP_1HRK_3HDR)",
        objective  = "시험대상 장비(HRK 또는 HDR)를 재부팅했을 때 Wi-Fi 및 HDR 연동이 "
                     "자동으로 복구되는지 확인",
        precondition = (
            "1. 연결구성: 1AP_1HRK_3HDR (AP 1대, HRK 1대, HDR 3대)\n"
            "2. HRK-9000A 1.1.1D 측정 중 정상 연결 상태\n"
            "3. 재부팅 전 REF/KER 측정 MODE 정상 동작 확인"
        ),
        expected   = "장비 재부팅 후 Wi-Fi 자동 재연결 및 HDR 연동 복구 (OO: 양쪽 눈 정상)",
        status     = "ACTIVE",
        remark     = (
            "[보완근거] TEST_REPORT_HRK_9000A_1_1_1D_WIFI_TEST_260526, no=381, PASSED(OO)\n"
            "[연결구성] 1AP_1HRK_3HDR\n"
            "[원본 Case ID] 비정규 한글 ID — Test Cases 시트에 미등록\n"
            "[동일 정규 Case] TEST_CASE-1AP_1HRK-WIFI-시험대상_장비_재부팅_후_복구-001 과 동일 시나리오\n"
            "[향후 조치] 정규 Case ID로 통합 권장"
        ),
    )
    add_procedure(conn, cid, 1,
        action   = "측정 중인 HRK 전원 OFF",
        criteria = "OP 홈 화면 우측상단 HRK 아이콘 미연결 상태 확인")
    add_procedure(conn, cid, 2,
        action   = "1분 이상 대기 후 HRK 전원 ON 및 부팅 완료 대기\n"
                   "(다중HDR연동의 경우 약 1분 추가 대기 필요)",
        criteria = "OP 홈 화면 우측상단 RK 아이콘 미연결 상태 확인 (부팅 중)")
    add_procedure(conn, cid, 3,
        action   = "HRK Wi-Fi 자동 재연결 대기",
        criteria = "REF/KER 측정 MODE 화면 우측상단 Wi-Fi & HDR 정상연결 상태 확인\n"
                   "· Wi-Fi 아이콘: 연결상태\n"
                   "· HDR 아이콘: 연결상태")
    add_procedure(conn, cid, 4,
        action   = "REF/KER 측정 수행 후 OP 화면 데이터 비교",
        criteria = "측정화면 좌우 R, L 데이터와 OP Basic Operation 화면 데이터 일치 확인 (OO 기준)")
    print(f"  [4/6] '{cid}' 보완 완료")

    # ──────────────────────────────────────────────────────────────────────────
    # 5. PLACEHOLDER_EMPTY_CASE (no=382, 383)
    #    - TEST_REPORT_HRK_9000A_1_1_1D_WIFI_TEST_260526 에 순번0004, 0005
    #    - 모든 필드 None (combo=TBD)
    #    - Report 상태가 IN TESTING → 시험 진행 예정 항목
    # ──────────────────────────────────────────────────────────────────────────
    cid = f"PLACEHOLDER_EMPTY_CASE-{PROJECT_ID}"
    update_case(conn, cid,
        title      = "[미입력] HRK-9000A 1.1.1D WIFI 시험 예정 항목 (순번 0004·0005)",
        objective  = "TEST_REPORT_HRK_9000A_1_1_1D_WIFI_TEST_260526 시험에서 "
                     "아직 Case ID와 결과가 입력되지 않은 2개 항목",
        precondition = "시험 진행 전 Case ID 및 절차 확정 필요",
        expected   = "TBD — Case ID 및 절차 확정 후 입력 필요",
        status     = "DRAFT",
        remark     = (
            "[원본 행] Excel Results no=382(순번0004), no=383(순번0005)\n"
            "[Report] TEST_REPORT_HRK_9000A_1_1_1D_WIFI_TEST_260526 (IN TESTING)\n"
            "[연결구성] TBD\n"
            "[필수 조치] 시험 완료 후 실제 Case ID와 결과값 입력 및 이 placeholder 삭제"
        ),
    )
    print(f"  [5/6] PLACEHOLDER_EMPTY_CASE 보완 완료")

    # ──────────────────────────────────────────────────────────────────────────
    # 6. skeleton env: 20AP_4HDR 다운그레이드 비교 시험 Config
    #    - Report에서 파악한 정보:
    #      · 시험장소: Huvitz Connectivity Room
    #      · AP 구성: 연결할AP 1대(MERCUSYS MR30G) + 주변AP 19대 = 20AP
    #      · Band: 5GHz
    #      · 시험대상: 5개 제품 각 1대 (총 5대), HDR 4대 포함
    #      · 시험목적: 구버전 S/W 다운그레이드 후 Wi-Fi 기능 비교
    # ──────────────────────────────────────────────────────────────────────────
    config_id = ("TEST_CONFIG-5GHz_연결성-20AP_4HDR-"
                 "TARGET_Wi-Fi_기능_다운그래이드_비교_시험-20260526-001")
    env_def_id = f"ENV_DEF-{config_id}"
    env_id     = f"ENV-{config_id}"
    env_name   = "해외전시회 모의 5GHz 환경 (20AP, 5개제품, 다운그레이드 비교)"

    full_remark = (
        "[보완근거] TEST_REPORT_WIFI_DOWNGRADE_TEST_260526_1454 리포트에서 역추적\n\n"
        "[시험장소] Huvitz Connectivity Room\n\n"
        "[Router 구성]\n"
        "· 연결할AP: MERCUSYS MR30G 1대 (5GHz, SN: 2232318003141)\n"
        "· 주변AP:   5GHz AP 19대 (신호강도 강함 — 해외전시회 환경 모의)\n"
        "· 합계:     20AP\n\n"
        "[시험대상 — 5개 제품 각 1대]\n"
        "· HRK-9000A 1.1.0A  (SN: 9HA09A24I0014)\n"
        "· HLM-9000  1.1.13B (SN: 9LM00024D0014)\n"
        "· HTR-1A    1.1.8B  (SN: 2601-J004)\n"
        "· HDR-9000  1.1.7A  (SN: BE 260128-096, 공정대여제품)\n"
        "· HDR-7100P 1.1.7i\n"
        "· HDC-9100  1.0.4A  (PP #1, 관리번호 L-062)\n"
        "· HDR 합계: 4대 (HDR-9000 + HDR-7100P 포함 시 4대 구성)\n\n"
        "[시험목적] 구버전 S/W 다운그레이드 후 Wi-Fi 연결 기능 비교\n"
        "          → 최신버전 대비 기능 저하 없음을 확인\n\n"
        "[원본 Config ID] " + config_id + "\n"
        "[원본 Excel Configs 시트] 미등록 — Results에서 참조됨"
    )

    update_env_def(conn, env_def_id,
        name         = env_name,
        test_room    = "Huvitz Connectivity Room",
        network_type = "WiFi-5GHz-20AP",
        remark       = full_remark)

    update_env(conn, env_id,
        name         = env_name,
        network_type = "WiFi-5GHz-20AP",
        remark       = (
            "[시험일] 2026-05-26\n"
            "[AP 구성] MERCUSYS MR30G(연결용 1대) + 5GHz 주변AP 19대\n"
            "[시험대상] HRK·HLM·HTR·HDR-9000·HDR-7100P·HDC 각 1대"
        ))
    print(f"  [6/6] skeleton env '{config_id[:50]}...' 보완 완료")

    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")

    # ── 최종 확인 ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  보완 후 상태 확인")
    print("=" * 65)

    drafts = conn.execute(
        "SELECT product_test_case_id, product_test_case_title, "
        "product_test_case_status FROM product_test_case "
        "WHERE project_id=? ORDER BY product_test_case_status",
        (PROJECT_ID,)
    ).fetchall()
    active  = [r for r in drafts if r[2] == "ACTIVE"]
    draft   = [r for r in drafts if r[2] == "DRAFT"]
    print(f"\n  test_case ACTIVE : {len(active)}건")
    print(f"  test_case DRAFT  : {len(draft)}건 (향후 조치 필요)")
    for r in draft:
        print(f"    - {r[0][:60]}")

    sk_envs = conn.execute(
        "SELECT product_test_environment_definition_id, "
        "product_test_environment_definition_status "
        "FROM product_test_environment_definition "
        "WHERE project_id=? AND "
        "product_test_environment_definition_name LIKE '[SKELETON]%'",
        (PROJECT_ID,)
    ).fetchall()
    print(f"\n  env_definition skeleton 잔여: {len(sk_envs)}건")

    proc_added = conn.execute(
        "SELECT COUNT(*) FROM product_test_procedure "
        "WHERE project_id=? AND created_by=?",
        (PROJECT_ID, UPDBY)
    ).fetchone()[0]
    print(f"  이번 보완으로 추가된 procedure: {proc_added}건")

    conn.close()
    print("\n[완료] skeleton 보완 완료")

    print("\n" + "=" * 65)
    print("  향후 조치 권장 사항")
    print("=" * 65)
    print("""
  1. [DRAFT] PLACEHOLDER_EMPTY_CASE (no=382, 383)
     → HRK-9000A 1.1.1D 시험 진행 완료 후 실제 Case ID·결과 입력
     → 입력 완료 후 이 placeholder 레코드 삭제

  2. [권장] 비정규 한글 Case ID 3건 정규화
     · 'Wi-Fi 재ON 후 복구'
       → TEST_CASE-1AP_1HRK-WIFI-WIFI_재ON_후_복구-001 으로 재등록
     · '라우터 재부팅 후 복구'
       → TEST_CASE-1AP_1HRK-WIFI-라우터_재부팅_후_복구-001 로 통합
     · '시험대상장비 재부팅 후 복구'
       → TEST_CASE-1AP_1HRK-WIFI-시험대상_장비_재부팅_후_복구-001 로 통합

  3. [권장] skeleton Config 원본 정보 확정
     · TEST_CONFIG-5GHz_연결성-20AP_4HDR 다운그래이드 시험
       → Excel Configs 시트에 정식 등록하고 이 skeleton 교체
""")


if __name__ == "__main__":
    main()
