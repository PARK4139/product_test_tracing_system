"""Legacy entrypoint: runs pytest integration test (Wi‑Fi AP seed / report / snapshot).

Prefer: `uv run pytest tests/integration/test_wifi_ap_seed_and_report.py -v`
"""

from __future__ import annotations


def main() -> None:
    import subprocess
    import sys
    from pathlib import Path

    target = Path(__file__).resolve().parents[2] / "tests" / "integration" / "test_wifi_ap_seed_and_report.py"
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", str(target), "-v"]))


if __name__ == "__main__":
    main()
