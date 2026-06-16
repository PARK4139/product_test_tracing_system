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
import json
import re
import shutil
import statistics
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from app.services.logging_service import get_logger
from app.services.status_vocab import (
    RELEASE_STATUS_PRIORITY,
    STATUS_BLOCKED,
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_QI_TEAM_RELEASED,
    STATUS_QI_TEAM_REVIEWED,
    STATUS_SKIPPED,
    STATUS_TESTING,
    VALID_RELEASE_STATUSES,
    derive_rollup_status,
    normalize_status,
)

_client_log = get_logger("client")
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

EVIDENCE_UPLOAD_DIR = Path(__file__).resolve().parent.parent / "static" / "uploads" / "evidence"
EVIDENCE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

from app.auth import ROLE_ADMIN, ROLE_MASTER_ADMIN, ROLE_TESTER
from app.deps import current_role_name_dependency, database_session_dependency
from app.models import CustomSheetTab, UiStatePref, WorkCalendar, get_utc_now_datetime

tracking_router = APIRouter()


def _clean_device_round_alias(display_alias: str) -> str:
    return re.sub(r"\s*\(\d+(?:\.\d+)*[A-Za-z]?\)\s*$", "", display_alias or "").strip()


def _strip_release_prefix(release_id: str | None) -> str:
    return re.sub(r"^(?:TEST_)?RELEASE-", "", release_id or "")


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


def _empty_result_counts() -> dict[str, int]:
    return {
        "passed": 0,
        "blocked": 0,
        "testing": 0,
        "failed": 0,
        "skipped": 0,
        "cancelled": 0,
    }


def _apply_result_status_count(counts: dict[str, int], raw_status: str | None, increment: int = 1) -> None:
    status_name = normalize_status(raw_status)
    if status_name == STATUS_PASSED:
        counts["passed"] += increment
    elif status_name == STATUS_BLOCKED:
        counts["blocked"] += increment
    elif status_name == STATUS_TESTING:
        counts["testing"] += increment
    elif status_name == STATUS_FAILED:
        counts["failed"] += increment
    elif status_name == STATUS_SKIPPED:
        counts["skipped"] += increment
    elif status_name == STATUS_CANCELLED:
        counts["cancelled"] += increment


# ── 트래킹 요약 ───────────────────────────────────────────────────────────────

@tracking_router.get("/admin/api/tracking/summary")
def get_tracking_summary(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    if current_role_name not in (ROLE_TESTER, ROLE_ADMIN, ROLE_MASTER_ADMIN):
        raise HTTPException(status_code=403, detail="Access denied.")

    from app.services.custom_sheet_trace_service import _rows

    # ── 1. 전체 엔티티 로드 (custom_sheet_tab rows_json) ──────────────────────
    rounds_all       = _rows(database_session, "entity/round")
    runs_all         = _rows(database_session, "entity/run")
    results_all      = _rows(database_session, "entity/result")
    defects_all      = _rows(database_session, "entity/defect")
    proc_results_all = _rows(database_session, "entity/proc_result")
    evidences_all    = _rows(database_session, "entity/evidence")
    targets_all      = _rows(database_session, "entity/target")
    environments_all = _rows(database_session, "entity/environment")
    cases_all        = _rows(database_session, "entity/case")
    procedures_all   = _rows(database_session, "entity/procedure")

    # ── 2. JOIN lookup 딕셔너리 ───────────────────────────────────────────────
    runs_by_round: dict[str, list[dict]] = {}
    for _run in runs_all:
        _rid = _run.get("test_round_id", "")
        if _rid:
            runs_by_round.setdefault(_rid, []).append(_run)

    results_by_run: dict[str, list[dict]] = {}
    for _res in results_all:
        _rid = _res.get("product_test_run_id", "")
        if _rid:
            results_by_run.setdefault(_rid, []).append(_res)

    defects_by_result: dict[str, list[dict]] = {}
    for _def in defects_all:
        _rid = _def.get("product_test_result_id", "")
        if _rid:
            defects_by_result.setdefault(_rid, []).append(_def)

    proc_results_by_result: dict[str, list[dict]] = {}
    for _pr in proc_results_all:
        _rid = _pr.get("product_test_result_id", "")
        if _rid:
            proc_results_by_result.setdefault(_rid, []).append(_pr)

    environments_by_id: dict[str, dict] = {
        e.get("product_test_config_id", ""): e for e in environments_all
    }
    cases_by_id: dict[str, dict] = {
        c.get("product_test_case_id", ""): c for c in cases_all
    }
    procedures_by_case: dict[str, list[dict]] = {}
    for _p in procedures_all:
        _cid = _p.get("product_test_case_id", "")
        if _cid:
            procedures_by_case.setdefault(_cid, []).append(_p)

    results_by_id: dict[str, dict] = {
        r.get("product_test_result_id", ""): r for r in results_all
    }
    runs_by_id: dict[str, dict] = {
        r.get("product_test_run_id", ""): r for r in runs_all
    }
    procedures_by_id: dict[str, dict] = {
        p.get("product_test_procedure_id", ""): p for p in procedures_all
    }

    # ── 3. Releases (rounds as releases, 원본 positional offset 유지) ─────────
    # 원본 SQL positional mapping:
    # row[0]=test_round_id, row[1]=test_round_name, row[2]=workday(→stage),
    # row[3]=start_date(→sequence), row[4]=end_date(→status),
    # row[5]=migration_status(→remark), row[6]=''(→upstream_system),
    # row[7]=''(→visible=False), row[8]=1(→run_count),
    # row[9]=COUNT(DISTINCT runs)(→total_results),
    # row[10]=COUNT(results)(→defect_count), row[11]=COUNT(DISTINCT defects)(→open_defects)

    release_result_counts: dict[str, dict[str, int]] = {}
    for _round in rounds_all:
        _round_id = _round.get("test_round_id", "")
        for _run in runs_by_round.get(_round_id, []):
            for _res in results_by_run.get(_run.get("product_test_run_id", ""), []):
                _counts = release_result_counts.setdefault(_round_id, _empty_result_counts())
                _apply_result_status_count(_counts, _res.get("product_test_result_status"))

    releases = []
    for round_row in sorted(rounds_all, key=lambda r: r.get("test_round_id", "")):
        round_id        = round_row.get("test_round_id", "") or ""
        round_name      = round_row.get("test_round_name", "") or ""
        workday_val     = str(round_row.get("workday", "") or "")
        start_date_val  = str(round_row.get("start_date", "") or "")
        end_date_val    = str(round_row.get("end_date", "") or "")
        migration_status = str(round_row.get("migration_status", "") or "")

        # row[5]=migration_status → remark (positional offset 유지)
        remark_field = migration_status
        work_period = _parse_release_work_period(remark_field)

        alias = ""
        for _line in remark_field.split("\n"):
            _line = _line.strip()
            if _line.startswith("[Report Alias]"):
                alias = _line.replace("[Report Alias]", "").strip()

        # row[2]=workday → stage
        stage = workday_val
        if stage in ("device_round", "run_session"):
            display_alias = remark_field.split("\n")[0].strip() or _strip_release_prefix(round_id)
            if stage == "device_round":
                display_alias = _clean_device_round_alias(display_alias)
        else:
            display_alias = alias or _strip_release_prefix(round_id)

        _run_list  = runs_by_round.get(round_id, [])
        _run_ids   = [r.get("product_test_run_id", "") for r in _run_list]
        _result_ids: list[str] = []
        _defect_ids: set[str] = set()
        for _rid in _run_ids:
            for _res in results_by_run.get(_rid, []):
                _result_ids.append(_res.get("product_test_result_id", ""))
                for _def in defects_by_result.get(_res.get("product_test_result_id", ""), []):
                    _defect_ids.add(_def.get("product_test_defect_id", ""))

        result_counts = release_result_counts.get(round_id, _empty_result_counts())
        releases.append({
            "id":             round_id,
            "upstream_id":    round_name,          # row[1] test_round_name → upstream_id
            "alias":          display_alias,
            "stage":          workday_val,          # row[2] workday → stage
            "sequence":       start_date_val if start_date_val not in ("", "None") else "",  # row[3]
            "status":         normalize_status(end_date_val if end_date_val not in ("", "None") else ""),  # row[4]
            "remark":         remark_field,         # row[5] migration_status → remark
            "upstream_system": "",                  # row[6] = ''
            "visible":        False,                # row[7] = '' → bool('') = False
            "workday":        work_period["workday"],
            "start_date":     work_period["start_date"],
            "end_date":       work_period["end_date"],
            "run_count":      1,                    # row[8] = 1 (constant)
            "total_results":  len(set(_run_ids)),   # row[9] = COUNT(DISTINCT runs)
            "passed":         result_counts["passed"],
            "blocked":        result_counts["blocked"],
            "testing":        result_counts["testing"],
            "failed":         result_counts["failed"],
            "skipped":        result_counts["skipped"],
            "cancelled":      result_counts["cancelled"],
            "defect_count":   len(_result_ids),     # row[10] = COUNT(results)
            "open_defects":   len(_defect_ids),     # row[11] = COUNT(DISTINCT defects)
        })

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
        child_statuses = [
            c["status"] for c in children
            if not c["visible"]
            and "TEST_REPORT_" not in c["id"]
            and "TBD_REPORT_" not in c["id"]
        ]
        if not child_statuses:
            continue
        best = min(child_statuses, key=lambda s: RELEASE_STATUS_PRIORITY.get(s, 99))
        parent["status"] = best

    # ── 4. Helper closures (원본 동일) ────────────────────────────────────────
    release_upstream  = {r["id"]: r["upstream_id"] for r in releases}
    release_visible   = {r["id"]: r["visible"] for r in releases}
    release_by_id     = {r["id"]: r for r in releases}

    def resolve_release_work_period(release_id: str) -> dict[str, str]:
        cur = release_id
        for _ in range(8):
            row = release_by_id.get(cur)
            if row:
                period = {
                    "workday":    row.get("workday") or "",
                    "start_date": row.get("start_date") or "",
                    "end_date":   row.get("end_date") or "",
                }
                if period["workday"] or period["start_date"] or period["end_date"]:
                    return period
            parent = release_upstream.get(cur, "")
            if not parent or parent not in release_by_id:
                break
            cur = parent
        return {"workday": "", "start_date": "", "end_date": ""}

    def resolve_parent_release(release_id: str) -> str:
        cur = release_id
        for _ in range(5):
            if cur and release_visible.get(cur, False):
                parent = release_upstream.get(cur, "")
                if parent and release_visible.get(parent, False):
                    return cur
                return cur
            cur = release_upstream.get(cur, "")
            if not cur:
                break
        return release_id

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
            target_key = _strip_release_prefix(round_row["id"])
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

    # ── 5. Active Defects ─────────────────────────────────────────────────────
    _severity_order = {"S": 1, "A": 2, "B": 3, "C": 4}
    opened_defects = sorted(
        [d for d in defects_all if d.get("product_test_defect_status") == "opened"],
        key=lambda d: (
            _severity_order.get(d.get("defect_severity", ""), 5),
            d.get("created_at", "") or "",
        ),
    )

    active_defects = []
    for d in opened_defects:
        _result_id = d.get("product_test_result_id", "")
        _res_row   = results_by_id.get(_result_id)
        _run_id    = _res_row.get("product_test_run_id", "") if _res_row else ""
        _run_row   = runs_by_id.get(_run_id) if _run_id else None
        _round_id  = _run_row.get("test_round_id", "") if _run_row else ""
        active_defects.append({
            "id":                       d.get("product_test_defect_id", ""),
            "title":                    d.get("defect_title", ""),
            "severity":                 d.get("defect_severity", ""),
            "priority":                 d.get("defect_priority", ""),
            "status":                   normalize_status(d.get("product_test_defect_status", "")),
            "assigned_to":              d.get("assigned_to", "") or "-",
            "expected_resolution_date": d.get("expected_resolution_date", "") or "",
            "created_at":               d.get("created_at", ""),
            "release_id":               _round_id,
            "parent_release_id":        resolve_parent_release(_round_id),
            "run_id":                   _run_id,
            "images":                   parse_images(d.get("remark", "")),
        })

    # ── 6. Runs (result 있는 것만, started_at 정렬) ───────────────────────────
    run_result_counts: dict[str, dict[str, int]] = {}
    run_total_results_map: dict[str, int] = {}
    for _res in results_all:
        _rid = _res.get("product_test_run_id", "")
        _counts = run_result_counts.setdefault(_rid, _empty_result_counts())
        _apply_result_status_count(_counts, _res.get("product_test_result_status"))
        run_total_results_map[_rid] = run_total_results_map.get(_rid, 0) + 1

    def _run_display_remark(raw_remark: str, work_period: dict[str, str]) -> str:
        period_label = _format_release_work_period(work_period)
        if not period_label:
            return raw_remark or ""
        if raw_remark and period_label in raw_remark:
            return raw_remark
        return f"{raw_remark}\n[Release Work Period] {period_label}".strip()

    runs_with_results = sorted(
        [run for run in runs_all if run.get("product_test_run_id", "") in run_result_counts],
        key=lambda r: r.get("started_at", "") or "",
    )

    runs = []
    for run in runs_with_results:
        _run_id   = run.get("product_test_run_id", "")
        _round_id = run.get("test_round_id", "") or ""
        _run_counts = run_result_counts.get(_run_id, _empty_result_counts())
        run_target  = logical_target_from_release(_round_id, run.get("product_test_target_id", "") or "")
        normalized_statuses = (
            [STATUS_FAILED]    * _run_counts["failed"]
            + [STATUS_BLOCKED] * _run_counts["blocked"]
            + [STATUS_TESTING] * _run_counts["testing"]
            + [STATUS_PASSED]  * _run_counts["passed"]
            + [STATUS_SKIPPED] * _run_counts["skipped"]
            + [STATUS_CANCELLED] * _run_counts["cancelled"]
        )
        _work_period = resolve_release_work_period(_round_id)
        runs.append({
            "id":                 _run_id,
            "release_id":         _round_id,
            "parent_release_id":  resolve_parent_release(_round_id),
            "status":             derive_rollup_status(normalized_statuses),
            "run_status":         normalize_status(run.get("product_test_run_status", "")),
            "started_at":         run.get("started_at", ""),
            "finished_at":        run.get("finished_at", ""),
            "planned_workday":    _work_period["workday"],
            "planned_start_date": _work_period["start_date"],
            "planned_end_date":   _work_period["end_date"],
            "total_results":      run_total_results_map.get(_run_id, 0),
            "passed":             _run_counts["passed"],
            "blocked":            _run_counts["blocked"],
            "testing":            _run_counts["testing"],
            "failed":             _run_counts["failed"],
            "skipped":            _run_counts["skipped"],
            "cancelled":          _run_counts["cancelled"],
            "target_id":          run_target["id"],
            "target_model_name":  run_target["model_name"],
            "target_sw_version":  run_target["sw_version"],
            "physical_target_id": run.get("product_test_target_id", "") or "",
            "target_round_id":    run_target["round_id"],
            "environment_id":     run.get("product_test_config_id", "") or "",
            "remark":             _run_display_remark(run.get("remark", "") or "", _work_period),
        })

    timeline_test_target_by_id: dict[str, dict] = {}
    for run in runs:
        target_round_id = run.get("target_round_id") or ""
        target_id       = run.get("target_id") or ""
        if not target_round_id or not target_id:
            continue
        timeline_test_target_by_id.setdefault(target_id, {
            "id":               target_id,
            "definition_id":    "",
            "product_code":     run.get("target_model_name") or "",
            "model_name":       run.get("target_model_name") or "",
            "hardware_revision": "",
            "serial_number":    "",
            "software_version": run.get("target_sw_version") or "",
            "firmware_version": "",
            "manufacture_lot":  "",
            "status":           run.get("status") or "",
            "round_id":         target_round_id,
            "physical_target_id": run.get("physical_target_id") or "",
            "remark":           "timeline target by test round",
        })
    timeline_test_targets = sorted(
        timeline_test_target_by_id.values(),
        key=lambda target: (target["round_id"], target["id"]),
    )

    # ── 7. Results Summary (case 단위 집계) ───────────────────────────────────
    case_map: dict[tuple, dict] = {}
    for _res in results_all:
        _run_id2   = _res.get("product_test_run_id", "")
        _run_row2  = runs_by_id.get(_run_id2)
        _round_id2 = _run_row2.get("test_round_id", "") if _run_row2 else ""
        _case_id   = _res.get("product_test_case_id", "")
        _res_status = normalize_status(_res.get("product_test_result_status", ""))
        _result_id = _res.get("product_test_result_id", "")
        _parent    = resolve_parent_release(_round_id2)
        _key       = (_parent, _case_id)
        if _key not in case_map:
            case_map[_key] = {
                "parent_release_id": _parent,
                "case_id":   _case_id,
                "passed":    0,
                "blocked":   0,
                "testing":   0,
                "total":     0,
                "run_ids":   set(),
                "result_ids": [],
                "defect_ids": [],
            }
        _entry = case_map[_key]
        _entry["total"] += 1
        if _res_status == STATUS_PASSED:
            _entry["passed"] += 1
        elif _res_status == STATUS_BLOCKED:
            _entry["blocked"] += 1
        elif _res_status == STATUS_TESTING:
            _entry["testing"] += 1
        _entry["run_ids"].add(_run_id2)
        _entry["result_ids"].append(_result_id)
        for _def in defects_by_result.get(_result_id, []):
            if _def.get("product_test_defect_status") == "opened":
                _entry["defect_ids"].append(_def.get("product_test_defect_id", ""))

    results_summary = [
        {
            "parent_release_id": v["parent_release_id"],
            "case_id":    v["case_id"],
            "passed":     v["passed"],
            "blocked":    v["blocked"],
            "testing":    v["testing"],
            "total":      v["total"],
            "run_ids":    sorted(v["run_ids"]),
            "result_ids": v["result_ids"],
            "defect_ids": v["defect_ids"],
        }
        for v in case_map.values()
    ]

    # ── 8. Procedure Results ──────────────────────────────────────────────────
    sorted_proc_results = sorted(
        proc_results_all,
        key=lambda pr: (
            procedures_by_id.get(pr.get("product_test_procedure_id", ""), {}).get("product_test_case_id", "") or "",
            procedures_by_id.get(pr.get("product_test_procedure_id", ""), {}).get("procedure_sequence", 0) or 0,
        ),
    )

    procedure_results = []
    for pr in sorted_proc_results:
        _result_id3  = pr.get("product_test_result_id", "")
        _res_row3    = results_by_id.get(_result_id3)
        _run_id3     = _res_row3.get("product_test_run_id", "") if _res_row3 else ""
        _run_row3    = runs_by_id.get(_run_id3) if _run_id3 else None
        _round_id3   = _run_row3.get("test_round_id", "") if _run_row3 else ""
        _proc_id     = pr.get("product_test_procedure_id", "")
        _proc_row    = procedures_by_id.get(_proc_id, {})
        procedure_results.append({
            "id":               pr.get("product_test_procedure_result_id", ""),
            "result_id":        _result_id3,
            "procedure_id":     _proc_id,
            "status":           normalize_status(pr.get("product_test_procedure_result_status", "")),
            "actual_result":    pr.get("actual_result", "") or "",
            "judgement_reason": pr.get("judgement_reason", "") or "",
            "judged_at":        pr.get("judged_at", "") or "",
            "judged_by":        pr.get("judged_by", "") or "",
            "case_id":          _proc_row.get("product_test_case_id", ""),
            "sequence":         _proc_row.get("procedure_sequence", ""),
            "action":           (_proc_row.get("procedure_action", "") or "")[:120],
            "parent_release_id": resolve_parent_release(_round_id3),
        })

    # ── 9. Evidence ───────────────────────────────────────────────────────────
    sorted_evidences = sorted(evidences_all, key=lambda e: e.get("captured_at", "") or "")

    evidence = []
    for ev in sorted_evidences:
        _result_id4 = ev.get("product_test_result_id", "")
        _defect_id4 = ev.get("product_test_defect_id", "")
        _round_id4  = ""
        if _result_id4:
            _res_row4 = results_by_id.get(_result_id4)
            if _res_row4:
                _run_row4 = runs_by_id.get(_res_row4.get("product_test_run_id", ""))
                if _run_row4:
                    _round_id4 = _run_row4.get("test_round_id", "") or ""
        if not _round_id4 and _defect_id4:
            _def4 = next((d for d in defects_all if d.get("product_test_defect_id") == _defect_id4), None)
            if _def4:
                _res_row4b = results_by_id.get(_def4.get("product_test_result_id", ""))
                if _res_row4b:
                    _run_row4b = runs_by_id.get(_res_row4b.get("product_test_run_id", ""))
                    if _run_row4b:
                        _round_id4 = _run_row4b.get("test_round_id", "") or ""
        evidence.append({
            "id":                   ev.get("product_test_evidence_id", ""),
            "result_id":            _result_id4 or "",
            "procedure_result_id":  ev.get("product_test_procedure_result_id", "") or "",
            "defect_id":            _defect_id4 or "",
            "type":                 ev.get("product_test_evidence_type", "") or "",
            "file_name":            ev.get("file_name", "") or "",
            "file_path":            ev.get("file_path", "") or "",
            "captured_at":          ev.get("captured_at", "") or "",
            "captured_by":          ev.get("captured_by", "") or "",
            "parent_release_id":    resolve_parent_release(_round_id4) if _round_id4 else "",
        })

    reports = []

    # ── 10. Physical test targets ─────────────────────────────────────────────
    physical_test_targets = sorted(
        [
            {
                "id":               t.get("product_test_target_id", "") or "",
                "entity_type":      "product_test_target",
                "entity_id":        t.get("product_test_target_id", "") or "",
                "product_code":     t.get("product_code", "") or "",
                "model_name":       t.get("model_name", "") or "",
                "hardware_revision": t.get("hardware_revision", "") or "",
                "serial_number":    t.get("serial_number", "") or "",
                "software_version": t.get("software_version", "") or "",
                "firmware_version": t.get("firmware_version", "") or "",
                "manufacture_lot":  t.get("manufacture_lot", "") or "",
                "status":           t.get("product_test_target_status", "") or "",
                "round_id":         "",
                "physical_target_id": t.get("product_test_target_id", "") or "",
                "remark":           t.get("remark", "") or "",
            }
            for t in targets_all
        ],
        key=lambda t: t["id"],
    )
    test_targets = timeline_test_targets + physical_test_targets

    # ── 11. Test Environments (master list) ───────────────────────────────────
    test_environments = sorted(
        [
            {
                "id":             e.get("product_test_config_id", "") or "",
                "name":           e.get("product_test_config_name", "") or "",
                "country":        e.get("test_country", "") or "",
                "city":           e.get("test_city", "") or "",
                "company":        e.get("test_company", "") or "",
                "room":           e.get("test_room", "") or "",
                "network_type":   e.get("network_type", "") or "",
                "computer_name":  e.get("test_computer_name", "") or "",
                "os_version":     e.get("operating_system_version", "") or "",
                "tool_name":      e.get("test_tool_name", "") or "",
                "tool_version":   e.get("test_tool_version", "") or "",
                "power_voltage":  e.get("power_voltage", "") or "",
                "power_frequency": e.get("power_frequency", "") or "",
                "power_condition": e.get("power_condition", "") or "",
                "captured_at":    e.get("captured_at", "") or "",
                "status":         e.get("product_test_config_status", "") or "",
                "remark":         e.get("remark", "") or "",
            }
            for e in environments_all
        ],
        key=lambda e: e["id"],
    )

    # ── 12. Test Cases (master list) ──────────────────────────────────────────
    test_cases = sorted(
        [
            {
                "id":              c.get("product_test_case_id", "") or "",
                "title":           c.get("product_test_case_title", "") or "",
                "category":        c.get("test_category", "") or "",
                "objective":       c.get("test_objective", "") or "",
                "precondition":    c.get("precondition", "") or "",
                "expected_result": c.get("expected_result", "") or "",
                "status":          c.get("product_test_case_status", "") or "",
                "remark":          c.get("remark", "") or "",
            }
            for c in cases_all
        ],
        key=lambda c: c["id"],
    )

    # ── 13. Test Procedures (master list, used_releases 포함) ─────────────────
    _proc_release_map: dict[str, list[str]] = {}
    for _res in results_all:
        _case_id5 = _res.get("product_test_case_id", "")
        _run_id5  = _res.get("product_test_run_id", "")
        _run_row5 = runs_by_id.get(_run_id5)
        _round_id5 = _run_row5.get("test_round_id", "") if _run_row5 else ""
        if not _round_id5:
            continue
        for _proc5 in procedures_by_case.get(_case_id5, []):
            _proc_id5 = _proc5.get("product_test_procedure_id", "")
            if _round_id5 not in _proc_release_map.get(_proc_id5, []):
                _proc_release_map.setdefault(_proc_id5, []).append(_round_id5)

    sorted_procedures = sorted(
        procedures_all,
        key=lambda p: (
            p.get("product_test_case_id", "") or "",
            p.get("procedure_sequence", 0) or 0,
            p.get("product_test_procedure_id", "") or "",
        ),
    )

    test_procedures = [
        {
            "id":                    p.get("product_test_procedure_id", "") or "",
            "case_id":               p.get("product_test_case_id", "") or "",
            "sequence":              p.get("procedure_sequence", 0) or 0,
            "action":                p.get("procedure_action", "") or "",
            "acceptance_criteria":   p.get("acceptance_criteria", "") or "",
            "required_evidence_type": p.get("required_evidence_type", "") or "",
            "status":                p.get("product_test_procedure_status", "") or "",
            "remark":                p.get("remark", "") or "",
            "used_releases": ", ".join(
                _strip_release_prefix(rid)
                for rid in _proc_release_map.get(p.get("product_test_procedure_id", "") or "", [])
            ),
        }
        for p in sorted_procedures
    ]

    # ── 14. Targets (logical, via runs) ──────────────────────────────────────
    seen_tgt: set[str] = set()
    targets = []
    for run in runs:
        tid = run.get("target_id") or ""
        if not tid or tid in seen_tgt:
            continue
        seen_tgt.add(tid)
        targets.append({
            "id":               tid,
            "model_name":       run.get("target_model_name") or "",
            "sw_version":       run.get("target_sw_version") or "",
            "serial_number":    "",
            "physical_target_id": run.get("physical_target_id") or "",
            "round_id":         run.get("target_round_id") or "",
            "remark":           "logical target by model/software version",
        })
    targets.sort(key=lambda t: (t["model_name"], t["sw_version"], t["id"]))

    # ── 15. Environments (via runs, 중복 제거) ─────────────────────────────────
    seen_env: set[str] = set()
    environments = []
    for run in runs_with_results:
        _env_id = run.get("product_test_config_id", "")
        if _env_id and _env_id not in seen_env:
            seen_env.add(_env_id)
            _env_row = environments_by_id.get(_env_id, {})
            environments.append({
                "id":   _env_id,
                "name": _env_row.get("product_test_config_name", "") or "",
            })

    # ── 16. Cases (via results, parent_release_id 포함) ───────────────────────
    _seen_cases: dict[tuple, bool] = {}
    cases = []
    for _res in sorted(results_all, key=lambda r: r.get("product_test_case_id", "") or ""):
        _case_id6 = _res.get("product_test_case_id", "")
        _run_id6  = _res.get("product_test_run_id", "")
        _run_row6 = runs_by_id.get(_run_id6)
        _round_id6 = _run_row6.get("test_round_id", "") if _run_row6 else ""
        _key6 = (_case_id6, _round_id6)
        if _key6 not in _seen_cases:
            _seen_cases[_key6] = True
            _case_row6 = cases_by_id.get(_case_id6, {})
            cases.append({
                "id":               _case_id6,
                "title":            (_case_row6.get("product_test_case_title", "") or "")[:120],
                "parent_release_id": resolve_parent_release(_round_id6),
            })

    # ── 17. Procedures (via results, parent_release_id 포함) ──────────────────
    _seen_procs: dict[tuple, bool] = {}
    procedures = []
    for _res in sorted(results_all, key=lambda r: r.get("product_test_case_id", "") or ""):
        _case_id7 = _res.get("product_test_case_id", "")
        _run_id7  = _res.get("product_test_run_id", "")
        _run_row7 = runs_by_id.get(_run_id7)
        _round_id7 = _run_row7.get("test_round_id", "") if _run_row7 else ""
        for _proc7 in sorted(
            procedures_by_case.get(_case_id7, []),
            key=lambda p: (p.get("procedure_sequence", 0) or 0),
        ):
            _proc_id7 = _proc7.get("product_test_procedure_id", "")
            _key7 = (_proc_id7, _round_id7)
            if _key7 not in _seen_procs:
                _seen_procs[_key7] = True
                procedures.append({
                    "id":               _proc_id7,
                    "case_id":          _case_id7,
                    "sequence":         _proc7.get("procedure_sequence", ""),
                    "action":           (_proc7.get("procedure_action", "") or "")[:120],
                    "parent_release_id": resolve_parent_release(_round_id7),
                })

    return JSONResponse({
        "releases":          releases,
        "active_defects":    active_defects,
        "runs":              runs,
        "results_summary":   results_summary,
        "procedure_results": procedure_results,
        "evidence":          evidence,
        "reports":           reports,
        "test_releases":     releases,
        "test_targets":      test_targets,
        "test_environments": test_environments,
        "test_cases":        test_cases,
        "test_procedures":   test_procedures,
        "targets":           targets,
        "environments":      environments,
        "cases":             cases,
        "procedures":        procedures,
    })


# ── 배포 상태 변경 ───────────────────────────────────────────────────────────

class ReleaseStatusBody(BaseModel):
    status: str

@tracking_router.patch("/admin/api/release/{release_id}/status")
def patch_release_status(
    release_id: str,
    body: ReleaseStatusBody,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    raise HTTPException(status_code=410, detail="Release status API removed in v2 (round/run model).")


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


# ── 커스텀 스프레드시트 탭 (탭바 '+' 버튼으로 생성) ──────────────────────────
# GET    /admin/api/custom-sheets?region_key=...        : 탭 목록(시트 포함) 조회
# POST   /admin/api/custom-sheets                       : 탭 생성
# PATCH  /admin/api/custom-sheets/{id}                  : 탭 이름/컬럼/행/정렬 수정(자동저장)
# DELETE /admin/api/custom-sheets/{id}                  : 탭 삭제
# POST   /admin/api/custom-sheets/{id}/compute          : 컬럼 통계 계산(파이썬 로직, 수식 미지원)

_CUSTOM_SHEET_REGION_KEYS = ("configs", "primary", "secondary", "quaternary", "entity")
_CUSTOM_SHEET_DEFAULT_COLUMNS = [
    {"key": "col_1", "label": "항목", "type": "text"},
    {"key": "col_2", "label": "값", "type": "number"},
    {"key": "col_3", "label": "비고", "type": "text"},
]


def _custom_sheet_to_dict(row: CustomSheetTab) -> dict:
    try:
        columns = json.loads(row.columns_json or "[]")
    except (TypeError, ValueError):
        columns = []
    try:
        rows = json.loads(row.rows_json or "[]")
    except (TypeError, ValueError):
        rows = []
    return {
        "id": row.custom_sheet_tab_id,
        "region_key": row.region_key,
        "tab_label": row.tab_label,
        "columns": columns,
        "rows": rows,
        "sort_order": row.sort_order,
        "updated_at": row.updated_at,
        "remark": row.remark or "",
    }


def _custom_sheet_normalize_columns(raw) -> list[dict]:
    if not isinstance(raw, list) or not raw:
        return [dict(c) for c in _CUSTOM_SHEET_DEFAULT_COLUMNS]
    normalized = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or f"col_{index + 1}").strip() or f"col_{index + 1}"
        label = str(item.get("label") or key).strip() or key
        col_type = str(item.get("type") or "text").strip().lower()
        if col_type not in ("text", "number", "date", "select"):
            col_type = "text"
        entry = {"key": key, "label": label, "type": col_type}
        if col_type == "select" and isinstance(item.get("options"), list):
            entry["options"] = [str(option) for option in item["options"]][:50]
        normalized.append(entry)
    return normalized or [dict(c) for c in _CUSTOM_SHEET_DEFAULT_COLUMNS]


def _custom_sheet_normalize_rows(raw, columns: list[dict]) -> list[dict]:
    if not isinstance(raw, list):
        return []
    keys = [c["key"] for c in columns]
    normalized = []
    for item in raw[:5000]:
        if not isinstance(item, dict):
            continue
        normalized.append({k: item.get(k, "") for k in keys})
    return normalized


class CustomSheetCreateBody(BaseModel):
    region_key: str
    tab_label: str = "새 시트"


class CustomSheetUpdateBody(BaseModel):
    tab_label: str | None = None
    columns: list | None = None
    rows: list | None = None
    sort_order: int | None = None
    remark: str | None = None


class CustomSheetComputeBody(BaseModel):
    column: str
    operation: str = "sum"   # sum/avg/min/max/count/median/group_count
    group_by: str | None = None


@tracking_router.get("/admin/api/custom-sheets")
def list_custom_sheets(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    region_key: str = Query(default=""),
):
    if current_role_name not in (ROLE_TESTER, ROLE_ADMIN, ROLE_MASTER_ADMIN):
        raise HTTPException(status_code=403)
    query = database_session.query(CustomSheetTab)
    if region_key:
        if region_key == "entity":
            # entity 탭 영역: region_key='entity' 또는 'entity/...' 시트 모두 반환
            query = query.filter(
                (CustomSheetTab.region_key == "entity")
                | CustomSheetTab.region_key.startswith("entity/")
            )
        else:
            query = query.filter_by(region_key=region_key)
    rows = query.order_by(CustomSheetTab.region_key, CustomSheetTab.sort_order).all()
    return JSONResponse([_custom_sheet_to_dict(r) for r in rows])


@tracking_router.post("/admin/api/custom-sheets")
def create_custom_sheet(
    body: CustomSheetCreateBody,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    region_key = (body.region_key or "").strip().lower()
    if region_key not in _CUSTOM_SHEET_REGION_KEYS:
        raise HTTPException(status_code=400, detail="invalid region_key")
    now = get_utc_now_datetime()
    max_sort = (
        database_session.query(CustomSheetTab)
        .filter_by(region_key=region_key)
        .count()
    )
    new_id = f"sheet_{uuid.uuid4().hex[:12]}"
    columns = [dict(c) for c in _CUSTOM_SHEET_DEFAULT_COLUMNS]
    row = CustomSheetTab(
        custom_sheet_tab_id=new_id,
        region_key=region_key,
        tab_label=(body.tab_label or "새 시트").strip()[:80] or "새 시트",
        columns_json=json.dumps(columns, ensure_ascii=False),
        rows_json=json.dumps([{c["key"]: "" for c in columns}], ensure_ascii=False),
        sort_order=max_sort,
        created_at=now,
        created_by=current_role_name,
        updated_at=now,
        updated_by=current_role_name,
    )
    database_session.add(row)
    database_session.commit()
    return JSONResponse(_custom_sheet_to_dict(row))


@tracking_router.patch("/admin/api/custom-sheets/{sheet_id}")
def update_custom_sheet(
    sheet_id: str,
    body: CustomSheetUpdateBody,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    row = database_session.query(CustomSheetTab).filter_by(custom_sheet_tab_id=sheet_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")

    columns = json.loads(row.columns_json or "[]")
    if body.columns is not None:
        columns = _custom_sheet_normalize_columns(body.columns)
        row.columns_json = json.dumps(columns, ensure_ascii=False)
    if body.rows is not None:
        row.rows_json = json.dumps(_custom_sheet_normalize_rows(body.rows, columns), ensure_ascii=False)
    if body.tab_label is not None:
        label = body.tab_label.strip()[:80]
        row.tab_label = label or row.tab_label
    if body.sort_order is not None:
        row.sort_order = int(body.sort_order)
    if body.remark is not None:
        row.remark = body.remark.strip() or None

    row.updated_at = get_utc_now_datetime()
    row.updated_by = current_role_name
    database_session.commit()
    return JSONResponse(_custom_sheet_to_dict(row))


@tracking_router.delete("/admin/api/custom-sheets/{sheet_id}")
def delete_custom_sheet(
    sheet_id: str,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    row = database_session.query(CustomSheetTab).filter_by(custom_sheet_tab_id=sheet_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    database_session.delete(row)
    database_session.commit()
    return JSONResponse({"ok": True})


def _custom_sheet_numeric(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text_value = str(value).strip().replace(",", "")
    if not text_value:
        return None
    try:
        return float(text_value)
    except ValueError:
        return None


@tracking_router.post("/admin/api/custom-sheets/{sheet_id}/compute")
def compute_custom_sheet(
    sheet_id: str,
    body: CustomSheetComputeBody,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    """시트 컬럼에 대한 통계 계산 — 사용자 수식이 아닌 하드코딩된 파이썬 로직만 지원."""
    if current_role_name not in (ROLE_TESTER, ROLE_ADMIN, ROLE_MASTER_ADMIN):
        raise HTTPException(status_code=403)
    row = database_session.query(CustomSheetTab).filter_by(custom_sheet_tab_id=sheet_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")

    rows = json.loads(row.rows_json or "[]")
    column = body.column
    operation = (body.operation or "sum").strip().lower()

    def _aggregate(values: list[float], op: str):
        if not values:
            return None
        if op == "sum":
            return sum(values)
        if op == "avg":
            return statistics.fmean(values)
        if op == "min":
            return min(values)
        if op == "max":
            return max(values)
        if op == "median":
            return statistics.median(values)
        if op == "count":
            return float(len(values))
        return None

    if body.group_by:
        group_key = body.group_by
        groups: dict[str, list[float]] = {}
        group_counts: dict[str, int] = {}
        for record in rows:
            group_value = str(record.get(group_key, "") or "(빈 값)")
            group_counts[group_value] = group_counts.get(group_value, 0) + 1
            numeric = _custom_sheet_numeric(record.get(column))
            if numeric is not None:
                groups.setdefault(group_value, []).append(numeric)
        if operation == "group_count":
            result = {key: float(count) for key, count in group_counts.items()}
        else:
            result = {key: _aggregate(values, operation) for key, values in groups.items()}
        return JSONResponse({"ok": True, "operation": operation, "group_by": group_key, "result": result})

    numeric_values = [v for v in (_custom_sheet_numeric(record.get(column)) for record in rows) if v is not None]
    if operation == "count":
        value = float(len(rows))
    else:
        value = _aggregate(numeric_values, operation)
    return JSONResponse({
        "ok": True,
        "operation": operation,
        "column": column,
        "value": value,
        "sample_size": len(numeric_values),
        "row_count": len(rows),
    })


# ---------------------------------------------------------------------------
# UI 상태(키-값) 저장 — 탭 순서/접기 상태/활성 탭/라벨/뷰모드 등을
# 브라우저 localStorage 대신 서버 DB에 저장해서 다른 PC(clone)에서도 유지되게 한다.
# 화면 설정값이라 role 체크는 custom-sheets 조회와 동일하게 tester 이상으로 완화.
# ---------------------------------------------------------------------------

_UI_STATE_KEY_MAX_LEN = 200
_UI_STATE_VALUE_MAX_LEN = 200_000


class UiStateBulkPutBody(BaseModel):
    values: dict[str, object]


def _ui_state_can_access(role: str) -> None:
    if role not in (ROLE_TESTER, ROLE_ADMIN, ROLE_MASTER_ADMIN):
        raise HTTPException(status_code=403)


def _ui_state_validate_key(key: str) -> str:
    key = (key or "").strip()
    if not key or len(key) > _UI_STATE_KEY_MAX_LEN:
        raise HTTPException(status_code=400, detail="invalid pref key")
    return key


def _ui_state_dump_value(value) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) > _UI_STATE_VALUE_MAX_LEN:
        raise HTTPException(status_code=400, detail="value too large")
    return text


@tracking_router.get("/admin/api/ui-state")
def list_ui_state(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ui_state_can_access(current_role_name)
    rows = database_session.query(UiStatePref).all()
    values: dict[str, object] = {}
    for row in rows:
        try:
            values[row.pref_key] = json.loads(row.value_json or "null")
        except (TypeError, ValueError):
            continue
    return JSONResponse({"values": values})


@tracking_router.put("/admin/api/ui-state/{pref_key}")
def put_ui_state(
    pref_key: str,
    body: dict,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ui_state_can_access(current_role_name)
    key = _ui_state_validate_key(pref_key)
    value_json = _ui_state_dump_value(body.get("value") if isinstance(body, dict) else None)
    now = get_utc_now_datetime()
    row = database_session.query(UiStatePref).filter_by(pref_key=key).first()
    if row:
        row.value_json = value_json
        row.updated_at = now
        row.updated_by = current_role_name
    else:
        row = UiStatePref(
            pref_key=key,
            value_json=value_json,
            updated_at=now,
            updated_by=current_role_name,
        )
        database_session.add(row)
    database_session.commit()
    return JSONResponse({"ok": True, "key": key})


@tracking_router.put("/admin/api/ui-state")
def put_ui_state_bulk(
    body: UiStateBulkPutBody,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    """여러 키를 한 번에 upsert — 초기 마이그레이션(localStorage → DB) 시 사용."""
    _ui_state_can_access(current_role_name)
    if len(body.values) > 500:
        raise HTTPException(status_code=400, detail="too many keys")
    now = get_utc_now_datetime()
    saved_keys: list[str] = []
    for raw_key, value in body.values.items():
        key = _ui_state_validate_key(raw_key)
        value_json = _ui_state_dump_value(value)
        row = database_session.query(UiStatePref).filter_by(pref_key=key).first()
        if row:
            row.value_json = value_json
            row.updated_at = now
            row.updated_by = current_role_name
        else:
            row = UiStatePref(
                pref_key=key,
                value_json=value_json,
                updated_at=now,
                updated_by=current_role_name,
            )
            database_session.add(row)
        saved_keys.append(key)
    database_session.commit()
    return JSONResponse({"ok": True, "keys": saved_keys})


@tracking_router.delete("/admin/api/ui-state/{pref_key}")
def delete_ui_state(
    pref_key: str,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ui_state_can_access(current_role_name)
    key = _ui_state_validate_key(pref_key)
    row = database_session.query(UiStatePref).filter_by(pref_key=key).first()
    if row:
        database_session.delete(row)
        database_session.commit()
    return JSONResponse({"ok": True})
