"""
Playwright E2E: batch replace UI test
"""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.playwright.conftest import LIVE_SERVER_BASE

ADMIN_URL = f"{LIVE_SERVER_BASE}/admin"
ROUND_OLD_ID = "dummy_PRODUCT_TEST_RELEASE_ID-MERCUSYS_MR30G-1.0.0-RC1"
ROUND_NEW_ID = "ROUND-MERCUSYS_MR30G-1.0.0-RC1"

ADMIN_COOKIES = [
    {
        "name": "role_name",
        "value": "admin",
        "domain": "127.0.0.1",
        "path": "/",
        "httpOnly": False,
        "secure": False,
    }
]


# ── helpers ───────────────────────────────────────────────────────────

def goto_admin(page: Page) -> None:
    page.context.add_cookies(ADMIN_COOKIES)
    page.goto(ADMIN_URL)
    page.wait_for_load_state("networkidle")


def open_batch_replace_modal(page: Page) -> None:
    page.keyboard.press("`")
    page.wait_for_selector("#admin_adv_edit_menu", state="visible", timeout=3000)
    page.get_by_text("일괄치환").click()
    page.wait_for_selector("#admin_fr_modal", state="visible", timeout=3000)


def fill_find_replace(page: Page, find: str, replace: str,
                      *, substring: bool = False, case: bool = False) -> None:
    """
    substring=False  →  '부분 문자열' 체크박스 unchecked  →  전체 매치
    substring=True   →  checked  →  부분 매치
    """
    page.fill("#admin_fr_find", find)
    page.fill("#admin_fr_replace", replace)
    whole_cb = page.locator("#admin_fr_whole")
    if substring != whole_cb.is_checked():
        whole_cb.click()
    case_cb = page.locator("#admin_fr_case")
    if case != case_cb.is_checked():
        case_cb.click()


# ── TC1: backtick opens menu ──────────────────────────────────────────

def test_backtick_opens_advanced_menu(page: Page, live_server: str) -> None:
    goto_admin(page)
    page.keyboard.press("`")
    menu = page.locator("#admin_adv_edit_menu")
    expect(menu).to_be_visible(timeout=3000)
    expect(menu.get_by_text("일괄치환")).to_be_visible()


# ── TC2: modal UI ─────────────────────────────────────────────────────

def test_modal_opens_and_has_fields(page: Page, live_server: str) -> None:
    goto_admin(page)
    open_batch_replace_modal(page)
    expect(page.locator("#admin_fr_find")).to_be_visible()
    expect(page.locator("#admin_fr_replace")).to_be_visible()
    expect(page.locator("#admin_fr_scan_btn")).to_be_visible()


# ── TC3: no match ─────────────────────────────────────────────────────

def test_preview_no_match(page: Page, live_server: str) -> None:
    goto_admin(page)
    open_batch_replace_modal(page)
    fill_find_replace(page, "NONEXISTENT_VALUE_XYZ_99999", "anything", substring=False)
    page.click("#admin_fr_scan_btn")

    preview = page.locator("#admin_fr_preview")
    expect(preview).to_be_visible(timeout=3000)
    expect(preview).to_contain_text("매칭 셀 없음")

    # CSS가 hidden attribute를 override하므로 attribute로 확인
    apply_btn = page.locator("#admin_fr_apply_btn")
    expect(apply_btn).to_have_attribute("hidden", "")


# ── TC4: preview shows round_id scan result ───────────────────────────

def test_preview_shows_pk_warning_for_round_id(page: Page, live_server: str) -> None:
    """test_round_id 배치교체 스캔 → 프리뷰에 product_test_round 테이블 노출 + 적용 버튼 활성화.

    Note: data-primary-key="1" 속성 제거 후 PK 경고는 더 이상 표시되지 않음.
    """
    goto_admin(page)
    open_batch_replace_modal(page)
    fill_find_replace(page, ROUND_OLD_ID, ROUND_NEW_ID, substring=False)
    page.click("#admin_fr_scan_btn")

    preview = page.locator("#admin_fr_preview")
    expect(preview).to_be_visible(timeout=5000)
    expect(preview).to_contain_text("product_test_round")

    # 적용 버튼 노출
    expect(page.locator("#admin_fr_apply_btn")).not_to_have_attribute("hidden", "")


# ── TC5: apply batch replace round_id ────────────────────────────────

def test_apply_batch_replace_round_id(page: Page, live_server: str) -> None:
    goto_admin(page)

    # product_test_round 행의 test_round_id 셀만 지정
    # (product_test_run 행에도 같은 data-field가 있어 entity-type으로 범위 좁힘)
    old_cell = page.locator(
        "tr[data-entity-type='product_test_round'] td[data-field='test_round_id']"
    ).filter(has_text=ROUND_OLD_ID)
    expect(old_cell).to_have_count(1)

    open_batch_replace_modal(page)
    fill_find_replace(page, ROUND_OLD_ID, ROUND_NEW_ID, substring=False)
    page.click("#admin_fr_scan_btn")
    expect(page.locator("#admin_fr_apply_btn")).not_to_have_attribute("hidden", "", timeout=3000)
    page.click("#admin_fr_apply_btn")

    # 성공 토스트: "N/N건 완료"
    page.wait_for_function(
        "() => document.body.innerText.includes('건 완료')",
        timeout=5000,
    )

    # DOM에서 새 ID로 변경됐는지 확인 (round 행만 검사)
    new_cell = page.locator(
        "tr[data-entity-type='product_test_round'] td[data-field='test_round_id']"
    ).filter(has_text=ROUND_NEW_ID)
    expect(new_cell).to_have_count(1)
    expect(old_cell).to_have_count(0)


# ── TC6: text field batch replace ────────────────────────────────────

def test_apply_batch_replace_text_field(page: Page, live_server: str) -> None:
    goto_admin(page)

    name_cell = page.locator("td[data-field='test_round_name']").first
    original_name = name_cell.text_content() or ""
    original_name = original_name.strip()
    if not original_name:
        pytest.skip("test_round_name is empty")

    new_name = original_name + "_RENAMED"

    open_batch_replace_modal(page)
    fill_find_replace(page, original_name, new_name, substring=False)
    page.click("#admin_fr_scan_btn")
    expect(page.locator("#admin_fr_apply_btn")).not_to_have_attribute("hidden", "", timeout=3000)
    page.click("#admin_fr_apply_btn")

    page.wait_for_function(
        "() => document.body.innerText.includes('건 완료')",
        timeout=5000,
    )
    expect(
        page.locator("td[data-field='test_round_name']").filter(has_text=new_name)
    ).to_have_count(1)
