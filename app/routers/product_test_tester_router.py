from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.auth import ROLE_ADMIN, ROLE_MASTER_ADMIN, ROLE_TESTER
from app.deps import current_role_name_dependency, database_session_dependency
from app.models import UserAccount
from app.services.product_test_run_service import (
    BLOCKED_REASON_EXAMPLES,
    DEFECT_PRIORITY_VALUES,
    DEFECT_SEVERITY_VALUES,
    EVIDENCE_TYPE_VALUES,
    SKIPPED_REASON_EXAMPLES,
    finish_run,
    get_run_detail,
    get_product_test_defect_detail,
    list_case_options,
    list_environment_options,
    list_release_options,
    list_runs,
    list_target_options,
    save_defect,
    save_evidence,
    save_procedure_result,
    start_product_test_result,
    start_run,
    cancel_run,
    create_retest_product_test_result_from_defect,
    transition_product_test_defect_to_assigned,
    transition_product_test_defect_to_closed,
    transition_product_test_defect_to_fixed,
    transition_product_test_defect_to_rejected,
    transition_product_test_defect_to_retested,
)
from sqlalchemy import select


product_test_tester_router = APIRouter(prefix="/tester", tags=["product_test_tester"])


def _ensure_tester_role(current_role_name: str) -> None:
    if current_role_name not in {ROLE_TESTER, ROLE_ADMIN, ROLE_MASTER_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This role is not allowed for this action.",
        )


def _get_actor_name(request: Request, database_session) -> str:
    phone_number = (request.cookies.get("phone_number") or "").strip()
    if not phone_number:
        return "TESTER"
    user_account = database_session.scalar(
        select(UserAccount).where(UserAccount.phone_number == phone_number)
    )
    if user_account and (user_account.display_name or "").strip():
        return user_account.display_name.strip()
    return phone_number


def _render_product_test_run_page(
    request: Request,
    *,
    template_name: str,
    context: dict,
):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={"request": request, "page_title": "Product Test Run", **context},
    )


@product_test_tester_router.get("/product-test-runs")
def render_product_test_run_list(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_tester_role(current_role_name)
    return _render_product_test_run_page(
        request,
        template_name="tester_product_test_runs.html",
        context={
            "release_options": list_release_options(database_session),
            "target_options": list_target_options(database_session),
            "environment_options": list_environment_options(database_session),
            "rows": list_runs(database_session),
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
        },
    )


@product_test_tester_router.post("/product-test-runs/start")
def start_product_test_run(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_release_id: str = Form(""),
    product_test_target_id: str = Form(""),
    product_test_environment_id: str = Form(""),
):
    _ensure_tester_role(current_role_name)
    actor_name = _get_actor_name(request, database_session)
    try:
        run = start_run(
            database_session,
            product_test_release_id=product_test_release_id,
            product_test_target_id=product_test_target_id,
            product_test_environment_id=product_test_environment_id,
            started_by=actor_name,
        )
    except ValueError as exception:
        return RedirectResponse(
            url=f"/tester/product-test-runs?message={str(exception)}&message_type=error",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/tester/product-test-runs/{run['product_test_run_id']}?message=Run started&message_type=success",
        status_code=303,
    )


@product_test_tester_router.get("/product-test-runs/{product_test_run_id}")
def render_product_test_run_detail(
    product_test_run_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_tester_role(current_role_name)
    detail = get_run_detail(database_session, product_test_run_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return _render_product_test_run_page(
        request,
        template_name="tester_product_test_run_detail.html",
        context={
            **detail,
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
            "skipped_reason_examples": SKIPPED_REASON_EXAMPLES,
            "blocked_reason_examples": BLOCKED_REASON_EXAMPLES,
            "evidence_type_values": EVIDENCE_TYPE_VALUES,
            "defect_severity_values": DEFECT_SEVERITY_VALUES,
            "defect_priority_values": DEFECT_PRIORITY_VALUES,
        },
    )


@product_test_tester_router.post("/product-test-runs/{product_test_run_id}/finish")
def finish_product_test_run(
    product_test_run_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    transition_reason: str = Form("finish_run"),
):
    _ensure_tester_role(current_role_name)
    actor_name = _get_actor_name(request, database_session)
    try:
        finish_run(database_session, product_test_run_id=product_test_run_id, finished_by=actor_name, reason=transition_reason)
    except (LookupError, ValueError) as exception:
        return RedirectResponse(
            url=f"/tester/product-test-runs/{product_test_run_id}?message={str(exception)}&message_type=error",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/tester/product-test-runs/{product_test_run_id}?message=Run finished&message_type=success",
        status_code=303,
    )


@product_test_tester_router.post("/product-test-runs/{product_test_run_id}/cancel")
def cancel_product_test_run(
    product_test_run_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    transition_reason: str = Form("cancel_run"),
):
    _ensure_tester_role(current_role_name)
    actor_name = _get_actor_name(request, database_session)
    try:
        cancel_run(database_session, product_test_run_id=product_test_run_id, cancelled_by=actor_name, reason=transition_reason)
    except (LookupError, ValueError) as exception:
        return RedirectResponse(
            url=f"/tester/product-test-runs/{product_test_run_id}?message={str(exception)}&message_type=error",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/tester/product-test-runs/{product_test_run_id}?message=Run cancelled&message_type=success",
        status_code=303,
    )


@product_test_tester_router.post("/product-test-results/start")
def start_product_test_result_route(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_run_id: str = Form(""),
    product_test_case_id: str = Form(""),
):
    _ensure_tester_role(current_role_name)
    actor_name = _get_actor_name(request, database_session)
    try:
        start_product_test_result(
            database_session,
            product_test_run_id=product_test_run_id,
            product_test_case_id=product_test_case_id,
            started_by=actor_name,
        )
    except (LookupError, ValueError) as exception:
        return RedirectResponse(
            url=f"/tester/product-test-runs/{product_test_run_id}?message={str(exception)}&message_type=error",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/tester/product-test-runs/{product_test_run_id}?message=Test result started&message_type=success",
        status_code=303,
    )


@product_test_tester_router.post("/product-test-procedure-results/save")
def save_product_test_procedure_result_route(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_run_id: str = Form(""),
    product_test_result_id: str = Form(""),
    product_test_procedure_result_id: str = Form(""),
    product_test_procedure_result_status: str = Form("testing"),
    actual_result: str = Form(""),
    judgement_reason: str = Form(""),
    remark: str = Form(""),
):
    _ensure_tester_role(current_role_name)
    actor_name = _get_actor_name(request, database_session)
    try:
        save_procedure_result(
            database_session,
            product_test_result_id=product_test_result_id,
            product_test_procedure_result_id=product_test_procedure_result_id,
            next_status=product_test_procedure_result_status,
            actual_result=actual_result,
            judgement_reason=judgement_reason,
            remark=remark,
            updated_by=actor_name,
        )
    except (LookupError, ValueError) as exception:
        return RedirectResponse(
            url=f"/tester/product-test-runs/{product_test_run_id}?message={str(exception)}&message_type=error",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/tester/product-test-runs/{product_test_run_id}?message=Procedure result saved&message_type=success",
        status_code=303,
    )


@product_test_tester_router.post("/product-test-evidence/save")
def save_product_test_evidence_route(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_run_id: str = Form(""),
    product_test_result_id: str = Form(""),
    product_test_procedure_result_id: str = Form(""),
    product_test_defect_id: str = Form(""),
    product_test_evidence_type: str = Form(""),
    file_path: str = Form(""),
    remark: str = Form(""),
):
    _ensure_tester_role(current_role_name)
    actor_name = _get_actor_name(request, database_session)
    try:
        save_evidence(
            database_session,
            product_test_result_id=product_test_result_id,
            product_test_procedure_result_id=product_test_procedure_result_id,
            product_test_defect_id=product_test_defect_id,
            product_test_evidence_type=product_test_evidence_type,
            file_path=file_path,
            created_by=actor_name,
            remark=remark,
        )
    except (LookupError, ValueError) as exception:
        if str(product_test_defect_id or "").strip():
            return RedirectResponse(
                url=f"/tester/product-test-defects/{product_test_defect_id}?message={str(exception)}&message_type=error",
                status_code=303,
            )
        return RedirectResponse(
            url=f"/tester/product-test-runs/{product_test_run_id}?message={str(exception)}&message_type=error",
            status_code=303,
        )
    if str(product_test_defect_id or "").strip():
        return RedirectResponse(
            url=f"/tester/product-test-defects/{product_test_defect_id}?message=Evidence attached&message_type=success",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/tester/product-test-runs/{product_test_run_id}?message=Evidence attached&message_type=success",
        status_code=303,
    )


@product_test_tester_router.post("/product-test-defects/save")
def save_product_test_defect_route(
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_run_id: str = Form(""),
    product_test_result_id: str = Form(""),
    product_test_procedure_result_id: str = Form(""),
    defect_title: str = Form(""),
    defect_description: str = Form(""),
    defect_severity: str = Form(""),
    defect_priority: str = Form(""),
    assigned_to: str = Form(""),
    remark: str = Form(""),
):
    _ensure_tester_role(current_role_name)
    actor_name = _get_actor_name(request, database_session)
    try:
        save_defect(
            database_session,
            product_test_result_id=product_test_result_id,
            product_test_procedure_result_id=product_test_procedure_result_id,
            defect_title=defect_title,
            defect_description=defect_description,
            defect_severity=defect_severity,
            defect_priority=defect_priority,
            assigned_to=assigned_to,
            created_by=actor_name,
            remark=remark,
        )
    except (LookupError, ValueError) as exception:
        return RedirectResponse(
            url=f"/tester/product-test-runs/{product_test_run_id}?message={str(exception)}&message_type=error",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/tester/product-test-runs/{product_test_run_id}?message=Defect registered&message_type=success",
        status_code=303,
    )


@product_test_tester_router.get("/product-test-defects/{product_test_defect_id}")
def render_product_test_defect_detail(
    product_test_defect_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
):
    _ensure_tester_role(current_role_name)
    try:
        detail = get_product_test_defect_detail(database_session, product_test_defect_id)
    except LookupError as exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exception)) from exception
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Defect not found.")
    return _render_product_test_run_page(
        request,
        template_name="tester_product_test_defect_detail.html",
        context={
            **detail,
            "message": (request.query_params.get("message") or "").strip(),
            "message_type": (request.query_params.get("message_type") or "info").strip(),
            "evidence_type_values": EVIDENCE_TYPE_VALUES,
            "rejection_reason_examples": [
                "not_reproducible",
                "duplicate",
                "not_a_defect",
                "test_error",
                "environment_issue",
                "out_of_scope",
            ],
        },
    )


@product_test_tester_router.post("/product-test-defects/{product_test_defect_id}/assign")
def assign_product_test_defect_route(
    product_test_defect_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    assigned_to: str = Form(""),
    transition_reason: str = Form(""),
):
    _ensure_tester_role(current_role_name)
    try:
        transition_product_test_defect_to_assigned(
            database_session,
            product_test_defect_id=product_test_defect_id,
            assigned_to=assigned_to,
            transition_reason=transition_reason,
            transitioned_by=_get_actor_name(request, database_session),
        )
    except (LookupError, ValueError) as exception:
        return RedirectResponse(url=f"/tester/product-test-defects/{product_test_defect_id}?message={str(exception)}&message_type=error", status_code=303)
    return RedirectResponse(url=f"/tester/product-test-defects/{product_test_defect_id}?message=Defect assigned&message_type=success", status_code=303)


@product_test_tester_router.post("/product-test-defects/{product_test_defect_id}/fix")
def fix_product_test_defect_route(
    product_test_defect_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    fix_description: str = Form(""),
    transition_reason: str = Form(""),
):
    _ensure_tester_role(current_role_name)
    try:
        transition_product_test_defect_to_fixed(
            database_session,
            product_test_defect_id=product_test_defect_id,
            fix_description=fix_description,
            transition_reason=transition_reason,
            transitioned_by=_get_actor_name(request, database_session),
        )
    except (LookupError, ValueError) as exception:
        return RedirectResponse(url=f"/tester/product-test-defects/{product_test_defect_id}?message={str(exception)}&message_type=error", status_code=303)
    return RedirectResponse(url=f"/tester/product-test-defects/{product_test_defect_id}?message=Defect fixed&message_type=success", status_code=303)


@product_test_tester_router.post("/product-test-defects/{product_test_defect_id}/create-retest-result")
def create_retest_result_from_defect_route(
    product_test_defect_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    product_test_run_id: str = Form(""),
):
    _ensure_tester_role(current_role_name)
    try:
        result = create_retest_product_test_result_from_defect(
            database_session,
            product_test_defect_id=product_test_defect_id,
            product_test_run_id=product_test_run_id,
            started_by=_get_actor_name(request, database_session),
        )
    except (LookupError, ValueError) as exception:
        return RedirectResponse(url=f"/tester/product-test-defects/{product_test_defect_id}?message={str(exception)}&message_type=error", status_code=303)
    return RedirectResponse(url=f"/tester/product-test-runs/{result['product_test_run_id']}?message=Retest result created&message_type=success", status_code=303)


@product_test_tester_router.post("/product-test-defects/{product_test_defect_id}/retested")
def mark_product_test_defect_retested_route(
    product_test_defect_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    retest_product_test_result_id: str = Form(""),
    transition_reason: str = Form(""),
):
    _ensure_tester_role(current_role_name)
    try:
        transition_product_test_defect_to_retested(
            database_session,
            product_test_defect_id=product_test_defect_id,
            retest_product_test_result_id=retest_product_test_result_id,
            transition_reason=transition_reason,
            transitioned_by=_get_actor_name(request, database_session),
        )
    except (LookupError, ValueError) as exception:
        return RedirectResponse(url=f"/tester/product-test-defects/{product_test_defect_id}?message={str(exception)}&message_type=error", status_code=303)
    return RedirectResponse(url=f"/tester/product-test-defects/{product_test_defect_id}?message=Defect retested&message_type=success", status_code=303)


@product_test_tester_router.post("/product-test-defects/{product_test_defect_id}/close")
def close_product_test_defect_route(
    product_test_defect_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    transition_reason: str = Form(""),
):
    _ensure_tester_role(current_role_name)
    try:
        transition_product_test_defect_to_closed(
            database_session,
            product_test_defect_id=product_test_defect_id,
            transition_reason=transition_reason,
            transitioned_by=_get_actor_name(request, database_session),
        )
    except (LookupError, ValueError) as exception:
        return RedirectResponse(url=f"/tester/product-test-defects/{product_test_defect_id}?message={str(exception)}&message_type=error", status_code=303)
    return RedirectResponse(url=f"/tester/product-test-defects/{product_test_defect_id}?message=Defect closed&message_type=success", status_code=303)


@product_test_tester_router.post("/product-test-defects/{product_test_defect_id}/reject")
def reject_product_test_defect_route(
    product_test_defect_id: str,
    request: Request,
    database_session: database_session_dependency,
    current_role_name: current_role_name_dependency,
    rejection_reason: str = Form(""),
    transition_reason: str = Form(""),
):
    _ensure_tester_role(current_role_name)
    try:
        transition_product_test_defect_to_rejected(
            database_session,
            product_test_defect_id=product_test_defect_id,
            rejection_reason=rejection_reason,
            transition_reason=transition_reason,
            transitioned_by=_get_actor_name(request, database_session),
        )
    except (LookupError, ValueError) as exception:
        return RedirectResponse(url=f"/tester/product-test-defects/{product_test_defect_id}?message={str(exception)}&message_type=error", status_code=303)
    return RedirectResponse(url=f"/tester/product-test-defects/{product_test_defect_id}?message=Defect rejected&message_type=success", status_code=303)
