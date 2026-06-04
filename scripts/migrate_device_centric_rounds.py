"""
Device-Centric Round Migration (장비 중심 라운드 재편)
실행: 서버 중지 후 python scripts/migrate_device_centric_rounds.py

변경 전:
  TEST_RELEASE-WIFI_1ST  (라운드)
    └─ TEST_RELEASE-WIFI_1ST-1AP_1HRK_4HDR  (topology, HRK+HDR 혼재)
         └─ RC1 → Run → Result×44 (HRK/HDR 섞임)

변경 후:
  TEST_RELEASE-HRK_9000A_1_1_1A-WIFI_1ST  (장비 라운드)
    └─ TEST_RELEASE-HRK_9000A_1_1_1A-WIFI_1ST-1AP_1HRK_4HDR
         └─ RC1 → Run → HRK Results만

  TEST_RELEASE-HDR_9000_1_1_7E-WIFI_1ST  (장비 라운드)
    └─ TEST_RELEASE-HDR_9000_1_1_7E-WIFI_1ST-1AP_1HRK_4HDR
         └─ RC1 → Run → HDR Results만
"""
import sqlite3, shutil, os, sys, re
from datetime import datetime, timezone
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB   = os.path.join(BASE, "data", "product_test_tracking_system.db")
TMP  = "/tmp/device_round_migration.db"
NOW  = datetime.now(timezone.utc).isoformat()
BY   = "device_round_migration_v1"

# ── 장치 우선순위 ────────────────────────────────────────────────
DEVICE_ORDER = ['HRK', 'HTR', 'HLM', 'HDR', 'HDC', 'HIIS']

# ── 라운드별 장비 SW 버전 (엑셀 기준) ───────────────────────────
# key: round_short (e.g. 'WIFI_1ST'), value: {dev_abbr: (model_code, sw_ver)}
ROUND_DEVICE_VERSIONS = {
    'WIFI_1ST': {
        'HRK': ('HRK_9000A', '1.1.1A'),
        'HTR': ('HTR_1A',    '1.1.8'),
        'HLM': ('HLM_9000',  '1.1.14B'),
        'HDR': ('HDR_9000',  '1.1.7E'),
        'HDC': ('HDC_9100',  '1.0.5A'),
    },
    'WIFI_2ND': {
        'HRK': ('HRK_9000A', '1.1.1A'),
        'HTR': ('HTR_1A',    '1.1.8'),
        'HLM': ('HLM_9000',  '1.1.14B'),
        'HDR': ('HDR_9000',  '1.1.8'),
        'HDC': ('HDC_9100',  '1.0.5A'),
    },
    'WIFI_1_1_1D': {
        'HRK': ('HRK_9000A', '1.1.1D'),
        'HDR': ('HDR_9000',  '1.1.8'),
    },
    'WIFI_DOWNGRADE': {
        'HRK': ('HRK_9000A', '1.1.0A'),
        'HDR': ('HDR_9000',  '1.1.7A'),
        'HLM': ('HLM_9000',  '1.1.13B'),
        'HTR': ('HTR_1A',    '1.1.8B'),
        'HDC': ('HDC_9100',  '1.0.4A'),
    },
}

# ── 라운드 표시 이름 ─────────────────────────────────────────────
ROUND_DISPLAY = {
    'WIFI_1ST':       'WIFI 시험 1차',
    'WIFI_2ND':       'WIFI 시험 2차',
    'WIFI_1_1_1D':    'WIFI 시험 (1.1.1D)',
    'WIFI_DOWNGRADE': 'WIFI 다운그레이드 시험',
}

# ────────────────────────────────────────────────────────────────
def ver_to_id(ver: str) -> str:
    """1.1.1A → 1_1_1A"""
    return ver.replace('.', '_')

def devices_in_topo(topo_name: str) -> list[str]:
    """1AP_1HRK_4HDR → ['HRK','HDR']  (우선순위 순)"""
    return [d for d in DEVICE_ORDER if d in topo_name]

def primary_device_of_case(case_id: str):
    """TEST_CASE-1AP_1HRK-WIFI-... → 'HRK'"""
    s = re.sub(r'^(DEPRECATED_)?TEST_CASE-', '', case_id)
    topo_part = s.split('-WIFI-')[0] if '-WIFI-' in s else s
    for d in DEVICE_ORDER:
        if d in topo_part:
            return d
    return None

def calc_status(passed, blocked, testing):
    if blocked > 0:   return 'BLOCKED'
    if testing > 0:   return 'TESTING'
    if passed > 0:    return 'PASSED'
    return 'TESTING'

# ────────────────────────────────────────────────────────────────
print(f"DB: {DB}")
if not os.path.exists(DB):
    print("ERROR: DB 없음"); sys.exit(1)

shutil.copy2(DB, TMP)
try:
    shutil.copy2(DB + '-wal', TMP + '-wal')
except: pass
try:
    shutil.copy2(DB + '-shm', TMP + '-shm')
except: pass

conn = sqlite3.connect(TMP)
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.row_factory = sqlite3.Row

# ── 현재 라운드 조회 ────────────────────────────────────────────
rounds = conn.execute("""
    SELECT product_test_release_id, release_sequence, remark
    FROM product_test_release
    WHERE release_visible = 1
      AND (upstream_release_id IS NULL
           OR upstream_release_id NOT IN (
               SELECT product_test_release_id FROM product_test_release
               WHERE release_visible = 1
           ))
      AND product_test_release_id LIKE 'TEST_RELEASE-WIFI_%'
      AND product_test_release_id NOT LIKE '%-%-% '
    ORDER BY release_sequence
""").fetchall()

print(f"\n처리할 라운드: {len(rounds)}개")
for r in rounds:
    print(f"  {r[0]}")

total_new_rounds = 0
total_new_topos  = 0
total_moved_results = 0

for round_row in rounds:
    round_id    = round_row[0]
    round_short = round_id.replace("TEST_RELEASE-", "")
    dev_versions = ROUND_DEVICE_VERSIONS.get(round_short, {})
    display_base = ROUND_DISPLAY.get(round_short, round_short)

    if not dev_versions:
        print(f"\n[SKIP] {round_short} — 버전 매핑 없음")
        continue

    print(f"\n{'─'*60}")
    print(f"[ROUND] {round_id}")

    # topology 목록
    topos = conn.execute("""
        SELECT product_test_release_id
        FROM product_test_release
        WHERE upstream_release_id = ? AND release_visible = 1
        ORDER BY release_sequence
    """, (round_id,)).fetchall()

    # 전체 장비 목록 (이 라운드에 등장하는)
    round_devices = set()
    for topo_row in topos:
        topo_name = topo_row[0].split(f"-{round_short}-")[-1]
        round_devices.update(devices_in_topo(topo_name))
    round_devices = [d for d in DEVICE_ORDER if d in round_devices]
    print(f"  장비: {round_devices}")

    # ── 장비별 라운드 생성 ──────────────────────────────────────
    for dev in round_devices:
        if dev not in dev_versions:
            print(f"  [SKIP DEV] {dev} — 버전 정보 없음")
            continue

        model_code, sw_ver = dev_versions[dev]
        ver_id   = ver_to_id(sw_ver)
        dev_round_id = f"TEST_RELEASE-{model_code}_{ver_id}-{round_short}"
        dev_display  = f"{model_code.replace('_','-')} {sw_ver} {display_base}"

        # 라운드 release 생성 (없으면)
        exists = conn.execute(
            "SELECT 1 FROM product_test_release WHERE product_test_release_id=?",
            (dev_round_id,)
        ).fetchone()
        if not exists:
            conn.execute("""
                INSERT INTO product_test_release
                (product_test_release_id, upstream_release_id, upstream_release_system,
                 release_stage, release_sequence, release_visible,
                 product_test_release_status,
                 created_at, created_by, updated_at, updated_by, remark)
                VALUES (?,'MULTI_PRODUCT','INTERNAL','device_round',?,1,'TESTING',?,?,?,?,?)
            """, (dev_round_id, 0, NOW, BY, NOW, BY, dev_display))
            print(f"  [NEW ROUND] {dev_round_id}")
            total_new_rounds += 1

        # ── 이 장비가 포함된 topology 처리 ─────────────────────
        topo_seq = 0
        for topo_row in topos:
            orig_topo_id = topo_row[0]
            topo_name    = orig_topo_id.split(f"-{round_short}-")[-1]

            if dev not in devices_in_topo(topo_name):
                continue  # 이 장비가 포함되지 않은 topology 스킵

            topo_seq += 1
            dev_topo_id = f"TEST_RELEASE-{model_code}_{ver_id}-{round_short}-{topo_name}"

            # topology release 생성
            if not conn.execute(
                "SELECT 1 FROM product_test_release WHERE product_test_release_id=?",
                (dev_topo_id,)
            ).fetchone():
                conn.execute("""
                    INSERT INTO product_test_release
                    (product_test_release_id, upstream_release_id, upstream_release_system,
                     release_stage, release_sequence, release_visible,
                     product_test_release_status,
                     created_at, created_by, updated_at, updated_by, remark)
                    VALUES (?,?,'INTERNAL','RC',?,1,'TESTING',?,?,?,?,?)
                """, (dev_topo_id, dev_round_id, topo_seq, NOW, BY, NOW, BY,
                      f"[구성] {topo_name}\n[장비] {dev}"))
                total_new_topos += 1

            # 원본 RC 목록
            rcs = conn.execute("""
                SELECT product_test_release_id, release_sequence
                FROM product_test_release
                WHERE upstream_release_id = ? AND release_visible = 0
                ORDER BY release_sequence
            """, (orig_topo_id,)).fetchall()

            for rc_row in rcs:
                orig_rc_id = rc_row[0]
                rc_seq     = rc_row[1] or 1
                dev_rc_id  = f"{dev_topo_id}-RC{rc_seq}"

                # RC release 생성
                if not conn.execute(
                    "SELECT 1 FROM product_test_release WHERE product_test_release_id=?",
                    (dev_rc_id,)
                ).fetchone():
                    conn.execute("""
                        INSERT INTO product_test_release
                        (product_test_release_id, upstream_release_id, upstream_release_system,
                         release_stage, release_sequence, release_visible,
                         product_test_release_status,
                         created_at, created_by, updated_at, updated_by, remark)
                        VALUES (?,?,'INTERNAL','RC',?,0,'TESTING',?,?,?,?,?)
                    """, (dev_rc_id, dev_topo_id, rc_seq, NOW, BY, NOW, BY,
                          f"[구성] {topo_name} [장비] {dev} RC{rc_seq}"))

                # 원본 Run 목록
                orig_runs = conn.execute(
                    "SELECT product_test_run_id, product_test_target_id, product_test_environment_id, started_at, finished_at, product_test_run_status, started_by, remark FROM product_test_run WHERE product_test_release_id=?",
                    (orig_rc_id,)
                ).fetchall()

                for run_row in orig_runs:
                    orig_run_id = run_row[0]
                    new_run_id  = f"{orig_run_id}-{dev}"

                    # 이 run에서 이 장비에 해당하는 result들
                    dev_results = conn.execute("""
                        SELECT product_test_result_id
                        FROM product_test_result
                        WHERE product_test_run_id = ?
                          AND product_test_case_id IS NOT NULL
                    """, (orig_run_id,)).fetchall()

                    # 장비별 필터링
                    target_result_ids = []
                    for res_row in dev_results:
                        rid = res_row[0]
                        cid = conn.execute(
                            "SELECT product_test_case_id FROM product_test_result WHERE product_test_result_id=?",
                            (rid,)
                        ).fetchone()[0]
                        if primary_device_of_case(cid or '') == dev:
                            target_result_ids.append(rid)

                    if not target_result_ids:
                        continue  # 이 장비 결과 없으면 run 생성 안 함

                    # Run 생성
                    if not conn.execute(
                        "SELECT 1 FROM product_test_run WHERE product_test_run_id=?",
                        (new_run_id,)
                    ).fetchone():
                        conn.execute("""
                            INSERT INTO product_test_run
                            (product_test_run_id, product_test_release_id,
                             product_test_target_id, product_test_environment_id,
                             product_test_run_status, started_at, finished_at,
                             started_by, created_at, created_by, updated_at, updated_by, remark)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (new_run_id, dev_rc_id,
                              run_row[1], run_row[2],
                              run_row[5], run_row[3], run_row[4],
                              run_row[6], NOW, BY, NOW, BY,
                              f"[장비] {dev} [원본] {orig_run_id}"))

                    # Result 이관
                    for rid in target_result_ids:
                        conn.execute(
                            "UPDATE product_test_result SET product_test_run_id=? WHERE product_test_result_id=?",
                            (new_run_id, rid)
                        )
                    total_moved_results += len(target_result_ids)
                    print(f"    → {dev_rc_id} | {len(target_result_ids)}건 이관")

    # ── 기존 라운드 LEGACY 처리 ─────────────────────────────────
    conn.execute(
        "UPDATE product_test_release SET release_stage='round_legacy' WHERE product_test_release_id=?",
        (round_id,)
    )
    print(f"  [LEGACY] {round_id}")

# ── 신규 RC/Topology/Round status 재계산 ────────────────────────
print("\n\n[상태 재계산]")
new_rcs = conn.execute("""
    SELECT product_test_release_id FROM product_test_release
    WHERE created_by=? AND release_visible=0
""", (BY,)).fetchall()

for (rc_id,) in new_rcs:
    runs = conn.execute(
        "SELECT product_test_run_id FROM product_test_run WHERE product_test_release_id=?",
        (rc_id,)
    ).fetchall()
    p = b = t = 0
    for (run_id,) in runs:
        stats = conn.execute("""
            SELECT product_test_result_status, COUNT(*) FROM product_test_result
            WHERE product_test_run_id=? GROUP BY product_test_result_status
        """, (run_id,)).fetchall()
        for st, cnt in stats:
            if st == 'passed':   p += cnt
            elif st == 'blocked': b += cnt
            elif st == 'testing': t += cnt
    status = calc_status(p, b, t)
    conn.execute(
        "UPDATE product_test_release SET product_test_release_status=? WHERE product_test_release_id=?",
        (status, rc_id)
    )

    # topo status
    topo_id = conn.execute(
        "SELECT upstream_release_id FROM product_test_release WHERE product_test_release_id=?",
        (rc_id,)
    ).fetchone()[0]
    if topo_id:
        all_rcs = conn.execute(
            "SELECT product_test_release_id FROM product_test_release WHERE upstream_release_id=?",
            (topo_id,)
        ).fetchall()
        tp = tb = tt = 0
        for (r,) in all_rcs:
            s = conn.execute(
                "SELECT product_test_release_status FROM product_test_release WHERE product_test_release_id=?",
                (r,)
            ).fetchone()[0]
            if s == 'BLOCKED': tb += 1
            elif s == 'PASSED': tp += 1
            else: tt += 1
        conn.execute(
            "UPDATE product_test_release SET product_test_release_status=? WHERE product_test_release_id=?",
            (calc_status(tp, tb, tt), topo_id)
        )

        # round status
        round_id2 = conn.execute(
            "SELECT upstream_release_id FROM product_test_release WHERE product_test_release_id=?",
            (topo_id,)
        ).fetchone()[0]
        if round_id2:
            all_topos = conn.execute(
                "SELECT product_test_release_status FROM product_test_release WHERE upstream_release_id=?",
                (round_id2,)
            ).fetchall()
            rp = rb = rt = 0
            for (s,) in all_topos:
                if s == 'BLOCKED': rb += 1
                elif s == 'PASSED': rp += 1
                else: rt += 1
            conn.execute(
                "UPDATE product_test_release SET product_test_release_status=? WHERE product_test_release_id=?",
                (calc_status(rp, rb, rt), round_id2)
            )

# ── 커밋 및 DB 적용 ─────────────────────────────────────────────
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
print(f"완료:")
print(f"  신규 장비 라운드: {total_new_rounds}개")
print(f"  신규 Topology:   {total_new_topos}개")
print(f"  이관 Result:     {total_moved_results}")
