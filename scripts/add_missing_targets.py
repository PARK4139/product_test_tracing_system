"""
누락 Target / Target Definition 추가 스크립트
실행: 서버 중지 후 python scripts/add_missing_targets.py
"""
import sqlite3, shutil, os, sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB   = os.path.join(BASE, "data", "product_test_tracking_system.db")
TMP  = "/tmp/target_migration.db"

NOW = datetime.now(timezone.utc).isoformat()
BY  = "add_missing_targets_v1"

TARGET_DEFS = [
    # (id, product_code, manufacturer, model_name, default_sw_version)
    ("TARGET_DEF-HRK_9000A",  "HRK-9000A",  "Huvitz", "HRK-9000A",  "1.1.1A"),
    ("TARGET_DEF-HLM_9000",   "HLM-9000",   "Huvitz", "HLM-9000",   "1.1.14B"),
    ("TARGET_DEF-HTR_1A",     "HTR-1A",     "Huvitz", "HTR-1A",     "1.1.8"),
    ("TARGET_DEF-HDR_9000",   "HDR-9000",   "Huvitz", "HDR-9000",   "1.1.8"),
    ("TARGET_DEF-HDR_7100P",  "HDR-7100P",  "Huvitz", "HDR-7100P",  "1.1.7i"),
    ("TARGET_DEF-HDC_9100",   "HDC-9100",   "Huvitz", "HDC-9100",   "1.0.5A"),
]

TARGETS = [
    # (id, definition_id, serial_number, software_version, remark)
    ("TARGET-HRK_9000A-9HA09A24I0014", "TARGET_DEF-HRK_9000A", "9HA09A24I0014",        "1.1.1A",  "9HA09A24I0014"),
    ("TARGET-HLM_9000-9LM00024D0014",  "TARGET_DEF-HLM_9000",  "9LM00024D0014",        "1.1.14B", "9LM00024D0014"),
    ("TARGET-HTR_1A-2601_J004",        "TARGET_DEF-HTR_1A",    "2601-J004",            "1.1.8",   "2601-J004(제품외관스티커 정보)"),
    ("TARGET-HDR_9000-BE_260128_096",  "TARGET_DEF-HDR_9000",  "BE 260128-096",        "1.1.8",   "BE 260128-096(공정대여제품)"),
    ("TARGET-HDR_7100P-UNKNOWN",       "TARGET_DEF-HDR_7100P", "TBD",                  "1.1.7i",  None),
    ("TARGET-HDC_9100-PP__1",          "TARGET_DEF-HDC_9100",  "PP #1",                "1.0.5A",  "PP #1(관리번호 L-062)"),
]

print(f"DB: {DB}")
if not os.path.exists(DB):
    print("ERROR: DB 파일 없음"); sys.exit(1)

shutil.copy2(DB, TMP)
conn = sqlite3.connect(TMP)
conn.execute("PRAGMA journal_mode=WAL")

added_def = 0
for (tid, code, mfg, model, sw) in TARGET_DEFS:
    exists = conn.execute(
        "SELECT 1 FROM product_test_target_definition WHERE product_test_target_definition_id=?", (tid,)
    ).fetchone()
    if not exists:
        conn.execute("""
            INSERT INTO product_test_target_definition
            (product_test_target_definition_id, product_code, manufacturer, model_name,
             default_sw_version, product_test_target_definition_status,
             created_at, created_by, updated_at, updated_by)
            VALUES (?,?,?,?,?,'ACTIVE',?,?,?,?)
        """, (tid, code, mfg, model, sw, NOW, BY, NOW, BY))
        print(f"  [ADD DEF] {tid}")
        added_def += 1
    else:
        print(f"  [SKIP DEF] {tid}")

added_tgt = 0
for (tid, defid, serial, sw, remark) in TARGETS:
    exists = conn.execute(
        "SELECT 1 FROM product_test_target WHERE product_test_target_id=?", (tid,)
    ).fetchone()
    if not exists:
        conn.execute("""
            INSERT INTO product_test_target
            (product_test_target_id, product_test_target_definition_id,
             serial_number, software_version,
             product_test_target_status, created_at, created_by, updated_at, updated_by, remark)
            VALUES (?,?,?,?,'ACTIVE',?,?,?,?,?)
        """, (tid, defid, serial, sw, NOW, BY, NOW, BY, remark))
        print(f"  [ADD TGT] {tid}")
        added_tgt += 1
    else:
        print(f"  [SKIP TGT] {tid}")

conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.commit()
conn.close()

# 현재 DB에 적용
with open(TMP, 'rb') as f: data = f.read()
with open(DB, 'r+b') as f: f.write(data); f.truncate()
wal = DB + '-wal'
if os.path.exists(wal):
    with open(wal, 'r+b') as f: f.seek(0); f.truncate(0)

print(f"\n완료: Definition {added_def}개, Target {added_tgt}개 추가")
