"""
Environment ID 접두사 변경: ENV-TEST_CONFIG → TEST_CONFIG
ENV_DEF-TEST_CONFIG → TEST_CONFIG_DEF (또는 동일하게 TEST_CONFIG)
실행: 서버 중지 후 python scripts/migrate_env_id_prefix.py
"""
import sqlite3, shutil, os, sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB   = os.path.join(BASE, "data", "product_test_tracking_system.db")
TMP  = "/tmp/env_prefix_migration.db"
NOW  = datetime.now(timezone.utc).isoformat()

print(f"DB: {DB}")
if not os.path.exists(DB): print("ERROR: DB 없음"); sys.exit(1)

shutil.copy2(DB, TMP)
for ext in ('-wal', '-shm'):
    try: shutil.copy2(DB+ext, TMP+ext)
    except: pass

conn = sqlite3.connect(TMP)
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.execute("PRAGMA foreign_keys=OFF")

# 1. product_test_environment_definition: ENV_DEF-TEST_CONFIG → TEST_CONFIG_DEF
defs = conn.execute(
    "SELECT product_test_environment_definition_id FROM product_test_environment_definition"
).fetchall()
for (old_id,) in defs:
    new_id = old_id.replace("ENV_DEF-TEST_CONFIG", "TEST_CONFIG_DEF").replace("ENV_DEF-", "")
    if new_id == old_id: continue
    conn.execute("UPDATE product_test_environment_definition SET product_test_environment_definition_id=? WHERE product_test_environment_definition_id=?", (new_id, old_id))
    conn.execute("UPDATE product_test_environment SET product_test_environment_definition_id=? WHERE product_test_environment_definition_id=?", (new_id, old_id))
    print(f"  DEF: {old_id} → {new_id}")

# 2. product_test_environment: ENV-TEST_CONFIG → TEST_CONFIG
envs = conn.execute(
    "SELECT product_test_environment_id FROM product_test_environment"
).fetchall()
for (old_id,) in envs:
    new_id = old_id.replace("ENV-TEST_CONFIG", "TEST_CONFIG").replace("ENV-", "")
    if new_id == old_id: continue
    conn.execute("UPDATE product_test_environment SET product_test_environment_id=? WHERE product_test_environment_id=?", (new_id, old_id))
    conn.execute("UPDATE product_test_run SET product_test_environment_id=? WHERE product_test_environment_id=?", (new_id, old_id))
    print(f"  ENV: {old_id} → {new_id}")

conn.execute("PRAGMA foreign_keys=ON")
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.commit()
conn.close()

with open(TMP, 'rb') as f: data = f.read()
with open(DB, 'r+b') as f: f.write(data); f.truncate()
wal = DB + '-wal'
if os.path.exists(wal):
    with open(wal, 'r+b') as f: f.seek(0); f.truncate(0)

print("완료")
