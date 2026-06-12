"""
Playwright E2E: in-cell edit (admin-incell-edit.js) tests

커버:
  - 텍스트 셀 클릭 → input 편집 → Enter 저장
  - 텍스트 셀 클릭 → ESC 취소 (원래 값 유지)
  - select 셀 클릭 → dropdown 편집 → blur 저장
  - PK 셀 클릭 → 편집 불가 (input 미출현)
  - update-readonly 셀 클릭 → 편집 불가
  - 저장 후 Ctrl+Z undo → 이전 값 복구
"""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.playwright.conftest import LIVE_SERVER_BASE

ADMIN_URL = f"{LIVE_SERVER_BASE}/admin"

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


def activate_tab(page: Page, label: str) -> None:
    """탭 버튼 클릭으로 해당 탭 패널 활성화."""
    page.locator(f"[role='tab']").filter(has_text=label).first.click()
    page.wait_for_timeout(300)


def get_round_name_cell(page: Page):
    return page.locator(
        "tr[data-entity-type='product_test_round'] td[data-field='test_round_name']"
    ).first


def get_round_pk_cell(page: Page):
    return page.locator(
        "tr[data-entity-type='product_test_round'] td[data-field='test_round_id'][data-primary-key='1']"
    ).first


def get_round_status_cell(page: Page):
    """migration_status: data-options 있는 select 셀."""
    return page.locator(
        "tr[data-entity-type='product_test_round'] td[data-field='migration_status']"
    ).first


def get_run_round_id_cell(page: Page):
    """product_test_run 테이블의 test_round_id: update-readonly=1."""
    return page.locator(
        "tr[data-entity-type='product_test_run'] td[data-field='test_round_id'][data-update-readonly='1']"
    ).first


# ── TC1: 텍스트 셀 클릭 → Enter 저장 ────────────────────────────────

def test_text_cell_edit_enter_saves(page: Page, live_server: str) -> None:
    goto_admin(page)
    activate_tab(page, "Test Round")

    cell = get_round_name_cell(page)
    original = (cell.text_content() or "").strip()
    new_value = original + "_EDITED"

    cell.click()
    inp = cell.locator("input")
    expect(inp).to_be_visible(timeout=2000)

    inp.triple_click()
    inp.type(new_value)
    inp.press("Enter")

    # input 사라지고 새 값으로 업데이트
    expect(inp).to_have_count(0, timeout=3000)
    expect(cell).to_contain_text(new_value, timeout=3000)

    # 성공 토스트
    page.wait_for_function(
        "() => document.body.innerText.includes('셀 저장 완료')",
        timeout=5000,
    )


# ── TC2: ESC 취소 → 원래 값 유지 ─────────────────────────────────────

def test_text_cell_edit_escape_cancels(page: Page, live_server: str) -> None:
    goto_admin(page)
    activate_tab(page, "Test Round")

    cell = get_round_name_cell(page)
    original = (cell.text_content() or "").strip()

    cell.click()
    inp = cell.locator("input")
    expect(inp).to_be_visible(timeout=2000)

    inp.triple_click()
    inp.type("SHOULD_NOT_SAVE")
    inp.press("Escape")

    # input 사라지고 원래 값 복원
    expect(inp).to_have_count(0, timeout=3000)
    expect(cell).to_contain_text(original, timeout=2000)


# ── TC3: select 셀 편집 → blur 저장 ──────────────────────────────────

def test_select_cell_edit_saves(page: Page, live_server: str) -> None:
    goto_admin(page)
    activate_tab(page, "Test Round")

    cell = get_round_status_cell(page)
    original_badge = cell.locator(".status_badge").first
    original_value = (original_badge.text_content() or "").strip()

    # 현재 값이 아닌 다른 옵션 선택
    options = ["DRAFT", "TESTING", "REJECTED", "APPROVED", "ARCHIVED"]
    new_value = next(v for v in options if v != original_value.upper())

    cell.click()
    sel = cell.locator("select")
    expect(sel).to_be_visible(timeout=2000)
    sel.select_option(new_value)
    # blur로 저장 트리거
    page.keyboard.press("Tab")

    expect(sel).to_have_count(0, timeout=3000)
    expect(cell.locator(".status_badge")).to_contain_text(new_value, timeout=3000)

    page.wait_for_function(
        "() => document.body.innerText.includes('셀 저장 완료')",
        timeout=5000,
    )


# ── TC4: PK 셀 클릭 → 편집 불가 ──────────────────────────────────────

def test_pk_cell_not_editable(page: Page, live_server: str) -> None:
    goto_admin(page)
    activate_tab(page, "Test Round")

    cell = get_round_pk_cell(page)
    original = (cell.text_content() or "").strip()

    cell.click()
    page.wait_for_timeout(500)

    # input이 나타나지 않아야 함
    expect(cell.locator("input")).to_have_count(0)
    expect(cell).to_contain_text(original)


# ── TC5: update-readonly 셀 클릭 → 편집 불가 ─────────────────────────

def test_update_readonly_cell_not_editable(page: Page, live_server: str) -> None:
    goto_admin(page)
    activate_tab(page, "Runs")

    cell = get_run_round_id_cell(page)
    original = (cell.text_content() or "").strip()

    cell.click()
    page.wait_for_timeout(500)

    expect(cell.locator("input, select, textarea")).to_have_count(0)
    expect(cell).to_contain_text(original)


# ── TC6: Ctrl+Z undo ──────────────────────────────────────────────────

def test_ctrl_z_undoes_last_cell_edit(page: Page, live_server: str) -> None:
    goto_admin(page)
    activate_tab(page, "Test Round")

    cell = get_round_name_cell(page)
    original = (cell.text_content() or "").strip()
    new_value = original + "_TO_UNDO"

    # 편집 & 저장
    cell.click()
    inp = cell.locator("input")
    expect(inp).to_be_visible(timeout=2000)
    inp.triple_click()
    inp.type(new_value)
    inp.press("Enter")
    expect(inp).to_have_count(0, timeout=3000)
    expect(cell).to_contain_text(new_value, timeout=3000)

    page.wait_for_function(
        "() => document.body.innerText.includes('셀 저장 완료')",
        timeout=5000,
    )

    # Ctrl+Z undo
    page.keyboard.press("Control+z")

    page.wait_for_function(
        "() => document.body.innerText.includes('되돌리기 완료')",
        timeout=5000,
    )
    expect(cell).to_contain_text(original, timeout=3000)
