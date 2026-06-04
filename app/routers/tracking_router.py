"""
트래킹 대시보드 API 라우터.
- GET   /admin/api/tracking/summary          : 진행 중 + 전체 타임라인 요약
- PATCH /admin/api/release/{id}/status       : 배포 상태 변경
- GET   /admin/api/work-calendar             : 근무일 목록
- POST  /admin/api/work-calendar             : 근무일 등록/수정
- DELETE /admin/api/work-calendar/{date}     : 삭제
- POST  /admin/api/client-log               : 프런트엔드 로그 파일 기록
"""
from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from app.services.logging_service import get_logger

_client_log = get_logger("client")
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

EVIDENCE_UPLOAD_DIR = Path(__file__).resolve().parent.parent / "static" / "uploads" / "evidence"
EVIDENCE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

from app.auth import ROLE_ADMIN, ROLE_MASTER_ADMIN, ROLE_TESTER
from app.deps import current_role_name_dependency, database_session_dependency
from app.models import WorkCalendar, ProductTestRelease, get_utc_now_datetime

tracking_router = APIRouter()


def _clean_device_round_alias(display_alias: str) -> str:
    return re.sub(r"\s*\(\d+(?:\.\d+)*[A-Za-z]?\)\s*$", "", display_alias or "").strip()


def _parse_release_work_period(remark: str) -> dict[str, str]:
    workday = ""
    start_date = ""
    end_date = ""
    for line in (remark or "").split("\n"):
        line = line.strip()
        if line.startswith("[Workday]"):
            workday = line.replace("[Workday]", "").strip()
        elif line.startswith("[Start]"):
            rest = line.replace("[Start]", "").strip()
            if "[End]" in rest:
                parts = rest.split("[End]", 1)
                sd = parts[0].strip()
                ed = parts[1].strip()
                start_date = "" if sd in ("", "None") else sd
                end_date = "" if ed in ("", "None") else ed
            else:
                start_date = "" if rest in ("", "None") else rest
        elif line.startswith("[End]"):
            val = line.replace("[End]", "").strip()
            end_date = "" if val in ("", "None") else val
    return {"workday": workday, "start_date": start_date, "end_date": end_date}


def _format_release_work_period(period: dict[str, str]) -> str:
    parts = []
    if period.get("workday"):
        parts.append(f"Workday: {period['workday']}")
    if period.get("start_date"):
        parts.append(f"Start: {period['start_date']}")
    if period.get("end_date"):
        parts.append(f"End: {period['end_date']}")
    return " / ".join(parts)


def _ensure_admin_role(role: str) -> None:
    if role not in (ROLE_ADMIN, ROLE_MASTER_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required.")


# ── 트래킹 요약 ───────────────────────────────────────────────────────────────

@tracking_router.get("/admin/api/tracking/summary")
def get_tracking_summary(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    if current_role_name not in (ROLE_TESTER, ROLE_ADMIN, ROLE_MASTER_ADMIN):
        raise HTTPException(status_code=403, detail="Access denied.")

    conn = database_session.connection()

    # ── 전체 릴리즈 타임라인 ──────────────────────────────────────────────────
    releases_raw = conn.execute(text("""
        SELECT
            r.product_test_release_id,
            r.upstream_release_id,
            r.release_stage,
            r.release_sequence,
            r.product_test_release_status,
            r.remark,
            r.upstream_release_system,
            COALESCE(r.release_visible, 1)                    AS release_visible,
            COUNT(DISTINCT run.product_test_run_id)           AS run_count,
            COUNT(res.product_test_result_id)                 AS total_results,
            SUM(CASE WHEN res.product_test_result_status = 'passed'  THEN 1 ELSE 0 END) AS passed,
            SUM(CASE WHEN res.product_test_result_status = 'blocked' THEN 1 ELSE 0 END) AS blocked,
            SUM(CASE WHEN res.product_test_result_status = 'testing' THEN 1 ELSE 0 END) AS testing,
            COUNT(DISTINCT def.product_test_defect_id)        AS defect_count,
            SUM(CASE WHEN def.product_test_defect_status = 'opened' THEN 1 ELSE 0 END)  AS open_defects
        FROM product_test_release r
        LEFT JOIN product_test_run  run ON run.product_test_release_id = r.product_test_release_id
        LEFT JOIN product_test_result res ON res.product_test_run_id   = run.product_test_run_id
        LEFT JOIN product_test_defect def ON def.product_test_result_id = res.product_test_result_id
        WHERE (r.release_stage IS NULL OR r.release_stage != 'round_legacy')
        GROUP BY r.product_test_release_id
        ORDER BY r.release_sequence, r.product_test_release_id
    """)).fetchall()

    releases = []
    for row in releases_raw:
        alias = ""
        work_period = _parse_release_work_period(row[5] or "")
        for line in (row[5] or "").split("\n"):
            line = line.strip()
            if line.startswith("[Report Alias]"):
                alias = line.replace("[Report Alias]", "").strip()
            elif line.startswith("[Workday]"):
                workday = line.replace("[Workday]", "").strip()
            elif line.startswith("[Start]"):
                rest = line.replace("[Start]", "").strip()
                if "[End]" in rest:
                    parts = rest.split("[End]", 1)
                    sd = parts[0].strip()
                    ed = parts[1].strip()
                    start_date = "" if sd in ("", "None") else sd
                    end_date   = "" if ed in ("", "None") else ed
                else:
                    start_date = "" if rest in ("", "None") else rest
            elif line.startswith("[End]"):
                val = line.replace("[End]", "").strip()
                end_date = "" if val in ("", "None") else val

        # device_round / run_session 은 remark 를 표시명으로 사용
        stage = row[2] or ""
        if stage in ("device_round", "run_session"):
            display_alias = (row[5] or "").split("\n")[0].strip() or row[0].replace("TEST_RELEASE-", "")
            if stage == "device_round":
                display_alias = _clean_device_round_alias(display_alias)
        else:
            display_alias = alias or row[0].replace("TEST_RELEASE-", "")

        releases.append({
            "id": row[0],
            "upstream_id": row[1],
            "alias": display_alias,
            "stage": row[2],
            "sequence": row[3],
            "status": row[4],
            # row[5] = remark (already parsed)
            "upstream_system": row[6] or "",
            "visible": bool(row[7]),
            "workday": work_period["workday"],
            "start_date": work_period["start_date"],
            "end_date": work_period["end_date"],
            "run_count": row[8] or 0,
            "total_results": row[9] or 0,
            "passed": row[10] or 0,
            "blocked": row[11] or 0,
            "testing": row[12] or 0,
            "defect_count": row[13] or 0,
            "open_defects": row[14] or 0,
        })

    # ── 부모 상태 자동 결정 (자식 상태 기반) ─────────────────────────────────
    # 우선순위: BLOCKED > TESTING > DRAFT > PASSED/QI_TEAM_RELEASED/APPROVED > QI_TEAM_REVIEWED > DONE
    STATUS_PRIORITY = {
        "BLOCKED": 0, "TESTING": 1, "DRAFT": 2,
        "PASSED": 3, "QI_TEAM_RELEASED": 3, "APPROVED": 3,
        "QI_TEAM_REVIEWED": 4, "DONE": 5,
    }

    children_by_parent: dict = {}
    for r in releases:
        pid = r["upstream_id"]
        if pid:
            children_by_parent.setdefault(pid, []).append(r)

    release_map = {r["id"]: r for r in releases}

    for parent_id, children in children_by_parent.items():
        parent = release_map.get(parent_id)
        if not parent:
            continue
        # 숨긴 자식(visible=False)만 대상 — 장비별 하위 항목
        # 보고서 컨테이너(TEST_REPORT_*, TBD_REPORT_*)는 제외
        child_statuses = [
            c["status"] for c in children
            if not c["visible"]
            and "TEST_REPORT_" not in c["id"]
            and "TBD_REPORT_" not in c["id"]
        ]
        if not child_statuses:
            continue
        best = min(child_statuses, key=lambda s: STATUS_PRIORITY.get(s, 99))
        parent["status"] = best

    # ── 진행 중 릴리즈 활성 결함 상세 ────────────────────────────────────────
    active_defects_raw = conn.execute(text("""
        SELECT
            def.product_test_defect_id,
            def.defect_title,
            def.defect_severity,
            def.defect_priority,
            def.product_test_defect_status,
            def.assigned_to,
            def.expected_resolution_date,
            def.created_at,
            run.product_test_release_id,
            run.product_test_run_id,
            def.remark
        FROM product_test_defect def
        JOIN product_test_result  res ON res.product_test_result_id  = def.product_test_result_id
        JOIN product_test_run     run ON run.product_test_run_id     = res.product_test_run_id
        WHERE def.product_test_defect_status = 'opened'
        ORDER BY
            CASE def.defect_severity
                WHEN 'S' THEN 1 WHEN 'A' THEN 2 WHEN 'B' THEN 3 WHEN 'C' THEN 4 ELSE 5
            END,
            def.created_at
    """)).fetchall()

    # release_id → 상위 ID 맵 + visible 맵
    # 구조: RC(visible=0) → 장비행(visible=1) → 라운드(parent)
    release_upstream = {r["id"]: r["upstream_id"] for r in releases}
    release_visible = {r["id"]: r["visible"] for r in releases}
    release_by_id = {r["id"]: r for r in releases}

    def resolve_release_work_period(release_id: str) -> dict[str, str]:
        cur = release_id
        for _ in range(8):
            row = release_by_id.get(cur)
            if row:
                period = {
                    "workday": row.get("workday") or "",
                    "start_date": row.get("start_date") or "",
                    "end_date": row.get("end_date") or "",
                }
                if period["workday"] or period["start_date"] or period["end_date"]:
                    return period
            parent = release_upstream.get(cur, "")
            if not parent or parent not in release_by_id:
                break
            cur = parent
        return {"workday": "", "start_date": "", "end_date": ""}

    def resolve_parent_release(release_id: str) -> str:
        """run.release_id → 간트 장비 행 ID (visible=1인 자식 행)"""
        cur = release_id
        # 최대 5단계까지 올라가며 visible=1인 자식 행 찾기
        for _ in range(5):
            if cur and release_visible.get(cur, False):
                # 현재가 visible이고, 부모도 있으면 → 이것이 장비행
                parent = release_upstream.get(cur, "")
                if parent and release_visible.get(parent, False):
                    # 부모도 visible → cur는 장비행(자식)
                    return cur
                # 부모가 없거나 invisible → cur 자체가 최상위
                return cur
            # 현재가 invisible이면 위로 올라감
            cur = release_upstream.get(cur, "")
            if not cur:
                break
        return release_id  # fallback

    def resolve_round_release(release_id: str) -> dict | None:
        cur = release_id
        last_visible = None
        for _ in range(8):
            row = release_by_id.get(cur)
            if row and row.get("visible"):
                last_visible = row
            parent = release_upstream.get(cur, "")
            if not parent or parent not in release_by_id:
                break
            cur = parent
        return last_visible

    def model_sw_from_round_alias(alias: str) -> tuple[str, str]:
        match = re.match(r"^(.+?)\s+(\d+(?:\.\d+)*[A-Za-z]?)\s+", alias or "")
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return alias or "", ""

    def logical_target_from_release(release_id: str, fallback_target_id: str = "") -> dict:
        round_row = resolve_round_release(release_id)
        if round_row and round_row.get("stage") == "device_round":
            model_name, sw_version = model_sw_from_round_alias(round_row.get("alias") or "")
            target_key = round_row["id"].replace("TEST_RELEASE-", "")
            return {
                "id": f"TEST_TARGET_{target_key}",
                "model_name": model_name,
                "sw_version": sw_version,
                "round_id": round_row["id"],
            }
        return {
            "id": fallback_target_id,
            "model_name": "",
            "sw_version": "",
            "round_id": "",
        }

    def parse_images(remark: str) -> dict:
        imgs = {"other_device": [], "hdr_screen": [], "general": []}
        for line in (remark or "").split("\n"):
            line = line.strip()
            if line.startswith("[Image:other_device]"):
                imgs["other_device"].append(line.replace("[Image:other_device]", "").strip())
            elif line.startswith("[Image:hdr_screen]"):
                imgs["hdr_screen"].append(line.replace("[Image:hdr_screen]", "").strip())
            elif line.startswith("[Image]"):
                imgs["general"].append(line.replace("[Image]", "").strip())
        return imgs

    active_defects = [
        {
            "id": r[0],
            "title": r[1],
            "severity": r[2],
            "priority": r[3],
            "status": r[4],
            "assigned_to": r[5] or "-",
            "expected_resolution_date": r[6] or "",
            "created_at": r[7],
            "release_id": r[8],
            "parent_release_id": resolve_parent_release(r[8] or ""),
            "run_id": r[9],
            "images": parse_images(r[10]),
        }
        for r in active_defects_raw
    ]

    # ── 구성별 Run 목록 ──────────────────────────────────────────────────────
    runs_raw = conn.execute(text("""
        SELECT
            run.product_test_run_id,
            run.product_test_release_id,
            run.product_test_run_status,
            run.started_at,
            run.finished_at,
            COUNT(res.product_test_result_id)                                    AS total_results,
            SUM(CASE WHEN res.product_test_result_status = 'passed'  THEN 1 ELSE 0 END) AS passed,
            SUM(CASE WHEN res.product_test_result_status = 'blocked' THEN 1 ELSE 0 END) AS blocked,
            SUM(CASE WHEN res.product_test_result_status = 'testing' THEN 1 ELSE 0 END) AS testing,
            SUM(CASE WHEN res.product_test_result_status = 'failed'  THEN 1 ELSE 0 END) AS failed,
            SUM(CASE WHEN res.product_test_result_status = 'skipped' THEN 1 ELSE 0 END) AS skipped,
            SUM(CASE WHEN res.product_test_result_status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
            run.product_test_target_id,
            run.product_test_environment_id,
            run.remark
        FROM product_test_run run
        LEFT JOIN product_test_result res ON res.product_test_run_id = run.product_test_run_id
        GROUP BY run.product_test_run_id
        HAVING total_results > 0
        ORDER BY run.started_at
    """)).fetchall()

    def _run_display_remark(raw_remark: str, work_period: dict[str, str]) -> str:
        period_label = _format_release_work_period(work_period)
        if not period_label:
            return raw_remark or ""
        if raw_remark and period_label in raw_remark:
            return raw_remark
        return f"{raw_remark}\n[Release Work Period] {period_label}".strip()

    runs = [
        {
            "id": r[0],
            "release_id": r[1],
            "parent_release_id": resolve_parent_release(r[1] or ""),
            "status": (
                "FAILED" if (r[9] or 0) > 0 else
                "BLOCKED" if (r[7] or 0) > 0 else
                "TESTING" if (r[8] or 0) > 0 else
                "PASSED" if (r[5] or 0) > 0 and (r[6] or 0) == (r[5] or 0) else
                "SKIPPED" if (r[5] or 0) > 0 and (r[10] or 0) == (r[5] or 0) else
                "CANCELLED" if (r[5] or 0) > 0 and (r[11] or 0) == (r[5] or 0) else
                "TESTING"
            ),
            "run_status": r[2],
            "started_at": r[3],
            "finished_at": r[4],
            "planned_workday": resolve_release_work_period(r[1] or "")["workday"],
            "planned_start_date": resolve_release_work_period(r[1] or "")["start_date"],
            "planned_end_date": resolve_release_work_period(r[1] or "")["end_date"],
            "total_results": r[5] or 0,
            "passed": r[6] or 0,
            "blocked": r[7] or 0,
            "testing": r[8] or 0,
            "failed": r[9] or 0,
            "skipped": r[10] or 0,
            "cancelled": r[11] or 0,
            "target_id": logical_target_from_release(r[1] or "", r[12] or "")["id"],
            "target_model_name": logical_target_from_release(r[1] or "", r[12] or "")["model_name"],
            "target_sw_version": logical_target_from_release(r[1] or "", r[12] or "")["sw_version"],
            "physical_target_id": r[12] or "",
            "target_round_id": logical_target_from_release(r[1] or "", r[12] or "")["round_id"],
            "environment_id": r[13] or "",
            "remark": _run_display_remark(r[14] or "", resolve_release_work_period(r[1] or "")),
        }
        for r in runs_raw
    ]

    # ── 구성별 Result 요약 (case 단위 집계) ──────────────────────────────────
    results_summary_raw = conn.execute(text("""
        SELECT
            run.product_test_release_id,
            res.product_test_case_id,
            res.product_test_result_status,
            COUNT(*)                          AS cnt,
            res.product_test_run_id,
            res.product_test_result_id,
            def.product_test_defect_id
        FROM product_test_result res
        JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
        LEFT JOIN product_test_defect def ON def.product_test_result_id = res.product_test_result_id
            AND def.product_test_defect_status = 'opened'
        GROUP BY run.product_test_release_id, res.product_test_case_id,
                 res.product_test_result_status, res.product_test_run_id,
                 res.product_test_result_id, def.product_test_defect_id
        ORDER BY run.product_test_release_id, res.product_test_case_id
    """)).fetchall()

    # case 단위로 집계
    case_map: dict[tuple, dict] = {}
    for r in results_summary_raw:
        rc_release_id = r[0]
        case_id = r[1]
        result_status = r[2]
        run_id = r[4]
        result_id = r[5]
        defect_id = r[6]
        parent = resolve_parent_release(rc_release_id or "")
        key = (parent, case_id)
        if key not in case_map:
            case_map[key] = {
                "parent_release_id": parent,
                "case_id": case_id,
                "passed": 0,
                "blocked": 0,
                "testing": 0,
                "total": 0,
                "run_ids": set(),
                "result_ids": [],
                "defect_ids": [],
            }
        entry = case_map[key]
        entry["total"] += 1
        if result_status == "passed":
            entry["passed"] += 1
        elif result_status == "blocked":
            entry["blocked"] += 1
        elif result_status == "testing":
            entry["testing"] += 1
        entry["run_ids"].add(run_id)
        entry["result_ids"].append(result_id)
        if defect_id:
            entry["defect_ids"].append(defect_id)

    results_summary = [
        {
            "parent_release_id": v["parent_release_id"],
            "case_id": v["case_id"],
            "passed": v["passed"],
            "blocked": v["blocked"],
            "testing": v["testing"],
            "total": v["total"],
            "run_ids": sorted(v["run_ids"]),
            "result_ids": v["result_ids"],
            "defect_ids": v["defect_ids"],
        }
        for v in case_map.values()
    ]

    # ── Procedure Results ────────────────────────────────────────────────────
    procedure_results_raw = conn.execute(text("""
        SELECT
            pr.product_test_procedure_result_id,
            pr.product_test_result_id,
            pr.product_test_procedure_id,
            pr.product_test_procedure_result_status,
            pr.actual_result,
            pr.judgement_reason,
            pr.judged_at,
            pr.judged_by,
            p.product_test_case_id,
            p.procedure_sequence,
            p.procedure_action,
            run.product_test_release_id
        FROM product_test_procedure_result pr
        JOIN product_test_procedure p ON p.product_test_procedure_id = pr.product_test_procedure_id
        JOIN product_test_result res ON res.product_test_result_id = pr.product_test_result_id
        JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
        ORDER BY p.product_test_case_id, p.procedure_sequence
    """)).fetchall()

    procedure_results = [
        {
            "id": r[0],
            "result_id": r[1],
            "procedure_id": r[2],
            "status": r[3],
            "actual_result": r[4] or "",
            "judgement_reason": r[5] or "",
            "judged_at": r[6] or "",
            "judged_by": r[7] or "",
            "case_id": r[8],
            "sequence": r[9],
            "action": (r[10] or "")[:120],
            "parent_release_id": resolve_parent_release(r[11] or ""),
        }
        for r in procedure_results_raw
    ]

    # ── Evidence ──────────────────────────────────────────────────────────────
    evidence_raw = conn.execute(text("""
        SELECT
            ev.product_test_evidence_id,
            ev.product_test_result_id,
            ev.product_test_procedure_result_id,
            ev.product_test_defect_id,
            ev.product_test_evidence_type,
            ev.file_name,
            ev.file_path,
            ev.captured_at,
            ev.captured_by,
            COALESCE(run.product_test_release_id, run2.product_test_release_id) AS release_id
        FROM product_test_evidence ev
        LEFT JOIN product_test_result res ON res.product_test_result_id = ev.product_test_result_id
        LEFT JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
        LEFT JOIN product_test_defect def ON def.product_test_defect_id = ev.product_test_defect_id
        LEFT JOIN product_test_result res2 ON res2.product_test_result_id = def.product_test_result_id
        LEFT JOIN product_test_run run2 ON run2.product_test_run_id = res2.product_test_run_id
        ORDER BY ev.captured_at
    """)).fetchall()

    evidence = [
        {
            "id": r[0],
            "result_id": r[1] or "",
            "procedure_result_id": r[2] or "",
            "defect_id": r[3] or "",
            "type": r[4] or "",
            "file_name": r[5] or "",
            "file_path": r[6] or "",
            "captured_at": r[7] or "",
            "captured_by": r[8] or "",
            "parent_release_id": resolve_parent_release(r[9] or "") if r[9] else "",
        }
        for r in evidence_raw
    ]

    # ── Reports ────────────────────────────────────────────────────────────────
    reports_raw = conn.execute(text("""
        SELECT product_test_report_id, product_test_release_id,
               product_test_report_type, product_test_report_status,
               product_test_report_title, created_at
        FROM product_test_report
        ORDER BY created_at
    """)).fetchall()

    reports = [
        {
            "id": r[0],
            "release_id": r[1],
            "parent_release_id": resolve_parent_release(r[1] or ""),
            "type": r[2] or "",
            "status": r[3] or "",
            "title": r[4] or "",
            "created_at": r[5] or "",
        }
        for r in reports_raw
    ]

    test_target_definitions = [
        {
            "id": r[0] or "",
            "product_code": r[1] or "",
            "manufacturer": r[2] or "",
            "model_name": r[3] or "",
            "hardware_revision": r[4] or "",
            "default_software_version": r[5] or "",
            "default_firmware_version": r[6] or "",
            "status": r[7] or "",
            "remark": r[8] or "",
        }
        for r in conn.execute(text("""
            SELECT product_test_target_definition_id, product_code, manufacturer,
                   model_name, hardware_revision, default_software_version,
                   default_firmware_version, product_test_target_definition_status, remark
            FROM product_test_target_definition
            ORDER BY product_test_target_definition_id
        """)).fetchall()
    ]

    test_targets = [
        {
            "id": r[0] or "",
            "definition_id": r[1] or "",
            "model_name": r[2] or "",
            "serial_number": r[3] or "",
            "software_version": r[4] or "",
            "firmware_version": r[5] or "",
            "manufacture_lot": r[6] or "",
            "status": r[7] or "",
            "remark": r[8] or "",
        }
        for r in conn.execute(text("""
            SELECT t.product_test_target_id, t.product_test_target_definition_id,
                   d.model_name, t.serial_number, t.software_version, t.firmware_version,
                   t.manufacture_lot, t.product_test_target_status, t.remark
            FROM product_test_target t
            LEFT JOIN product_test_target_definition d
                ON d.product_test_target_definition_id = t.product_test_target_definition_id
            ORDER BY t.product_test_target_id
        """)).fetchall()
    ]

    test_environment_definitions = [
        {
            "id": r[0] or "",
            "name": r[1] or "",
            "country": r[2] or "",
            "city": r[3] or "",
            "company": r[4] or "",
            "room": r[5] or "",
            "network_type": r[6] or "",
            "computer_name": r[7] or "",
            "os_version": r[8] or "",
            "tool_name": r[9] or "",
            "tool_version": r[10] or "",
            "power_voltage": r[11] or "",
            "power_frequency": r[12] or "",
            "status": r[13] or "",
            "remark": r[14] or "",
        }
        for r in conn.execute(text("""
            SELECT product_test_environment_definition_id,
                   product_test_environment_definition_name, test_country, test_city,
                   test_company, test_room, network_type, test_computer_name,
                   operating_system_version, test_tool_name, test_tool_version,
                   power_voltage, power_frequency,
                   product_test_environment_definition_status, remark
            FROM product_test_environment_definition
            ORDER BY product_test_environment_definition_id
        """)).fetchall()
    ]

    test_environments = [
        {
            "id": r[0] or "",
            "definition_id": r[1] or "",
            "name": r[2] or "",
            "computer_name": r[3] or "",
            "os_version": r[4] or "",
            "tool_version": r[5] or "",
            "network_type": r[6] or "",
            "power_voltage": r[7] or "",
            "power_frequency": r[8] or "",
            "captured_at": r[9] or "",
            "status": r[10] or "",
            "remark": r[11] or "",
        }
        for r in conn.execute(text("""
            SELECT product_test_environment_id, product_test_environment_definition_id,
                   product_test_environment_name, test_computer_name,
                   operating_system_version, test_tool_version, network_type,
                   power_voltage, power_frequency, captured_at,
                   product_test_environment_status, remark
            FROM product_test_environment
            ORDER BY product_test_environment_id
        """)).fetchall()
    ]

    test_cases = [
        {
            "id": r[0] or "",
            "title": r[1] or "",
            "category": r[2] or "",
            "objective": r[3] or "",
            "precondition": r[4] or "",
            "expected_result": r[5] or "",
            "status": r[6] or "",
            "remark": r[7] or "",
        }
        for r in conn.execute(text("""
            SELECT product_test_case_id, product_test_case_title, test_category,
                   test_objective, precondition, expected_result,
                   product_test_case_status, remark
            FROM product_test_case
            ORDER BY product_test_case_id
        """)).fetchall()
    ]

    test_procedures = [
        {
            "id": r[0] or "",
            "case_id": r[1] or "",
            "sequence": r[2] or 0,
            "action": r[3] or "",
            "expected_result": r[4] or "",
            "acceptance_criteria": r[5] or "",
            "required_evidence_type": r[6] or "",
            "status": r[7] or "",
            "remark": r[8] or "",
        }
        for r in conn.execute(text("""
            SELECT product_test_procedure_id, product_test_case_id,
                   procedure_sequence, procedure_action, expected_result,
                   acceptance_criteria, required_evidence_type,
                   product_test_procedure_status, remark
            FROM product_test_procedure
            ORDER BY product_test_case_id, procedure_sequence, product_test_procedure_id
        """)).fetchall()
    ]

    # ── Targets (model/SW logical targets via runs) ──────────────────────
    seen_tgt = set()
    targets = []
    for run in runs:
        tid = run.get("target_id") or ""
        if not tid or tid in seen_tgt:
            continue
        seen_tgt.add(tid)
        targets.append({
            "id": tid,
            "model_name": run.get("target_model_name") or "",
            "sw_version": run.get("target_sw_version") or "",
            "serial_number": "",
            "physical_target_id": run.get("physical_target_id") or "",
            "round_id": run.get("target_round_id") or "",
            "remark": "logical target by model/software version",
        })
    targets.sort(key=lambda t: (t["model_name"], t["sw_version"], t["id"]))

    # ── Environments (via runs, 중복 제거 + 상세 정보 포함) ──────────────────
    seen_env = set()
    environments = []
    for r in conn.execute(text("""
        SELECT DISTINCT
            run.product_test_environment_id,
            e.product_test_environment_name
        FROM product_test_run run
        JOIN product_test_result res ON res.product_test_run_id = run.product_test_run_id
        LEFT JOIN product_test_environment e
            ON e.product_test_environment_id = run.product_test_environment_id
        ORDER BY run.product_test_environment_id
    """)).fetchall():
        env_id = r[0]
        if env_id and env_id not in seen_env:
            seen_env.add(env_id)
            environments.append({
                "id": env_id,
                "name": r[1] or "",
            })

    # ── Cases + Procedures (via results) ──────────────────────────────────────
    cases_raw = conn.execute(text("""
        SELECT DISTINCT
            res.product_test_case_id,
            c.product_test_case_title,
            run.product_test_release_id
        FROM product_test_result res
        JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
        LEFT JOIN product_test_case c ON c.product_test_case_id = res.product_test_case_id
        ORDER BY res.product_test_case_id
    """)).fetchall()

    cases = [
        {
            "id": r[0],
            "title": (r[1] or "")[:120],
            "parent_release_id": resolve_parent_release(r[2] or ""),
        }
        for r in cases_raw
    ]

    procedures_raw = conn.execute(text("""
        SELECT DISTINCT
            p.product_test_procedure_id,
            p.product_test_case_id,
            p.procedure_sequence,
            p.procedure_action,
            run.product_test_release_id
        FROM product_test_procedure p
        JOIN product_test_result res ON res.product_test_case_id = p.product_test_case_id
        JOIN product_test_run run ON run.product_test_run_id = res.product_test_run_id
        ORDER BY p.product_test_case_id, p.procedure_sequence
    """)).fetchall()

    procedures = [
        {
            "id": r[0],
            "case_id": r[1],
            "sequence": r[2],
            "action": (r[3] or "")[:120],
            "parent_release_id": resolve_parent_release(r[4] or ""),
        }
        for r in procedures_raw
    ]

    return JSONResponse({
        "releases": releases,
        "active_defects": active_defects,
        "runs": runs,
        "results_summary": results_summary,
        "procedure_results": procedure_results,
        "evidence": evidence,
        "reports": reports,
        "test_releases": releases,
        "test_target_definitions": test_target_definitions,
        "test_targets": test_targets,
        "test_environment_definitions": test_environment_definitions,
        "test_environments": test_environments,
        "test_cases": test_cases,
        "test_procedures": test_procedures,
        "targets": targets,
        "environments": environments,
        "cases": cases,
        "procedures": procedures,
    })


# ── 배포 상태 변경 ───────────────────────────────────────────────────────────

VALID_RELEASE_STATUSES = {"TESTING", "QI_TEAM_RELEASED", "QI_TEAM_REVIEWED", "DRAFT", "BLOCKED"}

class ReleaseStatusBody(BaseModel):
    status: str

@tracking_router.patch("/admin/api/release/{release_id}/status")
def patch_release_status(
    release_id: str,
    body: ReleaseStatusBody,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    new_status = body.status.upper()
    if new_status not in VALID_RELEASE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")
    row = database_session.query(ProductTestRelease).filter_by(
        product_test_release_id=release_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Release not found.")
    row.product_test_release_status = new_status
    row.updated_at = get_utc_now_datetime()
    database_session.commit()
    return JSONResponse({"ok": True, "status": new_status})


# ── 결함 이미지 업로드 ───────────────────────────────────────────────────────

@tracking_router.post("/admin/api/defect/{defect_id}/image")
async def upload_defect_image(
    defect_id: str,
    file: UploadFile = File(...),
    img_type: str = "other_device",
    database_session: database_session_dependency = None,
    current_role_name: current_role_name_dependency = None,
):
    if current_role_name not in (ROLE_TESTER, ROLE_ADMIN, ROLE_MASTER_ADMIN):
        raise HTTPException(status_code=403, detail="Access denied.")
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다 (jpg/png/gif/webp).")

    contents = await file.read()
    file_hash = hashlib.md5(contents).hexdigest()[:12]
    suffix = Path(file.filename or "image.jpg").suffix.lower() or ".jpg"
    save_name = f"{defect_id.replace('/', '_')}_{file_hash}{suffix}"
    save_path = EVIDENCE_UPLOAD_DIR / save_name
    save_path.write_bytes(contents)

    url = f"/static/uploads/evidence/{save_name}"

    # defect remark에 [Image] 태그 추가
    from app.models import ProductTestDefect
    defect = database_session.query(ProductTestDefect).filter_by(
        product_test_defect_id=defect_id
    ).first()
    if not defect:
        raise HTTPException(status_code=404, detail="결함을 찾을 수 없습니다.")
    valid_types = {"other_device", "hdr_screen", "general"}
    tag_type = img_type if img_type in valid_types else "general"
    defect.remark = (defect.remark or "") + f"\n[Image:{tag_type}] {url}"
    defect.updated_at = get_utc_now_datetime()
    database_session.commit()

    return JSONResponse({"ok": True, "url": url, "file_name": file.filename})


@tracking_router.delete("/admin/api/defect/{defect_id}/image")
def delete_defect_image(
    defect_id: str,
    url: str,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    if current_role_name not in (ROLE_TESTER, ROLE_ADMIN, ROLE_MASTER_ADMIN):
        raise HTTPException(status_code=403, detail="Access denied.")
    from app.models import ProductTestDefect
    defect = database_session.query(ProductTestDefect).filter_by(
        product_test_defect_id=defect_id
    ).first()
    if not defect:
        raise HTTPException(status_code=404, detail="결함을 찾을 수 없습니다.")
    lines = (defect.remark or "").split("\n")
    defect.remark = "\n".join(l for l in lines if f"[Image] {url}" not in l)
    defect.updated_at = get_utc_now_datetime()
    database_session.commit()
    # 파일 삭제
    file_path = EVIDENCE_UPLOAD_DIR / Path(url).name
    if file_path.exists():
        file_path.unlink()
    return JSONResponse({"ok": True})


# ── 근무 캘린더 CRUD ──────────────────────────────────────────────────────────

class WorkCalendarUpsertBody(BaseModel):
    calendar_date: str        # YYYY-MM-DD
    is_workday: int = 1       # 1 or 0
    day_type: str = "WORKDAY" # WORKDAY / HOLIDAY / WEEKEND
    note: str = ""


@tracking_router.get("/admin/api/work-calendar")
def list_work_calendar(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    if current_role_name not in (ROLE_TESTER, ROLE_ADMIN, ROLE_MASTER_ADMIN):
        raise HTTPException(status_code=403)
    rows = database_session.query(WorkCalendar).order_by(WorkCalendar.calendar_date).all()
    return JSONResponse([
        {
            "id": r.work_calendar_id,
            "date": r.calendar_date,
            "is_workday": r.is_workday,
            "day_type": r.day_type,
            "note": r.note or "",
        }
        for r in rows
    ])


@tracking_router.post("/admin/api/work-calendar")
def upsert_work_calendar(
    body: WorkCalendarUpsertBody,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    now = get_utc_now_datetime()
    existing = database_session.query(WorkCalendar).filter_by(
        calendar_date=body.calendar_date
    ).first()
    if existing:
        existing.is_workday = body.is_workday
        existing.day_type = body.day_type
        existing.note = body.note or None
    else:
        database_session.add(WorkCalendar(
            calendar_date=body.calendar_date,
            is_workday=body.is_workday,
            day_type=body.day_type,
            note=body.note or None,
            created_at=now,
            created_by=current_role_name,
        ))
    database_session.commit()
    return JSONResponse({"ok": True})


@tracking_router.delete("/admin/api/work-calendar/{calendar_date}")
def delete_work_calendar(
    calendar_date: str,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    row = database_session.query(WorkCalendar).filter_by(calendar_date=calendar_date).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    database_session.delete(row)
    database_session.commit()
    return JSONResponse({"ok": True})


# ── 프런트엔드 클라이언트 로그 ────────────────────────────────────────────────
@tracking_router.post("/admin/api/client-log")
async def post_client_log(request: Request):
    """JS console.log 대신 파일에 기록 — Claude가 읽을 수 있도록."""
    body = await request.json()
    level = str(body.get("level", "info")).lower()
    msg   = str(body.get("msg", ""))
    data  = body.get("data", "")
    full  = f"{msg}  {data}" if data else msg
    if level == "error":
        _client_log.error("[frontend] %s", full)
    elif level == "warn":
        _client_log.warning("[frontend] %s", full)
    else:
        _client_log.info("[frontend] %s", full)
    return JSONResponse({"ok": True})
