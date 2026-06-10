import sqlite3

c = sqlite3.connect("data/product_test_tracking_system.db")
c.row_factory = sqlite3.Row
print("procedure_result", c.execute("SELECT COUNT(*) FROM product_test_procedure_result").fetchone()[0])
for pat in ["product_test_run_id", "product_test_result_id", "product_test_case_id", "product_test_procedure_id"]:
    rows = c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE ?",
        (f"%{pat}%",),
    ).fetchall()
    print(pat, [r[0] for r in rows])
cols = [r[1] for r in c.execute("PRAGMA table_info(product_test_run)")]
print("run cols", cols)
print("test_round_id on run", "test_round_id" in cols)
c.close()
