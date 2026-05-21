"""호환용 진입점 — 실제 로직은 프로젝트 루트 ``test.py``."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    import importlib.util

    root = Path(__file__).resolve().parent.parent
    path = root / "test.py"
    spec = importlib.util.spec_from_file_location("ptts_regression_main", path)
    if spec is None or spec.loader is None:
        print("test.py를 불러올 수 없습니다.", file=sys.stderr)
        return 1
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return int(mod.main())


if __name__ == "__main__":
    raise SystemExit(main())
