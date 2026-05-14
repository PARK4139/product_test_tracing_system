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


# 자동제출 스크립트는 input/change 후 600ms 디바운스 뒤 POST 한다(admin_dashboard.html).
FIELD_INTERVAL_SECONDS = 0.05
FORM_SETTLE_SECONDS = 1.05
PAGE_SETTLE_SECONDS = 0.35
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
    return f"SQA_PRODUCT_TEST_RELEASE_ID-{str(upstream_value).strip()}-{stage_display}"


def _build_target_definition_id(model_value: str) -> str:
    return f"SQA_PRODUCT_TEST_TARGET_DEFINITION_ID-{_normalize_segment(model_value)}"


def _build_target_id(definition_id: str, serial_number: str) -> str:
    core = str(definition_id or "").strip().removeprefix("SQA_PRODUCT_TEST_TARGET_DEFINITION_ID-")
    return f"SQA_PRODUCT_TEST_TARGET_ID-{core}-{str(serial_number or '').strip()}"


def _build_environment_definition_id(company: str, city: str, room: str) -> str:
    return f"SQA_PRODUCT_TEST_ENVIRONMENT_DEFINITION_ID-{_normalize_segment(company)}-{_normalize_segment(city)}-{_normalize_segment(room)}"


def _build_environment_id(definition_id: str, captured_at: str) -> str:
    core = str(definition_id or "").strip().removeprefix("SQA_PRODUCT_TEST_ENVIRONMENT_DEFINITION_ID-")
    date_digits = re.sub(r"\D+", "", str(captured_at or ""))[:8]
    return f"SQA_PRODUCT_TEST_ENVIRONMENT_ID-{core}-{date_digits}-001"


def _build_case_id(category: str, title: str) -> str:
    return f"SQA_PRODUCT_TEST_CASE_ID-{_normalize_segment(category)}-{_build_case_title_core(title)}-001"


def _build_procedure_id(case_id: str, sequence: int) -> str:
    return f"SQA_PRODUCT_TEST_PROCEDURE_ID-{str(case_id or '').strip().removeprefix('SQA_PRODUCT_TEST_CASE_ID-')}-{int(sequence):03d}"


def _build_example_payload() -> dict[str, str]:
    """E2E 자동입력용: 타임스탬프로 ID 충돌을 피하면서 실제 시험 데이터에 가깝게 구성한다."""
    stamp = time.strftime("%Y%m%d%H%M%S")
    compact = stamp[-6:]
    patch_token = stamp[-4:]

    upstream_release_id = f"HRK_9000A-1.0.{patch_token}"
    release_stage = "RC"
    product_test_release_id = _build_release_id(upstream_release_id, release_stage)

    product_code = f"HRK_9000A_{compact}"
    model_name = f"HRK-9000A Digital Refractometer (Lot {compact})"
    target_definition_id = _build_target_definition_id(model_name)
    serial_number = f"HVZ-AAY-{compact}"
    target_id = _build_target_id(target_definition_id, serial_number)

    company_name = "Huvitz"
    city_name = "Anyang"
    room_name = f"Connectivity_Lab_3F_{compact}"
    environment_definition_id = _build_environment_definition_id(company_name, city_name, room_name)
    captured_at = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} 14:30:00"
    environment_id = _build_environment_id(environment_definition_id, captured_at)

    case_title = f"WiFi 5GHz 채널 고정 및 DFS 회피 확인 ({compact})"
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
        "report_title": f"HRK-9000A 제품 시험 종합 보고서 (RC·{compact})",
        "test_room": room_name,
        "manufacture_lot": f"SG-ASN-{stamp[:8]}-{compact}",
    }


def _fill_text_like_field(field, value: str) -> None:
    field.click()
    field.send_keys(Keys.CONTROL, "a")
    field.send_keys(Keys.BACKSPACE)
    text = str(value or "")
    if text:
        field.send_keys(text)
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


def _wait_merged_draft_row(driver, form, timeout: float = 10) -> None:
    """병합 입력 행만 대상으로 한다. 폼 전체에서 find 하면 숨김 테이블/제출 행 순서에 따라 잘못된 칸이 잡힐 수 있다."""

    def _draft_present(_unused_driver) -> bool:
        return bool(form.find_elements(By.CSS_SELECTOR, "tr.admin_merged_draft_row"))

    WebDriverWait(driver, timeout).until(_draft_present)


def _find_named_field(form, field_name: str):
    draft_row = form.find_element(By.CSS_SELECTOR, "tr.admin_merged_draft_row")
    return draft_row.find_element(By.CSS_SELECTOR, f"[name='{field_name}']")


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
        _wait_merged_draft_row(driver, release_form)
        _fill_field(release_form, "upstream_release_id", payload["upstream_release_id"])
        _fill_field(release_form, "upstream_release_system", "Huvitz Software Release System")
        _fill_field(release_form, "product_test_release_status", "TESTING")
        _fill_field(
            release_form,
            "remark",
            "RC 단계 WiFi·연결성 시험 베이스라인. 상용 펌웨어 1.0.x 대상.",
        )
        _fill_field(release_form, "product_test_release_id", payload["product_test_release_id"])
        _fill_field(release_form, "release_stage", payload["release_stage"])
        _wait_for_form_submission_cycle()
        _open_admin_page(driver, admin_url)

        definition_form = _find_form(driver, "/admin/product-test-target-definitions/create")
        _wait_merged_draft_row(driver, definition_form)
        _fill_field(definition_form, "product_code", payload["product_code"])
        _fill_field(definition_form, "hardware_revision", "B2")
        _fill_field(definition_form, "default_software_version", "2.1.4")
        _fill_field(definition_form, "default_firmware_version", "2.1.4-build.4821")
        _fill_field(definition_form, "product_test_target_definition_status", "ACTIVE")
        _fill_field(
            definition_form,
            "remark",
            "안양 본사 기준 의료기기용 국내 판매 모델. 시리얼 추적 단위는 장비 1대 단위.",
        )
        _fill_field(definition_form, "model_name", payload["model_name"])
        _fill_field(definition_form, "product_test_target_definition_id", payload["target_definition_id"])
        _fill_field(definition_form, "manufacturer", "Huvitz")
        _wait_for_form_submission_cycle()
        _open_admin_page(driver, admin_url)

        target_form = _find_form(driver, "/admin/product-test-targets/create")
        _wait_merged_draft_row(driver, target_form)
        _fill_field(target_form, "software_version", "2.1.4")
        _fill_field(target_form, "firmware_version", "2.1.4-build.4821")
        _fill_field(target_form, "manufacture_lot", payload["manufacture_lot"])
        _fill_field(target_form, "product_test_target_status", "ACTIVE")
        _fill_field(
            target_form,
            "remark",
            "시험 입고 완료. 외관·라벨·박스 일치 확인. 전원 인가 전 ESD 대기 10분 준수.",
        )
        _fill_field(target_form, "serial_number", payload["serial_number"])
        _fill_field(target_form, "product_test_target_id", payload["target_id"])
        _fill_field(target_form, "product_test_target_definition_id", payload["target_definition_id"])
        _wait_for_form_submission_cycle()
        _open_admin_page(driver, admin_url)

        environment_definition_form = _find_form(driver, "/admin/product-test-environment-definitions/create")
        _wait_merged_draft_row(driver, environment_definition_form)
        _fill_field(environment_definition_form, "test_country", "South Korea")
        _fill_field(environment_definition_form, "test_city", "Anyang")
        _fill_field(environment_definition_form, "test_company", "Huvitz")
        _fill_field(environment_definition_form, "test_room", payload["test_room"])
        _fill_field(environment_definition_form, "network_type", "ISOLATED_LAB_VLAN")
        _fill_field(environment_definition_form, "test_computer_name", "PT-LAB-WS03")
        _fill_field(environment_definition_form, "operating_system_version", "Windows 11 Pro 23H2")
        _fill_field(environment_definition_form, "test_tool_name", "Wireshark")
        _fill_field(environment_definition_form, "test_tool_version", "4.2.5")
        _fill_field(environment_definition_form, "power_voltage", "220 V AC")
        _fill_field(environment_definition_form, "power_frequency", "60 Hz")
        _fill_field(environment_definition_form, "power_connector_type", "IEC 60320 C13")
        _fill_field(
            environment_definition_form,
            "power_condition",
            "상용 전원, THD 5% 미만, UPS 경로 비차단",
        )
        _fill_field(environment_definition_form, "product_test_environment_definition_status", "ACTIVE")
        _fill_field(
            environment_definition_form,
            "remark",
            "3층 연결성 실험실 표준 구성. 5GHz 비-DFS 채널 고정 정책 적용.",
        )
        _fill_field(environment_definition_form, "product_test_environment_definition_id", payload["environment_definition_id"])
        _fill_field(
            environment_definition_form,
            "product_test_environment_definition_name",
            f"Huvitz Anyang · Connectivity Lab 표준환경 ({payload['upstream_release_id']})",
        )
        _wait_for_form_submission_cycle()
        _open_admin_page(driver, admin_url)

        environment_form = _find_form(driver, "/admin/product-test-environments/create")
        _wait_merged_draft_row(driver, environment_form)
        _fill_field(environment_form, "test_computer_name", "PT-LAB-WS03")
        _fill_field(environment_form, "operating_system_version", "Windows 11 Pro 23H2")
        _fill_field(environment_form, "test_tool_version", "4.2.5")
        _fill_field(environment_form, "network_type", "ISOLATED_LAB_VLAN")
        _fill_field(environment_form, "power_voltage", "220 V AC")
        _fill_field(environment_form, "power_frequency", "60 Hz")
        _fill_field(environment_form, "power_connector_type", "IEC 60320 C13")
        _fill_field(environment_form, "captured_at", payload["captured_at"])
        _fill_field(environment_form, "product_test_environment_status", "ACTIVE")
        _fill_field(
            environment_form,
            "remark",
            "캡처 시점 기준 스냅샷. AP·PC 시간 NTP 동기화 완료.",
        )
        _fill_field(environment_form, "product_test_environment_id", payload["environment_id"])
        _fill_field(
            environment_form,
            "product_test_environment_name",
            f"HRK-9000A WiFi 시험 스냅샷 · {payload['captured_at'][:10]}",
        )
        _fill_field(
            environment_form,
            "product_test_environment_definition_id",
            payload["environment_definition_id"],
        )
        _wait_for_form_submission_cycle()
        _open_admin_page(driver, admin_url)

        case_form = _find_form(driver, "/admin/product-test-cases/create")
        _wait_merged_draft_row(driver, case_form)
        _fill_field(
            case_form,
            "test_objective",
            "5GHz 대역에서 DFS 채널을 피한 고정 채널 운용이 제품 기본정책과 일치하는지 확인한다.",
        )
        _fill_field(
            case_form,
            "precondition",
            "공인된 시험용 SSID·PSK 적용, 주변 AP 스캔으로 간섭 채널 배제, 온도 23±2℃.",
        )
        _fill_field(
            case_form,
            "expected_result",
            "5GHz 대역에서 채널 36·40·44·48 중 하나로 고정되고, DFS 레이더 검출 이벤트가 관측되지 않는다.",
        )
        _fill_field(case_form, "product_test_case_status", "ACTIVE")
        _fill_field(
            case_form,
            "remark",
            "임상·연구용 제품군 공통 WiFi 구성 검증 케이스.",
        )
        _fill_field(case_form, "product_test_case_title", payload["case_title"])
        _fill_field(case_form, "test_category", payload["case_category"])
        _fill_field(case_form, "product_test_case_id", payload["case_id"])
        _wait_for_form_submission_cycle()
        _open_admin_page(driver, admin_url)

        procedure_form = _find_form(driver, "/admin/product-test-procedures/create")
        _wait_merged_draft_row(driver, procedure_form)
        _fill_field(
            procedure_form,
            "expected_result",
            "국가별 규제 DB에 등록된 허용 채널만 표시·선택 가능.",
        )
        _fill_field(procedure_form, "required_evidence_type", "screenshot")
        _fill_field(procedure_form, "product_test_procedure_status", "ACTIVE")
        _fill_field(
            procedure_form,
            "remark",
            "관리 UI 또는 CLI 중 하나로 캡처하면 됨. 파일명에 채널 번호 포함.",
        )
        _fill_field(procedure_form, "product_test_case_id", payload["case_id"])
        _fill_field(procedure_form, "procedure_sequence", payload["procedure_sequence"])
        _fill_field(
            procedure_form,
            "acceptance_criteria",
            "채널 리스트에 DFS(52–144) 계열이 노출되지 않거나 선택 불가(비활성) 상태여야 함.",
        )
        _fill_field(procedure_form, "product_test_procedure_id", payload["procedure_id"])
        _fill_field(
            procedure_form,
            "procedure_action",
            "무선 설정 화면에서 5GHz 채널 플랜을 조회하고 비-DFS 채널만 활성인지 확인",
        )
        _wait_for_form_submission_cycle()
        _open_admin_page(driver, admin_url)

        report_form = _find_form(driver, "/admin/product-test-reports/create")
        _wait_merged_draft_row(driver, report_form)
        _fill_field(
            report_form,
            "remark",
            "RC 게이트용 내부 공유 초안. 승인 전 법무·품질 검토 예정.",
        )
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
            return False, "E2E TEST already running."
        _is_running = True
    thread = threading.Thread(
        target=_run_fill_sequence_thread,
        args=(str(admin_url or "").strip(),),
        daemon=True,
    )
    thread.start()
    return True, "E2E TEST started."
