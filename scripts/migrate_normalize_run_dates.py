#!/usr/bin/env python3
"""
B: product_test_run 날짜 정규화 마이그레이션
================================================================================
문제:
  1. started_at/finished_at 비표준 형식 → ISO 8601 변환
     - "2026 04 22T..." (공백) → "2026-04-22T..."
     - "2026_05_26_0000T..." (언더스코어) → "2026-05-26T..."
  2. migration_script_v1 가짜 날짜 → NULL
     - "2026-05-28T00:30:50..." (created_by=migration_script_v1) → NULL
  3. product_test_release.remark의 [Start]/[End] 날짜 표기 정규화

실행:
  python scripts/migrate_normalize_run_dates.py            # dry-run
  python scripts/migrate_normalize_run_dates.py --apply    # 실제 적용
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
ACTOR = "migrate_normalize_run_dates_v1"

APPLY = "--apply" in sys.argv
DRY_RUN = not APPLY

# migration_script_v1이 넣은 가짜 날짜 (마이그레이션 실행 시점)
FAKE_DATE_PREFIX = "2026-05-28T00:30:50"


def normalize_iso(dt_str: str | None) -> str | None:
    """비표준 datetime 문자열 → ISO 8601 표준화.

    패턴:
      "2026 04 22T00:00:00+00:00" → "2026-04-22T00:00:00+00:00"
      "2026_05_26_0000T00:00:00+00:00" → "2026-05-26T00:00:00+00:00"
    """
    if not dt_str:
        return dt_str

    # 공백 패턴: "2026 04 22T..."
    m = re.match(r'^(\d{4}) (\d{2}) (\d{2})(T.+)$', dt_str)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}{m.group(4)}"

    # 언더스코어 패턴: "2026_05_26_0000T..."
    m = re.match(r'^(\d{4})_(\d{2})_(\d{2})_\d{4}(T.+)$', dt_str)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}{m.group(4)}"

    return dt_str  # 이미 정상


def normalize_date_only(date_str: str | None) -> str | None:
    """remark 안의 날짜 문자열만 정규화 (T 없는 형태).

    패턴:
      "2026 04 22"  → "2026-04-22"
      "2026_05_26_0000" → "2026-05-26"
    """
    if not date_str:
        return date_str

    m = re.match(r'^(\d{4}) (\d{2}) (\d{2})$', date_str.strip())
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    m = re.match(r'^(\d{4})_(\d{2})_(\d{2})_\d{4}$', date_str.strip())
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    return date_str


def normalize_remark_dates(remark: str | None) -> str | None:
    """remark 내 [Start] xxx  [End] xxx 날짜 정규화."""
    if not remark:
        return remark

    def replace_date(m):
        tag = m.group(1)      # "Start" or "End"
        date = m.group(2)     # "2026 04 22" or "2026_05_26_0000" or "None"
        normalized = normalize_date_only(date.strip()) if date.strip() != "None" else date.strip()
        return f"[{tag}] {normalized}"

    # 날짜 패턴만 정밀 매칭: "YYYY MM DD", "YYYY_MM_DD_HHMM", "YYYY-MM-DD", "None"
    DATE_PATTERN = r'(\d{4} \d{2} \d{2}|\d{4}_\d{2}_\d{2}_\d{4}|\d{4}-\d{2}-\d{2}|None)'
    return re.sub(r'\[(Start|End)\] ' + DATE_PATTERN, replace_date, remark)


def main():
    if not DB_PATH.exists():
        print(f"ERROR: DB 없음 → {DB_PATH}")
        sys.exit(1)

    # 백업
    if APPLY:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = DB_PATH.with_name(f"{DB_PATH.stem}.backup_{ts}.db")
        shutil.copy2(DB_PATH, backup)
        print(f"백업 완료 → {backup.name}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print(f"\n{'[DRY-RUN]' if DRY_RUN else '[APPLY]'} product_test_run 날짜 정규화")
    print("=" * 70)

    # ── 1. product_test_run started_at / finished_at ──────────────────────
    cur.execute("SELECT product_test_run_id, started_at, finished_at, created_by FROM product_test_run")
    runs = cur.fetchall()

    run_updates = []
    for r in runs:
        run_id = r["product_test_run_id"]
        orig_start = r["started_at"]
        orig_end = r["finished_at"]
        created_by = r["created_by"] or ""

        # migration_script 가짜 날짜 → NULL
        new_start = None if (orig_start and orig_start.startswith(FAKE_DATE_PREFIX)) else normalize_iso(orig_start)
        new_end = None if (orig_end and orig_end.startswith(FAKE_DATE_PREFIX)) else normalize_iso(orig_end)

        if new_start != orig_start or new_end != orig_end:
            run_updates.append({
                "run_id": run_id,
                "old_start": orig_start,
                "new_start": new_start,
                "old_end": orig_end,
                "new_end": new_end,
                "reason": "fake_date→NULL" if (orig_start and orig_start.startswith(FAKE_DATE_PREFIX)) else "nonstandard_format",
            })

    print(f"\n[product_test_run] 변경 대상: {len(run_updates)}건")
    for u in run_updates:
        print(f"  {u['run_id'][:60]}")
        print(f"    started_at: {u['old_start']} → {u['new_start']}")
        print(f"    finished_at: {u['old_end']} → {u['new_end']}")
        print(f"    사유: {u['reason']}")

    if APPLY and run_updates:
        for u in run_updates:
            cur.execute(
                "UPDATE product_test_run SET started_at=?, finished_at=?, updated_at=?, updated_by=? WHERE product_test_run_id=?",
                (u["new_start"], u["new_end"], NOW, ACTOR, u["run_id"]),
            )
        print(f"\n  → {len(run_updates)}건 업데이트 완료")

    # ── 2. product_test_release remark 날짜 정규화 ────────────────────────
    cur.execute("SELECT product_test_release_id, remark FROM product_test_release WHERE remark IS NOT NULL")
    releases = cur.fetchall()

    release_updates = []
    for r in releases:
        rid = r["product_test_release_id"]
        orig_remark = r["remark"]
        new_remark = normalize_remark_dates(orig_remark)
        if new_remark != orig_remark:
            release_updates.append({
                "release_id": rid,
                "old_remark": orig_remark,
                "new_remark": new_remark,
            })

    print(f"\n[product_test_release remark] 변경 대상: {len(release_updates)}건")
    for u in release_updates:
        print(f"  {u['release_id']}")
        # Start/End 줄만 출력
        old_lines = [l for l in u["old_remark"].split("\n") if "Start" in l or "End" in l]
        new_lines = [l for l in u["new_remark"].split("\n") if "Start" in l or "End" in l]
        for ol, nl in zip(old_lines, new_lines):
            print(f"    전: {ol.strip()}")
            print(f"    후: {nl.strip()}")

    if APPLY and release_updates:
        for u in release_updates:
            cur.execute(
                "UPDATE product_test_release SET remark=?, updated_at=?, updated_by=? WHERE product_test_release_id=?",
                (u["new_remark"], NOW, ACTOR, u["release_id"]),
            )
        print(f"\n  → {len(release_updates)}건 업데이트 완료")

    if APPLY:
        conn.commit()
        print(f"\n✅ 커밋 완료")
    else:
        conn.rollback()
        print(f"\n⚠️  Dry-run 완료. 실제 적용하려면 --apply 옵션 추가")

    conn.close()


if __name__ == "__main__":
    main()
