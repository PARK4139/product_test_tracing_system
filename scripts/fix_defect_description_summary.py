"""
결함 설명(defect_description)의 [요약] 필드 재보정 스크립트.

문제: migrate_excel_to_db.py의 parse_detail()이 '내용요약' 이후 첫 줄만 파싱하여
     여러 줄 요약이 잘려서 DB에 저장됨.

해결: 엑셀 원본에서 '내용요약' 이후 다음 섹션(내용:/검토자:/시험일자:) 전까지
     전체 텍스트를 추출하여 DB의 [요약] 필드를 덮어씀.

사용법:
    python scripts/fix_defect_description_summary.py
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

EXCEL_PATH = Path(__file__).parent.parent.parent / "ai_coworking" / "test_tracing_system_to_migrate.xlsx"
DB_PATH    = Path(__file__).parent.parent / "data" / "product_test_tracking_system.db"


def parse_full_summary(detail: str) -> str:
    """내용요약 이후 다음 섹션 전까지 전체 텍스트 추출."""
    m = re.search(
        r"내용요약\s*:\s*(.+?)(?=\n내용:|\n검토자:|\n시험일자:|\Z)",
        detail or "",
        re.DOTALL,
    )
    return m.group(1).strip() if m else (detail or "").strip()


def main() -> None:
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("openpyxl 필요: pip install openpyxl")

    wb = openpyxl.load_workbook(EXCEL_PATH)
    ws = wb["Test Results"]

    conn = sqlite3.connect(DB_PATH)
    updated = 0

    for row in ws.iter_rows(min_row=3, values_only=True):
        if not row[0]:
            continue
        result     = str(row[5] or "")
        detail     = str(row[6] or "")
        issues_raw = str(row[7] or "").strip()

        if result != "BLOCKED" or not issues_raw:
            continue

        summary = parse_full_summary(detail)
        if not summary:
            continue

        for issue_id in [i.strip() for i in issues_raw.split("\n") if i.strip()]:
            defects = conn.execute(
                "SELECT product_test_defect_id, defect_description "
                "FROM product_test_defect WHERE product_test_defect_id LIKE ?",
                (f"%{issue_id}%",),
            ).fetchall()

            for defect_id, old_desc in defects:
                old_desc = old_desc or ""
                new_desc = re.sub(r"\[요약\][^\n]*", f"[요약] {summary}", old_desc)
                if new_desc != old_desc:
                    conn.execute(
                        "UPDATE product_test_defect SET defect_description=? "
                        "WHERE product_test_defect_id=?",
                        (new_desc, defect_id),
                    )
                    print(f"✓ {defect_id}")
                    updated += 1

    conn.commit()
    conn.close()
    print(f"\n총 {updated}건 업데이트 완료")


if __name__ == "__main__":
    main()
