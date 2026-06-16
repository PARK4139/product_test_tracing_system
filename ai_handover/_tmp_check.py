import sqlite3, pathlib
db = pathlib.Path('data/product_test_tracking_system.db')
con = sqlite3.connect(str(db))
cur = con.cursor()
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%environment%' OR name LIKE '%config%')").fetchall()
print('tables:', tables)
cols_run = cur.execute('PRAGMA table_info(product_test_run)').fetchall()
print('product_test_run cols:', [c[1] for c in cols_run if 'env' in c[1].lower() or 'config' in c[1].lower()])
sheets = cur.execute("SELECT custom_sheet_tab_id, region_key, tab_label, columns_json FROM custom_sheet_tab WHERE region_key IN ('entity/environment','entity/run')").fetchall()
for s in sheets:
    print('---')
    print('id:', s[0], 'region_key:', s[1], 'tab_label:', s[2])
    print('columns_json:', s[3])
con.close()
