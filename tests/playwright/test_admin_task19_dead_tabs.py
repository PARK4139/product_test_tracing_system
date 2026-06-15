"""
Playwright E2E: ai_task19_remove_dead_tabs 검증

커버:
  - GET /admin 200
  - Tab View 2 (#admin_tab_region_primary) DOM에 없음 (빈 껍데기 제거 확인)
  - Tab View 3 (#admin_tab_region_secondary, 근무 캘린더) 여전히 렌더됨
  - Tab View 4 (#admin_tab_region_quaternary, 시험 추적) 여전히 렌더됨
  - Tab View 5 (#admin_tab_region_entity, Entity Sheets) 여전히 렌더됨
  - Tab View 5 Test Round 탭 클릭 가능 (회귀 없음)
  - Tab View 5 Runs 탭 클릭 가능 (회귀 없음)
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


def goto_admin(page: Page) -> None:
    page.context.add_cookies(ADMIN_COOKIES)
    page.goto(ADMIN_URL)
    page.wait_for_load_state("networkidle")


# ── TC1: GET /admin 200 ───────────────────────────────────────────────

def test_admin_page_ok(page: Page, live_server: str) -> None:
    page.context.add_cookies(ADMIN_COOKIES)
    resp = page.goto(ADMIN_URL)
    assert resp is not None and resp.status == 200


# ── TC2: Tab View 2 (빈 껍데기) 제거 확인 ────────────────────────────

def test_tab_view_2_removed(page: Page, live_server: str) -> None:
    goto_admin(page)
    expect(page.locator("#admin_tab_region_primary")).to_have_count(0)


# ── TC3: Tab View 3 (근무 캘린더) 여전히 존재 ────────────────────────

def test_tab_view_3_work_calendar_present(page: Page, live_server: str) -> None:
    goto_admin(page)
    expect(page.locator("#admin_tab_region_secondary")).to_be_visible()
    expect(page.locator("#work_calendar_card")).to_be_visible()


# ── TC4: Tab View 4 (시험 추적) 여전히 존재 ──────────────────────────

def test_tab_view_4_tracking_present(page: Page, live_server: str) -> None:
    goto_admin(page)
    expect(page.locator("#admin_tab_region_quaternary")).to_be_visible()
    expect(page.locator("#trk_root")).to_be_visible()


# ── TC5: Tab View 5 (Entity Sheets) 섹션 존재 ────────────────────────

def test_tab_view_5_entity_sheets_present(page: Page, live_server: str) -> None:
    goto_admin(page)
    expect(page.locator("#admin_tab_region_entity")).to_be_visible()


# ── TC6: Tab View 5 Test Round 탭 클릭 가능 ──────────────────────────

def test_tab_view_5_test_round_tab_clickable(page: Page, live_server: str) -> None:
    goto_admin(page)
    tab = page.locator("[role='tab']").filter(has_text="Test Round").first
    expect(tab).to_be_visible(timeout=5000)
    tab.click()
    page.wait_for_timeout(300)
    expect(page.locator("tr[data-entity-type='product_test_round']").first).to_be_visible(timeout=5000)


# ── TC7: Tab View 5 Runs 탭 클릭 가능 ────────────────────────────────

def test_tab_view_5_runs_tab_clickable(page: Page, live_server: str) -> None:
    goto_admin(page)
    tab = page.locator("[role='tab']").filter(has_text="Runs").first
    expect(tab).to_be_visible(timeout=5000)
    tab.click()
    page.wait_for_timeout(300)
    expect(page.locator("tr[data-entity-type='product_test_run']").first).to_be_visible(timeout=5000)
