from __future__ import annotations

from app.services.status_vocab import (
    STATUS_APPROVED,
    STATUS_BLOCKED,
    STATUS_CANCELLED,
    STATUS_DRAFT,
    STATUS_FAILED,
    STATUS_FINISHED,
    STATUS_PASSED,
    STATUS_QI_TEAM_RELEASED,
    STATUS_QI_TEAM_REVIEWED,
    STATUS_RUNNING,
    STATUS_SKIPPED,
    STATUS_TESTING,
    VALID_RELEASE_STATUSES,
    derive_rollup_status,
    normalize_status,
)


def test_normalize_status_maps_result_release_and_run_aliases() -> None:
    cases = {
        "passed": STATUS_PASSED,
        "PASS": STATUS_PASSED,
        "blocked": STATUS_BLOCKED,
        "testing": STATUS_TESTING,
        "failed": STATUS_FAILED,
        "skipped": STATUS_SKIPPED,
        "canceled": STATUS_CANCELLED,
        "APPROVED": STATUS_APPROVED,
        "draft": STATUS_DRAFT,
        "qi_team_reviewed": STATUS_QI_TEAM_REVIEWED,
        "QI_TEAM_RELEASED": STATUS_QI_TEAM_RELEASED,
        "running": STATUS_RUNNING,
        "finished": STATUS_FINISHED,
    }
    for raw, expected in cases.items():
        assert normalize_status(raw) == expected


def test_derive_rollup_status_uses_priority_order() -> None:
    assert derive_rollup_status([STATUS_PASSED, STATUS_BLOCKED, STATUS_TESTING]) == STATUS_BLOCKED
    assert derive_rollup_status([STATUS_PASSED, STATUS_FAILED]) == STATUS_FAILED
    assert derive_rollup_status([STATUS_SKIPPED, STATUS_CANCELLED]) == STATUS_SKIPPED
    assert derive_rollup_status([]) == STATUS_TESTING


def test_valid_release_statuses_accept_normalized_aliases() -> None:
    normalized = {normalize_status(raw) for raw in ["testing", "blocked", "approved", "passed"]}
    assert normalized.issubset(VALID_RELEASE_STATUSES)
