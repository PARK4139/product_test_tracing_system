"""
v2 추적성 회귀테스트 (ROUND -> RUN -> RESULT 체인)
실행: python scripts/traceability_regression_v2.py [db_path]
기본 DB: data/product_test_tracking_system.db
"""
from __future__ import annotations

import os
import sqlite3
import sys

DB_DEFAULT = os.path.join(os.path.dirname(__file__), "..", "data", "product_test_tracking_system.db")


def main() -> int:
    db_path = sys.argv[1] if len(sys.argv) > 1 else DB_DEFAULT
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT 1 FROM product_test_round LIMIT 1")
    except Exception as exc:
        print(f"[ERROR] DB 연결 실패: {exc}")
        return 2

    results: list[tuple[str, str, int, list]] = []

    def tc(name: str, query: str, *, expect_zero: bool = False, warn_only: bool = False, info_only: bool = False) -> None:
        rows = conn.execute(query).fetchall()
        count = len(rows)
        if info_only:
            print(f"[INFO] {name}: {count}건")
            results.append(("INFO", name, count, rows[:3]))
            return
        if expect_zero:
            ok = count == 0
            label = "PASS" if ok else ("WARN" if warn_only else "FAIL")
            print(f"[{label}] {name}" + ("" if ok else f" -> {count}건 위반"))
            results.append((label, name, count, rows[:3]))
        else:
            ok = count > 0
            label = "PASS" if ok else "FAIL"
            print(f"[{label}] {name} ({count}건)")
            results.append((label, name, count, rows[:3]))

    print(f"\n{'=' * 65}\n  v2 추적성 회귀테스트\n  DB: {os.path.abspath(db_path)}\n{'=' * 65}")

    print("\n[그룹 1] Round 구조")
    tc("TC-R01: canonical round 존재", "SELECT test_round_id FROM product_test_round LIMIT 1")
    tc(
        "TC-R02: 고아 Run 없음 (test_round_id FK)",
        """
        SELECT product_test_run_id FROM product_test_run
        WHERE test_round_id NOT IN (SELECT test_round_id FROM product_test_round)
        """,
        expect_zero=True,
    )

    print("\n[그룹 2] Run -> Result 체인")
    tc(
        "TC-RN01: 고아 Result 없음",
        """
        SELECT product_test_result_id FROM product_test_result
        WHERE product_test_run_id NOT IN (SELECT product_test_run_id FROM product_test_run)
        """,
        expect_zero=True,
    )
    tc("TC-RS01: Result 수", "SELECT product_test_result_id FROM product_test_result")

    print("\n[그룹 3] Report -> Round 체인")
    tc(
        "TC-RP01: Report round FK",
        """
        SELECT product_test_report_id FROM product_test_report
        WHERE test_round_id NOT IN (SELECT test_round_id FROM product_test_round)
        """,
        expect_zero=True,
    )

    conn.close()
    failed = sum(1 for row in results if row[0] == "FAIL")
    print(f"\n{'=' * 65}\n  FAIL {failed}\n{'=' * 65}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
