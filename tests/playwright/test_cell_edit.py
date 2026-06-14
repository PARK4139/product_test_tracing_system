"""
Playwright E2E: in-cell edit (admin-incell-edit.js) tests

커버:
  - 텍스트 셀 클릭 → input 편집 → Enter 저장
  - 텍스트 셀 클릭 → ESC 취소 (원래 값 유지)
  - select 셀 클릭 → dropdown 편집 → blur 저장
  - PK 셀 클릭 → 편집 불가 (input 미출현)
  - update-readonly 셀 클릭 → 편집 불가
  - 저장 후 Ctrl+Z undo → 이전 값 복구
  - 두 셀 빠르게 연속 편집 → 둘 다 저장 성공
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


def get_round_id_cell(page: Page):
    """product_test_round 테이블의 test_round_id 셀 (*_id 편집 가능 여부 검증용)."""
    return page.locator(
        "tr[data-entity-type='product_test_round'] td[data-field='test_round_id']"
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

    inp.click(click_count=3)
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

    inp.click(click_count=3)
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


# ── TC4: test_round_id (*_id) 편집 → 저장 ───────────────────────────

def test_pk_cell_not_editable(page: Page, live_server: str) -> None:
    """*_id 셀은 편집 가능해야 한다 (data-primary-key 제한 제거 후).

    test_round_id 셀을 직접 편집해 저장이 성공하는지 확인한다.
    "Cases" 탭은 별도 탭 레이블이 없으므로 "Test Round" 탭의 test_round_id 사용.
    """
    goto_admin(page)
    activate_tab(page, "Test Round")

    cell = get_round_id_cell(page)
    original = (cell.text_content() or "").strip()
    new_value = original + "_ID"

    cell.click()
    inp = cell.locator("input")
    expect(inp).to_be_visible(timeout=2000)
    inp.click(click_count=3)
    inp.type(new_value)
    inp.press("Enter")

    expect(inp).to_have_count(0, timeout=5000)
    expect(cell).to_contain_text(new_value, timeout=5000)

    page.wait_for_function(
        "() => document.body.innerText.includes('셀 저장 완료')",
        timeout=5000,
    )


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


# ── TC7: 두 셀 빠르게 연속 편집 → 둘 다 저장 ────────────────────────

def test_rapid_two_cell_edit_both_save(page: Page, live_server: str) -> None:
    """셀 A 편집(Enter) 직후 셀 B 클릭→편집(Enter) → 둘 다 저장 성공."""
    goto_admin(page)
    activate_tab(page, "Test Round")

    # 첫 번째 셀: test_round_name
    cell_a = get_round_name_cell(page)
    original_a = (cell_a.text_content() or "").strip()
    new_a = original_a + "_A"

    # 두 번째 셀: start_date (편집 가능한 텍스트 셀)
    cell_b = page.locator(
        "tr[data-entity-type='product_test_round'] td[data-field='start_date']"
    ).first
    original_b = (cell_b.text_content() or "").strip()
    new_b = "2099-01-01"

    # ── 셀 A 편집 후 즉시 셀 B 클릭 (저장 완료 기다리지 않음) ──────
    cell_a.click()
    inp_a = cell_a.locator("input")
    expect(inp_a).to_be_visible(timeout=2000)
    inp_a.click(click_count=3)
    inp_a.type(new_a)
    inp_a.press("Enter")  # 저장 시작 (비동기) - 완료 기다리지 않음

    # 즉시 셀 B 클릭
    cell_b.click()
    inp_b = cell_b.locator("input")
    expect(inp_b).to_be_visible(timeout=2000)
    inp_b.click(click_count=3)
    inp_b.type(new_b)
    inp_b.press("Enter")

    # 두 번째 저장 완료 대기 (큐 직렬화이므로 두 번 완료됐을 때 텍스트 포함)
    expect(inp_b).to_have_count(0, timeout=5000)

    # 두 셀 모두 새 값으로 업데이트됐는지 확인
    expect(cell_a).to_contain_text(new_a, timeout=5000)
    expect(cell_b).to_contain_text(new_b, timeout=5000)


# ── TC8: MERCUSYS round_id 행의 round_name 편집 ───────────────────────

def test_mercusys_round_name_edit(page: Page, live_server: str) -> None:
    """Rounds 탭에서 round_id 에 MERCUSYS 가 포함된 첫 번째 행의 round_name 을 편집·저장."""
    goto_admin(page)
    activate_tab(page, "Test Round")

    row = page.locator(
        "tr[data-entity-type='product_test_round']"
    ).filter(
        has=page.locator("td[data-field='test_round_id']", has_text="MERCUSYS")
    ).first

    cell = row.locator("td[data-field='test_round_name']")
    original = (cell.text_content() or "").strip()
    new_value = original + "_MRC"

    cell.click()
    inp = cell.locator("input")
    expect(inp).to_be_visible(timeout=2000)
    inp.click(click_count=3)
    inp.type(new_value)
    inp.press("Enter")

    expect(inp).to_have_count(0, timeout=5000)
    expect(cell).to_contain_text(new_value, timeout=5000)

    page.wait_for_function(
        "() => document.body.innerText.includes('셀 저장 완료')",
        timeout=5000,
    )



# ── TC9: F2 on admin-incell-edit table → 충돌 없음 ─────────────────────
# 루트 원인: table-cell-f2-edit.js 가 admin-incell-edit.js 의 input 을 가로채면
# blur 발생 시 optimistic update 가 input 을 DOM 에서 제거 → multiEditPrimary detached
# → 이후 타이핑 불가 (“view stops while editing”).
# 수정: selectedCell.closest(“[data-incell-edit-table]”) 이면 F2 무시.

def test_f2_does_not_break_admin_incell_edit(page: Page, live_server: str) -> None:
    """admin-incell-edit 테이블 셀에서 F2 를 눈러도 admin 인셀 편집이 정상 동작해야 한다.

    재현 시나리오:
      1. round_name 셀 클릭 → admin-incell-edit 이 <input> 생성
      2. F2 키 → (수정 전) table-cell-f2-edit 가 그 input 을 multiEditPrimary 로 가로채서
         blur 발생 시 input 제거 → 편집 멈춤
         (수정 후) F2 무시 → admin input 그대로 활성
      3. 값 입력 후 Enter → 정상 저장
    """
    goto_admin(page)
    activate_tab(page, "Test Round")

    cell = get_round_name_cell(page)
    original = (cell.text_content() or "").strip()
    new_value = original + "_F2TEST"

    # 1. 셀 클릭 → admin input 생성
    cell.click()
    inp = cell.locator("input")
    expect(inp).to_be_visible(timeout=2000)

    # 2. F2 키 (수정 후 무시되어야 함 → input 여전히 존재)
    page.keyboard.press("F2")
    expect(inp).to_be_visible(timeout=1000)  # input 이 사라지지 않아야 함

    # 3. 값 입력 → Enter 저장
    inp.click(click_count=3)
    inp.type(new_value)
    inp.press("Enter")

    expect(inp).to_have_count(0, timeout=5000)
    expect(cell).to_contain_text(new_value, timeout=5000)

    page.wait_for_function(
        "() => document.body.innerText.includes('\uc140 \uc800\uc7a5 \uc644\ub8cc')",
        timeout=5000,
    )


# ── TC10: F2 → Enter 연속 후 재편집 정상 동작 ────────────────────

def test_f2_enter_then_reeditable(page: Page, live_server: str) -> None:
    """F2 + Enter 입력 이후에도 셀 재클릭 → 편집 가능해야 한다.

    (수정 전) F2 가 admin input 을 가로채면 Enter 시 두 핸들러 모두 발화
    → finished 플래그가 꽔여 다음 클릭 시 편집 불가.
    (수정 후) F2 무시 → Enter 는 admin-incell-edit 핸들러만 처리 → 정상.
    """
    goto_admin(page)
    activate_tab(page, "Test Round")

    cell = get_round_name_cell(page)
    original = (cell.text_content() or "").strip()
    first_val = original + "_F2A"
    second_val = original + "_F2B"

    # 1차 편집: 클릭 → F2 → Enter
    cell.click()
    inp = cell.locator("input")
    expect(inp).to_be_visible(timeout=2000)
    page.keyboard.press("F2")
    inp.click(click_count=3)
    inp.type(first_val)
    inp.press("Enter")
    expect(inp).to_have_count(0, timeout=5000)
    expect(cell).to_contain_text(first_val, timeout=5000)

    # 2차 편집: 재클릭 → 편집 가능한지 확인
    cell.click()
    inp2 = cell.locator("input")
    expect(inp2).to_be_visible(timeout=2000)
    inp2.click(click_count=3)
    inp2.type(second_val)
    inp2.press("Enter")
    expect(inp2).to_have_count(0, timeout=5000)
    expect(cell).to_contain_text(second_val, timeout=5000)

    page.wait_for_function(
        "() => document.body.innerText.includes('\uc140 \uc800\uc7a5 \uc644\ub8cc')",
        timeout=5000,
    )


# ── TC6: Ctrl+Z undo ──────────────────────────────────────────────────────

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
    inp.click(click_count=3)
    inp.type(new_value)
    inp.press("Enter")
    expect(inp).to_have_count(0, timeout=3000)
    expect(cell).to_contain_text(new_value, timeout=3000)

    page.wait_for_function(
        "() => document.body.innerText.includes('\uc140 \uc800\uc7a5 \uc644\ub8cc')",
        timeout=5000,
    )

    # Ctrl+Z undo
    page.keyboard.press("Control+z")

    page.wait_for_function(
        "() => document.body.innerText.includes('\ub418돌리기 \uc644\ub8cc')",
        timeout=5000,
    )
    expect(cell).to_contain_text(original, timeout=3000)
