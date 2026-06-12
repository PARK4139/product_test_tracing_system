"""Helpers for procedure_action step count and summary display."""
from __future__ import annotations

import re

_NUMBERED_LINE = re.compile(r"^\s*(?:\d+[\.\)]|[①-⑳]|\(\d+\))")


def count_procedure_action_steps(procedure_action: str | None) -> int:
    text = str(procedure_action or "").strip()
    if not text:
        return 0
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return 1
    numbered = sum(1 for line in lines if _NUMBERED_LINE.match(line))
    if numbered >= 2:
        return numbered
    if len(lines) >= 2:
        return len(lines)
    return 1


def format_procedure_action_summary(procedure_action: str | None) -> str:
    step_count = count_procedure_action_steps(procedure_action)
    if step_count <= 0:
        return ""
    return ", ".join(str(index) for index in range(1, step_count + 1))
