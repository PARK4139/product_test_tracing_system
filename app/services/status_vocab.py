from __future__ import annotations

from collections import Counter
from typing import Iterable


STATUS_FAILED = "FAILED"
STATUS_BLOCKED = "BLOCKED"
STATUS_TESTING = "TESTING"
STATUS_PASSED = "PASSED"
STATUS_SKIPPED = "SKIPPED"
STATUS_CANCELLED = "CANCELLED"
STATUS_APPROVED = "APPROVED"
STATUS_DRAFT = "DRAFT"
STATUS_QI_TEAM_REVIEWED = "QI_TEAM_REVIEWED"
STATUS_QI_TEAM_RELEASED = "QI_TEAM_RELEASED"
STATUS_DONE = "DONE"
STATUS_RUNNING = "RUNNING"
STATUS_FINISHED = "FINISHED"

CANONICAL_STATUS_PRIORITY = {
    STATUS_FAILED: 0,
    STATUS_BLOCKED: 1,
    STATUS_TESTING: 2,
    STATUS_PASSED: 3,
    STATUS_SKIPPED: 4,
    STATUS_CANCELLED: 5,
}

RELEASE_STATUS_PRIORITY = {
    STATUS_BLOCKED: 0,
    STATUS_TESTING: 1,
    STATUS_DRAFT: 2,
    STATUS_PASSED: 3,
    STATUS_QI_TEAM_RELEASED: 3,
    STATUS_APPROVED: 3,
    STATUS_QI_TEAM_REVIEWED: 4,
    STATUS_DONE: 5,
}

VALID_RELEASE_STATUSES = {
    STATUS_TESTING,
    STATUS_QI_TEAM_RELEASED,
    STATUS_QI_TEAM_REVIEWED,
    STATUS_DRAFT,
    STATUS_BLOCKED,
    STATUS_PASSED,
    STATUS_APPROVED,
}

STATUS_ALIASES = {
    "PASS": STATUS_PASSED,
    "PASSED": STATUS_PASSED,
    "passed": STATUS_PASSED,
    "BLOCK": STATUS_BLOCKED,
    "BLOCKED": STATUS_BLOCKED,
    "blocked": STATUS_BLOCKED,
    "TESTING": STATUS_TESTING,
    "testing": STATUS_TESTING,
    "IN_PROGRESS": STATUS_TESTING,
    "in_progress": STATUS_TESTING,
    "RUNNING": STATUS_RUNNING,
    "running": STATUS_RUNNING,
    "FINISHED": STATUS_FINISHED,
    "finished": STATUS_FINISHED,
    "FAIL": STATUS_FAILED,
    "FAILED": STATUS_FAILED,
    "failed": STATUS_FAILED,
    "SKIP": STATUS_SKIPPED,
    "SKIPPED": STATUS_SKIPPED,
    "skipped": STATUS_SKIPPED,
    "CANCELLED": STATUS_CANCELLED,
    "cancelled": STATUS_CANCELLED,
    "CANCELED": STATUS_CANCELLED,
    "canceled": STATUS_CANCELLED,
    "APPROVED": STATUS_APPROVED,
    "approved": STATUS_APPROVED,
    "DRAFT": STATUS_DRAFT,
    "draft": STATUS_DRAFT,
    "QI_TEAM_REVIEWED": STATUS_QI_TEAM_REVIEWED,
    "qi_team_reviewed": STATUS_QI_TEAM_REVIEWED,
    "QI_TEAM_RELEASED": STATUS_QI_TEAM_RELEASED,
    "qi_team_released": STATUS_QI_TEAM_RELEASED,
    "DONE": STATUS_DONE,
    "done": STATUS_DONE,
}


def normalize_status(raw: str | None) -> str:
    normalized = str(raw or "").strip()
    if not normalized:
        return ""
    return STATUS_ALIASES.get(normalized, STATUS_ALIASES.get(normalized.upper(), normalized.upper()))


def build_status_counter(statuses: Iterable[str | None]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for raw_status in statuses:
        status = normalize_status(raw_status)
        if status:
            counter[status] += 1
    return counter


def derive_rollup_status(statuses: Iterable[str | None], *, fallback: str = STATUS_TESTING) -> str:
    counter = build_status_counter(statuses)
    if not counter:
        return fallback
    return min(counter, key=lambda status: CANONICAL_STATUS_PRIORITY.get(status, 99))
