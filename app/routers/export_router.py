from io import BytesIO
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, status
from fastapi.responses import StreamingResponse

from app.auth import ROLE_ADMIN, ROLE_MASTER_ADMIN, ensure_role_allowed
from app.config import is_qc_mode_enabled
from app.deps import current_role_name_dependency, database_session_dependency
from app.services.excel_export_service import (
    append_test_results_to_existing_workbook,
    build_test_result_workbook,
)


export_router = APIRouter(prefix="/admin/export", tags=["export"])


@export_router.get("/xlsx")
def export_test_results_as_excel(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    qc_mode_enabled = is_qc_mode_enabled()
    if not qc_mode_enabled:
        ensure_role_allowed(current_role_name, {ROLE_ADMIN, ROLE_MASTER_ADMIN})
    workbook = build_test_result_workbook(database_session=database_session)
    output_stream = BytesIO()
    workbook.save(output_stream)
    output_stream.seek(0)
    export_file_name = f"product_test_data_{datetime.now().strftime('%y%m%d')}.xlsx"
    return StreamingResponse(
        output_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={export_file_name}"},
    )


@export_router.post("/xlsx/append")
def append_to_existing_excel_sheet(
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    excel_file_path: str = Form(""),
    sheet_name: str = Form(""),
):
    qc_mode_enabled = is_qc_mode_enabled()
    if not qc_mode_enabled:
        ensure_role_allowed(current_role_name, {ROLE_ADMIN, ROLE_MASTER_ADMIN})
    try:
        result = append_test_results_to_existing_workbook(
            database_session=database_session,
            excel_file_path=excel_file_path,
            sheet_name=sheet_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Excel file not found.") from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result
