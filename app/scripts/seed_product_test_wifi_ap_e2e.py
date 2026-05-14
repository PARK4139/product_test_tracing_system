from __future__ import annotations

import json

from app.db import initialize_database, session_local
from app.services.product_test_run_service import (
    get_product_test_report_detail,
    seed_product_test_wifi_ap_configuration_sample_data,
)


def main() -> None:
    initialize_database()
    with session_local() as database_session:
        seed_product_test_wifi_ap_configuration_sample_data(database_session)
        detail = get_product_test_report_detail(
            database_session,
            "SQA_PRODUCT_TEST_REPORT_ID-SQA_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1-FULL-001",
        )
    if detail is None:
        raise SystemExit("Seed completed but report detail was not found.")
    payload = {
        "seed_report_id": detail["report"]["product_test_report_id"],
        "seed_release_id": detail["report"]["product_test_release_id"],
        "result_summary": detail["result_summary"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
