#!/usr/bin/env python3
"""
A: product_test_round 테이블 신설 + release 매핑 마이그레이션
================================================================================
작업:
  1. product_test_round 테이블 생성
  2. TEST_ROUND 기준 데이터 삽입 (13건 + ORPHAN 1건)
  3. product_test_release에 test_round_id 컬럼 추가
  4. release_id 패턴 기반으로 test_round_id 매핑

주의:
  - TEST_ROUND-HDC_9100_1_0_5A, HDR_9000_1_1_7E, HLM_9000_1_1_14B, HTR_1A_1_1_8,
    HDR_9000_1_1_8 는 MISSING_SOURCE → release 매핑 없음 (NULL 유지)
  - HDC/HDR/HLM/HTR 관련 release는 WIFI_1ST 그룹 시험으로 매핑됨

실행:
  python scripts/migrate_add_test_round.py            # dry-run
  python scripts/migrate_add_test_round.py --apply    # 실제 적용
================================================================================
"""
from __future__ import annotations

import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
NOW = datetime.now(timezone.utc).isoformat()
ACTOR = "migrate_add_test_round_v1"

APPLY = "--apply" in sys.argv
DRY_RUN = not APPLY

# ── TEST_ROUND 마스터 데이터 (사용자 제공 CSV 기반) ─────────────────────────
ROUNDS = [
    # (test_round_id, name, workday, start_date, end_date, date_quality, migration_status, note)
    ("TEST_ROUND-WIFI_1ST",
     "Wi-Fi Connectivity Test 1차",
     6.5, "2026-04-22", "2026-04-30",
     "EXACT", "CONFIRMED", "5개 제품 1차 Wi-Fi 시험"),

    ("TEST_ROUND-WIFI_1ST_IMPROVE",
     "Wi-Fi Connectivity Test 1차 개선확인 시험",
     0.5, None, None,
     "PARTIAL_WORKDAY_ONLY", "INFER_NEEDED", "Start/End 없음"),

    ("TEST_ROUND-WIFI_2ND",
     "Wi-Fi Connectivity Test 2차",
     3.0, None, None,
     "PARTIAL_WORKDAY_ONLY", "INFER_NEEDED", "Start/End 없음"),

    ("TEST_ROUND-WIFI_2ND_IMPROVE",
     "Wi-Fi Connectivity Test 2차 개선확인 시험",
     0.5, None, None,
     "PARTIAL_WORKDAY_ONLY", "INFER_NEEDED", "Start/End 없음"),

    ("TEST_ROUND-HDC_9100_1_0_5A",
     "HDC-9100 1.0.5A 시험",
     None, None, None,
     "MISSING_SOURCE", "INFER_NEEDED", "직접 매핑 release 없음 - WIFI_1ST 그룹 내 포함"),

    ("TEST_ROUND-HDR_9000_1_1_7E",
     "HDR-9000 1.1.7E 시험",
     None, None, None,
     "MISSING_SOURCE", "INFER_NEEDED", "직접 매핑 release 없음 - WIFI_1ST 그룹 내 포함"),

    ("TEST_ROUND-HDR_9000_1_1_8",
     "HDR-9000 1.1.8 시험",
     None, None, None,
     "MISSING_SOURCE", "INFER_NEEDED", "직접 매핑 release 없음 - WIFI_2ND/WIFI_1_1_1D 그룹 내 포함"),

    ("TEST_ROUND-HLM_9000_1_1_14B",
     "HLM-9000 1.1.14B 시험",
     None, None, None,
     "MISSING_SOURCE", "INFER_NEEDED", "직접 매핑 release 없음 - WIFI_1ST 그룹 내 포함"),

    ("TEST_ROUND-HRK_9000A_1_1_0A",
     "HRK-9000A 1.1.0A 시험",
     1.0, "2026-05-26", "2026-05-26",
     "EXACT", "CONFIRMED", "단독 시험"),

    ("TEST_ROUND-HRK_9000A_1_1_1A",
     "HRK-9000A 1.1.1A 시험",
     3.0, None, None,
     "PARTIAL_WORKDAY_ONLY", "INFER_NEEDED", "Start/End 없음"),

    ("TEST_ROUND-HRK_9000A_1_1_1D",
     "HRK-9000A 1.1.1D 시험",
     0.8, None, None,
     "PARTIAL_WORKDAY_ONLY", "INFER_NEEDED", "Start/End 없음"),

    ("TEST_ROUND-HTR_1A_1_1_8",
     "HTR-1A 1.1.8 시험",
     None, None, None,
     "MISSING_SOURCE", "INFER_NEEDED", "직접 매핑 release 없음 - WIFI_1ST 그룹 내 포함"),

    ("TEST_ROUND-WIFI_DOWNGRADE_COMPARE_20260526",
     "5개 제품 Wi-Fi 기능 다운그래이드 비교 시험",
     1.0, "2026-05-26", "2026-05-26",
     "EXACT", "ORPHAN_REVIEW_NEEDED", "상위 목록 외 별도 시험 - 검토 필요"),
]


def get_test_round_id(release_id: str) -> str | None:
    """release_id 패턴 → test_round_id 매핑.

    우선순위:
      1. _IMPROVE 먼저 체크 (WIFI_1ST보다 먼저 매칭)
      2. WIFI_DOWNGRADE
      3. WIFI_1_1_1D (HRK 1.1.1D)
      4. WIFI_1ST, WIFI_2ND (제품 prefix 포함)
      5. HRK 단독 시험
    """
    rid = release_id

    if "WIFI_1ST_IMPROVE" in rid:
        return "TEST_ROUND-WIFI_1ST_IMPROVE"
    if "WIFI_2ND_IMPROVE" in rid:
        return "TEST_ROUND-WIFI_2ND_IMPROVE"

    if "WIFI_DOWNGRADE" in rid:
        return "TEST_ROUND-WIFI_DOWNGRADE_COMPARE_20260526"

    # WIFI_1_1_1D → HRK 1.1.1D 시험 세션
    if "WIFI_1_1_1D" in rid:
        return "TEST_ROUND-HRK_9000A_1_1_1D"

    if "WIFI_1ST" in rid:
        return "TEST_ROUND-WIFI_1ST"
    if "WIFI_2ND" in rid:
        return "TEST_ROUND-WIFI_2ND"

    # HRK 단독 시험
    if rid.startswith("TEST_RELEASE-HRK_9000A_1_1_0A"):
        return "TEST_ROUND-HRK_9000A_1_1_0A"
    if rid.startswith("TEST_RELEASE-HRK_9000A_1_1_1A"):
        return "TEST_ROUND-HRK_9000A_1_1_1A"
    if rid.startswith("TEST_RELEASE-HRK_9000A_1_1_1D"):
        return "TEST_ROUND-HRK_9000A_1_1_1D"

    # 레거시 TEST_REPORT 기반 release
    if "TEST_REPORT_WIFI_TEST_1ST" in rid:
        return "TEST_ROUND-WIFI_1ST"
    if "TEST_REPORT_WIFI_TEST_2ND" in rid:
        return "TEST_ROUND-WIFI_2ND"
    if "TEST_REPORT_HRK_9000A_1_1_1D" in rid:
        return "TEST_ROUND-HRK_9000A_1_1_1D"
    if "TEST_REPORT_WIFI_DOWNGRADE" in rid:
        return "TEST_ROUND-WIFI_DOWNGRADE_COMPARE_20260526"

    # FALLBACK, TBD → NULL 유지
    return None


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS product_test_round (
    test_round_id       TEXT PRIMARY KEY,
    test_round_name     TEXT NOT NULL,
    workday             REAL,
    start_date          TEXT,           -- ISO 날짜 YYYY-MM-DD
    end_date            TEXT,           -- ISO 날짜 YYYY-MM-DD
    date_quality        TEXT,           -- EXACT / PARTIAL_WORKDAY_ONLY / MISSING_SOURCE
    migration_status    TEXT,           -- CONFIRMED / INFER_NEEDED / ORPHAN_REVIEW_NEEDED
    migration_note      TEXT,
    project_id          TEXT,
    created_at          TEXT NOT NULL,
    created_by          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    updated_by          TEXT NOT NULL
)
"""


def main():
    if not DB_PATH.exists():
        print(f"ERROR: DB 없음 → {DB_PATH}")
        sys.exit(1)

    if APPLY:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = DB_PATH.with_name(f"{DB_PATH.stem}.backup_{ts}.db")
        shutil.copy2(DB_PATH, backup)
        print(f"백업 완료 → {backup.name}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print(f"\n{'[DRY-RUN]' if DRY_RUN else '[APPLY]'} product_test_round 테이블 신설")
    print("=" * 70)

    # ── 1. product_test_round 테이블 생성 ───────────────────────────────────
    existing_tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]

    if "product_test_round" in existing_tables:
        print("\n[1] product_test_round 테이블 이미 존재 → 건너뜀")
    else:
        print("\n[1] product_test_round 테이블 생성")
        if APPLY:
            cur.execute(CREATE_TABLE_SQL)
            print("    → 생성 완료")
        else:
            print("    → [dry-run] 생성 예정")

    # ── 2. TEST_ROUND 데이터 삽입 ────────────────────────────────────────────
    print(f"\n[2] TEST_ROUND 마스터 데이터 삽입 ({len(ROUNDS)}건)")

    if APPLY:
        cur.executemany("""
            INSERT OR IGNORE INTO product_test_round
                (test_round_id, test_round_name, workday, start_date, end_date,
                 date_quality, migration_status, migration_note,
                 project_id, created_at, created_by, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7],
             "WIFI_CONNECTIVITY_TEST_2026", NOW, ACTOR, NOW, ACTOR)
            for r in ROUNDS
        ])
        inserted = cur.rowcount
        print(f"    → {len(ROUNDS)}건 삽입 (중복 제외: INSERT OR IGNORE)")
    else:
        for r in ROUNDS:
            print(f"    {r[0]} | {r[3] or '?'} ~ {r[4] or '?'} | {r[6]}")

    # ── 3. product_test_release에 test_round_id 컬럼 추가 ───────────────────
    print(f"\n[3] product_test_release.test_round_id 컬럼 추가")

    cols = [r[1] for r in cur.execute("PRAGMA table_info(product_test_release)").fetchall()]
    if "test_round_id" in cols:
        print("    → 이미 존재, 건너뜀")
    else:
        if APPLY:
            cur.execute("ALTER TABLE product_test_release ADD COLUMN test_round_id TEXT")
            print("    → 컬럼 추가 완료")
        else:
            print("    → [dry-run] 컬럼 추가 예정")

    # ── 4. release → test_round_id 매핑 ─────────────────────────────────────
    print(f"\n[4] release → test_round_id 매핑")

    cur.execute("SELECT product_test_release_id FROM product_test_release")
    releases = [r[0] for r in cur.fetchall()]

    mapped, unmapped = [], []
    round_counts: dict[str, int] = {}
    for rid in releases:
        trid = get_test_round_id(rid)
        if trid:
            mapped.append((rid, trid))
            round_counts[trid] = round_counts.get(trid, 0) + 1
        else:
            unmapped.append(rid)

    print(f"\n    매핑 성공: {len(mapped)}건")
    for trid, cnt in sorted(round_counts.items()):
        print(f"      {trid}: {cnt}건")

    print(f"\n    매핑 실패(NULL): {len(unmapped)}건")
    for rid in unmapped:
        print(f"      {rid}")

    if APPLY and mapped:
        for rid, trid in mapped:
            cur.execute(
                "UPDATE product_test_release SET test_round_id=?, updated_at=?, updated_by=? WHERE product_test_release_id=?",
                (trid, NOW, ACTOR, rid),
            )
        print(f"\n    → {len(mapped)}건 업데이트 완료")

    if APPLY:
        conn.commit()
        print(f"\n✅ 커밋 완료")

        # 결과 확인
        print(f"\n[검증] product_test_round 테이블 내용:")
        for r in conn.execute("SELECT test_round_id, workday, start_date, end_date, migration_status FROM product_test_round ORDER BY test_round_id").fetchall():
            print(f"  {r[0]} | workday={r[1]} | {r[2]}~{r[3]} | {r[4]}")
    else:
        conn.rollback()
        print(f"\n⚠️  Dry-run 완료. 실제 적용하려면 --apply 옵션 추가")

    conn.close()


if __name__ == "__main__":
    main()
