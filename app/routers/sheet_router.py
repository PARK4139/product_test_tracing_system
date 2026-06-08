from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import ROLE_ADMIN, ROLE_MASTER_ADMIN, ROLE_TESTER
from app.deps import current_role_name_dependency, database_session_dependency
from app.services.sheet_service import (
    apply_evidence_create,
    apply_sheet_update,
    get_sheet_payload,
    preview_evidence_create,
    preview_sheet_update,
)


sheet_router = APIRouter()


class SheetPatchBody(BaseModel):
    mode: str = Field(default="preview")
    changes: dict[str, str] = Field(default_factory=dict)
    preview_hash: str | None = None
    reason: str = Field(default="sheet_edit")


class SheetEvidenceCreateBody(BaseModel):
    mode: str = Field(default="preview")
    result_id: str
    procedure_result_id: str | None = None
    defect_id: str | None = None
    evidence_type: str
    file_name: str | None = None
    file_path: str
    file_hash: str | None = None
    captured_at: str | None = None
    remark: str | None = None
    preview_hash: str | None = None
    reason: str = Field(default="sheet_evidence_create")


def _ensure_admin_role(role_name: str) -> None:
    if role_name not in (ROLE_ADMIN, ROLE_MASTER_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required.")


@sheet_router.get("/admin/api/sheet/{table_name}")
def get_sheet_table(
    table_name: str,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    if current_role_name not in (ROLE_TESTER, ROLE_ADMIN, ROLE_MASTER_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    try:
        payload = get_sheet_payload(database_session, table_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return JSONResponse(payload)


@sheet_router.patch("/admin/api/sheet/{table_name}/{record_id}")
def patch_sheet_table(
    table_name: str,
    record_id: str,
    body: SheetPatchBody,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    try:
        if body.mode == "apply":
            payload = apply_sheet_update(
                database_session,
                table_name=table_name,
                record_id=record_id,
                changes=body.changes,
                preview_hash=body.preview_hash or "",
                updated_by=current_role_name,
                reason=body.reason,
            )
        else:
            payload = preview_sheet_update(
                database_session,
                table_name=table_name,
                record_id=record_id,
                changes=body.changes,
            )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return JSONResponse(payload)


@sheet_router.post("/admin/api/sheet/evidence")
def post_sheet_evidence(
    body: SheetEvidenceCreateBody,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_admin_role(current_role_name)
    payload_data = body.model_dump(exclude={"mode", "preview_hash", "reason"})
    try:
        if body.mode == "apply":
            payload = apply_evidence_create(
                database_session,
                payload=payload_data,
                preview_hash=body.preview_hash or "",
                updated_by=current_role_name,
                reason=body.reason,
            )
        else:
            payload = preview_evidence_create(
                database_session,
                payload=payload_data,
            )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return JSONResponse(payload)
