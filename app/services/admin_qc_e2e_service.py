from __future__ import annotations

import re
import threading
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait


FIELD_INTERVAL_SECONDS = 0.2
TYPE_INTERVAL_SECONDS = 0.03
FORM_SETTLE_SECONDS = 2.2
PAGE_SETTLE_SECONDS = 0.8
REMOTE_DEBUGGING_ADDRESS = "127.0.0.1:9222"

_run_state_lock = threading.Lock()
_is_running = False


def _normalize_segment(value: str) -> str:
    normalized = str(value or "").strip()
    normalized = normalized.replace("?", " UNKNOWN ")
    normalized = re.sub(r"[()]", " ", normalized)
    normalized = re.sub(r"[\/\\\s:\*\|\"'<>\-]+", "_", normalized)
    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_").upper()


def _build_case_title_core(title_value: str) -> str:
    normalized = _normalize_segment(title_value or "")
    normalized = re.sub(r"^WIFI_AP_", "AP_", normalized)
    normalized = re.sub(r"^PRODUCT_TEST_", "", normalized)
    normalized = normalized[:24]
    return normalized.rstrip("_")


def _build_release_id(upstream_value: str, stage_value: str) -> str:
    stage = str(stage_value or "").strip().upper()
    stage_display = "GA" if stage == "GA" else f"{stage}1"
    return f"QA_PTREL-{str(upstream_value).strip()}-{stage_display}"


def _build_target_definition_id(model_value: str) -> str:
    return f"QA_PTTGTDEF-{_normalize_segment(model_value)}"


def _build_target_id(definition_id: str, serial_number: str) -> str:
    core = str(definition_id or "").strip().removeprefix("QA_PTTGTDEF-")
    return f"QA_PTTGT-{core}-{str(serial_number or '').strip()}"


def _build_environment_definition_id(company: str, city: str, room: str) -> str:
    return f"QA_PTENVDEF-{_normalize_segment(company)}-{_normalize_segment(city)}-{_normalize_segment(room)}"


def _build_environment_id(definition_id: str, captured_at: str) -> str:
    core = str(definition_id or "").strip().removeprefix("QA_PTENVDEF-")
    date_digits = re.sub(r"\D+", "", str(captured_at or ""))[:8]
    return f"QA_PTENV-{core}-{date_digits}-001"


def _build_case_id(category: str, title: str) -> str:
    return f"QA_PTCASE-{_normalize_segment(category)}-{_build_case_title_core(title)}-001"


def _build_procedure_id(case_id: str, sequence: int) -> str:
    return f"QA_PTPROC-{str(case_id or '').strip().removeprefix('QA_PTCASE-')}-{int(sequence):03d}"


def _build_example_payload() -> dict[str, str]:
    stamp = time.strftime("%Y%m%d%H%M%S")
    compact = stamp[-6:]

    upstream_release_id = f"QC_E2E_{stamp}"
    release_stage = "RC"
    product_test_release_id = _build_release_id(upstream_release_id, release_stage)

    product_code = f"QC_E2E_{compact}"
    model_name = f"QC E2E Model {compact}"
    target_definition_id = _build_target_definition_id(model_name)
    serial_number = f"SN{compact}"
    target_id = _build_target_id(target_definition_id, serial_number)

    company_name = "Huvitz"
    city_name = "Anyang"
    room_name = f"QC Lab {compact}"
    environment_definition_id = _build_environment_definition_id(company_name, city_name, room_name)
    captured_at = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} 09:00:00"
    environment_id = _build_environment_id(environment_definition_id, captured_at)

    case_title = f"WiFi AP QC E2E {compact}"
    case_category = "WIFI"
    case_id = _build_case_id(case_category, case_title)
    procedure_sequence = 1
    procedure_id = _build_procedure_id(case_id, procedure_sequence)

    return {
        "upstream_release_id": upstream_release_id,
        "release_stage": release_stage,
        "product_test_release_id": product_test_release_id,
        "product_code": product_code,
        "model_name": model_name,
        "target_definition_id": target_definition_id,
        "serial_number": serial_number,
        "target_id": target_id,
        "environment_definition_id": environment_definition_id,
        "captured_at": captured_at,
        "environment_id": environment_id,
        "case_title": case_title,
        "case_category": case_category,
        "case_id": case_id,
        "procedure_sequence": str(procedure_sequence),
        "procedure_id": procedure_id,
        "report_title": f"QC E2E REPORT {compact}",
    }


def _fill_text_like_field(field, value: str) -> None:
    field.click()
    field.send_keys(Keys.CONTROL, "a")
    field.send_keys(Keys.BACKSPACE)
    for character in str(value or ""):
        field.send_keys(character)
        time.sleep(TYPE_INTERVAL_SECONDS)
    time.sleep(FIELD_INTERVAL_SECONDS)


def _fill_select_field(field, value: str) -> None:
    select = Select(field)
    target = str(value or "").strip()
    matched = False
    for option in select.options:
        option_value = str(option.get_attribute("value") or "").strip()
        option_text = str(option.text or "").strip()
        if target and (option_value == target or option_text == target):
            select.select_by_value(option_value)
            matched = True
            break
    if not matched:
        for option in select.options:
            option_value = str(option.get_attribute("value") or "").strip()
            if option_value:
                select.select_by_value(option_value)
                break
    time.sleep(FIELD_INTERVAL_SECONDS)


def _find_form(driver, action_suffix: str):
    selector = f"form.admin_autosubmit_form[action$='{action_suffix}']"
    return WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )


def _find_named_field(form, field_name: str):
    return form.find_element(By.CSS_SELECTOR, f"[name='{field_name}']")


def _fill_field(form, field_name: str, value: str) -> None:
    field = _find_named_field(form, field_name)
    tag_name = (field.tag_name or "").lower()
    if tag_name == "select":
        _fill_select_field(field, value)
        return
    _fill_text_like_field(field, value)


def _wait_for_form_submission_cycle() -> None:
    time.sleep(FORM_SETTLE_SECONDS)


def _open_admin_page(driver, admin_url: str) -> None:
    driver.get(admin_url)
    WebDriverWait(driver, 10).until(
        lambda target_driver: target_driver.execute_script("return document.readyState") == "complete"
    )
    time.sleep(PAGE_SETTLE_SECONDS)


def _connect_driver() -> webdriver.Chrome:
    options = Options()
    options.add_experimental_option("debuggerAddress", REMOTE_DEBUGGING_ADDRESS)
    return webdriver.Chrome(options=options)


def _run_fill_sequence(admin_url: str) -> None:
    payload = _build_example_payload()
    driver = _connect_driver()
    try:
        _open_admin_page(driver, admin_url)

        release_form = _find_form(driver, "/admin/product-test-releases/create")
        _fill_field(release_form, "upstream_release_id", payload["upstream_release_id"])
        _fill_field(release_form, "upstream_release_system", "QC E2E Release System")
        _fill_field(release_form, "product_test_release_status", "DRAFT")
        _fill_field(release_form, "remark", "QC MODE E2E release sample")
        _fill_field(release_form, "product_test_release_id", payload["product_test_release_id"])
        _fill_field(release_form, "release_stage", payload["release_stage"])
        _wait_for_form_submission_cycle()
        _open_admin_page(driver, admin_url)

        definition_form = _find_form(driver, "/admin/product-test-target-definitions/create")
        _fill_field(definition_form, "product_code", payload["product_code"])
        _fill_field(definition_form, "hardware_revision", "REV-A")
        _fill_field(definition_form, "default_software_version", "1.0.0")
        _fill_field(definition_form, "default_firmware_version", "1.0.0")
        _fill_field(definition_form, "product_test_target_definition_status", "ACTIVE")
        _fill_field(definition_form, "remark", "QC MODE E2E target definition sample")
        _fill_field(definition_form, "model_name", payload["model_name"])
        _fill_field(definition_form, "product_test_target_definition_id", payload["target_definition_id"])
        _fill_field(definition_form, "manufacturer", "Huvitz")
        _wait_for_form_submission_cycle()
        _open_admin_page(driver, admin_url)

        target_form = _find_form(driver, "/admin/product-test-targets/create")
        _fill_field(target_form, "software_version", "1.0.0")
        _fill_field(target_form, "firmware_version", "1.0.0")
        _fill_field(target_form, "manufacture_lot", f"LOT-{payload['upstream_release_id']}")
        _fill_field(target_form, "product_test_target_status", "ACTIVE")
        _fill_field(target_form, "remark", "QC MODE E2E target sample")
        _fill_field(target_form, "serial_number", payload["serial_number"])
        _fill_field(target_form, "product_test_target_id", payload["target_id"])
        _fill_field(target_form, "product_test_target_definition_id", payload["target_definition_id"])
        _wait_for_form_submission_cycle()
        _open_admin_page(driver, admin_url)

        environment_definition_form = _find_form(driver, "/admin/product-test-environment-definitions/create")
        _fill_field(environment_definition_form, "test_country", "Korea")
        _fill_field(environment_definition_form, "test_city", "Anyang")
        _fill_field(environment_definition_form, "test_company", "Huvitz")
        _fill_field(environment_definition_form, "test_room", f"QC Lab {payload['upstream_release_id'][-6:]}")
        _fill_field(environment_definition_form, "network_type", "ISOLATED_NETWORK")
        _fill_field(environment_definition_form, "test_computer_name", "QC-E2E-PC")
        _fill_field(environment_definition_form, "operating_system_version", "Windows 10")
        _fill_field(environment_definition_form, "test_tool_name", "Product Test Tool")
        _fill_field(environment_definition_form, "test_tool_version", "1.0.0")
        _fill_field(environment_definition_form, "power_voltage", "220V")
        _fill_field(environment_definition_form, "power_frequency", "60Hz")
        _fill_field(environment_definition_form, "power_connector_type", "QC_CONNECTOR")
        _fill_field(environment_definition_form, "power_condition", "Commercial AC power")
        _fill_field(environment_definition_form, "product_test_environment_definition_status", "ACTIVE")
        _fill_field(environment_definition_form, "remark", "QC MODE E2E environment definition sample")
        _fill_field(environment_definition_form, "product_test_environment_definition_id", payload["environment_definition_id"])
        _fill_field(
            environment_definition_form,
            "product_test_environment_definition_name",
            f"Huvitz Anyang QC E2E Environment {payload['upstream_release_id'][-6:]}",
        )
        _wait_for_form_submission_cycle()
        _open_admin_page(driver, admin_url)

        environment_form = _find_form(driver, "/admin/product-test-environments/create")
        _fill_field(environment_form, "test_computer_name", "QC-E2E-PC")
        _fill_field(environment_form, "operating_system_version", "Windows 10")
        _fill_field(environment_form, "test_tool_version", "1.0.0")
        _fill_field(environment_form, "network_type", "ISOLATED_NETWORK")
        _fill_field(environment_form, "power_voltage", "220V")
        _fill_field(environment_form, "power_frequency", "60Hz")
        _fill_field(environment_form, "power_connector_type", "QC_CONNECTOR")
        _fill_field(environment_form, "captured_at", payload["captured_at"])
        _fill_field(environment_form, "product_test_environment_status", "ACTIVE")
        _fill_field(environment_form, "remark", "QC MODE E2E environment sample")
        _fill_field(environment_form, "product_test_environment_id", payload["environment_id"])
        _fill_field(
            environment_form,
            "product_test_environment_name",
            f"QC E2E Environment Snapshot {payload['upstream_release_id'][-6:]}",
        )
        _fill_field(
            environment_form,
            "product_test_environment_definition_id",
            payload["environment_definition_id"],
        )
        _wait_for_form_submission_cycle()
        _open_admin_page(driver, admin_url)

        case_form = _find_form(driver, "/admin/product-test-cases/create")
        _fill_field(case_form, "test_objective", "QC MODE E2E objective sample")
        _fill_field(case_form, "precondition", "Admin dashboard opened in QC mode")
        _fill_field(case_form, "expected_result", "All cards accept example values")
        _fill_field(case_form, "product_test_case_status", "ACTIVE")
        _fill_field(case_form, "remark", "QC MODE E2E case sample")
        _fill_field(case_form, "product_test_case_title", payload["case_title"])
        _fill_field(case_form, "test_category", payload["case_category"])
        _fill_field(case_form, "product_test_case_id", payload["case_id"])
        _wait_for_form_submission_cycle()
        _open_admin_page(driver, admin_url)

        procedure_form = _find_form(driver, "/admin/product-test-procedures/create")
        _fill_field(procedure_form, "expected_result", "Field-by-field E2E input succeeds")
        _fill_field(procedure_form, "required_evidence_type", "screenshot")
        _fill_field(procedure_form, "product_test_procedure_status", "ACTIVE")
        _fill_field(procedure_form, "remark", "QC MODE E2E procedure sample")
        _fill_field(procedure_form, "product_test_case_id", payload["case_id"])
        _fill_field(procedure_form, "procedure_sequence", payload["procedure_sequence"])
        _fill_field(procedure_form, "acceptance_criteria", "No duplicate-id or validation errors")
        _fill_field(procedure_form, "product_test_procedure_id", payload["procedure_id"])
        _fill_field(procedure_form, "procedure_action", "Fill admin cards by selenium")
        _wait_for_form_submission_cycle()
        _open_admin_page(driver, admin_url)

        report_form = _find_form(driver, "/admin/product-test-reports/create")
        _fill_field(report_form, "remark", "QC MODE E2E report sample")
        _fill_field(report_form, "product_test_report_type", "FULL")
        _fill_field(report_form, "product_test_report_title", payload["report_title"])
        _fill_field(report_form, "product_test_release_id", payload["product_test_release_id"])
        _wait_for_form_submission_cycle()
    finally:
        try:
            driver.stop_client()
        except Exception:
            pass
        try:
            driver.service.stop()
        except Exception:
            pass


def _run_fill_sequence_thread(admin_url: str) -> None:
    global _is_running
    try:
        _run_fill_sequence(admin_url)
    finally:
        with _run_state_lock:
            _is_running = False


def start_admin_qc_e2e_fill(admin_url: str) -> tuple[bool, str]:
    global _is_running
    with _run_state_lock:
        if _is_running:
            return False, "E2E Test already running."
        _is_running = True
    thread = threading.Thread(
        target=_run_fill_sequence_thread,
        args=(str(admin_url or "").strip(),),
        daemon=True,
    )
    thread.start()
    return True, "E2E Test started."
