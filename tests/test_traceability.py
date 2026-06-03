"""
추적성 회귀테스트 (Traceability Regression Tests)
실행: python tests/test_traceability.py [db_path]
기본 DB: data/product_test_tracking_system.db

체인 검증:
  Release(visible=1 구성행)
    └─ RC(visible=0)
         └─ Run
              └─ Result ─── Case ─── Procedure
                   └─ Defect
                        └─ Retest Result (해소 Run)
"""
import sqlite3, sys, os

DB_DEFAULT = os.path.join(os.path.dirname(__file__), '..', 'data', 'product_test_tracking_system.db')
DB = sys.argv[1] if len(sys.argv) > 1 else DB_DEFAULT

try:
    conn = sqlite3.connect(DB)
    conn.execute("SELECT 1 FROM product_test_release LIMIT 1")
except Exception as e:
    print(f"[ERROR] DB 연결 실패: {e}")
    sys.exit(2)

GREEN = "\033[32m"; RED = "\033[31m"; YELLOW = "\033[33m"; RESET = "\033[0m"
PASS = f"{GREEN}PASS{RESET}"; FAIL = f"{RED}FAIL{RESET}"; WARN = f"{YELLOW}WARN{RESET}"

results = []

def tc(name, query, expect_zero=False, warn_only=False, info_only=False):
    rows = conn.execute(query).fetchall()
    count = len(rows)
    if info_only:
        label = "INFO"
        print(f"[INFO] {name}: {count}건")
        results.append(("INFO", name, count, rows[:3]))
        return
    if expect_zero:
        ok = count == 0
        status = PASS if ok else (WARN if warn_only else FAIL)
        label = "PASS" if ok else ("WARN" if warn_only else "FAIL")
        print(f"[{status}] {name}")
        if not ok:
            print(f"       → {count}건 위반: {rows[:3]}")
    else:
        ok = count > 0
        status = PASS if ok else FAIL
        label = "PASS" if ok else "FAIL"
        print(f"[{status}] {name} ({count}건)")
    results.append((label, name, count, rows[:3]))


print(f"\n{'='*65}")
print(f"  추적성 회귀테스트")
print(f"  DB: {os.path.abspath(DB)}")
print(f"{'='*65}")

# ─── 그룹 1. Release 구조 ──────────────────────────────────
print("\n[그룹 1] Release 구조 무결성")

tc("TC-R01: visible=1 구성행 존재",
   "SELECT product_test_release_id FROM product_test_release WHERE release_visible=1 LIMIT 1")

tc("TC-R02: visible=0 RC 존재",
   "SELECT product_test_release_id FROM product_test_release WHERE release_visible=0 LIMIT 1")

tc("TC-R03: RC의 upstream이 존재하는 release를 가리킴 (고아 RC 없음)",
   """
   SELECT rc.product_test_release_id, rc.upstream_release_id
   FROM product_test_release rc
   WHERE rc.release_visible = 0
     AND rc.upstream_release_id IS NOT NULL
     AND rc.upstream_release_id NOT IN (
         SELECT product_test_release_id FROM product_test_release
     )
   """, expect_zero=True)

tc("TC-R04: RC의 upstream이 visible=1 구성행을 가리킴",
   """
   SELECT rc.product_test_release_id, rc.upstream_release_id
   FROM product_test_release rc
   JOIN product_test_release parent ON parent.product_test_release_id = rc.upstream_release_id
   WHERE rc.release_visible = 0
     AND parent.release_visible != 1
   """, expect_zero=True)

# ─── 그룹 2. Run → Release 체인 ──────────────────────────
print("\n[그룹 2] Run → Release 체인")

tc("TC-RN01: 고아 Run 없음 (release_id가 실제 release 가리킴)",
   """
   SELECT product_test_run_id FROM product_test_run
   WHERE product_test_release_id NOT IN (
       SELECT product_test_release_id FROM product_test_release
   )
   """, expect_zero=True)

tc("TC-RN02: Run이 RC(visible=0) 또는 TBD에만 연결 (일반 구성행에 직접 연결 없음)",
   """
   SELECT run.product_test_run_id, run.product_test_release_id, rel.release_stage
   FROM product_test_run run
   JOIN product_test_release rel ON rel.product_test_release_id = run.product_test_release_id
   WHERE rel.release_visible = 1
     AND rel.release_stage NOT IN ('RC', 'TEST')
   """, expect_zero=True)

tc("TC-RN03: TBD/미분류 run (visible=1에 직접 연결)",
   """
   SELECT run.product_test_run_id, run.product_test_release_id
   FROM product_test_run run
   JOIN product_test_release rel ON rel.product_test_release_id = run.product_test_release_id
   WHERE rel.release_visible = 1
   """, expect_zero=False, warn_only=False, info_only=True)

# ─── 그룹 3. Result → Run 체인 ───────────────────────────
print("\n[그룹 3] Result → Run 체인")

tc("TC-RS01: 고아 Result 없음 (run_id가 실제 run 가리킴)",
   """
   SELECT product_test_result_id FROM product_test_result
   WHERE product_test_run_id NOT IN (SELECT product_test_run_id FROM product_test_run)
   """, expect_zero=True)

tc("TC-RS02: Result 상태값 유효 (passed/blocked/testing/cancelled만 허용)",
   """
   SELECT DISTINCT product_test_result_status FROM product_test_result
   WHERE product_test_result_status NOT IN ('passed','blocked','testing','cancelled')
   """, expect_zero=True)

tc("TC-RS03: 전체 Result 수",
   "SELECT product_test_result_id FROM product_test_result")

# ─── 그룹 4. Result → Case 체인 ──────────────────────────
print("\n[그룹 4] Result → Case 체인")

tc("TC-CS01: case_id NULL인 Result (미분류)",
   "SELECT product_test_result_id FROM product_test_result WHERE product_test_case_id IS NULL",
   expect_zero=True, warn_only=True)

tc("TC-CS02: Result의 case_id가 실제 case 테이블을 가리킴",
   """
   SELECT res.product_test_result_id, res.product_test_case_id
   FROM product_test_result res
   WHERE res.product_test_case_id IS NOT NULL
     AND res.product_test_case_id NOT IN (
         SELECT product_test_case_id FROM product_test_case
     )
   """, expect_zero=True)

# ─── 그룹 5. Case → Procedure 체인 ──────────────────────
print("\n[그룹 5] Case → Procedure 체인")

tc("TC-PR01: 모든 Case에 Procedure 존재",
   """
   SELECT c.product_test_case_id
   FROM product_test_case c
   WHERE c.product_test_case_id NOT IN (
       SELECT DISTINCT product_test_case_id FROM product_test_procedure
   )
   """, expect_zero=True, warn_only=True)

tc("TC-PR02: Procedure의 case_id가 실제 case 가리킴",
   """
   SELECT p.product_test_procedure_id, p.product_test_case_id
   FROM product_test_procedure p
   WHERE p.product_test_case_id NOT IN (
       SELECT product_test_case_id FROM product_test_case
   )
   """, expect_zero=True)

tc("TC-PR03: Procedure sequence 중복 없음",
   """
   SELECT product_test_case_id, procedure_sequence, COUNT(*) as cnt
   FROM product_test_procedure
   GROUP BY product_test_case_id, procedure_sequence HAVING cnt > 1
   """, expect_zero=True, warn_only=True)

# ─── 그룹 6. Defect → Result 체인 ────────────────────────
print("\n[그룹 6] Defect → Result 체인")

tc("TC-DF01: 고아 Defect 없음 (result_id가 실제 result 가리킴)",
   """
   SELECT def.product_test_defect_id
   FROM product_test_defect def
   WHERE def.product_test_result_id NOT IN (
       SELECT product_test_result_id FROM product_test_result
   )
   """, expect_zero=True)

tc("TC-DF02: Defect 수",
   "SELECT product_test_defect_id FROM product_test_defect")

tc("TC-DF03: opened 결함이 blocked result에 연결됨 (불일치 경고)",
   """
   SELECT def.product_test_defect_id, res.product_test_result_status
   FROM product_test_defect def
   JOIN product_test_result res ON res.product_test_result_id = def.product_test_result_id
   WHERE def.product_test_defect_status = 'opened'
     AND res.product_test_result_status NOT IN ('blocked', 'testing')
   """, expect_zero=True, warn_only=True)

tc("TC-DF04: blocked Result인데 defect 없는 케이스 (미등록 결함 가능성)",
   """
   SELECT res.product_test_result_id, res.product_test_case_id
   FROM product_test_result res
   LEFT JOIN product_test_defect def ON def.product_test_result_id = res.product_test_result_id
   WHERE res.product_test_result_status = 'blocked'
     AND def.product_test_defect_id IS NULL
   """, expect_zero=True, warn_only=True)

# ─── 그룹 7. Defect → Retest 체인 ────────────────────────
print("\n[그룹 7] Defect → Retest(해소) 체인")

tc("TC-RT01: retest_result가 있으면 유효한 result_id 가리킴",
   """
   SELECT def.product_test_defect_id, def.retest_product_test_result_id
   FROM product_test_defect def
   WHERE def.retest_product_test_result_id IS NOT NULL
     AND def.retest_product_test_result_id NOT IN (
         SELECT product_test_result_id FROM product_test_result
     )
   """, expect_zero=True)

tc("TC-RT02: retest 완료된 결함 수 (0건=아직 재시험 없음)",
   """
   SELECT product_test_defect_id FROM product_test_defect
   WHERE retest_product_test_result_id IS NOT NULL
   """, info_only=True)

tc("TC-RT03: closed 결함에 retest 연결됨 (closed인데 retest 없으면 경고)",
   """
   SELECT product_test_defect_id
   FROM product_test_defect
   WHERE product_test_defect_status = 'closed'
     AND retest_product_test_result_id IS NULL
   """, expect_zero=True, warn_only=True)

# ─── 그룹 8. API 집계 무결성 ──────────────────────────────
print("\n[그룹 8] API 집계 무결성")

tc("TC-API01: resolve_parent_release — RC upstream이 모두 visible=1 가리킴",
   """
   SELECT rc.product_test_release_id, parent.product_test_release_id, parent.release_visible
   FROM product_test_release rc
   JOIN product_test_release parent ON parent.product_test_release_id = rc.upstream_release_id
   WHERE rc.release_visible = 0 AND parent.release_visible != 1
   """, expect_zero=True)

tc("TC-API02: Run 집계 — release당 result 수 일치",
   """
   SELECT run.product_test_release_id,
          COUNT(res.product_test_result_id) as result_cnt
   FROM product_test_run run
   LEFT JOIN product_test_result res ON res.product_test_run_id = run.product_test_run_id
   GROUP BY run.product_test_release_id
   HAVING result_cnt = 0
   """, expect_zero=True, warn_only=True)

tc("TC-API03: data-parent-release-id 역추적 — 모든 Run의 RC가 upstream 보유",
   """
   SELECT run.product_test_run_id, run.product_test_release_id
   FROM product_test_run run
   JOIN product_test_release rc ON rc.product_test_release_id = run.product_test_release_id
   WHERE rc.release_visible = 0 AND rc.upstream_release_id IS NULL
   """, expect_zero=True)

# ─── 결과 집계 ──────────────────────────────────────────
print(f"\n{'='*65}")
total  = len([r for r in results if r[0] != 'INFO'])
passed = sum(1 for r in results if r[0] == 'PASS')
failed = sum(1 for r in results if r[0] == 'FAIL')
warned = sum(1 for r in results if r[0] == 'WARN')
print(f"  결과: {total}건 | PASS {passed} | FAIL {failed} | WARN {warned}")
print(f"{'='*65}")
if failed > 0:
    print("\n실패:")
    for r in results:
        if r[0] == 'FAIL':
            print(f"  [{RED}FAIL{RESET}] {r[1]} ({r[2]}건)")
if warned > 0:
    print("\n경고:")
    for r in results:
        if r[0] == 'WARN' and r[2] > 0:
            print(f"  [{YELLOW}WARN{RESET}] {r[1]} ({r[2]}건)")


# ─── 그룹 9. Target 체인 ──────────────────────────────────
print("\n[그룹 9] Target 체인")

tc("TC-TG01: Target 존재",
   "SELECT product_test_target_id FROM product_test_target LIMIT 1")

tc("TC-TG02: Target_Definition 존재",
   "SELECT product_test_target_definition_id FROM product_test_target_definition LIMIT 1")

tc("TC-TG03: Target의 definition_id가 실제 target_definition 가리킴",
   """
   SELECT t.product_test_target_id, t.product_test_target_definition_id
   FROM product_test_target t
   WHERE t.product_test_target_definition_id IS NOT NULL
     AND t.product_test_target_definition_id NOT IN (
         SELECT product_test_target_definition_id FROM product_test_target_definition
     )
   """, expect_zero=True)

tc("TC-TG04: Run의 target_id가 실제 target 가리킴",
   """
   SELECT run.product_test_run_id, run.product_test_target_id
   FROM product_test_run run
   WHERE run.product_test_target_id IS NOT NULL
     AND run.product_test_target_id NOT IN (
         SELECT product_test_target_id FROM product_test_target
     )
   """, expect_zero=True)

tc("TC-TG05: target_id 없는 Run (미연결)",
   """
   SELECT product_test_run_id FROM product_test_run
   WHERE product_test_target_id IS NULL
   """, expect_zero=True, warn_only=True)

# ─── 그룹 10. Environment 체인 ────────────────────────────
print("\n[그룹 10] Environment 체인")

tc("TC-EN01: Environment 존재",
   "SELECT product_test_environment_id FROM product_test_environment LIMIT 1")

tc("TC-EN02: Environment_Definition 존재",
   "SELECT product_test_environment_definition_id FROM product_test_environment_definition LIMIT 1")

tc("TC-EN03: Environment의 definition_id가 실제 env_definition 가리킴",
   """
   SELECT e.product_test_environment_id, e.product_test_environment_definition_id
   FROM product_test_environment e
   WHERE e.product_test_environment_definition_id IS NOT NULL
     AND e.product_test_environment_definition_id NOT IN (
         SELECT product_test_environment_definition_id FROM product_test_environment_definition
     )
   """, expect_zero=True)

tc("TC-EN04: Run의 environment_id가 실제 environment 가리킴",
   """
   SELECT run.product_test_run_id, run.product_test_environment_id
   FROM product_test_run run
   WHERE run.product_test_environment_id IS NOT NULL
     AND run.product_test_environment_id NOT IN (
         SELECT product_test_environment_id FROM product_test_environment
     )
   """, expect_zero=True)

tc("TC-EN05: environment_id 없는 Run (미연결)",
   """
   SELECT product_test_run_id FROM product_test_run
   WHERE product_test_environment_id IS NULL
   """, expect_zero=True, warn_only=True)

# ─── 그룹 11. Report 체인 ─────────────────────────────────
print("\n[그룹 11] Report 체인")

tc("TC-RP01: Report 존재",
   "SELECT product_test_report_id FROM product_test_report LIMIT 1")

tc("TC-RP02: Report의 release_id가 실제 release 가리킴",
   """
   SELECT r.product_test_report_id, r.product_test_release_id
   FROM product_test_report r
   WHERE r.product_test_release_id NOT IN (
       SELECT product_test_release_id FROM product_test_release
   )
   """, expect_zero=True)

tc("TC-RP03: Report가 RC(visible=0) 또는 TBD에 연결됨 (구성행 직접 연결 없어야 함)",
   """
   SELECT r.product_test_report_id, r.product_test_release_id, rel.release_visible
   FROM product_test_report r
   JOIN product_test_release rel ON rel.product_test_release_id = r.product_test_release_id
   WHERE rel.release_visible = 1 AND rel.release_stage NOT IN ('RC','TEST')
   """, expect_zero=True, warn_only=True)

tc("TC-RP04: Report 상태값 유효 (DRAFT/APPROVED/REJECTED)",
   """
   SELECT DISTINCT product_test_report_status FROM product_test_report
   WHERE product_test_report_status NOT IN ('DRAFT','APPROVED','REJECTED','IN_REVIEW')
   """, expect_zero=True, warn_only=True)

tc("TC-RP05: Report_Snapshot 스키마 체크 (테이블 존재)",
   "SELECT COUNT(*) FROM product_test_report_snapshot", info_only=True)

# ─── 그룹 12. Procedure_Result 체인 (0건, 스키마만) ──────
print("\n[그룹 12] Procedure_Result 체인 (운영 전 스키마 검증)")

tc("TC-PC01: procedure_result 데이터 수",
   "SELECT product_test_procedure_result_id FROM product_test_procedure_result",
   info_only=True)

tc("TC-PC02: procedure_result의 result_id가 실제 result 가리킴",
   """
   SELECT pr.product_test_procedure_result_id
   FROM product_test_procedure_result pr
   WHERE pr.product_test_result_id NOT IN (
       SELECT product_test_result_id FROM product_test_result
   )
   """, expect_zero=True)

tc("TC-PC03: procedure_result의 procedure_id가 실제 procedure 가리킴",
   """
   SELECT pr.product_test_procedure_result_id
   FROM product_test_procedure_result pr
   WHERE pr.product_test_procedure_id NOT IN (
       SELECT product_test_procedure_id FROM product_test_procedure
   )
   """, expect_zero=True)

tc("TC-PC04: Defect의 procedure_result_id가 실제 procedure_result 가리킴",
   """
   SELECT def.product_test_defect_id, def.product_test_procedure_result_id
   FROM product_test_defect def
   WHERE def.product_test_procedure_result_id IS NOT NULL
     AND def.product_test_procedure_result_id NOT IN (
         SELECT product_test_procedure_result_id FROM product_test_procedure_result
     )
   """, expect_zero=True)

# ─── 그룹 13. Evidence 체인 (0건, 스키마만) ──────────────
print("\n[그룹 13] Evidence 체인 (운영 전 스키마 검증)")

tc("TC-EV01: evidence 데이터 수",
   "SELECT product_test_evidence_id FROM product_test_evidence",
   info_only=True)

tc("TC-EV02: evidence의 result_id가 실제 result 가리킴",
   """
   SELECT ev.product_test_evidence_id
   FROM product_test_evidence ev
   WHERE ev.product_test_result_id IS NOT NULL
     AND ev.product_test_result_id NOT IN (
         SELECT product_test_result_id FROM product_test_result
     )
   """, expect_zero=True)

tc("TC-EV03: evidence의 defect_id가 실제 defect 가리킴",
   """
   SELECT ev.product_test_evidence_id
   FROM product_test_evidence ev
   WHERE ev.product_test_defect_id IS NOT NULL
     AND ev.product_test_defect_id NOT IN (
         SELECT product_test_defect_id FROM product_test_defect
     )
   """, expect_zero=True)

tc("TC-EV04: evidence의 procedure_result_id가 실제 procedure_result 가리킴",
   """
   SELECT ev.product_test_evidence_id
   FROM product_test_evidence ev
   WHERE ev.product_test_procedure_result_id IS NOT NULL
     AND ev.product_test_procedure_result_id NOT IN (
         SELECT product_test_procedure_result_id FROM product_test_procedure_result
     )
   """, expect_zero=True)

# ─── 그룹 14. Status_Transition 체인 (0건, 스키마만) ─────
print("\n[그룹 14] Status_Transition (운영 전 스키마 검증)")

tc("TC-ST01: status_transition 데이터 수",
   "SELECT COUNT(*) FROM product_test_status_transition",
   info_only=True)

conn.close()
sys.exit(0 if failed == 0 else 1)
