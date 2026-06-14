from __future__ import annotations

import json

from app.db import initialize_database, session_local
from app.services.product_test_run_service import (
    seed_product_test_wifi_ap_configuration_sample_data,
)


def main() -> None:
    initialize_database()
    with session_local() as database_session:
        seed_product_test_wifi_ap_configuration_sample_data(database_session)
    print("Seed completed.")


if __name__ == "__main__":
    main()
