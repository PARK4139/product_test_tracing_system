#!/usr/bin/env python3
"""
구성(Topology) 기반 Release 구조 재편 마이그레이션
================================================================================
장비행(HRK, HDR, ...) 중심 → 시험 구성(1AP_1HRK_4HDR, ...) 중심으로 전환

실행:
  python scripts/migrate_topology_restructure.py            # dry-run
  python scripts/migrate_topology_restructure.py --apply    # 실제 적용

원칙:
  ① result 375건 전량 보존 (1건도 누락 없음)
  ② defect 15건 경로 무결성 유지 (defect→result→run→release)
  ③ 엑셀 추적: result_id 불변, remark에 원본 정보 보존
  ④ 롤백 가능: 실행 전 자동 백업
================================================================================
"""
from __future__ import annotations

import re
import shutil
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "product_test_tracking_system.db"
NOW = datetime.now(timezone.utc).isoformat()
ACTOR = "topology_restructure_v1"

# ── 장비 순서 (네이밍 정규화용) ──
DEVICE_ORDER = ["HRK", "HTR", "HLM", "HDR", "HDC", "HIIS"]


def normalize_combo(raw: str) -> str | None:
    """원본 combo 문자열 → 정규화된 구성 이름.

    규칙:
      - {AP수}AP_{장비수}{장비명}_{장비수}{장비명}_...
      - 장비 순서: HRK > HTR > HLM > HDR > HDC > HIIS
      - 같은 장비 대수는 합산 (1HDR_1HDR → 2HDR)
      - 숫자 없는 장비명은 1로 간주 (HRK → 1HRK)

    Returns None for unclassifiable combos (TBD, empty, etc.)
    """
    if not raw or raw.strip() in ("TBD", "VARIOUS_CONNECTIONS", ""):
        return None

    combo = raw.strip().replace(" ", "")
    parts = re.findall(r"(\d*)(AP|HRK|HTR|HLM|HDR|HDC|HIIS)", combo)
    if not parts:
        return None

    ap_part = ""
    device_counts: dict[str, int] = {}
    for count_str, device in parts:
        count = int(count_str) if count_str else 1
        if device == "AP":
            ap_part = f"{count}AP"
        else:
            device_counts[device] = device_counts.get(device, 0) + count

    if not ap_part:
        return None

    sorted_devices = sorted(
        device_counts.items(),
        key=lambda x: DEVICE_ORDER.index(x[0]) if x[0] in DEVICE_ORDER else 99,
    )
    device_part = "_".join(f"{cnt}{dev}" for dev, cnt in sorted_devices)
    return f"{ap_part}_{device_part}" if device_part else None


def extract_combo_from_remark(remark: str) -> str:
    """result remark에서 [연결구성] 값 추출."""
    m = re.search(r"\[연결구성\]\s*(.+)", remark or "")
    return m.group(1).strip() if m else ""


def extract_topo_from_case_id(case_id: str) -> str:
    """case_id에서 구성 파트 추출. TEST_CASE-{topo}-WIFI-... → topo"""
    m = re.match(r"TEST_CASE-([^-]+)-", case_id or "")
    return m.group(1) if m else ""


def get_round_id(conn: sqlite3.Connection, rc_release_id: str) -> str | None:
    """RC release_id → 라운드 release_id (upstream=MULTI_PRODUCT인 조상)."""
    cur = rc_release_id
    for _ in range(10):
        row = conn.execute(
            "SELECT upstream_release_id FROM product_test_release WHERE product_test_release_id=?",
            (cur,),
        ).fetchone()
        if not row or not row[0]:
            return None
        parent_id = row[0]
        if parent_id == "MULTI_PRODUCT":
            return cur  # cur is the round
        # check if parent exists
        exists = conn.execute(
            "SELECT 1 FROM product_test_release WHERE product_test_release_id=?",
            (parent_id,),
        ).fetchone()
        if not exists:
            return cur  # cur's parent doesn't exist → cur is top
        cur = parent_id
    return None


def main() -> None:
    apply_mode = "--apply" in sys.argv
    mode_label = "적용" if apply_mode else "DRY-RUN (미리보기)"

    print("=" * 70)
    print(f"  구성(Topology) 기반 Release 구조 재편 [{mode_label}]")
    print(f"  DB: {DB_PATH}")
    print("=" * 70)

    if not DB_PATH.exists():
        sys.exit(f"[ERROR] DB 없음: {DB_PATH}")

    # ── 1. 백업 ──
    backup_path = DB_PATH.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"\n[1/9] 백업 완료: {backup_path}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")

    # ── 2. 현재 상태 기록 ──
    before_result_count = conn.execute("SELECT COUNT(*) FROM product_test_result").fetchone()[0]
    before_defect_count = conn.execute("SELECT COUNT(*) FROM product_test_defect").fetchone()[0]
    before_release_count = conn.execute("SELECT COUNT(*) FROM product_test_release").fetchone()[0]
    before_run_count = conn.execute("SELECT COUNT(*) FROM product_test_run").fetchone()[0]
    print(f"[2/9] 현재 상태: result={before_result_count}, defect={before_defect_count}, "
          f"release={before_release_count}, run={before_run_count}")

    # ── 3. 전체 result + run + release 체인 읽기 ──
    results_raw = conn.execute("""
        SELECT
            res.product_test_result_id,
            res.product_test_case_id,
            res.product_test_run_id,
            res.remark           AS result_remark,
            res.product_test_result_status,
            run.product_test_release_id AS rc_release_id,
            run.product_test_target_id,
            run.product_test_environment_id,
            run.remark           AS run_remark,
            run.product_test_run_status,
            run.started_at,
            run.started_by,
            run.finished_at
        FROM product_test_result res
        JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
    """).fetchall()

    print(f"[3/9] result {len(results_raw)}건 읽기 완료")

    # ── 4. 각 result의 (round, combo, rc_seq) 결정 ──
    # 먼저 라운드별 RC 순서 매핑
    rc_to_round: dict[str, str] = {}
    round_rc_order: dict[str, list[str]] = defaultdict(list)  # round → [rc_ids in order]

    rc_release_ids = set(r[5] for r in results_raw)
    for rc_id in rc_release_ids:
        round_id = get_round_id(conn, rc_id)
        if round_id:
            rc_to_round[rc_id] = round_id
            if rc_id not in round_rc_order[round_id]:
                round_rc_order[round_id].append(rc_id)

    # RC 순서를 release_sequence + ID로 정렬 (sequence 동일 시 ID 알파벳순)
    for round_id, rc_list in round_rc_order.items():
        seqs = {}
        for rc_id in rc_list:
            row = conn.execute(
                "SELECT release_sequence FROM product_test_release WHERE product_test_release_id=?",
                (rc_id,),
            ).fetchone()
            seqs[rc_id] = row[0] if row else 0
        rc_list.sort(key=lambda x: (seqs.get(x, 0), x))

    # RC → 라운드 내 순번
    rc_seq_in_round: dict[str, int] = {}
    for round_id, rc_list in round_rc_order.items():
        for i, rc_id in enumerate(rc_list, 1):
            rc_seq_in_round[rc_id] = i

    print(f"    라운드 {len(round_rc_order)}개, RC {len(rc_to_round)}개 매핑 완료")
    for round_id, rc_list in round_rc_order.items():
        print(f"    {round_id}: {[f'{rc}(seq{rc_seq_in_round[rc]})' for rc in rc_list]}")

    # ── 5. result별 normalized combo 결정 ──
    ResultMapping = dict  # result_id → {round, combo, rc_seq, original_run_id, ...}
    result_mappings: list[dict] = []
    combo_stats: dict[str, int] = defaultdict(int)
    unclassified: list[dict] = []

    for r in results_raw:
        result_id = r[0]
        case_id = r[1]
        original_run_id = r[2]
        result_remark = r[3] or ""
        result_status = r[4]
        rc_release_id = r[5]

        # combo 결정: remark > case_id
        raw_combo = extract_combo_from_remark(result_remark)
        if not raw_combo:
            raw_combo = extract_topo_from_case_id(case_id)

        normalized = normalize_combo(raw_combo)
        round_id = rc_to_round.get(rc_release_id)
        rc_seq = rc_seq_in_round.get(rc_release_id, 1)

        if not normalized or not round_id:
            unclassified.append({
                "result_id": result_id,
                "case_id": case_id,
                "raw_combo": raw_combo,
                "rc_release_id": rc_release_id,
                "status": result_status,
            })
            # fallback: case_id의 topology를 직접 사용
            if not normalized:
                topo = extract_topo_from_case_id(case_id)
                if topo:
                    normalized = normalize_combo(topo)
            if not round_id:
                round_id = rc_to_round.get(rc_release_id)

        mapping = {
            "result_id": result_id,
            "case_id": case_id,
            "original_run_id": original_run_id,
            "result_remark": result_remark,
            "result_status": result_status,
            "rc_release_id": rc_release_id,
            "round_id": round_id,
            "normalized_combo": normalized,
            "rc_seq": rc_seq,
            "target_id": r[6],
            "env_id": r[7],
            "run_remark": r[8],
            "run_status": r[9],
            "started_at": r[10],
            "started_by": r[11],
            "finished_at": r[12],
        }
        result_mappings.append(mapping)
        if normalized:
            combo_stats[normalized] += 1

    print(f"\n[5/9] combo 분류 완료")
    print(f"    분류됨: {sum(combo_stats.values())}건, {len(combo_stats)}개 구성")
    print(f"    미분류: {len([m for m in result_mappings if not m['normalized_combo']])}건")

    for combo, cnt in sorted(combo_stats.items(), key=lambda x: -x[1]):
        print(f"      {combo}: {cnt}건")

    if unclassified:
        print(f"\n    [미분류 상세]")
        for u in unclassified:
            print(f"      {u['result_id']}: combo='{u['raw_combo']}' case={u['case_id'][:40]} status={u['status']}")

    # ── 6. 라운드별 기존 device row 정보 수집 (날짜/workday 상속용) ──
    round_meta: dict[str, dict] = {}
    for round_id in round_rc_order:
        # 기존 device row들의 remark에서 날짜 추출
        device_rows = conn.execute("""
            SELECT remark FROM product_test_release
            WHERE upstream_release_id = ?
            AND COALESCE(release_visible, 1) = 1
            AND product_test_release_id NOT LIKE '%TEST_REPORT_%'
            AND product_test_release_id NOT LIKE '%TBD_REPORT_%'
            LIMIT 1
        """, (round_id,)).fetchone()
        remark = device_rows[0] if device_rows else ""
        start = ""
        end = ""
        workday = ""
        for line in (remark or "").split("\n"):
            line = line.strip()
            if line.startswith("[Start]"):
                rest = line.replace("[Start]", "").strip()
                if "[End]" in rest:
                    parts = rest.split("[End]", 1)
                    start = parts[0].strip()
                    end = parts[1].strip()
                else:
                    start = rest
            elif line.startswith("[End]"):
                end = line.replace("[End]", "").strip()
            elif line.startswith("[Workday]"):
                workday = line.replace("[Workday]", "").strip()
        round_meta[round_id] = {"start": start, "end": end, "workday": workday}

    # ── 7. 새 구조 생성 ──
    # 그룹: (round_id, normalized_combo) → topology release
    # 그룹: (round_id, normalized_combo, rc_seq) → RC release
    # 그룹: (round_id, normalized_combo, rc_seq, original_run_id) → new Run

    topo_releases_to_create: dict[tuple[str, str], dict] = {}
    rc_releases_to_create: dict[tuple[str, str, int], dict] = {}
    runs_to_create: dict[tuple[str, str, int, str], dict] = {}
    result_updates: list[tuple[str, str]] = []  # (result_id, new_run_id)

    # 라운드별 topology 순번 (gantt 표시 순서용)
    round_topo_seq: dict[str, int] = defaultdict(int)

    for m in result_mappings:
        round_id = m["round_id"]
        combo = m["normalized_combo"]
        rc_seq = m["rc_seq"]
        original_run_id = m["original_run_id"]

        if not round_id or not combo:
            # 미분류 result → 원래 위치 유지
            continue

        # round_id에서 짧은 이름 추출 (예: TEST_RELEASE-WIFI_1ST → WIFI_1ST)
        round_short = round_id.replace("TEST_RELEASE-", "")

        # Topology release
        topo_key = (round_id, combo)
        if topo_key not in topo_releases_to_create:
            round_topo_seq[round_id] += 1
            meta = round_meta.get(round_id, {})
            topo_release_id = f"TEST_RELEASE-{round_short}-{combo}"
            topo_releases_to_create[topo_key] = {
                "id": topo_release_id,
                "upstream_id": round_id,
                "alias": combo,
                "stage": "RC",
                "sequence": round_topo_seq[round_id],
                "status": "TESTING",  # 후에 result 기반으로 재계산
                "visible": 1,
                "remark": (
                    f"[Report Alias] {combo}\n"
                    f"[Workday] {meta.get('workday', '')}\n"
                    f"[Start] {meta.get('start', '')}  [End] {meta.get('end', '')}"
                ),
            }

        topo_release_id = topo_releases_to_create[topo_key]["id"]

        # RC release
        rc_key = (round_id, combo, rc_seq)
        if rc_key not in rc_releases_to_create:
            rc_release_id = f"TEST_RELEASE-{round_short}-{combo}-RC{rc_seq}"
            rc_releases_to_create[rc_key] = {
                "id": rc_release_id,
                "upstream_id": topo_release_id,
                "alias": f"{combo} RC{rc_seq}",
                "stage": "RC",
                "sequence": rc_seq,
                "status": "TESTING",
                "visible": 0,
                "remark": f"[구성] {combo}\n[라운드내 시험차수] RC{rc_seq}",
            }

        new_rc_release_id = rc_releases_to_create[rc_key]["id"]

        # Run
        run_key = (round_id, combo, rc_seq, original_run_id)
        if run_key not in runs_to_create:
            new_run_id = f"RUN-{round_short}-{combo}-RC{rc_seq}"
            # 같은 RC 내에서 여러 원본 run이 있을 수 있음 → suffix 추가
            existing = [k for k in runs_to_create if k[:3] == (round_id, combo, rc_seq)]
            if existing:
                new_run_id += f"-{len(existing) + 1}"

            runs_to_create[run_key] = {
                "id": new_run_id,
                "release_id": new_rc_release_id,
                "target_id": m["target_id"],
                "env_id": m["env_id"],
                "status": m["run_status"],
                "started_at": m["started_at"],
                "started_by": m["started_by"],
                "finished_at": m["finished_at"],
                "remark": (
                    f"[구성] {combo}\n"
                    f"[원본Run] {original_run_id}\n"
                    f"{m['run_remark'] or ''}"
                ),
            }

        new_run_id = runs_to_create[run_key]["id"]
        result_updates.append((m["result_id"], new_run_id))

    print(f"\n[7/9] 새 구조 계획:")
    print(f"    신규 topology release: {len(topo_releases_to_create)}개")
    print(f"    신규 RC release: {len(rc_releases_to_create)}개")
    print(f"    신규 Run: {len(runs_to_create)}개")
    print(f"    result 재매핑: {len(result_updates)}건")

    # 미분류 건수
    unmapped_count = before_result_count - len(result_updates)
    if unmapped_count > 0:
        print(f"    [주의] 미분류 result: {unmapped_count}건 (원래 위치 유지)")

    # 상세 출력
    print(f"\n    [신규 topology release 목록]")
    for (round_id, combo), info in sorted(topo_releases_to_create.items()):
        print(f"      {info['id']}")

    if not apply_mode:
        print(f"\n{'=' * 70}")
        print(f"  DRY-RUN 완료. 실제 적용하려면:")
        print(f"    python scripts/migrate_topology_restructure.py --apply")
        print(f"{'=' * 70}")
        conn.close()
        return

    # ══════════════════════════════════════════════════════════════
    # 이하 --apply 모드에서만 실행
    # ══════════════════════════════════════════════════════════════

    print(f"\n[적용 시작]")

    # ── 7a. 신규 topology release 생성 ──
    for info in topo_releases_to_create.values():
        conn.execute("""
            INSERT INTO product_test_release
              (product_test_release_id, upstream_release_id, upstream_release_system,
               release_stage, release_sequence, product_test_release_status,
               release_visible,
               created_at, created_by, updated_at, updated_by, remark,
               project_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            info["id"], info["upstream_id"], "TOPOLOGY_RESTRUCTURE",
            info["stage"], info["sequence"], info["status"],
            info["visible"],
            NOW, ACTOR, NOW, ACTOR, info["remark"],
            "WIFI_CONNECTIVITY_TEST_2026",
        ))
    print(f"    topology release {len(topo_releases_to_create)}개 생성")

    # ── 7b. 신규 RC release 생성 ──
    for info in rc_releases_to_create.values():
        conn.execute("""
            INSERT INTO product_test_release
              (product_test_release_id, upstream_release_id, upstream_release_system,
               release_stage, release_sequence, product_test_release_status,
               release_visible,
               created_at, created_by, updated_at, updated_by, remark,
               project_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            info["id"], info["upstream_id"], "TOPOLOGY_RESTRUCTURE",
            info["stage"], info["sequence"], info["status"],
            info["visible"],
            NOW, ACTOR, NOW, ACTOR, info["remark"],
            "WIFI_CONNECTIVITY_TEST_2026",
        ))
    print(f"    RC release {len(rc_releases_to_create)}개 생성")

    # ── 7c. 신규 Run 생성 ──
    for info in runs_to_create.values():
        conn.execute("""
            INSERT INTO product_test_run
              (product_test_run_id, product_test_release_id,
               product_test_target_id, product_test_environment_id,
               product_test_run_status,
               started_at, started_by, finished_at,
               created_at, created_by, updated_at, updated_by, remark,
               project_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            info["id"], info["release_id"],
            info["target_id"], info["env_id"],
            info["status"],
            info["started_at"], info["started_by"], info["finished_at"],
            NOW, ACTOR, NOW, ACTOR, info["remark"],
            "WIFI_CONNECTIVITY_TEST_2026",
        ))
    print(f"    Run {len(runs_to_create)}개 생성")

    # ── 7d. result의 run_id 업데이트 ──
    for result_id, new_run_id in result_updates:
        conn.execute("""
            UPDATE product_test_result
            SET product_test_run_id = ?, updated_at = ?, updated_by = ?
            WHERE product_test_result_id = ?
        """, (new_run_id, NOW, ACTOR, result_id))
    print(f"    result {len(result_updates)}건 재매핑")

    # ── 8. 기존 장비행/RC/Run 정리 ──
    # 기존 device rows 식별 (created_by='restructure', visible=1, 장비명 패턴)
    old_device_rows = conn.execute("""
        SELECT product_test_release_id FROM product_test_release
        WHERE created_by = 'restructure'
        AND COALESCE(release_visible, 1) = 1
    """).fetchall()
    old_device_ids = [r[0] for r in old_device_rows]

    # 기존 RC releases (visible=0, created_by='migration_script_v1')
    old_rc_releases = conn.execute("""
        SELECT product_test_release_id FROM product_test_release
        WHERE created_by = 'migration_script_v1'
        AND COALESCE(release_visible, 1) = 0
    """).fetchall()
    old_rc_ids = [r[0] for r in old_rc_releases]

    # 기존 Run 중 result가 0건인 것만 삭제 (안전)
    old_runs = conn.execute("""
        SELECT run.product_test_run_id
        FROM product_test_run run
        WHERE run.created_by = 'migration_script_v1'
        AND NOT EXISTS (
            SELECT 1 FROM product_test_result res
            WHERE res.product_test_run_id = run.product_test_run_id
        )
    """).fetchall()
    old_run_ids = [r[0] for r in old_runs]

    # 삭제 실행
    for run_id in old_run_ids:
        conn.execute("DELETE FROM product_test_run WHERE product_test_run_id = ?", (run_id,))
    print(f"\n[8/9] 정리:")
    print(f"    기존 Run 삭제: {len(old_run_ids)}건")

    # RC release 삭제 (run이 없는 것만)
    deleted_rc = 0
    for rc_id in old_rc_ids:
        has_runs = conn.execute(
            "SELECT 1 FROM product_test_run WHERE product_test_release_id = ?", (rc_id,)
        ).fetchone()
        if not has_runs:
            conn.execute("DELETE FROM product_test_release WHERE product_test_release_id = ?", (rc_id,))
            deleted_rc += 1
    print(f"    기존 RC release 삭제: {deleted_rc}건")

    # device row 삭제 (하위 release가 없는 것만)
    deleted_device = 0
    for dev_id in old_device_ids:
        has_children = conn.execute(
            "SELECT 1 FROM product_test_release WHERE upstream_release_id = ?", (dev_id,)
        ).fetchone()
        has_reports = conn.execute(
            "SELECT 1 FROM product_test_report WHERE product_test_release_id = ?", (dev_id,)
        ).fetchone()
        if not has_children and not has_reports:
            conn.execute("DELETE FROM product_test_release WHERE product_test_release_id = ?", (dev_id,))
            deleted_device += 1
    print(f"    기존 device row 삭제: {deleted_device}건")

    # ── 8b. Release status 보정 ──
    # RC별 result 집계 → status 결정
    STATUS_PRIORITY = {
        "BLOCKED": 0, "TESTING": 1, "DRAFT": 2,
        "PASSED": 3, "QI_TEAM_RELEASED": 3, "APPROVED": 3,
        "QI_TEAM_REVIEWED": 4, "DONE": 5,
    }

    new_rc_ids = [info["id"] for info in rc_releases_to_create.values()]
    for rc_id in new_rc_ids:
        statuses = conn.execute("""
            SELECT res.product_test_result_status, COUNT(*)
            FROM product_test_result res
            JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
            WHERE run.product_test_release_id = ?
            GROUP BY res.product_test_result_status
        """, (rc_id,)).fetchall()

        if not statuses:
            continue

        status_map = dict(statuses)
        blocked = status_map.get("blocked", 0)
        testing = status_map.get("testing", 0)
        passed = status_map.get("passed", 0)

        # opened defect 확인
        open_defects = conn.execute("""
            SELECT COUNT(*) FROM product_test_defect def
            JOIN product_test_result res ON res.product_test_result_id = def.product_test_result_id
            JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
            WHERE run.product_test_release_id = ?
            AND def.product_test_defect_status = 'opened'
        """, (rc_id,)).fetchone()[0]

        if blocked > 0 or open_defects > 0:
            new_status = "BLOCKED"
        elif testing > 0:
            new_status = "TESTING"
        elif passed > 0:
            new_status = "PASSED"
        else:
            new_status = "TESTING"

        conn.execute(
            "UPDATE product_test_release SET product_test_release_status = ? WHERE product_test_release_id = ?",
            (new_status, rc_id),
        )

    # Topology release status = 하위 RC 중 최우선
    new_topo_ids = [info["id"] for info in topo_releases_to_create.values()]
    for topo_id in new_topo_ids:
        child_statuses = conn.execute("""
            SELECT product_test_release_status FROM product_test_release
            WHERE upstream_release_id = ? AND COALESCE(release_visible, 1) = 0
        """, (topo_id,)).fetchall()

        if child_statuses:
            best = min(
                [s[0] for s in child_statuses],
                key=lambda s: STATUS_PRIORITY.get(s, 99),
            )
            conn.execute(
                "UPDATE product_test_release SET product_test_release_status = ? WHERE product_test_release_id = ?",
                (best, topo_id),
            )

    print(f"    RC/Topology status 보정 완료")

    # ── 9. 검증 ──
    conn.commit()

    after_result_count = conn.execute("SELECT COUNT(*) FROM product_test_result").fetchone()[0]
    after_defect_count = conn.execute("SELECT COUNT(*) FROM product_test_defect").fetchone()[0]
    after_release_count = conn.execute("SELECT COUNT(*) FROM product_test_release").fetchone()[0]
    after_run_count = conn.execute("SELECT COUNT(*) FROM product_test_run").fetchone()[0]

    # defect 경로 무결성
    defect_integrity = conn.execute("""
        SELECT COUNT(*) FROM product_test_defect def
        JOIN product_test_result res ON res.product_test_result_id = def.product_test_result_id
        JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
        JOIN product_test_release rel ON rel.product_test_release_id = run.product_test_release_id
    """).fetchone()[0]

    # 구성별 result 분포
    topo_dist = conn.execute("""
        SELECT rel_parent.product_test_release_id, COUNT(res.product_test_result_id)
        FROM product_test_result res
        JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
        JOIN product_test_release rc ON rc.product_test_release_id = run.product_test_release_id
        JOIN product_test_release rel_parent ON rel_parent.product_test_release_id = rc.upstream_release_id
        WHERE rel_parent.created_by = ?
        GROUP BY rel_parent.product_test_release_id
        ORDER BY COUNT(res.product_test_result_id) DESC
    """, (ACTOR,)).fetchall()

    print(f"\n[9/9] 검증 결과:")
    print(f"    result: {before_result_count} → {after_result_count}  "
          f"{'OK' if before_result_count == after_result_count else 'MISMATCH!'}")
    print(f"    defect: {before_defect_count} → {after_defect_count}  "
          f"{'OK' if before_defect_count == after_defect_count else 'MISMATCH!'}")
    print(f"    defect 경로 무결성: {defect_integrity}/{after_defect_count}  "
          f"{'OK' if defect_integrity == after_defect_count else 'INTEGRITY BROKEN!'}")
    print(f"    release: {before_release_count} → {after_release_count}")
    print(f"    run: {before_run_count} → {after_run_count}")

    if topo_dist:
        print(f"\n    [구성별 result 분포]")
        topo_total = 0
        for topo_id, cnt in topo_dist:
            short = topo_id.replace("TEST_RELEASE-", "")
            print(f"      {short}: {cnt}건")
            topo_total += cnt
        remaining = after_result_count - topo_total
        if remaining > 0:
            print(f"      (미분류/기존 위치 유지): {remaining}건")
        print(f"      합계: {topo_total + remaining}건")

    # 최종 확인
    ok = (
        before_result_count == after_result_count
        and before_defect_count == after_defect_count
        and defect_integrity == after_defect_count
    )

    print(f"\n{'=' * 70}")
    if ok:
        print(f"  [OK] migration complete. backup: {backup_path}")
    else:
        print(f"  [FAIL] verification failed! restore from: {backup_path}")
    print(f"{'=' * 70}")

    conn.close()


if __name__ == "__main__":
    main()
