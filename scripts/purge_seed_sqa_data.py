"""
프로덕션 DB에서 SQA_ seed 더미 데이터를 삭제한다.

대상:
  - product_test_round  : test_round_id LIKE 'SQA_PRODUCT_TEST_RELEASE_ID%'
  - product_test_report : product_test_report_id LIKE 'SQA_PRODUCT_TEST_REPORT_ID%'
  - 연관 자식 테이블 전체 (FK 역순)

사용:
  uv run python scripts/purge_seed_sqa_data.py [--dry-run]
"""
from __future__ import annotations

import sys

DRY_RUN = "--dry-run" in sys.argv


def main() -> None:
    import os
    os.environ.setdefault("PRODUCT_TEST_QC_MODE", "false")

    from sqlalchemy import text
    from app.db import engine

    stmts: list[tuple[str, str]] = [
        ("product_test_status_transition",
         "DELETE FROM product_test_status_transition WHERE entity_id LIKE 'SQA_%'"),
        ("product_test_evidence",
         "DELETE FROM product_test_evidence WHERE product_test_run_id IN "
         "(SELECT product_test_run_id FROM product_test_run WHERE test_round_id LIKE 'SQA_PRODUCT_TEST_RELEASE_ID%')"),
        ("product_test_procedure_result",
         "DELETE FROM product_test_procedure_result WHERE product_test_run_id IN "
         "(SELECT product_test_run_id FROM product_test_run WHERE test_round_id LIKE 'SQA_PRODUCT_TEST_RELEASE_ID%')"),
        ("product_test_result",
         "DELETE FROM product_test_result WHERE product_test_run_id IN "
         "(SELECT product_test_run_id FROM product_test_run WHERE test_round_id LIKE 'SQA_PRODUCT_TEST_RELEASE_ID%')"),
        ("product_test_run",
         "DELETE FROM product_test_run WHERE test_round_id LIKE 'SQA_PRODUCT_TEST_RELEASE_ID%'"),
        ("product_test_report_snapshot",
         "DELETE FROM product_test_report_snapshot WHERE product_test_report_id LIKE 'SQA_PRODUCT_TEST_REPORT_ID%'"),
        ("product_test_report",
         "DELETE FROM product_test_report WHERE product_test_report_id LIKE 'SQA_PRODUCT_TEST_REPORT_ID%'"),
        ("product_test_round",
         "DELETE FROM product_test_round WHERE test_round_id LIKE 'SQA_PRODUCT_TEST_RELEASE_ID%'"),
    ]

    preview_stmts: list[tuple[str, str]] = [
        ("product_test_round",
         "SELECT test_round_id FROM product_test_round WHERE test_round_id LIKE 'SQA_PRODUCT_TEST_RELEASE_ID%'"),
        ("product_test_run",
         "SELECT product_test_run_id FROM product_test_run WHERE test_round_id LIKE 'SQA_PRODUCT_TEST_RELEASE_ID%'"),
        ("product_test_report",
         "SELECT product_test_report_id FROM product_test_report WHERE product_test_report_id LIKE 'SQA_PRODUCT_TEST_REPORT_ID%'"),
    ]

    with engine.begin() as conn:
        print("=== 삭제 대상 확인 ===")
        total = 0
        for table, sel in preview_stmts:
            rows = conn.execute(text(sel)).fetchall()
            for r in rows:
                print(f"  [{table}] {r[0]}")
            total += len(rows)

        if total == 0:
            print("삭제할 seed 데이터 없음.")
            return

        if DRY_RUN:
            print(f"\n--dry-run 모드: 실제 삭제 안 함 (대상 {total}건)")
            return

        confirm = input(f"\n위 {total}건을 삭제합니다. 계속하시겠습니까? [y/N] ").strip().lower()
        if confirm != "y":
            print("취소.")
            return

        conn.execute(text("PRAGMA foreign_keys=OFF"))
        for table, stmt in stmts:
            result = conn.execute(text(stmt))
            if result.rowcount:
                print(f"  {table}: {result.rowcount}건 삭제")
        conn.execute(text("PRAGMA foreign_keys=ON"))

    print("\n완료.")


if __name__ == "__main__":
    main()
