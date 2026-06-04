"""
RunSession 레이어 삽입 마이그레이션
실행: 서버 중지 후 python scripts/migrate_run_session_layer.py

변경 전:
  Round (visible=1)
    └─ Topology (visible=1)
         └─ RC (visible=0) → Run → Result

변경 후:
  Round (visible=1)
    └─ RunSession (visible=1, stage='run_session')
         └─ Topology (visible=1)
              └─ RC (visible=0) → Run → Result

그룹핑 기준: RC 번호 (RC1 → Session 1, RC2 → Session 2)
"""
import sqlite3, shutil, os, sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB   = os.path.join(BASE, "data", "product_test_tracking_system.db")
TMP  = "/tmp/run_session_migration.db"
NOW  = datetime.now(timezone.utc).isoformat()
BY   = "run_session_migration_v1"

print(f"DB: {DB}")
if not os.path.exists(DB):
    print("ERROR: DB 없음"); sys.exit(1)

shutil.copy2(DB, TMP)
for ext in ('-wal', '-shm'):
    try: shutil.copy2(DB + ext, TMP + ext)
    except: pass

conn = sqlite3.connect(TMP)
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.row_factory = sqlite3.Row

all_visible = {r[0] for r in conn.execute(
    "SELECT product_test_release_id FROM product_test_release WHERE release_visible=1"
).fetchall()}

rounds = conn.execute("""
    SELECT product_test_release_id, release_sequence, remark
    FROM product_test_release
    WHERE release_visible = 1
      AND (upstream_release_id IS NULL
           OR upstream_release_id NOT IN (
               SELECT product_test_release_id
               FROM product_test_release WHERE release_visible=1
           ))
    ORDER BY release_sequence
""").fetchall()

print(f"\n처리할 라운드: {len(rounds)}개")
for r in rounds: print(f"  {r[0]}")

new_sessions = 0
new_topos    = 0

for round_row in rounds:
    round_id = round_row[0]
    print(f"\n{'─'*60}")
    print(f"[ROUND] {round_id}")

    topos = conn.execute("""
        SELECT product_test_release_id, release_sequence, remark
        FROM product_test_release
        WHERE upstream_release_id=? AND release_visible=1
        ORDER BY release_sequence
    """, (round_id,)).fetchall()

    if not topos:
        print("  topology 없음, 스킵")
        continue

    already = conn.execute("""
        SELECT 1 FROM product_test_release
        WHERE upstream_release_id=? AND release_stage='run_session'
        LIMIT 1
    """, (round_id,)).fetchone()
    if already:
        print("  이미 run_session 존재, 스킵")
        continue

    topo_rcs = {}
    all_rc_seqs = set()
    for topo in topos:
        rcs = conn.execute("""
            SELECT product_test_release_id, release_sequence
            FROM product_test_release
            WHERE upstream_release_id=? AND release_visible=0
            ORDER BY release_sequence
        """, (topo[0],)).fetchall()
        topo_rcs[topo[0]] = list(rcs)
        for rc in rcs:
            all_rc_seqs.add(rc[1] or 1)

    if not all_rc_seqs:
        all_rc_seqs = {1}

    print(f"  RC 세션: {sorted(all_rc_seqs)}")

    round_short = round_id.replace("TEST_RELEASE-", "")
    session_ids = {}
    for seq in sorted(all_rc_seqs):
        sid = f"TEST_RELEASE-{round_short}-RUN_RC{seq}"
        conn.execute("""
            INSERT OR IGNORE INTO product_test_release
            (product_test_release_id, upstream_release_id, upstream_release_system,
             release_stage, release_sequence, release_visible,
             product_test_release_status,
             created_at, created_by, updated_at, updated_by, remark)
            VALUES (?,?,'INTERNAL','run_session',?,1,'TESTING',?,?,?,?,?)
        """, (sid, round_id, seq, NOW, BY, NOW, BY,
              "RC{} 시험 세션".format(seq)))
        session_ids[seq] = sid
        print(f"  [NEW SESSION] {sid}")
        new_sessions += 1

    for topo in topos:
        topo_id = topo[0]
        rcs = topo_rcs.get(topo_id, [])

        if not rcs:
            first_key = sorted(session_ids.keys())[0]
            conn.execute(
                "UPDATE product_test_release SET upstream_release_id=? WHERE product_test_release_id=?",
                (session_ids[first_key], topo_id)
            )
            print(f"  [REPARENT] {topo_id} -> Session {first_key} (no RC)")
            continue

        rc_seqs = [rc[1] or 1 for rc in rcs]

        if len(set(rc_seqs)) == 1:
            seq = rc_seqs[0]
            conn.execute(
                "UPDATE product_test_release SET upstream_release_id=? WHERE product_test_release_id=?",
                (session_ids[seq], topo_id)
            )
            print(f"  [REPARENT] {topo_id} -> Session {seq}")
        else:
            topo_name = topo_id.split(f"-{round_short}-")[-1]
            sorted_seqs = sorted(set(rc_seqs))
            first_seq = sorted_seqs[0]
            conn.execute(
                "UPDATE product_test_release SET upstream_release_id=? WHERE product_test_release_id=?",
                (session_ids[first_seq], topo_id)
            )
            print(f"  [REPARENT] {topo_id} -> Session {first_seq} (orig)")

            for seq in sorted_seqs[1:]:
                new_topo_id = f"TEST_RELEASE-{round_short}-RUN_RC{seq}-{topo_name}"
                conn.execute("""
                    INSERT OR IGNORE INTO product_test_release
                    (product_test_release_id, upstream_release_id, upstream_release_system,
                     release_stage, release_sequence, release_visible,
                     product_test_release_status,
                     created_at, created_by, updated_at, updated_by, remark)
                    SELECT ?,?,upstream_release_system,release_stage,release_sequence,release_visible,
                           product_test_release_status,?,?,?,?,remark
                    FROM product_test_release WHERE product_test_release_id=?
                """, (new_topo_id, session_ids[seq], NOW, BY, NOW, BY, topo_id))

                for rc in rcs:
                    if (rc[1] or 1) == seq:
                        conn.execute(
                            "UPDATE product_test_release SET upstream_release_id=? WHERE product_test_release_id=?",
                            (new_topo_id, rc[0])
                        )
                print(f"  [NEW TOPO ] {new_topo_id} -> Session {seq}")
                new_topos += 1

conn.commit()
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.commit()
conn.close()

with open(TMP, 'rb') as f: data = f.read()
with open(DB, 'r+b') as f: f.write(data); f.truncate()
wal = DB + '-wal'
if os.path.exists(wal):
    with open(wal, 'r+b') as f: f.seek(0); f.truncate(0)

print(f"\n{'='*60}")
print(f"완료: RunSession {new_sessions}개 생성, Topology 복제 {new_topos}개")
