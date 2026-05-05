from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
import os

from app.auth import ROLE_ADMIN, ROLE_MASTER_ADMIN, ROLE_TESTER, ensure_active_user_limit
from app.deps import database_session_dependency
from app.models import UserAccount
from app.services.dropdown_option_service import list_dropdown_options_for_field
from app.services.ui_sample_profile_service import list_ui_sample_profiles_map


auth_router = APIRouter(tags=["auth"])


def _is_qc_mode_enabled() -> bool:
    return os.getenv("QC_MODE", "True").strip().lower() in {"1", "true", "yes", "on"}


def _build_qc_mode_admin_redirect_response() -> RedirectResponse:
    response = RedirectResponse(url="/admin", status_code=303)
    response.set_cookie("role_name", ROLE_MASTER_ADMIN, httponly=False)
    response.set_cookie("phone_number", "", httponly=False)
    return response


@auth_router.get("/")
def redirect_root_to_login():
    if _is_qc_mode_enabled():
        return _build_qc_mode_admin_redirect_response()
    return RedirectResponse(url="/login", status_code=303)


@auth_router.get("/login")
def render_login_page(
    request: Request,
    database_session: database_session_dependency,
):
    if _is_qc_mode_enabled():
        return _build_qc_mode_admin_redirect_response()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "page_title": "Login",
            "error_message": "",
            "ui_sample_profiles_map": list_ui_sample_profiles_map(database_session),
        },
    )


@auth_router.post("/login")
def handle_login_submission(
    request: Request,
    database_session: database_session_dependency,
    phone_number: str = Form(...),
    password: str = Form(...),
):
    normalized_phone_number = phone_number.strip()
    normalized_password = password.strip()
    user_account = database_session.scalar(
        select(UserAccount).where(UserAccount.phone_number == normalized_phone_number)
    )
    if user_account is None:
        user_account = database_session.scalar(
            select(UserAccount).where(UserAccount.user_name == normalized_phone_number)
        )

    if user_account is None or (user_account.password_hash or "").strip() != normalized_password:
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "request": request,
                "page_title": "Login",
                "error_message": "전화번호 또는 비밀번호가 올바르지 않습니다.",
                "ui_sample_profiles_map": list_ui_sample_profiles_map(database_session),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if user_account.role_name == ROLE_TESTER and not bool(user_account.is_approved):
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "request": request,
                "page_title": "Login",
                "error_message": "Tester 가입 승인이 아직 완료되지 않았습니다. 관리자 승인 후 로그인해 주세요.",
                "ui_sample_profiles_map": list_ui_sample_profiles_map(database_session),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    ensure_active_user_limit(user_name=normalized_phone_number)
    is_admin_role = user_account.role_name in {ROLE_ADMIN, ROLE_MASTER_ADMIN}
    redirect_url = "/admin" if is_admin_role else "/user"
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie("role_name", user_account.role_name, httponly=False)
    response.set_cookie("phone_number", normalized_phone_number, httponly=False)
    return response


@auth_router.get("/join")
def render_join_page(
    request: Request,
    database_session: database_session_dependency,
):
    try:
        join_company_options = list_dropdown_options_for_field(
            database_session=database_session,
            field_name="key_1",
        )
    except Exception:
        join_company_options = []
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="join.html",
        context={
            "request": request,
            "page_title": "Join",
            "error_message": "",
            "success_message": "",
            "join_company_options": join_company_options,
            "ui_sample_profiles_map": list_ui_sample_profiles_map(database_session),
        },
    )


@auth_router.post("/join")
def handle_join_submission(
    request: Request,
    database_session: database_session_dependency,
    company_name: str = Form(...),
    display_name: str = Form(...),
    phone_number: str = Form(...),
    password: str = Form(...),
):
    normalized_company_name = company_name.strip()
    normalized_display_name = display_name.strip()
    normalized_phone_number = phone_number.strip()
    normalized_password = password.strip()
    if not normalized_company_name or not normalized_display_name or not normalized_phone_number or not normalized_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="모든 항목을 입력해 주세요.")

    existing_user_account = database_session.scalar(
        select(UserAccount).where(UserAccount.phone_number == normalized_phone_number)
    )
    try:
        join_company_options = list_dropdown_options_for_field(
            database_session=database_session,
            field_name="key_1",
        )
    except Exception:
        join_company_options = []
    if existing_user_account is not None:
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request,
            name="join.html",
            context={
                "request": request,
                "page_title": "Join",
                "error_message": "이미 등록된 전화번호입니다.",
                "success_message": "",
                "join_company_options": join_company_options,
                "ui_sample_profiles_map": list_ui_sample_profiles_map(database_session),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    new_user_account = UserAccount(
        user_name=normalized_phone_number,
        password_hash=normalized_password,
        role_name=ROLE_TESTER,
        display_name=normalized_display_name,
        phone_number=normalized_phone_number,
        company_name=normalized_company_name,
        department_name=None,
        is_approved=False,
    )
    database_session.add(new_user_account)
    database_session.commit()

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="join.html",
        context={
            "request": request,
            "page_title": "Join",
            "error_message": "",
            "success_message": "회원가입이 완료되었습니다. 로그인해 주세요.",
            "join_company_options": join_company_options,
            "ui_sample_profiles_map": list_ui_sample_profiles_map(database_session),
        },
    )


@auth_router.post("/logout")
def handle_logout_submission():
    if _is_qc_mode_enabled():
        return _build_qc_mode_admin_redirect_response()
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("role_name")
    response.delete_cookie("phone_number")
    return response
