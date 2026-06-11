from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.auth import ROLE_ADMIN, ROLE_MASTER_ADMIN, ROLE_TESTER
from app.deps import current_role_name_dependency


tester_router = APIRouter(prefix="/user", tags=["tester"])


@tester_router.get("")
def render_tester_dashboard(
    request: Request,
    current_role_name: current_role_name_dependency,
):
    if current_role_name in {ROLE_ADMIN, ROLE_MASTER_ADMIN}:
        return RedirectResponse(url="/admin", status_code=303)
    if current_role_name != ROLE_TESTER:
        return RedirectResponse(url="/login", status_code=303)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="tester_dashboard.html",
        context={
            "request": request,
            "page_title": "Product Test Data Tracing System",
            "recent_test_results": [],
            "current_role_name": current_role_name,
            "current_display_name": (request.cookies.get("phone_number") or "").strip() or "Tester",
            "current_company_name": "",
            "dropdown_options_map": {"field_01": [str(month) for month in range(1, 13)], "field_02": [str(count) for count in range(1, 31)]},
        },
    )
