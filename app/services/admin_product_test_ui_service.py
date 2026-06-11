"""관리자 통합 화면(admin_dashboard)용 UI 보조 로직.

식별자 후보 생성·검증·입력 순서 판단은 브라우저가 아닌 이 모듈(및 API)에서만 수행한다.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.product_test_run_service import (
    get_product_test_identifier_client_rules,
    get_product_test_identifier_guides,
)


def _js_like_normalize_segment(value: str) -> str:
    """기존 admin_dashboard.html 의 ``normalizeSegment`` 와 동일한 규칙."""
    normalized = str(value or "").strip()
    normalized = normalized.replace("?", " UNKNOWN ")
    normalized = normalized.replace("(", " ").replace(")", " ")
    normalized = re.sub(r"[/\\\s:\*|\"'<>-]+", "_", normalized)
    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_").upper()


def _unique_nonempty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        text = str(raw or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _read_strings(primary: str | None, hints: list[str] | None) -> list[str]:
    parts: list[str] = []
    if primary and str(primary).strip():
        parts.append(str(primary).strip())
    for item in hints or []:
        if str(item).strip():
            parts.append(str(item).strip())
    return _unique_nonempty(parts)


def _strip_prefix(value: str, prefix: str) -> str:
    text = str(value or "").strip()
    return text[len(prefix) :] if text.startswith(prefix) else text


def _capture_date_digits(value: str) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    return digits[:8] if len(digits) >= 8 else ""


def _build_case_title_core(title_value: str) -> str:
    core = _js_like_normalize_segment(title_value)
    core = re.sub(r"^WIFI_AP_", "AP_", core)
    core = re.sub(r"^PRODUCT_TEST_", "", core)
    core = core[:24]
    core = re.sub(r"_+$", "", core)
    return core


def _build_release_id_candidate(upstream_value: str, stage_value: str) -> str:
    upstream = str(upstream_value or "").strip()
    stage = str(stage_value or "").strip().upper()
    if not upstream or not stage:
        return ""
    stage_display = "GA" if stage == "GA" else f"{stage}1"
    return f"SQA_PRODUCT_TEST_RELEASE_ID-{upstream}-{stage_display}"



def _build_target_id_candidate(model_value: str, serial_value: str) -> str:
    model_core = _js_like_normalize_segment(model_value)
    serial_core = str(serial_value or "").strip()
    if not model_core or not serial_core:
        return ""
    return f"SQA_PRODUCT_TEST_TARGET_ID-{model_core}-{serial_core}"


def _build_environment_template_id_candidate(
    company_value: str,
    city_value: str,
    room_value: str,
) -> str:
    company = _js_like_normalize_segment(company_value)
    city = _js_like_normalize_segment(city_value)
    room = _js_like_normalize_segment(room_value)
    if not company or not city or not room:
        return ""
    return f"SQA_PRODUCT_TEST_ENVIRONMENT_DEFINITION_ID-{company}-{city}-{room}"


def _build_environment_id_candidate(definition_value: str, captured_at_value: str) -> str:
    definition_core = _strip_prefix(definition_value, "SQA_PRODUCT_TEST_ENVIRONMENT_DEFINITION_ID-")
    date_digits = _capture_date_digits(captured_at_value)
    if not definition_core or not date_digits:
        return ""
    return f"SQA_PRODUCT_TEST_ENVIRONMENT_ID-{definition_core}-{date_digits}-001"


def _build_case_id_candidate(category_value: str, title_value: str) -> str:
    category = _js_like_normalize_segment(category_value)
    title_core = _build_case_title_core(title_value) or "ITEM"
    if not category:
        return ""
    return f"SQA_PRODUCT_TEST_CASE_ID-{category}-{title_core}-001"


def _build_procedure_id_candidate(case_value: str, sequence_value: str) -> str:
    case_core = _strip_prefix(case_value, "SQA_PRODUCT_TEST_CASE_ID-")
    try:
        parsed_sequence = int(str(sequence_value or "").strip(), 10)
    except ValueError:
        return ""
    if not case_core:
        return ""
    return f"SQA_PRODUCT_TEST_PROCEDURE_ID-{case_core}-{str(parsed_sequence).zfill(3)}"


ADMIN_PRODUCT_TEST_WRITE_ORDER_PLANS: dict[str, dict[str, Any]] = {
    "/admin": {
        "order": [
            "upstream_release_id",
            "upstream_release_system",
            "release_stage",
            "test_round_id",
            "product_test_round_status",
            "remark",
        ],
        "optional": ["remark"],
    },
    "/admin/product-test-targets/create": {
        "order": [
            "manufacturer",
            "model_name",
            "product_code",
            "serial_number",
            "product_test_target_id",
            "hardware_revision",
            "default_software_version",
            "default_firmware_version",
            "software_version",
            "firmware_version",
            "manufacture_lot",
            "product_test_target_status",
            "remark",
        ],
        "optional": [
            "product_code",
            "hardware_revision",
            "default_software_version",
            "default_firmware_version",
            "software_version",
            "firmware_version",
            "manufacture_lot",
            "product_test_target_status",
            "remark",
        ],
    },
    "/admin/product-test-environments/create": {
        "order": [
            "product_test_environment_name",
            "test_company",
            "test_city",
            "test_room",
            "captured_at",
            "product_test_environment_id",
            "test_country",
            "test_building",
            "test_floor",
            "test_computer_name",
            "operating_system_version",
            "test_tool_name",
            "test_tool_version",
            "network_type",
            "power_voltage",
            "power_frequency",
            "power_connector_type",
            "power_condition",
            "product_test_environment_status",
            "remark",
        ],
        "optional": [
            "test_country",
            "test_building",
            "test_floor",
            "test_computer_name",
            "operating_system_version",
            "test_tool_name",
            "test_tool_version",
            "network_type",
            "power_voltage",
            "power_frequency",
            "power_connector_type",
            "power_condition",
            "product_test_environment_status",
            "remark",
        ],
    },
    "/admin/product-test-cases/create": {
        "order": [
            "test_category",
            "product_test_case_title",
            "product_test_case_id",
            "test_objective",
            "precondition",
            "expected_result",
            "product_test_case_status",
            "remark",
        ],
        "optional": [
            "test_objective",
            "precondition",
            "expected_result",
            "product_test_case_status",
            "remark",
        ],
    },
    "/admin/product-test-procedures/create": {
        "order": [
            "product_test_case_id",
            "procedure_sequence",
            "product_test_procedure_id",
            "procedure_action",
            "acceptance_criteria",
            "required_evidence_type",
            "product_test_procedure_status",
            "remark",
        ],
        "optional": [
            "required_evidence_type",
            "product_test_procedure_status",
            "remark",
        ],
    },
    "/admin/product-test-reports/create": {
        "order": ["test_round_id", "product_test_report_type", "product_test_report_title", "remark"],
        "optional": ["remark"],
    },
}


def get_admin_product_test_ui_client_config_payload() -> dict[str, Any]:
    """GET ``/admin/api/product-test/ui/client-config`` 응답 본문."""
    plans: dict[str, Any] = {}
    for action, plan in ADMIN_PRODUCT_TEST_WRITE_ORDER_PLANS.items():
        plans[action] = {"order": list(plan["order"]), "optional": list(plan.get("optional", []))}
    return {
        "id_rules": get_product_test_identifier_client_rules(),
        "id_guides": get_product_test_identifier_guides(),
        "write_order_plans": plans,
    }


def list_product_test_id_candidates(
    *,
    form_action: str,
    field_name: str,
    values: dict[str, str],
    datalist_hints: dict[str, list[str]] | None = None,
) -> list[str]:
    hints = datalist_hints or {}
    action = str(form_action or "").strip()
    fn = str(field_name or "").strip()

    def gv(name: str) -> str:
        return str(values.get(name, "") or "").strip()

    def hint(name: str) -> list[str] | None:
        raw = hints.get(name)
        return list(raw) if isinstance(raw, list) else None

    if fn == "test_round_id" and (
        action.endswith("/product-test-rounds/create") or action.rstrip("/") == "/admin"
    ):
        upstreams = _read_strings(gv("upstream_release_id"), hint("upstream_release_id"))
        stages = _read_strings(gv("release_stage"), hint("release_stage"))
        out: list[str] = []
        for u in upstreams:
            for s in stages:
                c = _build_release_id_candidate(u, s)
                if c:
                    out.append(c)
        return _unique_nonempty(out)

    if fn == "product_test_target_id" and action.endswith("/product-test-targets/create"):
        models = _read_strings(gv("model_name"), hint("model_name"))
        serials = _read_strings(gv("serial_number"), hint("serial_number"))
        out3: list[str] = []
        for model in models:
            for serial in serials:
                c = _build_target_id_candidate(model, serial)
                if c:
                    out3.append(c)
        return _unique_nonempty(out3)

    if fn == "product_test_environment_id" and action.endswith("/product-test-environments/create"):
        companies = _read_strings(gv("test_company"), hint("test_company"))
        cities = _read_strings(gv("test_city"), hint("test_city"))
        rooms = _read_strings(gv("test_room"), hint("test_room"))
        caps = _read_strings(gv("captured_at"), hint("captured_at"))
        out5: list[str] = []
        for co in companies:
            for ci in cities:
                for room in rooms:
                    definition_id = _build_environment_template_id_candidate(co, ci, room)
                    if not definition_id:
                        continue
                    for cap in caps:
                        c = _build_environment_id_candidate(definition_id, cap)
                        if c:
                            out5.append(c)
        return _unique_nonempty(out5)

    if fn == "product_test_case_id" and action.endswith("/product-test-cases/create"):
        cats = _read_strings(gv("test_category"), hint("test_category"))
        titles = _read_strings(gv("product_test_case_title"), hint("product_test_case_title"))
        out6: list[str] = []
        for cat in cats:
            for t in titles:
                c = _build_case_id_candidate(cat, t)
                if c:
                    out6.append(c)
        return _unique_nonempty(out6)

    if fn == "product_test_procedure_id" and action.endswith("/product-test-procedures/create"):
        cases = _read_strings(gv("product_test_case_id"), hint("product_test_case_id"))
        seqs = _read_strings(gv("procedure_sequence"), hint("procedure_sequence"))
        out7: list[str] = []
        for case in cases:
            for seq in seqs:
                c = _build_procedure_id_candidate(case, seq)
                if c:
                    out7.append(c)
        return _unique_nonempty(out7)

    return []


def validate_product_test_identifier_values(values: dict[str, str]) -> list[dict[str, str]]:
    """비어 있지 않은 식별자 필드만 검사. 위반 시 ``field`` / ``message`` dict 목록."""
    rules = get_product_test_identifier_client_rules()
    guides = get_product_test_identifier_guides()
    errors: list[dict[str, str]] = []
    for field_name, pattern_text in rules.items():
        value = str(values.get(field_name, "") or "").strip()
        if not value:
            continue
        if "/" in value or "\\" in value or re.search(r"\s", value):
            errors.append(
                {
                    "field": field_name,
                    "message": guides.get(field_name, f"{field_name} 형식이 맞지 않습니다. 수정하세요."),
                }
            )
            continue
        if not re.fullmatch(pattern_text, value):
            errors.append(
                {
                    "field": field_name,
                    "message": guides.get(field_name, f"{field_name} 형식이 맞지 않습니다. 수정하세요."),
                }
            )
    return errors


def get_first_blocking_prerequisite_field(
    *,
    form_action: str,
    target_field_name: str,
    values: dict[str, str],
) -> str | None:
    """선행 필수 입력이 비어 있으면 그 ``name`` 을, 없으면 ``None``."""
    plan = ADMIN_PRODUCT_TEST_WRITE_ORDER_PLANS.get(str(form_action or "").strip())
    if not plan:
        return None
    order = list(plan["order"])
    optional = set(plan.get("optional", []))
    try:
        idx = order.index(str(target_field_name or "").strip())
    except ValueError:
        return None
    if idx <= 0:
        return None
    for name in order[:idx]:
        if name in optional:
            continue
        if not str(values.get(name, "") or "").strip():
            return name
    return None
