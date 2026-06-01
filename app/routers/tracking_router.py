"""
트래킹 대시보드 API 라우터.
- GET   /admin/api/tracking/summary          : 진행 중 + 전체 타임라인 요약
- PATCH /admin/api/release/{id}/status       : 배포 상태 변경
- GET   /admin/api/work-calendar             : 근무일 목록
- POST  /admin/api/work-calendar             : 근무일 등록/수정
- DELETE /admin/api/work-calendar/{date}     : 삭제
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import ROLE_ADMIN, ROLE_MASTER_ADMIN, ROLE_TESTER
from app.deps import current_role_name_dependency, database_session_dependency
from app.models import WorkCalendar, ProductTestRelease, get_utc_now_datetime

tracking_router = APIRouter()


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
        GROUP BY r.product_test_release_id
        ORDER BY r.release_sequence, r.product_test_release_id
    """)).fetchall()

    releases = []
    for row in releases_raw:
        alias = ""
        workday = ""
        start_date = ""
        end_date = ""
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

        releases.append({
            "id": row[0],
            "upstream_id": row[1],
            "alias": alias or row[1],
            "stage": row[2],
            "sequence": row[3],
            "status": row[4],
            # row[5] = remark (already parsed)
            "upstream_system": row[6] or "",
            "visible": bool(row[7]),
            "workday": workday,
            "start_date": start_date,
            "end_date": end_date,
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
            run.product_test_run_id
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

    # Run ID에서 Report ID 추출 → 상위 WIFI 릴리즈 역추적
    # Run ID 형식: RUN-{REPORT_ID}-{CONFIG_ID}
    report_upstream = {r["id"]: r["upstream_id"] for r in releases}

    def resolve_wifi_release(run_id: str) -> str:
        # RUN-REPORT_ID-... 에서 REPORT_ID 추출
        parts = run_id[4:] if run_id.startswith("RUN-") else run_id
        # CONFIG 부분 제거: 첫 번째 -CFG_ 앞까지
        if "-CFG_" in parts:
            report_part = parts.split("-CFG_")[0]
        else:
            report_part = parts
        release_key = f"TEST_RELEASE-{report_part}"
        return report_upstream.get(release_key, "")

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
            "wifi_release_id": resolve_wifi_release(r[9] or ""),
        }
        for r in active_defects_raw
    ]

    return JSONResponse({
        "releases": releases,
        "active_defects": active_defects,
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
