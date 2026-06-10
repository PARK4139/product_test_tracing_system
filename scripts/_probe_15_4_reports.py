import sqlite3

c = sqlite3.connect("data/product_test_tracking_system.db")
c.row_factory = sqlite3.Row

print("=== defects -> run -> release ===")
for d in c.execute(
    """
    SELECT def.product_test_defect_id, res.product_test_result_id, res.product_test_run_id,
           run.product_test_release_id, rel.test_round_id
    FROM product_test_defect def
    JOIN product_test_result res ON res.product_test_result_id = def.product_test_result_id
    JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
    LEFT JOIN product_test_release rel ON rel.product_test_release_id = run.product_test_release_id
    """
):
    print(
        d["product_test_defect_id"],
        d["product_test_run_id"],
        d["product_test_release_id"],
        d["test_round_id"],
    )

print("=== legacy TEST_REPORT runs ===")
for r in c.execute(
    "SELECT product_test_run_id, product_test_release_id FROM product_test_run WHERE product_test_run_id LIKE 'RUN-TEST_REPORT%'"
):
    print(dict(r))

print("=== report titles ===")
for r in c.execute("SELECT product_test_report_id, product_test_release_id, product_test_report_title FROM product_test_report"):
    print(dict(r))

c.close()
