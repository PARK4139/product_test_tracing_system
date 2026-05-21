"""프로젝트 회귀 테스트 단일 진입점 (``test.cmd``에서 호출).

``tests/unit`` → ``tests/e2e_api`` → ``tests/integration`` 순으로, 각 디렉터리 안의
모든 ``test_*.py``를 수집해 한 번에 실행한다. 회귀 범위는 이 파일의 정책만 보면 된다.

사용:

  test.cmd
  uv run python test.py
  uv run python test.py -q
  uv run python test.py -- tests/unit/test_config.py -k bool
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent

# 회귀 스위트 계층 (가벼운 것 우선). 각 층 아래 ``test_*.py`` 전부 포함.
_REGRESSION_TIERS: tuple[str, ...] = (
    "tests/unit",
    "tests/e2e_api",
    "tests/integration",
)


def regression_test_paths() -> list[str]:
    """프로젝트에 등록된 모든 회귀 테스트 모듈 경로(프로젝트 루트 기준 posix)."""
    paths: list[str] = []
    for tier in _REGRESSION_TIERS:
        tier_dir = _PROJECT_ROOT / tier
        if not tier_dir.is_dir():
            continue
        for py_file in sorted(tier_dir.glob("test_*.py")):
            rel = py_file.relative_to(_PROJECT_ROOT).as_posix()
            paths.append(rel)
    return paths


def _default_pytest_argv() -> list[str]:
    discovered = regression_test_paths()
    if not discovered:
        raise RuntimeError(
            f"회귀 테스트를 찾을 수 없습니다. 다음 디렉터리와 test_*.py를 확인하세요: {_REGRESSION_TIERS}"
        )
    return [
        "-v",
        "--tb=short",
        *discovered,
    ]


def main() -> int:
    try:
        import pytest
    except ImportError:
        print(
            "pytest가 없습니다. 다음을 실행한 뒤 다시 시도하세요.\n"
            "  uv sync --group dev",
            file=sys.stderr,
        )
        return 1

    os.chdir(_PROJECT_ROOT)
    argv = _default_pytest_argv()
    argv.extend(sys.argv[1:])
    return pytest.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
