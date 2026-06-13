"""Playwright E2E 테스트 인터랙티브 실행 스크립트.

사용:
  run_tests.cmd        (CMD 더블클릭)
  uv run python run_tests.py
"""

from __future__ import annotations

import ast
import datetime
import shutil
import subprocess
import sys
from pathlib import Path


# TODO : _________________________________________________ 0. CONFIG

PROJECT_ROOT = Path(__file__).resolve().parent
PLAYWRIGHT_TEST_DIR = PROJECT_ROOT / "tests" / "playwright"
LOG_PATH = PROJECT_ROOT / "run_tests.log"


class _Tee:
    """stdout 을 터미널과 로그 파일에 동시에 기록한다."""

    def __init__(self, terminal, log_file):
        self._terminal = terminal
        self._log = log_file

    def write(self, data: str) -> int:
        self._terminal.write(data)
        try:
            self._log.write(data)
        except Exception:
            pass
        return len(data)

    def flush(self) -> None:
        self._terminal.flush()
        try:
            self._log.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._terminal, name)


def _setup_logging() -> None:
    """run_tests.log 에 append 로깅을 시작한다."""
    log_file = open(LOG_PATH, "a", encoding="utf-8")
    log_file.write(f"\n{'=' * 70}\n")
    log_file.write(f"run_tests.py  started at {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n")
    log_file.write(f"{'=' * 70}\n")
    sys.stdout = _Tee(sys.__stdout__, log_file)
SLOW_MO_MS = 800

# get_pk_fzf_options 에서 로드한 fzf 플래그 (_check_prerequisites 에서 채워짐)
_PK_FZF_BASE_ARGS: list[str] = []


# TODO : _________________________________________________ 1. HELPERS

def print_section(title: str) -> None:
    line = "=" * 70
    print()
    print(line)
    print(title)
    print(line)


def run_command(
    args: list[str],
    cwd: Path,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args=args,
        cwd=str(cwd),
        capture_output=capture_output,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    if check and result.returncode != 0:
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        raise RuntimeError(
            "\n".join([
                f"Command failed: {' '.join(args)}",
                f"Return code: {result.returncode}",
                f"STDOUT:\n{stdout}" if stdout else "STDOUT: <empty>",
                f"STDERR:\n{stderr}" if stderr else "STDERR: <empty>",
            ])
        )
    return result


# TODO : _________________________________________________ 2. FZF HELPERS

def _fzf_exe() -> str | None:
    """fzf 실행 파일 경로. pk_tools > 루트 fzf.exe > PATH 순으로 탐색."""
    try:
        from pk_tools.pk_functions.get_fzf_executable_command import (  # type: ignore[import]
            get_fzf_executable_command,
        )
        exe = get_fzf_executable_command()
        if exe and Path(str(exe)).exists():
            return str(exe)
    except ImportError:
        pass
    for candidate in [
        PROJECT_ROOT / "fzf.exe",
        PROJECT_ROOT / "fzf",
    ]:
        if candidate.exists():
            return str(candidate)
    return shutil.which("fzf") or shutil.which("fzf.exe")


def _fzf_available() -> bool:
    return _fzf_exe() is not None


def _pk_fzf_base_args_default() -> list[str]:
    """get_pk_fzf_options 가 없을 때 사용하는 로컬 기본 fzf 옵션."""
    return [
        "--extended",
        "--no-sort",
        "--reverse",
        "--no-select-1",
        "--height=20",
        "--no-border",
        "--border",
        "--color=fg:#d0d0d0,fg+:#ffffff,bg+:#3a3a3a,hl:#5f87af,hl+:#87afd7,"
        "info:#afaf87,prompt:#d7005f,pointer:#af5fff,marker:#87ff00",
        "--bind", "shift-tab:up,alt-a:select-all,alt-d:deselect-all",
    ]


def _fzf_select(items: list[str], prompt: str, multi: bool = False) -> list[str]:
    """fzf 로 items 중 선택. 선택 없으면 [] 반환."""
    exe = _fzf_exe()
    if not exe:
        return []
    input_bytes = "\n".join(items).encode("utf-8")
    args = [exe, f"--prompt={prompt}"] + _PK_FZF_BASE_ARGS
    if multi:
        # --no-multi 가 base_args 에 있어도 마지막 --multi 가 우선
        args += ["--multi", "--bind", "ctrl-a:select-all"]
    result = subprocess.run(
        args,
        input=input_bytes,
        stdout=subprocess.PIPE,   # 선택 결과만 캡처
        stderr=None,              # fzf UI 는 터미널로 직접 출력 (키 입력 활성화)
        shell=False,
    )
    if result.returncode != 0:
        return []
    return [line.decode("utf-8").strip() for line in result.stdout.splitlines() if line.strip()]


def _select_with_pk_or_fzf(
    key_name: str,
    options: list[str],
    multi: bool = False,
) -> list[str]:
    """pk_tools.ensure_values_completed 우선, 없으면 로컬 fzf 사용."""
    try:
        from pk_tools.pk_functions.ensure_values_completed import (  # type: ignore[import]
            ensure_values_completed as pk_evc,
        )
        result = pk_evc(key_name=key_name, options=options) or []
        if result:
            return result
        # [] 반환 → pk_tools fzf 실패/취소 → 로컬 fzf 로 fallback
    except ImportError:
        pass
    except Exception as exc:
        print(f"  pk_evc: skipped ({type(exc).__name__}: {exc})")

    # local fzf fallback
    if _fzf_available():
        return _fzf_select(options, prompt=f"{key_name}> ", multi=multi)
    return []


# TODO : _________________________________________________ 3. PREREQUISITES

def _ensure_uv() -> str:
    uv_path = shutil.which("uv") or shutil.which("uv.exe")
    if not uv_path:
        raise RuntimeError(
            "uv not found in PATH.\n"
            "  See: https://docs.astral.sh/uv/"
        )
    return uv_path


def _ensure_playwright_package() -> None:
    check = subprocess.run(
        ["uv", "run", "python", "-c", "import playwright; print('ok')"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    if check.returncode != 0 or "ok" not in (check.stdout or ""):
        raise RuntimeError(
            "playwright package is not installed.\n"
            "  Run: temp.cmd"
        )


def _ensure_chromium_executable() -> str:
    check = subprocess.run(
        [
            "uv", "run", "python", "-c",
            "from playwright.sync_api import sync_playwright\n"
            "with sync_playwright() as p:\n"
            "    print(p.chromium.executable_path)",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    if check.returncode != 0:
        raise RuntimeError(
            "Failed to query Chromium path.\n"
            "  Run: temp.cmd"
        )
    exe = (check.stdout or "").strip()
    if not Path(exe).exists():
        raise RuntimeError(
            f"Chromium not found: {exe}\n"
            "  Run: temp.cmd"
        )
    return exe


def _check_prerequisites() -> None:
    """uv · playwright · chromium 확인. pk_tools 있으면 env setup + fzf 옵션 로드."""
    global _PK_FZF_BASE_ARGS

    # pk_env_file_setup (pk_tools)
    try:
        import inspect
        from pk_tools.pk_functions.ensure_pk_env_file_setup import (  # type: ignore[import]
            ensure_pk_env_file_setup,
        )
        sig = inspect.signature(ensure_pk_env_file_setup)
        params = list(sig.parameters.keys())
        if "traced_file" in params:
            ensure_pk_env_file_setup(traced_file=__file__)
        elif params:
            ensure_pk_env_file_setup(__file__)
        else:
            ensure_pk_env_file_setup()
        print("  pk_env_file_setup : ok (via pk_tools)")
    except ImportError:
        pass
    except Exception as exc:
        print(f"  pk_env_file_setup : skipped ({type(exc).__name__}: {exc})")

    # get_pk_fzf_options (pk_tools) — local default fallback
    try:
        from pk_tools.pk_functions.get_pk_fzf_options import (  # type: ignore[import]
            get_pk_fzf_options,
        )
        _PK_FZF_BASE_ARGS = get_pk_fzf_options()
        print(f"  get_pk_fzf_options: {len(_PK_FZF_BASE_ARGS)} opts (via pk_tools)")
    except ImportError:
        _PK_FZF_BASE_ARGS = _pk_fzf_base_args_default()
        print(f"  get_pk_fzf_options: local default ({len(_PK_FZF_BASE_ARGS)} opts)")
    except Exception as exc:
        _PK_FZF_BASE_ARGS = _pk_fzf_base_args_default()
        print(f"  get_pk_fzf_options: skipped ({type(exc).__name__}: {exc}), using local default")

    # uv
    uv_path = _ensure_uv()
    print(f"  uv        : {uv_path}")

    # playwright
    _ensure_playwright_package()
    print("  playwright: installed")

    # chromium
    chromium_exe = _ensure_chromium_executable()
    print(f"  chromium  : {chromium_exe}")

    # fzf
    if _fzf_available():
        print(f"  fzf       : {_fzf_exe()}")
    else:
        print("  fzf       : not found  (install fzf for fuzzy select)")


# TODO : _________________________________________________ 4. TC DISCOVERY

# 모듈 파일명 → 한글 그룹 이름
_MODULE_LABELS: dict[str, str] = {
    "test_batch_replace.py": "배치교체",
    "test_cell_edit.py":     "셀편집",
}

# pytest TC ID (file::func) → 한글 레이블
_TC_LABELS: dict[str, str] = {
    # ── 배치 교체 ─────────────────────────────────────────────────────
    "test_batch_replace.py::test_backtick_opens_advanced_menu":         "백틱(`) → 고급 메뉴 열림",
    "test_batch_replace.py::test_modal_opens_and_has_fields":           "일괄 교체 모달 열기 + 필드 확인",
    "test_batch_replace.py::test_preview_no_match":                     "미리보기: 매칭 없음",
    "test_batch_replace.py::test_preview_shows_pk_warning_for_round_id":"미리보기: PK 경고 표시",
    "test_batch_replace.py::test_apply_batch_replace_round_id":         "일괄 교체 적용: round_id",
    "test_batch_replace.py::test_apply_batch_replace_text_field":       "일괄 교체 적용: 텍스트 필드",
    # ── 셀 편집 ───────────────────────────────────────────────────────
    "test_cell_edit.py::test_text_cell_edit_enter_saves":               "텍스트 셀 → Enter 저장",
    "test_cell_edit.py::test_text_cell_edit_escape_cancels":            "텍스트 셀 → ESC 취소",
    "test_cell_edit.py::test_select_cell_edit_saves":                   "Select 셀 → blur 저장",
    "test_cell_edit.py::test_pk_cell_not_editable":                     "자동생성 PK(run_id) → 편집 불가",
    "test_cell_edit.py::test_update_readonly_cell_not_editable":        "update-readonly 셀 → 편집 불가",
    "test_cell_edit.py::test_rapid_two_cell_edit_both_save":            "연속 두 셀 편집 → 둘 다 저장",
    "test_cell_edit.py::test_mercusys_round_name_edit":                 "MERCUSYS 행 round_name 편집",
    "test_cell_edit.py::test_f2_does_not_break_admin_incell_edit":      "F2: admin 셀 충돌 없음",
    "test_cell_edit.py::test_f2_enter_then_reeditable":                 "F2 + Enter 후 재편집 가능",
    "test_cell_edit.py::test_ctrl_z_undoes_last_cell_edit":             "Ctrl+Z 되돌리기",
}


def _make_display_label(num: int, tc: str) -> str:
    """01  [셀편집]  텍스트 셀 → Enter 저장 형식의 표시명을 반환한다."""
    file, _, func = tc.partition("::")
    module = _MODULE_LABELS.get(file, file.replace("test_", "").replace(".py", ""))
    label = _TC_LABELS.get(tc) or func.replace("test_", "").replace("_", " ")
    return f"{num:02d}  [{module}]  {label}"


def discover_tcs() -> list[str]:
    """tests/playwright/test_*.py 에서 test_ 함수를 수집한다."""
    tcs: list[str] = []
    for py_file in sorted(PLAYWRIGHT_TEST_DIR.glob("test_*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                tcs.append(f"{py_file.name}::{node.name}")
    return tcs


# TODO : _________________________________________________ 5. MENU

def _select_run_mode() -> tuple[bool, int]:
    """실행 모드 선택. pk_tools > fzf > 번호 입력 순으로 fallback."""
    mode_options = [
        "1  Headless",
        "2  Headed",
        f"3  Headed + SlowMo {SLOW_MO_MS}ms",
    ]
    mode_map = {
        "1": (False, 0),
        "2": (True, 0),
        "3": (True, SLOW_MO_MS),
    }
    result = _select_with_pk_or_fzf("playwright_run_mode", mode_options, multi=False)
    if result:
        raw = result[0][0]  # "1", "2", or "3"
        return mode_map.get(raw, (False, 0))

    # fallback: 번호 입력
    print()
    print("  [1] Headless  (기본, 빠름)")
    print("  [2] Headed    (브라우저 창 표시)")
    print(f"  [3] Headed + SlowMo {SLOW_MO_MS}ms  (눈으로 따라가기)")
    print()
    while True:
        raw = input("모드 선택 [1/2/3, 기본=1]: ").strip()
        if raw in ("1", ""):
            return False, 0
        if raw == "2":
            return True, 0
        if raw == "3":
            return True, SLOW_MO_MS
        print("  1, 2, 3 중 하나를 입력하세요.")


def prompt_tc_selection(tcs: list[str]) -> list[str]:
    """TC 선택. pk_tools > fzf > 번호 메뉴 순으로 fallback.

    표시: "01  [셀편집]  텍스트 셀 → Enter 저장"
    선택 결과를 실제 pytest ID 로 역변환한다.
    """
    display_labels = [_make_display_label(i, tc) for i, tc in enumerate(tcs, 1)]
    label_to_tc = dict(zip(display_labels, tcs))

    result = _select_with_pk_or_fzf(
        "playwright_tc_selection",
        display_labels,
        multi=True,
    )
    if result:
        return [
            f"tests/playwright/{label_to_tc[label]}"
            for label in result
            if label in label_to_tc
        ]

    # fallback: 번호 메뉴
    print()
    for label in display_labels:
        print(f"  {label}")
    print()
    while True:
        raw = input("TC 번호 (쉼표 구분 가능, 예: 1  또는  1,3,5): ").strip()
        if not raw:
            continue
        try:
            indices = [int(x.strip()) for x in raw.split(",")]
        except ValueError:
            print("  숫자를 입력하세요.")
            continue
        if any(i < 1 or i > len(tcs) for i in indices):
            print(f"  1 ~ {len(tcs)} 범위의 숫자를 입력하세요.")
            continue
        return [f"tests/playwright/{tcs[i - 1]}" for i in indices]


# TODO : _________________________________________________ 6. RUN

def run_tcs(tc_paths: list[str], headed: bool, slowmo_ms: int) -> int:
    args = [
        "uv", "run", "pytest",
        *tc_paths,
        "-v",
        "--browser", "chromium",
    ]
    if headed:
        args.append("--headed")
    if slowmo_ms > 0:
        args.extend(["--slowmo", str(slowmo_ms)])

    label = "ALL" if len(tc_paths) > 1 else tc_paths[0].split("::")[-1]
    print_section(f"Running: {label}")
    print("  " + " ".join(args))

    result = subprocess.run(
        args=args,
        cwd=str(PROJECT_ROOT),
        capture_output=False,
        shell=False,
    )
    return result.returncode


# TODO : _________________________________________________ 7. MAIN

def main() -> int:
    _setup_logging()
    print_section("Playwright E2E Test Runner")

    print_section("1/3  Prerequisites")
    try:
        _check_prerequisites()
    except RuntimeError as exc:
        print(f"\n[ERROR] {exc}")
        return 1
    print("\n  All prerequisites satisfied.")

    print_section("2/3  Select Run Mode")
    headed, slowmo_ms = _select_run_mode()

    print_section("3/3  Select TC")
    tcs = discover_tcs()
    if not tcs:
        print("[ERROR] No TCs found in tests/playwright/.")
        return 1
    print(f"  Found {len(tcs)} TCs.")
    selected = prompt_tc_selection(tcs)

    return run_tcs(selected, headed, slowmo_ms)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
    except Exception as exc:
        print_section("ERROR")
        print(str(exc))
        raise SystemExit(1)
